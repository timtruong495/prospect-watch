"""One-time test, round 3: save real copies of World Juniors data.

Rounds 1 and 2 found that hockeycanada.ca pages carry the whole tournament
(schedule, scores, player stats) as built-in data, with full box scores only
for Canada's games. This round saves trimmed copies of that data from last
year's tournament (plus this year's schedule) into wjc_samples/, along with
the HockeyTech official game report for one non-Canada game, so the World
Juniors tab can be built and tested against real data.

Run by the "World Juniors data test" workflow (Actions tab, run by hand).
Python standard library only. Delete this file, its workflow and wjc_samples/
once the World Juniors tab is finished.
"""
import json, pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "wjc_samples"
SITE = "https://www.hockeycanada.ca"
PAGE = SITE + "/en-ca/team-canada/men/junior/{season}/world-championship/stats/{page}"
REPORT = "https://lscluster.hockeytech.com/game_reports/official-game-report.php?client_code=hockeycanada&game_id={}&lang_id=1"
UA = "Mozilla/5.0 (compatible; prospect-watch; +https://github.com/timtruong495/prospect-watch)"
LOG = {}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
            LOG[url] = {"status": r.status, "length": len(body)}
            return body
    except Exception as e:
        LOG[url] = {"status": getattr(e, "code", 0), "error": str(e)[:200]}
        return ""


def next_data(body):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
    try:
        return json.loads(m.group(1)) if m else None
    except ValueError:
        return None


def first(o, key):
    """First value stored under key, at any depth."""
    if isinstance(o, dict):
        if key in o:
            return o[key]
        o = list(o.values())
    if isinstance(o, list):
        for v in o:
            r = first(v, key)
            if r is not None:
                return r
    return None


def save(name, data):
    OUT.mkdir(exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, indent=1, ensure_ascii=False)
    (OUT / name).write_text(text, encoding="utf-8")


def skaters(game):
    gd = (game or {}).get("GameDetail") or {}
    return [p for p in (gd.get("homeSkaterStats") or []) + (gd.get("awaySkaterStats") or []) if p.get("name")]


def main():
    links = []
    for season, tag in (("2025-26", "2026"), ("2026-27", "2027")):
        for page in ("schedule", "player-stats"):
            body = get(PAGE.format(season=season, page=page))
            nd = next_data(body)
            mt = first(nd, "modelTournament") if nd else None
            if mt is not None:
                save(f"{tag}-{page}.json", mt)
            if page == "schedule" and tag == "2026":
                links = sorted(set(re.findall(r'/stats/game-summary/(\d+)', body)))
    # single-game pages: one Canada game (full box score) and one other game
    picked = {}
    for gid in links[:16]:
        gd = first(next_data(get(PAGE.format(season="2025-26", page="game-summary/" + gid))), "gameData")
        if not gd:
            continue
        kind = "canada" if skaters(gd) else "other"
        if kind not in picked:
            picked[kind] = gid
            save(f"2026-game-{kind}-{gid}.json", gd)
        if len(picked) == 2:
            break
    if "other" in picked:
        save(f"2026-report-{picked['other']}.html", get(REPORT.format(picked["other"])))
    save("log.json", {"picked": picked, "requests": LOG})
    print(json.dumps({"picked": picked, "files": sorted(p.name for p in OUT.iterdir())}, indent=1))


if __name__ == "__main__":
    main()
