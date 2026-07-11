"""
Elo computation for RugbyAnalytics.

Two levels:
  1. TEAM Elo  — classic Elo updated match-by-match from real results
                 (margin-of-victory multiplier + home advantage).
  2. PLAYER Elo — each player inherits their team's Elo delta for every match
                 they appeared in, weighted by share of minutes played, so a
                 player who plays 80 min moves more than a 20-min sub. Player
                 rating starts at their team's rating when they debut.

Team Elo is the sound, standard quantity. Player Elo here is a *defensible
heuristic* (rugby has no per-player win/loss), documented as such so Davia can
challenge or replace it — e.g. with a minutes-weighted plus/minus later.
"""
from collections import defaultdict

BASE = 1500.0
K = 32.0
HOME_ADV = 40.0     # Elo points added to home team's expected score
MOV_ON = True


def expected(ra, rb):
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def mov_multiplier(margin, elo_diff):
    """Margin-of-victory multiplier (FiveThirtyEight-style), dampens Elo inflation."""
    if not MOV_ON:
        return 1.0
    return (abs(margin) + 3) ** 0.8 / (7.5 + 0.006 * abs(elo_diff))


def compute_team_elo(matches):
    """
    matches: list of dicts sorted by date, each
             {date, home, away, hs, aw}  (team codes + scores)
    Returns:
      final:   {team: rating}
      history: list of per-match rows with pre/post ratings + deltas
    """
    rating = defaultdict(lambda: BASE)
    history = []
    for m in sorted(matches, key=lambda x: x['date']):
        h, a = m['home'], m['away']
        rh, ra = rating[h], rating[a]
        eh = expected(rh + HOME_ADV, ra)
        ea = 1 - eh
        if m['hs'] > m['aw']:
            sh, sa = 1.0, 0.0
        elif m['hs'] < m['aw']:
            sh, sa = 0.0, 1.0
        else:
            sh = sa = 0.5
        margin = m['hs'] - m['aw']
        mult = mov_multiplier(margin, (rh + HOME_ADV) - ra)
        dh = K * mult * (sh - eh)
        da = K * mult * (sa - ea)
        rating[h] = rh + dh
        rating[a] = ra + da
        history.append({**m, 'rh_pre': rh, 'ra_pre': ra,
                        'rh_post': rating[h], 'ra_post': rating[a],
                        'dh': dh, 'da': da})
    return dict(rating), history


def compute_player_elo(team_history, player_minutes):
    """
    team_history:   output of compute_team_elo (per-match deltas).
    player_minutes: {pid: {'team':code, 'matches':[(eid, minutes), ...],
                            'name':..., 'total_min':...}}
                    Simplified here: we attribute each team match delta to the
                    players of that team weighted by that match's minute share.
                    Since we only hold season-total minutes (not per-match), we
                    approximate: player's season Elo delta =
                        sum over team matches of (team delta * player_share)
                    where player_share = min(player_total_min / (team_matches*80), 1)
                    spread evenly across the team's matches.
    Returns {pid: rating} starting from team rating at season start (BASE here).
    """
    # aggregate team deltas per match in order
    team_match_deltas = defaultdict(list)   # team -> [delta, ...]
    for row in team_history:
        team_match_deltas[row['home']].append(row['dh'])
        team_match_deltas[row['away']].append(row['da'])

    player_rating = {}
    for pid, info in player_minutes.items():
        team = info['team']
        deltas = team_match_deltas.get(team, [])
        n = len(deltas) if deltas else 1
        # share of a full 80-min game per team match
        share = min(info['total_min'] / (n * 80.0), 1.0) if n else 0.0
        rating = BASE + share * sum(deltas)
        player_rating[pid] = rating
    return player_rating
