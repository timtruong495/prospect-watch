"""One-time test, round 5: other sources for non-Canada World Juniors games.

Hockey Canada only records player stats for Canada's games, and iihf.com turns
away automated requests. This round checks Elite Prospects and Flashscore the
same way: their published rules for automated visitors (robots.txt), then
ordinary page requests with an honest User-Agent. It does not call any site's
internal data feeds or copy headers from their pages.

Run by the "World Juniors data test" workflow (Actions tab, run by hand).
Writes wjc_samples/round5.json. Python standard library only. Delete this
file, its workflow and wjc_samples/ once the World Juniors tab is finished.
"""
import html, json, pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "wjc_samples"
UA = "Mozilla/5.0 (compatible; prospect-watch; +https://github.com/timtruong495/prospect-watch)"
ROBOTS = ["https://www.eliteprospects.com/robots.txt", "https://www.flashscore.ca/robots.txt",
          "https://www.flashscore.info/robots.txt"]
PAGES = {
    # Adam Novotný (Elite Prospects id 876572, from follow.json): profile and 2025-26 game log
    "ep.player": "https://www.eliteprospects.com/player/876572/adam-novotny",
    "ep.gamelog": "https://www.eliteprospects.com/player/876572/adam-novotny/gamelog/2025-2026",
    # Flashscore match page for Czechia vs Sweden, Jan 5, 2026 (the page itself, not its data feed)
    "fs.match": "https://www.flashscore.info/match/ice-hockey/czech-republic-n5YYqbwk/sweden-MFCb1chr/summary/player-stats/overall/?mid=Ox8UWYHO",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), ""


def text(body):
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))


def around(t, words, width=700, limit=6):
    out = []
    for w in words:
        for m in re.finditer(w, t):
            out.append(t[max(0, m.start() - 150): m.start() + width])
            if len(out) >= limit:
                return out
    return out


def main():
    OUT.mkdir(exist_ok=True)
    result = {"robots": {}, "pages": {}}
    for url in ROBOTS:
        st, body = get(url)
        result["robots"][url] = {"status": st, "text": body[:6000]}
    for label, url in PAGES.items():
        st, body = get(url)
        t = text(body)
        result["pages"][label] = {"url": url, "status": st, "length": len(body),
                                  "title": (re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I) or [None, ""])[1][:200],
                                  "wjc": around(t, ["WJC", "World Junior"]), "start": t[:1500]}
    (OUT / "round5.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v["status"] for k, v in {**result["robots"], **result["pages"]}.items()}, indent=1))


if __name__ == "__main__":
    main()
