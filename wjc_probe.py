"""One-time test: find a usable data source for World Juniors games.

Run by the "World Juniors data test" workflow (Actions tab, run by hand).
Writes wjc_probe.json: for each candidate page, the HTTP status and any lines
that look like data feeds (HockeyTech keys, API or JSON addresses). If a
HockeyTech key turns up, it also asks that feed for its season list.
Python standard library only. Delete this file and its workflow once done.
"""
import json, pathlib, re, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).parent
UA = "Mozilla/5.0 (compatible; prospect-watch; +https://github.com/timtruong495/prospect-watch)"
PAGES = {
    "hc.2026.schedule": "https://www.hockeycanada.ca/en-ca/team-canada/men/junior/2025-26/world-championship/stats/schedule",
    "hc.2026.playerstats": "https://www.hockeycanada.ca/en-ca/team-canada/men/junior/2025-26/world-championship/stats/player-stats",
    "hc.2027.schedule": "https://www.hockeycanada.ca/en-ca/team-canada/men/junior/2026-27/world-championship/stats/schedule",
    "iihf.2026.schedule": "https://www.iihf.com/en/events/2026/wm20/schedule",
    "iihf.2027.schedule": "https://www.iihf.com/en/events/2027/wm20/schedule",
}
PATTERNS = re.compile(r"hockeytech|lscluster|client_code|[?&]key=|\bkey\s*[:=]|/api/|\.json\b|realtime|gameid|game_id|feed", re.I)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, "", ""
    except Exception as e:
        return 0, type(e).__name__ + ": " + str(e)[:200], ""


def hits(text, limit=40):
    out = []
    for m in PATTERNS.finditer(text):
        s = text[max(0, m.start() - 120): m.end() + 160].replace("\n", " ")
        if not any(s[100:200] in o for o in out):
            out.append(s)
        if len(out) >= limit:
            break
    return out


def main():
    probe, keys, codes = {}, set(), set()
    for label, url in PAGES.items():
        status, ctype, body = get(url)
        title = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
        scripts = re.findall(r"<script[^>]+src=[\"']([^\"']+)", body, re.I)
        entry = {"url": url, "status": status, "type": ctype, "length": len(body),
                 "title": title.group(1).strip()[:200] if title else "", "scripts": scripts[:60], "hits": hits(body)}
        # look inside scripts that might hold feed settings
        for src in [s for s in scripts if re.search(r"stat|hockeytech|ht|config|app|main", s, re.I)][:6]:
            full = urllib.parse.urljoin(url, src)
            st, _, js = get(full)
            entry.setdefault("scriptHits", {})[full] = {"status": st, "hits": hits(js, 15)}
            body += js
        codes.update(re.findall(r"client_code[\"'=:\s]+([a-z][a-z0-9_]{1,30})", body, re.I))
        keys.update(re.findall(r"key[\"'=:\s]+([a-f0-9]{16})\b", body, re.I))
        probe[label] = entry
    probe["hockeytech.found"] = {"client_codes": sorted(codes), "keys": sorted(keys)}
    for code, key in [(c, k) for c in sorted(codes) for k in sorted(keys)][:8]:
        q = urllib.parse.urlencode({"feed": "modulekit", "view": "seasons", "fmt": "json", "lang": "en",
                                    "client_code": code, "key": key})
        st, _, body = get("https://lscluster.hockeytech.com/feed/?" + q)
        probe["hockeytech." + code + "." + key[:4] + ".seasons"] = {"status": st, "body": body[:6000]}
    (ROOT / "wjc_probe.json").write_text(json.dumps(probe, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: (v.get("status") if isinstance(v, dict) else v) for k, v in probe.items()}, indent=1))


if __name__ == "__main__":
    main()
