import argparse
import json
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import requests

FIRECRAWL_ENDPOINT = os.environ.get("FIRECRAWL_ENDPOINT") or "https://api.firecrawl.dev/v2/scrape"
BASE_URL = "https://www.hh520.com/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

class VisibleTextParser(HTMLParser):
    def __init__(self): super().__init__(); self.skip=0; self.parts=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script","style","noscript","svg"}: self.skip += 1
    def handle_endtag(self, tag):
        if tag.lower() in {"script","style","noscript","svg"} and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip:
            text=re.sub(r"\s+"," ",data).strip()
            if text: self.parts.append(text)

class LinkParser(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=="a":
            for k,v in attrs:
                if k.lower()=="href" and v: self.links.append(v)

def canonicalize_url(url):
    p=urlparse(url)
    return urlunparse((p.scheme,p.netloc,p.path,p.params,p.query,""))

def slugify(url):
    p=urlparse(url); raw=f"{p.netloc}{p.path}_{p.query}".strip("_")
    return re.sub(r"[^A-Za-z0-9._-]+","_",raw)[:180] or "page"

def scrape_url(url, api_key, retries=6, min_interval=3.0):
    payload={"url":url,"formats":["markdown","html","rawHtml"],"onlyMainContent":False,"onlyCleanContent":False,"blockAds":False,"removeBase64Images":True,"proxy":"auto","maxAge":0,"timeout":60000}
    last_error=None
    for attempt in range(retries):
        if attempt==0: time.sleep(min_interval)
        try:
            r=requests.post(FIRECRAWL_ENDPOINT,headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},json=payload,timeout=90)
            if r.status_code==429:
                retry_after=r.headers.get("Retry-After")
                try: wait=float(retry_after) if retry_after else min(5*(2**attempt),120)
                except ValueError: wait=min(5*(2**attempt),120)
                print(f"Firecrawl 429 for {url}; waiting {wait}s (attempt {attempt+1}/{retries})")
                time.sleep(wait); continue
            r.raise_for_status(); body=r.json()
            if not body.get("success"): raise RuntimeError(f"Firecrawl failed: {body}")
            return body
        except (requests.RequestException, RuntimeError) as exc:
            last_error=exc
            if attempt < retries-1:
                wait=min(5*(2**attempt),120); print(f"Firecrawl retry for {url}: {exc}; waiting {wait}s"); time.sleep(wait)
    raise RuntimeError(f"Firecrawl exhausted retries for {url}: {last_error or 'HTTP 429'}")

def fetch_source(url):
    r=requests.get(url,headers={"User-Agent":UA,"Accept-Language":"zh-CN,zh;q=0.9"},timeout=60); r.raise_for_status()
    if not r.encoding or r.encoding.lower()=="iso-8859-1": r.encoding=r.apparent_encoding or "utf-8"
    return {"status_code":r.status_code,"final_url":r.url,"fetched_at":datetime.now(timezone.utc).isoformat(),"html":r.text}

def visible_text(html):
    p=VisibleTextParser(); p.feed(html or ""); return "\n".join(p.parts)

def normalize_dynamic(text):
    text=re.sub(r"\d+\s*(秒|分钟|小时|天)(后|前)","<RELATIVE_TIME>",text)
    return re.sub(r"\s+"," ",text).strip()

def validate_source(url,source,firecrawl):
    data=firecrawl.get("data",{}); st=visible_text(source.get("html","")); ft=visible_text(data.get("rawHtml","")); sn=normalize_dynamic(st); fn=normalize_dynamic(ft)
    lines=[normalize_dynamic(x) for x in st.splitlines() if len(normalize_dynamic(x))>=2]; missing=[x for x in lines if x not in fn]
    coverage=(len(lines)-len(missing))/len(lines) if lines else 1.0
    sim=SequenceMatcher(None,sn,fn,autojunk=False).ratio() if sn or fn else 1.0
    return {"url":url,"source_status_code":source.get("status_code"),"source_html_chars":len(source.get("html","")),"firecrawl_raw_html_chars":len(data.get("rawHtml","")),"normalized_similarity":round(sim,6),"source_line_coverage":round(coverage,6),"missing_source_lines_sample":missing[:30],"result":"PASS" if coverage>=0.98 else "CHECK"}

def load_seed_urls(cli,target_date):
    seeds=list(cli or [])
    if not cli and Path("urls.txt").exists(): seeds += [x.strip() for x in Path("urls.txt").read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    compact=target_date.replace("-",""); seeds += [BASE_URL,f"{BASE_URL}?date={compact}",f"{BASE_URL}tx/10012.php?date={target_date}",f"{BASE_URL}tx/7.php"]
    return list(dict.fromkeys(canonicalize_url(x) for x in seeds))

def extract_links(html,base):
    p=LinkParser(); p.feed(html or ""); out=[]
    for href in p.links:
        u=canonicalize_url(urljoin(base,href)); q=urlparse(u)
        if q.scheme in {"http","https"} and q.netloc.lower() in {"hh520.com","www.hh520.com"}: out.append(u)
    return out

def classify_supported_url(url,date):
    p=urlparse(url); path=p.path; q=parse_qs(p.query); compact=date.replace("-","")
    if path in {"","/"}:
        d=(q.get("date") or [""])[0]; return "match_list" if not d or d==compact else None
    if path=="/xi.php" and (q.get("id") or [""])[0].isdigit(): return "mixed_data"
    if path=="/tx/10017.php" and (q.get("riqi") or [""])[0]==date and (q.get("changci") or [""])[0].isdigit(): return "score_odds_changes"
    if path in {"/tx/10016.php","/tx/10015.php"}:
        code=(q.get("code") or [""])[0]
        if re.fullmatch(r"\d{11}",code) and code.startswith(compact): return "predicted_lineup" if path.endswith("10016.php") else "historical_lineup_ratings"
    if path=="/tx/10012.php" and (q.get("date") or [""])[0]==date: return "daily_asian_handicap_summary"
    if path=="/tx/10013.php" and (q.get("date") or [""])[0]==date and (q.get("changci") or [""])[0].isdigit(): return "asian_handicap_changes"
    if path=="/tx/7.php": return "internal_model_analysis"
    return None

def discover(html,base,date):
    base_path=urlparse(base).path
    if base_path in {"/tx/10015.php","/tx/10016.php"}:
        return []
    out=[]; seen=set()
    for u in extract_links(html,base):
        c=classify_supported_url(u,date)
        if c and u not in seen: seen.add(u); out.append((u,c))
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--date",required=True); ap.add_argument("--urls",nargs="*"); ap.add_argument("--skip-source-validation",action="store_true"); ap.add_argument("--max-pages",type=int,default=500); a=ap.parse_args()
    key=os.environ.get("FIRECRAWL_API_KEY")
    if not key: raise SystemExit("Missing FIRECRAWL_API_KEY")
    started=datetime.now(timezone.utc); sid=started.strftime("%Y%m%dT%H%M%SZ"); raw=Path("data/raw")/a.date/"snapshots"/sid; src=raw/"source"; raw.mkdir(parents=True,exist_ok=True); src.mkdir(parents=True,exist_ok=True)
    queue=deque(); queued=set()
    for u in load_seed_urls(a.urls,a.date): queue.append((u,classify_supported_url(u,a.date) or "seed","seed")); queued.add(u)
    docs=[]; vals=[]; discoveries=[]; processed=set(); failures=[]
    while queue and len(processed)<a.max_pages:
        url,cat,origin=queue.popleft(); url=canonicalize_url(url)
        if url in processed: continue
        processed.add(url); source=None
        if not a.skip_source_validation:
            try: source=fetch_source(url); (src/f"{slugify(url)}.html").write_text(source["html"],encoding="utf-8")
            except Exception as e: source={"error":str(e)}
        print(f"Firecrawl scrape [{cat}]: {url}")
        try: response=scrape_url(url,key)
        except Exception as e:
            print(f"SKIP after retries: {url}: {e}"); failures.append({"url":url,"category":cat,"error":str(e)}); continue
        rec={"url":url,"category":cat,"discovered_from":origin,"fetched_at":datetime.now(timezone.utc).isoformat(),"snapshot_id":sid,"response":response}; docs.append(rec); (raw/f"{slugify(url)}.json").write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding="utf-8")
        if source and "html" in source: vals.append(validate_source(url,source,response))
        elif source: vals.append({"url":url,"result":"SOURCE_FETCH_FAILED","error":source.get("error")})
        data=response.get("data",{}); html=data.get("rawHtml") or data.get("html") or (source or {}).get("html","")
        for nu,nc in discover(html,url,a.date):
            nu=canonicalize_url(nu)
            if nu not in queued and nu not in processed: queued.add(nu); queue.append((nu,nc,url)); discoveries.append({"url":nu,"category":nc,"discovered_from":url})
    counts={}
    for x in docs: counts[x["category"]]=counts.get(x["category"],0)+1
    validation={"date":a.date,"snapshot_id":sid,"validated_urls":len(vals),"passed":sum(x.get("result")=="PASS" for x in vals),"checked":sum(x.get("result")=="CHECK" for x in vals),"results":vals}
    discovery={"date":a.date,"snapshot_id":sid,"processed_pages":len(docs),"failed_pages":len(failures),"category_counts":counts,"discovered":discoveries,"failures":failures,"truncated":bool(queue)}
    (raw/"source_validation.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf-8"); (raw/"url_discovery.json").write_text(json.dumps(discovery,ensure_ascii=False,indent=2),encoding="utf-8")
    manifest={"date":a.date,"snapshot_id":sid,"started_at":started.isoformat(),"scraped_pages":len(docs),"failed_pages":len(failures),"category_counts":counts,"source_validation":str(raw/"source_validation.json"),"url_discovery":str(raw/"url_discovery.json"),"mode":"data-only"}
    (raw/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8"); latest=Path("data/raw")/a.date/"latest.json"; latest.write_text(json.dumps({"date":a.date,"snapshot_id":sid,"snapshot_dir":str(raw),"manifest":str(raw/"manifest.json"),"source_validation":str(raw/"source_validation.json"),"url_discovery":str(raw/"url_discovery.json")},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"validation":validation,"discovery":discovery},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
