# Data Dictionary

RugbyAnalytics uses **two tables at two grains**. Both are required: the player table
feeds *style* (how a team plays); the match table feeds *prediction* (who wins). Team
style vectors, aggregated from the player table, become **features** in the match model —
this is how style and prediction connect into one pipeline.

Team codes (from Davia's NOTES sheet): JPN, AUS, NWZ, FIJ, SA, ARG, ITL, IRE, FRE, WAL,
ENG, SCT (+ add any others as sourced).

---

## Table 1 — `player_stats` (grain: one player, per competition-season)
Source: Davia's STAT_SHEET. Aggregates roll up to **team style vectors**.

| Column | Category | Notes |
|---|---|---|
| PLAYER_NAME | id | |
| COUNTRY | id | team code |
| POSITION | id | SH, HK, FH, ... |
| SEASON | id | **added** — e.g. 2025; required for a time dimension |
| COMPETITION | id | **added** — Six Nations / Rugby Championship / Autumn / RWC |
| POINTS | attack | |
| TRIES | attack | |
| LINE_BREAKS | attack | |
| CARRIES | attack | |
| CARRIES_PER_MIN | attack | |
| METERS_CARRIED | attack | |
| DEFENDERS_BEATEN | attack | |
| TURNOVERS_WON_ATT | attack | **renamed** from ambiguous TURNOVERS_WON (attack) |
| TOUCHES | attack | |
| POST_CONTACT_METERS | attack | |
| TACKLES_MADE | defense | |
| TACKLES_COMPLETED | defense | |
| DOMINANT_TACKLES | defense | |
| TACKLES_PER_MIN | defense | |
| TURNOVERS_WON_DEF | defense | **renamed** from the 2nd TURNOVERS_WON (defense) |
| RUCK_ARRIVAL_EFFECTIVENESS | defense | |
| TRY_ASSISTS | passing | |
| SUCCESSFUL_PASSES | passing | |
| BAD_PASSES | passing | |
| PASS_ACCURACY | passing | |
| PENALTIES_CONCEDED | discipline | |
| YELLOW_CARDS | discipline | |
| RED_CARDS | discipline | |

**Fixes applied vs the original sheet:**
- The two identically-named `TURNOVERS_WON` columns are split into
  `TURNOVERS_WON_ATT` / `TURNOVERS_WON_DEF` (they would otherwise overwrite on import).
- Added `SEASON` and `COMPETITION` so the data has a time dimension — mandatory for
  walk-forward validation.

---

## Table 2 — `match_results` (grain: one international match)
The missing piece. Without match outcomes there is nothing to train "who wins" on.

| Column | Notes |
|---|---|
| MATCH_ID | unique key |
| DATE | ISO YYYY-MM-DD — drives walk-forward splits |
| COMPETITION | Six Nations / Rugby Championship / Autumn / RWC |
| SEASON | e.g. 2025 |
| ROUND | pool/round/knockout stage |
| HOME_TEAM | team code |
| AWAY_TEAM | team code |
| VENUE | stadium / city |
| NEUTRAL | 1 if neutral venue (most RWC + finals), else 0 |
| HOME_SCORE | full-time points |
| AWAY_SCORE | full-time points |
| HOME_TRIES | optional |
| AWAY_TRIES | optional |
| RESULT | H / A / D (derived) |

---

## How the two tables meet
1. Aggregate `player_stats` by (COUNTRY, SEASON, COMPETITION) -> a **team style vector**.
2. For each row in `match_results`, attach the style-vector **delta** (home minus away).
3. The match model learns win probability from rating diff + style delta + form.
4. Monte Carlo simulates the bracket from the match model -> champion probability.
