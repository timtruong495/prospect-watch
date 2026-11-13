"""One-time test, round 4: save the full tournament data blocks.

Round 3 saved each page's small menu block by mistake (it took the first
"modelTournament" it found). This round saves the largest "customData" block
on each page instead, which is where round 2 found the schedule (dateGames)
and player stats (Leaders). It also saves the rosters and standings pages.
Single-game samples from round 3 stay in wjc_samples/.

Run by the "World Juniors data test" workflow (Actions tab, run by hand).
Python standard library only. Delete this file, its workflow and wjc_samples/
once the World Juniors tab is finished.
"""
import json, pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "wjc_samples"
PAGE = "https://www.hockeycanada.ca/en-ca/team-canada/men/junior/{season}/world-championship/stats/{page}"
PAGES = [("2025-26", "2026", "schedule"), ("2025-26", "2026", "Player-Stats"), ("2025-26", "2026", "Team-Rosters"),
         ("2025-26", "2026", "Team-Standings"), ("2026-27", "2027", "schedule"), ("2026-27", "2027", "Team-Rosters")]
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


def every(o, key, out=None):
    """Every value stored under key, at any depth."""
    out = [] if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                out.append(v)
            every(v, key, out)
    elif isinstance(o, list):
        for v in o:
            every(v, key, out)
    return out


def main():
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("20*-schedule.json"):
        old.unlink()
    for old in OUT.glob("20*-player-stats.json"):
        old.unlink()
    saved = {}
    for season, tag, page in PAGES:
        nd = next_data(get(PAGE.format(season=season, page=page)))
        blocks = [json.dumps(b, indent=1, ensure_ascii=False) for b in every(nd, "customData") if b] if nd else []
        name = f"{tag}-{page.lower()}.json"
        if blocks:
            text = max(blocks, key=len)
            (OUT / name).write_text(text, encoding="utf-8")
            saved[name] = {"blocks": len(blocks), "sizes": sorted(len(b) for b in blocks)[-5:]}
        else:
            saved[name] = "no data found" if nd else "page has no built-in data"
    (OUT / "log.json").write_text(json.dumps({"saved": saved, "requests": LOG}, indent=1), encoding="utf-8")
    print(json.dumps(saved, indent=1))


if __name__ == "__main__":
    main()
