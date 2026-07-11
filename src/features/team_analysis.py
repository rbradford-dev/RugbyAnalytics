"""
Team-level aggregation + walk-forward win-probability backtest for RugbyAnalytics.

- aggregate_team_stats: roll player Opta stats up to team style vectors per season.
- backtest_elo: walk-forward Brier/accuracy for the Elo match model vs a
  home-always baseline. This is the calibration seed required by
  docs/MODELING.md §4 — a model that cannot beat the baseline is not shipped.
"""
from collections import defaultdict
from . import elo as elomod

SUM_FIELDS = ['points', 'tries', 'clean_breaks', 'carries', 'metres', 'defenders_beaten',
              'turnovers_won', 'touches', 'post_contact_metres', 'tackles', 'missed_tackles',
              'dominant_tackles', 'try_assist', 'passes', 'bad_passes', 'offloads',
              'penalties_conceded', 'yellow_cards', 'red_cards', 'minutes_played_total']


def aggregate_team_stats(results, abbr, seasons):
    """results: {pid: {country, seasons:{yr:opta}}} -> {(season,team): summed_stats}."""
    team = defaultdict(lambda: defaultdict(float))
    for pid, r in results.items():
        code = abbr.get(r['country'], r['country'])
        for yr in seasons:
            blk = r['seasons'].get(yr)
            if not blk:
                continue
            for f in SUM_FIELDS:
                team[(yr, code)][f] += blk.get(f) or 0
    return {k: dict(v) for k, v in team.items()}


def backtest_elo(matches_by_season, seasons):
    """Walk-forward: predict each match from Elo fit on prior matches only.
    Returns dict with Brier + accuracy for Elo and the home-always baseline."""
    def exp(a, b):
        return 1 / (1 + 10 ** ((b - a) / 400))

    rating = defaultdict(lambda: 1500.0)
    ordered = []
    for yr in seasons:
        for m in sorted(matches_by_season.get(yr, []), key=lambda x: x['date']):
            ordered.append(m)

    brier_elo = brier_home = 0.0
    correct_elo = correct_home = n = 0
    rows = []
    for m in ordered:
        h, a = m['home'], m['away']
        rh, ra = rating[h], rating[a]
        p_home = exp(rh + elomod.HOME_ADV, ra)
        actual = 1.0 if m['hs'] > m['aw'] else (0.0 if m['hs'] < m['aw'] else 0.5)
        brier_elo += (p_home - actual) ** 2
        brier_home += (1.0 - actual) ** 2
        if actual != 0.5:
            n += 1
            if (p_home > 0.5) == (actual == 1):
                correct_elo += 1
            if actual == 1:
                correct_home += 1
        rows.append({**m, 'p_home': round(p_home, 3), 'actual': actual})
        # update
        sh = 1.0 if m['hs'] > m['aw'] else (0.0 if m['hs'] < m['aw'] else 0.5)
        mult = elomod.mov_multiplier(m['hs'] - m['aw'], (rh + elomod.HOME_ADV) - ra)
        rating[h] = rh + elomod.K * mult * (sh - exp(rh + elomod.HOME_ADV, ra))
        rating[a] = ra + elomod.K * mult * ((1 - sh) - exp(ra, rh + elomod.HOME_ADV))

    N = len(ordered)
    return {
        'rows': rows, 'N': N, 'n': n,
        'brier_elo': brier_elo / N, 'brier_home': brier_home / N,
        'acc_elo': correct_elo / n, 'acc_home': correct_home / n,
    }
