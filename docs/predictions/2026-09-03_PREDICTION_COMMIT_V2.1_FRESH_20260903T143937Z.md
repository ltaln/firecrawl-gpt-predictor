# HH520 V2.1-Test Prediction Commit — 2026-09-03

Status: LOCKED PREDICTION COMMIT
Model: HH520 V2.1-Test
Upgrade Package 1: PARKED / NOT USED
Fresh Firecrawl snapshot: 20260903T143937Z
Fresh task source: issue #12 / Firecrawl Data Collection run #25
Rule: no prior 2026-09-03 package, analysis, or Prediction Commit reused.

## Data Integrity Audit

7/7 match packages passed the package completeness gate. Content-level audit found an important score-market mapping defect:

- Match 001 mixed_data = 迈季宽广 vs 拉斯永恒, but 10017 score page = 迈季迈阿宽广 vs 利雅得新月. INVALID score-market input; excluded.
- Match 002 mixed_data = 新未来SC vs 赛哈海湾, but 10017 score page = 巴列卡诺 vs 阿拉维斯. INVALID score-market input; excluded.
- Match 003 mixed_data = 米亚尔比 vs 佐加顿斯, but 10017 score page = 科林蒂安 vs 罗萨里奥. INVALID score-market input; excluded.
- Match 004 10017 = 迪里耶 vs 胡巴尔卡德西亚. VALID.
- Match 005 10017 = 图卢兹 vs 里尔. VALID.
- Match 006 10017 = 皇家社会 vs 塞尔塔. VALID.
- Match 007 10017 = 格雷米奥 vs 巴西国际. VALID.

For matches 001-003, Correct Score confidence is reduced and uses valid Water/mixed data plus pre-match external statistical context; the mismatched 10017 data receives zero weight.

## Model Synthesis

### 001 迈季宽广 vs 拉斯永恒
Water: initial level ball shifted toward home +0.25; away side strengthened. Mixed 1X2: 33.53/29.25/37.22, market 26.81/37.41/35.78. Team form also favors away non-loss, but external score distribution remains tight. Conflict = medium-high.
Calibrated 1X2: H32 D31 A37.
Correct Score Top3: 1-1, 0-1, 1-2.
HT Stage A: H26 D48 A26.
HT/FT 9D (HH/HD/HA/DH/DD/DA/AH/AD/AA): 12/5/5/12/24/18/4/7/13.
HT/FT Top3: D/D, D/A, A/A.
A Asian: 拉斯永恒 -0.25.
B O/U: Under 2.75.
G First Half: Draw.
H Total Goals: 1-3.
Confidence: Medium-Low (score market invalid).

### 002 新未来SC vs 赛哈海湾
Mixed 1X2 strongly favors home: 53.33/24.93/21.74; institutional 51.97/32.69/15.34. Home squad value materially higher; Al Khaleej recent attack weak and multiple personnel absences were reported externally. Market direction supports home.
Calibrated 1X2: H58 D25 A17.
Correct Score Top3: 2-0, 2-1, 1-0.
HT Stage A: H44 D42 A14.
HT/FT 9D: 35/7/2/20/14/4/8/4/6.
HT/FT Top3: H/H, D/H, D/D.
A Asian: 新未来SC -0.75.
B O/U: Under 3.0.
G First Half: Home/Draw lean, primary Home.
H Total Goals: 2-3.
Confidence: Medium (score market invalid).

### 003 米亚尔比 vs 佐加顿斯
Mixed 1X2 = 25.20/25.06/49.74, institutional = 17.99/34.75/47.26; home price drift and away price compression support the away direction. External xG models also place Djurgarden clearly ahead, with a high-goal tail.
Calibrated 1X2: H23 D23 A54.
Correct Score Top3: 1-2, 0-2, 1-3.
HT Stage A: H21 D42 A37.
HT/FT 9D: 8/4/8/8/16/24/3/7/22.
HT/FT Top3: D/A, A/A, D/D.
A Asian: 佐加顿斯 -0.5.
B O/U: Over 2.5.
G First Half: Draw/Away, primary Draw.
H Total Goals: 2-4.
Confidence: Medium (score market invalid).

### 004 迪里耶 vs 胡巴尔卡德西亚
Mixed 1X2 = 16.75/21.10/62.15; institutional = 11.21/27.34/61.45. Away squad/form advantage and market agreement are strong. 10017 fixture mapping valid.
Calibrated 1X2: H15 D22 A63.
Correct Score Top3: 0-2, 1-2, 0-3.
HT Stage A: H15 D38 A47.
HT/FT 9D: 4/2/7/5/11/25/2/5/39.
HT/FT Top3: A/A, D/A, D/D.
A Asian: 胡巴尔卡德西亚 -1.0.
B O/U: Over 2.5.
G First Half: Away.
H Total Goals: 2-4.
Confidence: High-Medium.

### 005 图卢兹 vs 里尔
Mixed 1X2 = 26.98/28.27/44.75; institutional = 12.44/34.80/52.76. Lille away price compresses. Valid 10017 plus external xG/Poisson sources make 1-1 the single most likely exact score while Lille remains the most likely match winner; this is a classic score-vs-1X2 distinction.
Calibrated 1X2: H27 D29 A44.
Correct Score Top3: 1-1, 0-1, 1-2.
HT Stage A: H22 D51 A27.
HT/FT 9D: 9/5/8/8/21/24/2/7/16.
HT/FT Top3: D/A, D/D, A/A.
A Asian: 里尔 -0.25.
B O/U: Under 3.0.
G First Half: Draw.
H Total Goals: 2-3.
Confidence: Medium-High.

### 006 皇家社会 vs 塞尔塔
Mixed 1X2 = 49.26/26.42/24.32; institutional = 36.76/36.71/26.53. Home price is shortening, but draw risk remains meaningful. External xG models also favor Sociedad while Celta retain scoring probability. 10017 fixture mapping valid.
Calibrated 1X2: H49 D29 A22.
Correct Score Top3: 1-0, 2-1, 1-1.
HT Stage A: H34 D49 A17.
HT/FT 9D: 27/8/3/21/20/7/5/4/5.
HT/FT Top3: H/H, D/H, D/D.
A Asian: 皇家社会 -0.25.
B O/U: Over 2.0/2.25 lean.
G First Half: Draw.
H Total Goals: 1-3.
Confidence: Medium-High.

### 007 格雷米奥 vs 巴西国际
Mixed 1X2 = 38.55/32.56/28.89; institutional = 40.76/38.43/20.81. Derby/cup state substantially raises draw and low-score probability. First leg was 0-0; Gremio have home advantage and Inter entered the tie in poor form. 10017 fixture mapping valid.
Calibrated 1X2: H43 D35 A22.
Correct Score Top3: 1-0, 0-0, 1-1.
HT Stage A: H26 D58 A16.
HT/FT 9D: 15/8/4/20/28/8/5/6/6.
HT/FT Top3: D/D, D/H, H/H.
A Asian: 格雷米奥 0/-0.25.
B O/U: Under 2.5.
G First Half: Draw.
H Total Goals: 0-2.
Confidence: High-Medium.

## Calibration / Cross-Model Notes

- Score market weight = 0 for matches 001-003 because fixture identity failed content-level validation.
- Water direction and mixed 1X2 agree most strongly on 002, 003, 004, 005, 006; 001 has higher conflict; 007 is structurally draw-sensitive because of derby + knockout game state.
- Exact score Top1 should not be forced to equal the modal 1X2 outcome. This is especially relevant to Toulouse-Lille, where 1-1 can be the highest individual score cell while Lille remains the largest aggregate 1X2 class.
- HT/FT outputs are full 9-class vectors and sum to 100 for each match.
- No result/post-match information was used in this commit.

## FINAL LOCKED OUTPUT

| # | Match | Correct Score Top1 | Score Top3 | HT/FT Top1 | HT/FT Top3 | Asian | O/U | 1X2 | First Half | Total Goals |
|---|---|---|---|---|---|---|---|---|---|---|
|1|迈季宽广 vs 拉斯永恒|1-1|1-1 / 0-1 / 1-2|D/D|D/D / D/A / A/A|拉斯永恒 -0.25|Under 2.75|Away lean|Draw|1-3|
|2|新未来SC vs 赛哈海湾|2-0|2-0 / 2-1 / 1-0|H/H|H/H / D/H / D/D|新未来SC -0.75|Under 3.0|Home|Home|2-3|
|3|米亚尔比 vs 佐加顿斯|1-2|1-2 / 0-2 / 1-3|D/A|D/A / A/A / D/D|佐加顿斯 -0.5|Over 2.5|Away|Draw|2-4|
|4|迪里耶 vs 胡巴尔卡德西亚|0-2|0-2 / 1-2 / 0-3|A/A|A/A / D/A / D/D|胡巴尔卡德西亚 -1.0|Over 2.5|Away|Away|2-4|
|5|图卢兹 vs 里尔|1-1|1-1 / 0-1 / 1-2|D/A|D/A / D/D / A/A|里尔 -0.25|Under 3.0|Away lean|Draw|2-3|
|6|皇家社会 vs 塞尔塔|1-0|1-0 / 2-1 / 1-1|H/H|H/H / D/H / D/D|皇家社会 -0.25|Over 2.0/2.25 lean|Home|Draw|1-3|
|7|格雷米奥 vs 巴西国际|1-0|1-0 / 0-0 / 1-1|D/D|D/D / D/H / H/H|格雷米奥 0/-0.25|Under 2.5|Home lean|Draw|0-2|
