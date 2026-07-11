# Modeling & Validation Protocol

This document is the statistical contract for RugbyAnalytics. It defines the estimand,
the data, the models, and — most importantly — how we decide a model is good enough to
trust on a once-every-four-years event.

## 1. Estimand
For each team *i*: **P(i = RWC 2027 champion)**, plus secondary estimands
P(reach final), P(win pool), and a full predictive distribution over the bracket.

## 2. Data
| Source | Coverage | Use |
|---|---|---|
| Six Nations | annual, 2000– | training + backtest |
| The Rugby Championship | annual, 2012– (Tri-Nations before) | training + backtest |
| Autumn internationals | annual | training + backtest |
| Past Rugby World Cups | 4-yearly | out-of-sample bracket tests |

Each row is one international match: date, home/away team, venue (neutral flag), full-time
score, competition, and optional RugbyIQ style-vector deltas.

## 3. Three-layer model
### 3.1 Rating layer (R)
- **Elo** with a rugby-tuned K-factor and margin-of-victory multiplier — the baseline.
- **Glicko-2** to carry a rating *uncertainty*, important for teams with sparse fixtures.
- **Bayesian state-space rating**: team strength as a latent AR(1) process, updated
  match to match (Kalman / Stan). Produces credible intervals, not just point ratings.

### 3.2 Match layer
Given (home, away, date, neutral) -> distribution over (home_score, away_score) and P(win).
- **Bayesian hierarchical GLM (R / Stan):** score_ij ~ Poisson/NegBinomial(attack_i,
  defense_j, home_adv), partial pooling across teams; priors informed by ratings.
- **ML challenger (Python / XGBoost):** features = rating diff, rating uncertainty, recent
  form, rest days, RugbyIQ style deltas; predicts win prob and expected margin.
- The two compete; the winner is the better-*calibrated* model (Section 4).

### 3.3 Tournament layer (Python)
Monte Carlo: for each of N>=10,000 rollouts, draw every pool and knockout match from the
match layer, resolve the bracket, record the champion. Championship probability =
fraction of rollouts each team wins. Propagate rating uncertainty by re-sampling team
strengths per rollout.

## 4. Validation — the part that matters
Point-forecast accuracy is not enough for a probabilistic model; it must be **calibrated**
(when we say 30%, it should happen ~30% of the time).

- **Walk-forward backtest:** fit on all matches up to date *t*, predict the next
  tournament, score, roll *t* forward. No peeking.
- **Scoring rules:** Brier score and log-loss on match win-probabilities; reliability
  diagrams for calibration.
- **Baselines to beat:** (a) home-team-always, (b) higher-Elo-always, (c) bookmaker
  implied probabilities where available. A model that cannot beat Elo-only is not shipped.
- **Bracket-level check:** replay past RWCs — did the eventual champion sit in the top
  handful of pre-tournament probabilities? Did final-four hit rates match stated odds?

## 5. Deliverable
A single reproducible notebook that outputs the RWC 2027 champion probability table with
credible intervals, the reliability diagram proving calibration, and a sensitivity panel
(draw, key injuries, current form) showing how the forecast moves.
