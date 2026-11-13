"""One-time test, round 2: look inside Hockey Canada's World Juniors pages.

Round 1 found that hockeycanada.ca serves the pages (status 200) with the data
built into each page (a Next.js "__NEXT_DATA__" block), and that iihf.com
refuses automated requests (403). This round records the shape of that built-in
data, sample game and player records, and links to game pages. iihf.com is
not tried again: it turns away automated requests, so it is not a source.

Run by the "World Juniors data test" workflow (Actions tab, run by hand).
Writes wjc_probe.json. Python standard library only. Delete this file and its
workflow once the data source is settled.
"""
import json, pathlib, re, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).parent
BASE = "https://www.hockeycanada.ca/en-ca/team-canada/men/junior/{season}/world-championship/{page}"
PAGES = {
    "hc.2026.schedule": ("2025-26", "stats/schedule"),
    "hc.2026.playerstats": ("2025-26", "stats/player-stats"),
    "hc.2026.standings": ("2025-26", "stats/standings"),
    "hc.2027.schedule": ("2026-27", "stats/schedule"),
}
UA = "Mozilla/5.0 (compatible; prospect-watch; +https://github.com/timtruong495/prospect-watch)"
GAMEY = {"gameid", "game_id", "homegoals", "homescore", "home_goal_count", "visitorgoals", "awayscore", "hometeam", "visitingteam", "awayteam"}
PLAYERY = {"playerid", "player_id", "goals", "assists", "points", "firstname", "first_name", "jersey"}


def get(url, accept="text/html,*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "en-CA,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, type(e).__name__ + ": " + str(e)[:200]


def shape(o, depth=0, maxd=7):
    """Keys tree with sample values; lists show their length and first item."""
    if depth >= maxd:
        return "…"
    if isinstance(o, dict):
        return {k: shape(v, depth + 1, maxd) for k, v in list(o.items())[:60]}
    if isinstance(o, list):
        return [f"list of {len(o)}", shape(o[0], depth + 1, maxd)] if o else []
    if isinstance(o, str):
        return o[:80]
    return o


def find(o, wanted, path="", out=None, limit=4):
    """Paths of lists whose items look like games or players, with samples."""
    out = {} if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            find(v, wanted, path + "." + k, out, limit)
    elif isinstance(o, list):
        if o and isinstance(o[0], dict) and len({k.lower() for k in o[0]} & wanted) >= 2 and path not in out:
            out[path] = {"count": len(o), "samples": o[:limit]}
        for i, v in enumerate(o[:3]):
            find(v, wanted, path + f"[{i}]", out, limit)
    return out


def next_data(body):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def look(url):
    status, body = get(url)
    nd = next_data(body)
    entry = {"url": url, "status": status, "length": len(body), "hasNextData": nd is not None}
    if nd:
        entry["buildId"] = nd.get("buildId")
        entry["shape"] = shape(nd.get("props", {}).get("pageProps", {}), maxd=6)
        entry["games"] = find(nd, GAMEY)
        entry["players"] = find(nd, PLAYERY, limit=3)
        # other data addresses mentioned inside the data (feeds the page may call later)
        entry["addresses"] = sorted(set(re.findall(r"https?://[^\"'\s<>\\]+", json.dumps(nd))))[:80]
    entry["gameLinks"] = sorted(set(re.findall(r'href="([^"]*game[^"]*)"', body, re.I)))[:30]
    return entry, nd


def main():
    probe = {}
    for label, (season, page) in PAGES.items():
        entry, nd = look(BASE.format(season=season, page=page))
        probe[label] = entry
        # the same data as plain JSON (Next.js data address), if it answers
        if nd and nd.get("buildId"):
            slug = "/".join(nd.get("query", {}).get("slug", []))
            jurl = f"https://www.hockeycanada.ca/_next/data/{nd['buildId']}/en-ca/{slug}.json"
            st, body = get(jurl, "application/json")
            entry["jsonAddress"] = {"url": jurl, "status": st, "length": len(body)}
    # follow the first game link from last year's schedule (a single game page)
    links = [l for l in probe["hc.2026.schedule"].get("gameLinks", []) if re.search(r"\d{4,}", l)]
    if links:
        url = urllib.parse.urljoin(BASE.format(season="2025-26", page="stats/schedule"), links[0])
        probe["hc.2026.game"], _ = look(url)
    (ROOT / "wjc_probe.json").write_text(json.dumps(probe, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v.get("status") for k, v in probe.items()}, indent=1))


if __name__ == "__main__":
    main()
