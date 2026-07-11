"""
RugbyAnalytics ETL — Six Nations player stats + match results.

Two free sources, no API key required:
  * ESPN JSON API  (site.api.espn.com)  -> match results + rosters + minutes
  * RugbyPass.com player pages           -> full Opta stat feed per player

RugbyPass player pages embed every player's per-season Opta block (all the
advanced metrics: post-contact metres, dominant tackles, ruck-arrival
effectiveness, bad passes, etc.) that ESPN's free feed does not expose.

Usage:
    python -m src.etl.rugbypass_pull --seasons 2024 2025 --out data/processed

Notes / caveats:
  * ~15-25% of bench players won't resolve on RugbyPass (slug mismatch or no
    retained history). The script caches every fetched page under .cache/ so
    reruns are cheap and resumable.
  * ESPN occasionally returns fewer than 15 matches for a season (data gap
    upstream) — verify match counts before trusting a season.
  * PENALTIES_CONCEDED is sometimes null in the RugbyPass feed.
"""
import argparse, json, os, re, time, unicodedata, urllib.request
from collections import defaultdict

LEAGUE = "180659"  # Six Nations
ABBR = {'France':'FRE','Wales':'WAL','Scotland':'SCT','Italy':'ITL','Ireland':'IRE','England':'ENG'}
UA = {'User-Agent': 'Mozilla/5.0'}
CACHE = ".cache/rugbypass"


def _get_json(url):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


def _get_html(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=25).read().decode('utf-8', 'ignore')


def pull_espn(season):
    """Return (matches, players) for one Six Nations season from ESPN."""
    d = _get_json(f"https://sports.core.api.espn.com/v2/sports/rugby/leagues/{LEAGUE}"
                  f"/seasons/{season}/types/1/events?lang=en&region=us&limit=100")
    eids = [re.search(r'/events/(\d+)', it['$ref']).group(1) for it in d.get('items', [])]
    matches, players = [], {}
    for eid in eids:
        s = _get_json(f"https://site.api.espn.com/apis/site/v2/sports/rugby/{LEAGUE}/summary?event={eid}")
        comp = s.get('header', {}).get('competitions', [{}])[0]
        tm = {c.get('homeAway'): {'name': c.get('team', {}).get('displayName'),
                                  'score': c.get('score')} for c in comp.get('competitors', [])}
        if tm.get('home') and tm.get('away'):
            matches.append({'eid': eid, 'date': comp.get('date', '')[:10],
                            'home': ABBR.get(tm['home']['name'], tm['home']['name']), 'hs': int(tm['home']['score']),
                            'away': ABBR.get(tm['away']['name'], tm['away']['name']), 'aw': int(tm['away']['score'])})
        for tb in s.get('boxscore', {}).get('players', []):
            team = tb.get('team', {}).get('displayName')
            for grp in tb.get('statistics', []):
                for ath in grp.get('athletes', []):
                    a = ath.get('athlete', {}); pid = a.get('id')
                    if not pid:
                        continue
                    played = bool(ath.get('statistics') and ath['statistics'][0].get('stats'))
                    rec = players.setdefault(pid, {'name': a.get('displayName'), 'country': team,
                          'position': (a.get('position') or {}).get('abbreviation'), 'apps': 0})
                    if played:
                        rec['apps'] += 1
        time.sleep(0.2)
    return matches, players


def _slug_variants(name):
    base = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    v1 = re.sub(r'[^a-z0-9]+', '-', base.replace("'", "")).strip('-')
    v2 = re.sub(r'[^a-z0-9]+', '-', base.replace("'", "-")).strip('-')
    return list(dict.fromkeys([v1, v2]))


def _parse_seasons(html):
    """Extract {season: opta_stats_dict} for all Six Nations blocks on a player page."""
    un = html.replace('\\_', '_').replace('\\/', '/')
    out = {}
    for m in re.finditer(r'\{"success":1,"stats":\{"att_ruck_arrival_effectiveness"', un):
        start = m.start(); depth = 0; i = start
        while i < len(un):
            if un[i] == '{':
                depth += 1
            elif un[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        try:
            o = json.loads(un[start:i + 1])['stats']
        except Exception:
            continue
        before = un[:start]
        sm = list(re.finditer(r'"season":(\d{4})', before))
        nm = list(re.finditer(r'"name":"([^"]+)"', before))
        if sm and nm and 'Six Nations' in nm[-1].group(1):
            out[int(sm[-1].group(1))] = o
    return out


def pull_rugbypass(players):
    """Fetch each unique player's RugbyPass page (cached) -> {pid: {name,country,seasons}}."""
    os.makedirs(CACHE, exist_ok=True)
    results, failed = {}, []
    for pid, meta in players.items():
        blocks = None
        for s in _slug_variants(meta['name']):
            cf = os.path.join(CACHE, f"{s}.html")
            try:
                if os.path.exists(cf) and os.path.getsize(cf) > 1000:
                    html = open(cf, encoding='utf-8', errors='ignore').read()
                else:
                    html = _get_html(f"https://www.rugbypass.com/players/{s}/")
                    open(cf, 'w', encoding='utf-8').write(html)
                    time.sleep(0.35)
                blocks = _parse_seasons(html)
                if blocks:
                    break
            except Exception:
                continue
        if blocks:
            results[pid] = {'name': meta['name'], 'country': meta['country'], 'seasons': blocks}
        else:
            failed.append((pid, meta['name']))
    return results, failed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int, default=[2024, 2025])
    ap.add_argument("--out", default="data/processed")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    all_players, all_matches = {}, {}
    for yr in args.seasons:
        matches, players = pull_espn(yr)
        all_matches[yr] = matches
        all_players.update(players)
        print(f"{yr}: {len(matches)} matches, {len(players)} players")

    results, failed = pull_rugbypass(all_players)
    print(f"RugbyPass: {len(results)} players resolved, {len(failed)} failed")

    json.dump({'matches': all_matches, 'players': results,
               'failed': failed},
              open(os.path.join(args.out, "sixnations_raw.json"), "w"), indent=2)
    print(f"wrote {args.out}/sixnations_raw.json")
