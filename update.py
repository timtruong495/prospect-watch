#!/usr/bin/env python3
"""Prospect Watch updater (no Claude needed).

Reads follow.json (who to follow), pulls schedules, scores, player game lines,
season stats and standings from the NHL and HockeyTech (AHL/OHL/WHL) feeds, and
writes data.json for the page. Leagues it can't read yet (NCAA) keep whatever
is already in data.json. Standard library only.

  python update.py            normal run
  python update.py --probe    also write probe.json (the shape of every feed
                              response) to help fix field names
"""
import datetime as dt, json, pathlib, re, sys, time, unicodedata, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
BC = dt.timezone(dt.timedelta(hours=-7))  # British Columbia: UTC-7 all year from 2026
NHL = "https://api-web.nhle.com/v1"
HT_URL = "https://lscluster.hockeytech.com/feed/"
HT = {  # public keys embedded in each league's own site
    "AHL": {"code": "ahl", "key": "50c2cd9b5e18e390", "game": "https://theahl.com/stats/game-center/{}",
            "player": "https://theahl.com/stats/player/{}"},
    "OHL": {"code": "ohl", "key": "2976319eb44abe94", "game": "https://chl.ca/ohl/gamecentre/{}/",
            "player": "https://chl.ca/ohl/players/{}/"},
    "WHL": {"code": "whl", "key": "41b145a848f4bd67", "game": "https://chl.ca/whl/gamecentre/{}/",
            "player": "https://chl.ca/whl/players/{}/"},
}
PROBE, WARN = {}, []


# ---------- small helpers ----------
def warn(msg):
    WARN.append(msg)
    print("WARN:", msg, file=sys.stderr)


def shape(o, depth=0):
    if isinstance(o, dict):
        return {k: shape(v, depth + 1) for k, v in list(o.items())[:80]} if depth < 5 else "{...}"
    if isinstance(o, list):
        return [shape(x, depth + 1) for x in o[:3]] + ["... %d items" % len(o)] if o else []
    return str(o)[:60]


def fetch_json(url, label):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "prospect-watch-updater", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            PROBE.setdefault(label, shape(data))
            return data
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("%s failed: %s" % (label, last))


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def g(d, *names, default=None):
    """First non-empty value among several possible field names."""
    for n in names:
        v = d.get(n)
        if v not in (None, ""):
            return v
    return default


def num(v):
    try:
        return int(float(str(v).replace("+", "").strip()))
    except (TypeError, ValueError):
        return None


def find_dicts(o, *alts):
    """Every dict (at any depth) that has at least one key from each group in alts."""
    if isinstance(o, dict):
        if all(any(k in o for k in grp) for grp in alts):
            yield o
        for v in o.values():
            yield from find_dicts(v, *alts)
    elif isinstance(o, list):
        for v in o:
            yield from find_dicts(v, *alts)


def to_bc(iso):
    """ISO time with offset (or Z) -> (date, time) in Vancouver."""
    t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    if t.tzinfo is None:
        return t.strftime("%Y-%m-%d"), None
    t = t.astimezone(BC)
    return t.strftime("%Y-%m-%d"), t.strftime("%H:%M")


def ordinal(n):
    n = int(n)
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def result(f, a, ot=None):
    s = {"f": f, "a": a, "res": "W" if f > a else "L"}
    if ot:
        s["ot"] = ot
    return s


# ---------- NHL ----------
def nhl_games(abbrev, season8):
    data = fetch_json("%s/club-schedule-season/%s/%s" % (NHL, abbrev, season8), "nhl.schedule")
    out = []
    for x in data.get("games", []):
        if x.get("gameType") != 2:  # regular season only
            continue
        home = x["homeTeam"]["abbrev"] == abbrev
        us, them = (x["homeTeam"], x["awayTeam"]) if home else (x["awayTeam"], x["homeTeam"])
        place = (them.get("placeName") or {}).get("default", them.get("abbrev"))
        if place == "New York":
            place = "NY " + (them.get("commonName") or {}).get("default", "")
        d, t = to_bc(x["startTimeUTC"])
        gm = {"team": None, "gid": str(x["id"]), "d": d, "t": t, "opp": place, "home": home}
        if x.get("gameState") in ("OFF", "FINAL") and us.get("score") is not None:
            last = (x.get("gameOutcome") or {}).get("lastPeriodType")
            gm["score"] = result(us["score"], them["score"], last if last in ("OT", "SO") else None)
            if x.get("gameCenterLink"):
                gm["box"] = "https://www.nhl.com" + x["gameCenterLink"]
        out.append(gm)
    return out


def nhl_record(abbrev, today):
    data = fetch_json(NHL + "/standings/now", "nhl.standings")
    for r in data.get("standings", []):
        if (r.get("teamAbbrev") or {}).get("default") == abbrev:
            return {"w": r.get("wins"), "l": r.get("losses"), "otl": r.get("otLosses"), "pts": r.get("points"),
                    "gp": r.get("gamesPlayed"),
                    "standing": "%s %s" % (ordinal(r.get("divisionSequence", 0)), r.get("divisionName", "")),
                    "asOf": today}
    raise RuntimeError("team %s not in NHL standings" % abbrev)


def nhl_player_id(abbrev, name):
    data = fetch_json("%s/roster/%s/current" % (NHL, abbrev), "nhl.roster")
    for grp in ("forwards", "defensemen", "goalies"):
        for p in data.get(grp, []):
            full = "%s %s" % ((p.get("firstName") or {}).get("default", ""), (p.get("lastName") or {}).get("default", ""))
            if norm(full) == norm(name):
                return str(p["id"])
    return None


def nhl_gamelog(pid, season8, goalie):
    data = fetch_json("%s/player/%s/game-log/%s/2" % (NHL, pid, season8), "nhl.gamelog")
    out = {}
    for r in data.get("gameLog", []):
        if goalie:
            sa, ga = num(r.get("shotsAgainst")), num(r.get("goalsAgainst"))
            line = {"sv": None if sa is None or ga is None else sa - ga, "ga": ga, "min": r.get("toi"),
                    "dec": r.get("decision")}
        else:
            line = {"g": num(r.get("goals")), "a": num(r.get("assists")), "pts": num(r.get("points")),
                    "pm": num(r.get("plusMinus")), "sog": num(r.get("shots")), "pim": num(r.get("pim"))}
        out[str(r.get("gameId"))] = {k: v for k, v in line.items() if v is not None}
    return out


# ---------- HockeyTech (AHL, OHL, WHL) ----------
def ht(league, label, **params):
    q = {"feed": "modulekit", "fmt": "json", "lang": "en", "client_code": HT[league]["code"], "key": HT[league]["key"]}
    q.update(params)
    return fetch_json(HT_URL + "?" + urllib.parse.urlencode(q), "%s.%s" % (league.lower(), label))


def ht_season(league, season):
    """Id of the regular season for a label like '2026-27'."""
    start = season.split("-")[0]
    rows = list(find_dicts(ht(league, "seasons", view="seasons"), ("season_id",), ("season_name",)))
    regular = [r for r in rows if str(r.get("playoff")) == "0" and str(r.get("career")) == "1"
               and "regular" in str(r.get("season_name")).lower()]
    for r in regular:
        if start in str(r.get("season_name")) or str(r.get("start_date", "")).startswith(start):
            return str(r["season_id"])
    if regular:
        return str(regular[0]["season_id"])
    raise RuntimeError("no regular season found for %s %s" % (league, season))


_TEAMS = {}


def ht_teams(league, sid):
    if (league, sid) not in _TEAMS:
        data = ht(league, "teams", view="teamsbyseason", season_id=sid)
        _TEAMS[(league, sid)] = list(find_dicts(data, ("id", "team_id"), ("name", "nickname")))
    return _TEAMS[(league, sid)]


def ht_team_id(league, sid, name):
    rows = ht_teams(league, sid)
    want = norm(name)
    for r in rows:
        names = {norm(r.get("name")), norm("%s %s" % (r.get("city", ""), r.get("nickname", "")))}
        if want in names:
            return str(g(r, "id", "team_id")), g(r, "code", "team_code")
    for r in rows:  # looser: nickname contained in the wanted name
        nick = norm(r.get("nickname"))
        if nick and nick in want and norm(r.get("city")) in want:
            return str(g(r, "id", "team_id")), g(r, "code", "team_code")
    raise RuntimeError("team '%s' not found in %s (have: %s)" % (name, league, ", ".join(sorted(str(r.get("name")) for r in rows))[:300]))


def ht_games(league, sid, tid):
    data = ht(league, "schedule", view="schedule", team_id=tid, season_id=sid)
    out, seen = [], set()
    for x in find_dicts(data, ("game_id", "id"), ("home_team",), ("visiting_team",)):
        gid = str(g(x, "game_id", "id"))
        if gid in seen:
            continue
        seen.add(gid)
        home = str(x.get("home_team")) == str(tid)
        opp = g(x, "visiting_team_city", "visiting_team_name") if home else g(x, "home_team_city", "home_team_name")
        iso = g(x, "GameDateISO8601", "game_date_iso_8601")
        try:
            d, t = to_bc(iso) if iso else (g(x, "date_played"), None)
        except ValueError:
            d, t = g(x, "date_played"), None
        gm = {"team": None, "gid": gid, "d": d, "t": t, "opp": opp, "home": home}
        status = str(g(x, "game_status", default=""))
        hs, vs = num(x.get("home_goal_count")), num(x.get("visiting_goal_count"))
        final = str(x.get("final")) == "1" or str(x.get("status")) == "4" or status.lower().startswith("final")
        if final and hs is not None and vs is not None and (hs or vs or status.lower().startswith("final")):
            ot = "SO" if str(x.get("shootout")) == "1" or "SO" in status else \
                 "OT" if str(x.get("overtime")) == "1" or "OT" in status else None
            gm["score"] = result(hs, vs, ot) if home else result(vs, hs, ot)
            gm["box"] = HT[league]["game"].format(gid)
        out.append(gm)
    if not out:
        raise RuntimeError("no games parsed from %s schedule (team %s)" % (league, tid))
    return out


def ht_player_id(league, sid, tid, name):
    data = ht(league, "roster", view="roster", team_id=tid, season_id=sid)
    want = norm(name)
    for p in find_dicts(data, ("player_id", "id"), ("name", "last_name")):
        full = g(p, "name") or "%s %s" % (p.get("first_name", ""), p.get("last_name", ""))
        if norm(full) == want:
            return str(g(p, "player_id", "id"))
    return None


def ht_gamelog(league, sid, pid, goalie):
    data = ht(league, "gamelog", view="player", category="gamebygame", player_id=pid, season_id=sid)
    out = {}
    for r in find_dicts(data, ("game_id", "id"), ("goals", "saves", "goals_against")):
        if goalie:
            sv, ga = num(r.get("saves")), num(r.get("goals_against"))
            line = {"sv": sv, "ga": ga, "min": g(r, "minutes", "minutes_played"),
                    "dec": "W" if str(r.get("win")) == "1" else "L" if str(r.get("loss")) == "1" else None}
        else:
            line = {"g": num(r.get("goals")), "a": num(r.get("assists")), "pts": num(r.get("points")),
                    "pm": num(r.get("plus_minus")), "sog": num(r.get("shots")), "pim": num(r.get("penalty_minutes"))}
        out[str(g(r, "game_id", "id"))] = {k: v for k, v in line.items() if v is not None}
    return out


def ht_record(league, sid, tid, today):
    rows = []
    for params in ({"view": "statviewtype", "type": "standings", "stat": "conference"}, {"view": "standings"}):
        try:
            rows = list(find_dicts(ht(league, "standings", season_id=sid, **params), ("team_id",), ("wins",)))
        except RuntimeError:
            rows = []
        if rows:
            break
    me = next((r for r in rows if str(r.get("team_id")) == str(tid)), None)
    if not me:
        raise RuntimeError("team %s not in %s standings" % (tid, league))
    # The division comes from the league's team list; the standings rows are grouped by conference.
    divs = {str(g(r, "id", "team_id")): g(r, "division_long_name", "division_short_name", default="")
            for r in ht_teams(league, sid)}
    div = divs.get(str(tid), "")

    def pts(r):
        return num(r.get("points")) or 0

    def order(r):  # the AHL ranks by points percentage, junior leagues by points
        gp = num(r.get("games_played")) or 0
        return (-(pts(r) / gp if gp else 0) if league == "AHL" else -pts(r), -(num(r.get("wins")) or 0))

    seen, same = set(), []
    for r in rows:
        rid = str(r.get("team_id"))
        if rid not in seen and div and divs.get(rid) == div:
            seen.add(rid)
            same.append(r)
    same.sort(key=order)
    rank = next((i + 1 for i, r in enumerate(same) if str(r.get("team_id")) == str(tid)), None)
    short = div[:-len(" Division")] if div.endswith(" Division") and len(div) > 13 else div
    otl = (num(me.get("ot_losses")) or 0) + (num(me.get("shootout_losses")) or 0)
    return {"w": num(me.get("wins")), "l": num(me.get("losses")), "otl": otl, "pts": num(me.get("points")),
            "gp": num(me.get("games_played")), "standing": ("%s %s" % (ordinal(rank), short)) if rank else "",
            "asOf": today}


# ---------- putting it together ----------
def season_stats(lines_by_game, games, goalie, league, team_name, url):
    """Season totals with the current team, summed from the game lines."""
    played = [(gm["d"], lines_by_game[gm["gid"]]) for gm in games if gm.get("score") and gm["gid"] in lines_by_game]
    if not played:
        return None
    st = {"gp": len(played), "league": league, "team": team_name, "asOf": max(d for d, _ in played),
          "src": league + " official stats", "url": url}
    if goalie:
        sv = sum(l.get("sv") or 0 for _, l in played)
        ga = sum(l.get("ga") or 0 for _, l in played)
        st.update(w=sum(1 for _, l in played if l.get("dec") == "W"), l=sum(1 for _, l in played if l.get("dec") == "L"))
        if sv + ga:
            st["svpct"] = ("%.3f" % (sv / (sv + ga))).lstrip("0")
    else:
        for k in ("g", "a", "pts", "pim", "pm"):
            st[k] = sum(l.get(k) or 0 for _, l in played)
    return st


def load(name, default):
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def main():
    follow = load("follow.json", None)
    if not follow:
        sys.exit("follow.json is missing")
    old = load("data.json", {"teams": {}, "players": [], "games": []})
    notes = load("notes.json", {})
    ids = load("ids.json", {"seasons": {}, "teams": {}, "players": {}})
    season = follow.get("season", "2026-27")
    season8 = season.split("-")[0] + str(int(season.split("-")[0]) + 1)
    today = dt.datetime.now(BC).strftime("%Y-%m-%d")

    # every team we need: followed ones plus each player's team
    teams = {}
    for t in follow.get("teamsFollowed", []):
        teams[t["key"]] = {"name": t["name"], "league": t["league"], "short": t.get("short"), "followed": True,
                           "ids": t.get("ids", {})}
    for p in follow.get("players", []):
        teams.setdefault(p["teamKey"], {"name": p["team"], "league": p["league"],
                                        "short": (old["teams"].get(p["teamKey"]) or {}).get("short"), "ids": {}})

    old_games = {}
    for gm in old.get("games", []):
        old_games.setdefault(gm["team"], []).append(gm)
    old_players = {p["id"]: p for p in old.get("players", [])}

    games_by_team, ok_teams, tried = {}, set(), 0
    for key, t in teams.items():
        lg = t["league"]
        prev = old["teams"].get(key) or {}
        t["record"] = prev.get("record")
        if lg not in HT and lg != "NHL":
            games_by_team[key] = old_games.get(key, [])  # not supported yet: keep what we have
            continue
        tried += 1
        try:
            if lg == "NHL":
                abbrev = t["ids"].get("nhlAbbrev") or t["short"]
                t["_abbrev"] = abbrev
                new = nhl_games(abbrev, season8)
            else:
                sid = ids["seasons"].get(lg + " " + season) or ht_season(lg, season)
                ids["seasons"][lg + " " + season] = sid
                tid = t["ids"].get("hockeytech") or ids["teams"].get(key)
                if not tid:
                    tid, code = ht_team_id(lg, sid, t["name"])
                    ids["teams"][key] = tid
                    t["short"] = t["short"] or code
                t["_sid"], t["_tid"] = sid, str(tid)
                new = ht_games(lg, sid, tid)
            # carry over anything the feed doesn't give us (older stat lines, notes)
            prev_by_day = {gm["d"]: gm for gm in old_games.get(key, [])}
            for gm in new:
                gm["team"] = key
                o = prev_by_day.get(gm["d"]) or {}
                if o.get("lines"):
                    gm["lines"] = dict(o["lines"])
                if o.get("note"):
                    gm["note"] = o["note"]
                if o.get("box") and not gm.get("box"):
                    gm["box"] = o["box"]
            games_by_team[key] = new
            ok_teams.add(key)
        except Exception as e:  # noqa: BLE001
            warn("%s: schedule not updated (%s)" % (t["name"], e))
            games_by_team[key] = old_games.get(key, [])
        if t.get("followed") and key in ok_teams:
            try:
                t["record"] = nhl_record(t["_abbrev"], today) if lg == "NHL" else ht_record(lg, t["_sid"], t["_tid"], today)
            except Exception as e:  # noqa: BLE001
                warn("%s: standings not updated (%s)" % (t["name"], e))

    if tried and not ok_teams:
        sys.exit("No feed could be read; data.json left unchanged.")

    players = []
    for p in follow.get("players", []):
        key, t = p["key"], teams[p["teamKey"]]
        o = old_players.get(key, {})
        out = {"id": key, "name": p["name"], "pos": p.get("pos", ""), "team": p["teamKey"],
               "note": notes.get(key, o.get("note", "")), "tags": p.get("tags", []), "draft": p.get("draft"),
               "stats": o.get("stats")}
        if p.get("list") == "other":
            out["list"] = "other"
        if p.get("pinTeam"):
            out["pinTeam"] = True
        lg, goalie = t["league"], p.get("pos") == "G"
        if p["teamKey"] in ok_teams:
            try:
                if lg == "NHL":
                    pid = (p.get("ids") or {}).get("nhl") or ids["players"].get(key) or nhl_player_id(t["_abbrev"], p["name"])
                    log = nhl_gamelog(pid, season8, goalie) if pid else None
                    url = "https://www.nhl.com/player/%s" % pid
                else:
                    pid = (p.get("ids") or {}).get("hockeytech") or ids["players"].get(key) \
                        or ht_player_id(lg, t["_sid"], t["_tid"], p["name"])
                    log = ht_gamelog(lg, t["_sid"], pid, goalie) if pid else None
                    url = HT[lg]["player"].format(pid)
                if not pid:
                    warn("%s: not found on the %s roster" % (p["name"], t["name"]))
                else:
                    ids["players"][key] = str(pid)
                    tg = games_by_team[p["teamKey"]]
                    for gm in tg:
                        if not gm.get("score"):
                            continue
                        lines = gm.setdefault("lines", {})
                        if gm["gid"] in log:
                            lines[key] = log[gm["gid"]]
                        elif key not in lines:
                            lines[key] = {"dnp": True}
                    st = season_stats(log, tg, goalie, lg, t["name"], url)
                    if st:
                        out["stats"] = st
            except Exception as e:  # noqa: BLE001
                warn("%s: stats not updated (%s)" % (p["name"], e))
        players.append(out)

    games = [gm for key in teams for gm in games_by_team.get(key, [])]
    games.sort(key=lambda gm: (gm.get("d") or "", gm.get("t") or "99"))
    data = {"updated": today, "updatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "teams": {k: {kk: vv for kk, vv in t.items() if not kk.startswith("_") and kk != "ids" and vv is not None}
                      for k, t in teams.items()},
            "players": players, "games": games, "warnings": WARN}
    (ROOT / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ROOT / "ids.json").write_text(json.dumps(ids, indent=1), encoding="utf-8")
    if "--probe" in sys.argv:
        (ROOT / "probe.json").write_text(json.dumps(PROBE, indent=1, ensure_ascii=False), encoding="utf-8")
    print("Updated %d of %d feed teams, %d players, %d games, %d warnings" % (len(ok_teams), tried, len(players), len(games), len(WARN)))


if __name__ == "__main__":
    main()
