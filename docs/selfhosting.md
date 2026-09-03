# Firecrawl self-host migration

The collector's URL discovery, request payload, source validation, package builder,
and prediction rules are unchanged. Only the scrape endpoint is configurable.

## Deployment

- Firecrawl is installed under `/opt/firecrawl` using Docker Compose.
- The base checkout is `v2.11.291`. The deployed prebuilt image digests are pinned
  in `docker-compose.override.yml`; the checkout tag does not imply that the
  independently published prebuilt images have the same release tag.
- The API is bound to `127.0.0.1:3003`; Redis, RabbitMQ, PostgreSQL and Playwright
  are not published externally.
- On the 4 GB host, `api.environment.NUQ_WORKER_COUNT=1` is explicitly passed to
  the container. Merely adding this variable to the Compose `.env` is insufficient.
- API memory/swap limits are 3 GB/4 GB; the host has 4 GB swap. Containers have
  restart policies. This is a low-concurrency deployment, not a high-throughput one.
- A separate `firecrawl-gateway` Caddy container handles HTTPS with a persistent,
  automatically renewed certificate. It accepts authenticated `POST /v2/scrape`
  requests only. The bearer token is stored in `/etc/firecrawl/api_token` (0600).
- The HTTPS hostname is currently provided by the public sslip.io DNS service.
  A user-owned domain can replace it later; service availability also depends on DNS.

Start the backend with:

```sh
cd /opt/firecrawl
docker compose -f docker-compose.yaml -f docker-compose.override.yml up -d --no-build api
```

Do not run `docker compose down -v`: database/queue state resides in Docker volumes.
Do not publish the unauthenticated backend port. Keep the gateway's certificate
volumes and `/etc/firecrawl/Caddyfile` when maintaining the deployment.

## Acceptance test and cutover

`verify_selfhost.py` uses the saved Cloud snapshot for 2026-09-02 as a 69-URL
contract, excluding the undated homepage. Each page must return the same requested
format fields and cover at least 98% of normalized visible source lines in
`rawHtml`. The live HH520 source is fetched separately for this comparison.
This checks current source coverage and API compatibility; it is not a claim of
byte-for-byte equality with historical Cloud data or a prediction/backtest result.

```sh
export FIRECRAWL_ENDPOINT=https://YOUR_HOST/v2/scrape
export FIRECRAWL_API_KEY=YOUR_SELFHOST_TOKEN
python verify_selfhost.py --workers 1 --output selfhost-verification.json
```

Only after 69/69 passes, configure GitHub repository secrets:

- `FIRECRAWL_ENDPOINT`: the HTTPS scrape endpoint.
- `FIRECRAWL_SELFHOST_API_KEY`: the gateway bearer token.
- Leave the original `FIRECRAWL_API_KEY` unchanged for Cloud rollback.

Run the existing `Firecrawl Data Collection` workflow and check both collection
and package completeness. To roll back, delete `FIRECRAWL_ENDPOINT`; the workflow
will use the original Cloud endpoint and Cloud key again. There is deliberately no
silent fallback during verification: a self-host failure must remain visible.

## Migration verification — 2026-09-04

- The fixed Cloud contract (`20260902T144150Z`): 69/69 pages passed, with 100%
  normalized source-line coverage on each page.
- HTTPS, unauthorized-request rejection and post-restart scraping passed.
- [GitHub integration run 33816088800](https://github.com/ltaln/firecrawl-gpt-predictor/actions/runs/33816088800):
  87 pages scraped, zero scrape failures, 87/87 source validations passed.
- The complete workflow **failed** its package gate: 13/27 packages complete;
  all 13 expected target-date packages were complete, but 14 additional packages
  were incomplete. No result commit was made by this run.
- The unchanged package builder includes all discovered mixed-data pages and
  assigns sequential numbers under the requested date, without date-aware mapping.
  Extra live-page discoveries expose this separate downstream issue. The builder
  must be corrected before claiming full workflow acceptance; collector logic
  remains unchanged apart from endpoint configuration.
