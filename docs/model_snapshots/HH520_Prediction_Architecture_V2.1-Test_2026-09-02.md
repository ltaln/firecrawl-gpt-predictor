# HH520 Prediction Architecture V2.1-Test — Frozen Snapshot

Snapshot date: 2026-09-02 (Asia/Singapore)
Status: FROZEN

## Purpose

This file preserves the current model specification exactly as the working baseline for prediction/backtest work. It is a documentation snapshot only. It does not modify the Firecrawl collector or production execution logic.

## Immutable hard rules

1. No Firecrawl Data, No Prediction, No Backtest.
2. Firecrawl is the mandatory first-stage collector for every formal prediction/backtest.
3. Ordinary web search may only be used to fill missing information after Firecrawl main collection succeeds; it may never replace Firecrawl.
4. Firecrawl collector implementation is immutable unless the user explicitly authorizes changes.
5. Historical backtests use an information cutoff of T-30 (30 minutes before kickoff).
6. No information generated after T-30 may contaminate historical predictions.
7. Final score, halftime score, cards, post-match reports, post-match ratings and other outcome-derived information remain locked until the prediction is committed.
8. xi_id must be discovered from real page links and must never be guessed.
9. Accuracy and calibration are prioritized over coverage. Low-edge or conflicted matches may be PASS.
10. Different betting markets use independent final models. Do not force all markets to agree.

## Version stack

- Architecture: HH520 Prediction Architecture V2.1-Test
- Master Prompt: v1.1
- Prediction Prompt: v1.1
- Backtest Prompt: v1.1
- SoccerSTATS HT/FT DNA Prompt: v1.0

## End-to-end pipeline

Firecrawl
→ Match Discovery
→ Full Collection
→ Data Completeness
→ Missing Data Recovery
→ T-30 Freeze
→ Historical DNA Reconstruction
→ Water Market Core
→ League DNA
→ Team DNA
→ Company DNA
→ SoccerSTATS HT/FT DNA
→ Independent Models
→ Calibration
→ Prediction Commit
→ Result Unlock
→ Scoring
→ Error DNA Update

No silent simplification or skipped stage is permitted in a formal run.

## HH520 page roles

- `/` — match discovery / date match list / match count / changci
- `xi.php?id=...` — aggregated mixed data; used mainly as agreement/conflict validator
- `tx/10012.php?date=YYYY-MM-DD` — date-wide Asian handicap summary
- `tx/10013.php?date=YYYY-MM-DD&changci=N` — single-match Asian handicap/water history
- `tx/10015.php?code=YYYYMMDDNNN` — historical starting lineups and ratings
- `tx/10016.php?code=YYYYMMDDNNN` — predicted/current starting lineup
- `tx/bfplsj.php` — correct-score market data
- `tx/10017.php?riqi=YYYY-MM-DD&changci=N` — correct-score odds movement/history
- `tx/7.php` — xG / total-goals / goal-difference independent supplement
- `tx/zhdy.php` — aggregate supplement

Module grouping rules:

- `10012 + 10013` = one Asian Handicap / Water Market module; never double-count.
- `bfplsj + 10017` = one Correct Score market module.
- `10015 + 10016` = one Lineup module.
- `7.php` = independent xG / goals supplement.
- `xi` and `zhdy` are aggregated sources and must not be double-counted with their underlying signals.
- `xi` direct model weight remains 0; it is a validator, not a primary driver.

Match code convention: `YYYYMMDD + 3-digit match_no`.

## Water Market Core

Primary axis:

**10012 + 10013 = 100% Water Market Core**

Other modules validate or supplement the market path and must not become co-equal duplicates of the same signal.

Core features include:

- initial_handicap
- live_handicap
- delta_handicap
- initial/live home water
- initial/live away water
- water deltas
- snapshot_count
- move_count
- reversal_count
- velocity_120 / velocity_60 / velocity_30
- late_move
- company_consensus
- company_sync_ratio
- dispersion
- leading_company
- follower_structure
- same_line_water_pressure
- line_move_timing
- pre/post line-move water pressure
- min/max water

Core outputs:

- Market Pressure Score
- Water Direction
- Company Consensus
- Market Conflict Score
- Water Confidence

Asian Handicap target is handicap settlement, not 1X2.

## Independent model family

Shared historical/raw data may be reused, but each final market calculation is independent:

- A — Asian Handicap
- B — Over/Under
- C — 1X2
- D — Handicap 1X2
- E — Correct Score
- F — SoccerSTATS Hierarchical HT/FT
- G — First Half
- H — Total Goals

Model conflicts are valid signals and must be recorded, not force-resolved.

## League DNA

Calibrate independently at League + Season level.

Key fields include:

- H/D/A rates
- home advantage
- O/U rates
- Asian cover by line depth
- favorite / strong-team behavior
- hot-team performance
- line upgrades / downgrades
- water reversals
- bookmaker synchronization
- HT / second-half scoring
- HT/FT distribution
- lead protection
- comeback
- first-goal timing
- late-goal rate
- league-specific market behavior

Patterns may not be transferred directly across leagues without calibration.

## Team DNA

Subdomains:

- Water DNA
- Goal DNA
- Correct Score DNA
- Lineup DNA
- HT/FT DNA
- Error DNA

A new rule may be promoted only when it is:

1. pre-match observable
2. quantifiable
3. repeated across multiple samples
4. verified out-of-sample

Post-match events may label variance/error but cannot become pre-match predictors without a legitimate pre-match proxy.

## Company DNA

Track:

- who moves first
- who follows
- league-leading bookmakers
- historical move accuracy
- possible false moves
- synchronized moves
- dispersion/disagreement
- late moves

Company DNA is combined with League DNA and Water Market Core.

## SoccerSTATS HT/FT DNA

Hierarchical two-stage model:

### Stage A — HT state

Estimate:

- P(HT home lead)
- P(HT draw)
- P(HT away lead)

### Stage B — HT→FT transition

Estimate FT state conditional on HT state.

Final 9 classes:

- Win/Win
- Win/Draw
- Win/Loss
- Draw/Win
- Draw/Draw
- Draw/Loss
- Loss/Win
- Loss/Draw
- Loss/Loss

Home and away HT/FT DNA remain separate.

HT goal time buckets:

- 0–15
- 16–30
- 31–45+

Second-half buckets:

- 46–60
- 61–75
- 76–90+

Behavior labels may include Fast Start, Slow Start, Fast Finish, Late Collapse, Comeback, Lead Protection, Front Loaded, Late Scoring.

Lead Protection DNA: when leading at HT → win/draw/lose.

Comeback DNA: when trailing at HT → draw/win/still lose.

HT Draw Break DNA: HT draw → FT transitions.

Important interactions include:

- Water Path × HT State × FT Result
- Asian Water × O/U Water × HT/FT
- Correct Score Odds Movement × HT/FT
- Lineup Rating × Water Movement × HT/FT
- Defense Rating × O/U Movement
- Attack Rating × Correct Score Movement
- Rest Days × Second-Half DNA
- Coach DNA × HT Draw
- Company DNA × Late Water Movement
- League DNA × Team DNA
- League DNA × Water Path
- Team DNA × Water Path

Correct-score interactions use the full `bfplsj + 10017` path, not only final/minimum odds.

Lineup interactions use `10015 + 10016` and may derive:

- Starting XI Rating
- Attack Rating
- Midfield Rating
- Defense Rating
- GK Rating
- Bench Rating
- Lineup Continuity
- Rotation Index

Historical SoccerSTATS summaries must be reconstructed as-of-date to prevent future leakage.

Small samples use hierarchical shrinkage:

League Prior + Season Prior + Team Data + Recent Form.

Time windows may include last 5 / 10 / 20 / current season / previous season with sensible decay and anti-overfitting controls.

## Calibration and confidence

Probability pipeline:

Raw Probability
→ League Adjusted
→ Team Adjusted
→ Final Probability

Calibration objective: predicted 60% events should occur about 60% empirically.

Confidence grades:

- S
- A
- B
- C
- PASS

## Prediction Record

Every formal run records:

- Match ID
- Model Version
- Prompt Version
- DNA Version
- Firecrawl timestamp
- Prediction cutoff
- sources
- raw features/inputs
- per-model probabilities
- final predictions
- confidence
- model conflicts
- prediction commit timestamp

This prevents retrospective edits and supports version comparisons.

## Backtest scoring

Score each model independently.

- Asian Handicap: Win / Half Win / Push / Half Loss / Loss
- O/U: Win / Half Win / Push / Half Loss / Loss
- 1X2: Accuracy
- Handicap 1X2: Accuracy
- Correct Score: Top1 / Top3
- HT/FT: Top1 / Top3

Also track:

- Brier Score
- Log Loss
- Calibration Error
- confidence-bucket accuracy

Error categories:

- Data Error
- Water Signal Error
- DNA Error
- Lineup Error
- Score Market Error
- HT Model Error
- Calibration Error
- Event Variance

HT/FT Error DNA further separates:

- HT prediction wrong
- HT correct but FT transition wrong
- water signal error
- team error
- league error
- lineup error
- fatigue error
- score-market error
- random variance

## Deep Research status

Deep Research is useful when feasible for motivation, injuries, rotation, rest, schedule density, coach comments, travel, weather, pitch, derby, referee and related context.

In V2.1-Test it is NOT a hard stop gate. Lack of full deep research alone does not invalidate a formal run after the Firecrawl gate is satisfied.

## Freeze declaration

This snapshot is the authoritative saved baseline for V2.1-Test as of 2026-09-02.

Until the user explicitly says to change/unfreeze/upgrade the model:

- do not alter model architecture
- do not change weights or calibration logic
- do not add/remove independent models
- do not promote new DNA rules
- do not rewrite prompts as a new active version
- do not modify the Firecrawl collector

Backtests may generate observations and Error DNA notes, but those observations must not change the frozen model automatically.
