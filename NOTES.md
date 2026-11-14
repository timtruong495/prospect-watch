# Prospect Watch: move off Claude (working notes)

Live shared page (do not change its code or layout): https://claude.ai/artifact/N9SkU1raGztRLpsjgQtaUZ
This artifact is the private working copy. Its files are laid out like the future GitHub project.

## Files here
- index.html: copy of the live page (snapshot 2026-11-10), read-only, data still inline.
- follow.json: who/what is followed (players, teams, tags, draft info, league IDs). Hand-editable.
- PLAN.md: this file.
- (to come) update.py: script that writes data.json; data.json: what the page reads.

## Chunks
1. [done 2026-11-10] Daily refresh task no longer rechecks old games with missing stat lines.
2. [done 2026-11-10] Feeds confirmed with URLs the user pasted: NHL club-schedule-season works (season 20262027,
   regular season = gameType 2, started 2026-09-29; fields verified: id, gameType, startTimeUTC, gameState "OFF",
   homeTeam/awayTeam .abbrev .score .placeName.default, gameOutcome.lastPeriodType, gameCenterLink).
   HockeyTech keys valid: AHL regular season id 94, OHL 88, WHL 295 (path SiteKit.Seasons).
   Verified later the same night: NHL /standings/now (standings[].teamAbbrev.default, wins, losses, otLosses,
   points, gamesPlayed, divisionName, divisionSequence: all as the script expects).
   HockeyTech player gamebygame (OHL, Novotný id 9638, season 88): path SiteKit.Player.games, 17 rows; game id
   field is "id" (not game_id); fields goals, assists, points, plus_minus, penalty_minutes ("0.00"), shots,
   shots_on, date_played, home_team, visiting_team, player_team (Petes team id = 6). Script handles all of these.
   Open question: "shots" (7) vs "shots_on" (3) for shots on goal; script uses "shots".
   NOT yet verified: HockeyTech teamsbyseason, schedule, roster, standings; NHL roster, game-log.
   The web fetch tool returned a stale seasons page for the teamsbyseason URL twice, so test it on GitHub. This session can only fetch URLs the user pastes, exactly as pasted.
3. [done 2026-11-10] Working copy created with follow.json.
4. [draft saved 2026-11-10] update.py written; logic tested offline against stand-in feeds only. It finds
   records by key names at any depth (find_dicts), so nesting differences don't matter, but field names for the
   unverified endpoints are from memory. First real run: `python update.py --probe`, then read probe.json and
   warnings in data.json and fix names. data.json here is the seed copied from the live page (2026-11-10).
   Files it writes: data.json (page data), ids.json (cached league ids), probe.json (with --probe).
   Optional notes.json {playerKey: note} overrides notes (this is where Claude's news notes will go).
5. [done 2026-11-10] index.html is now standalone: no Claude features, loads data.json (relative fetch, works on
   GitHub Pages and as an artifact), shows a stale-data warning after 2 days, tags with a tag filter, draft line,
   recent form (last 5 games with a stat line) and points per game, and lists script warnings in the footer.
   Checked in Chromium at phone and desktop width, light and dark: renders, no sideways scroll.
   data.json here = seed from the live page (2026-11-10) plus tags/draft from follow.json.
   github-workflow-update.yml is the scheduled job (goes to .github/workflows/update.yml in the repo).
6. NCAA (BU, Michigan, Michigan State, Denver): box-score page reader.
7. GitHub: account, repo, Pages, scheduled Action. Then cut Claude's task to news notes 1-2x a week.
Later: World Juniors (Dec 26 to Jan 5) games, calendar (.ics) feed.

## Decisions
- IDs are resolved by the script, not looked up by hand: fetch the team's roster for the season and match
  the player by name; cache the id back into follow.json. Team ids come from the league's team list by name.
- Player keys in follow.json equal the player ids in the live page data, so existing results carry over.
- Times stored as Vancouver local; BC stays on UTC-7 all year from 2026 (convert via UTC, subtract 7h).
- pinTeam: stay on this team through call-ups (Räty on the Marlies).

## Feed notes (from memory, UNTESTED)
NHL: https://api-web.nhle.com/v1/club-schedule-season/VAN/20262027 ; /v1/standings/now ;
     /v1/gamecenter/{gameId}/boxscore ; /v1/player/{id}/game-log/20262027/2
HockeyTech: https://lscluster.hockeytech.com/feed/?feed=modulekit&fmt=json&lang=en&client_code={ahl|ohl|whl}&key={key}
     &view=seasons | teamsbyseason&season_id= | schedule&team_id=&season_id= | roster&team_id=&season_id=
     | player&category=gamebygame&player_id=&season_id= | statviewtype&type=standings&season_id=
     game summary: feed=gc&tab=gamesummary&game_id=
     Keys are the public ones embedded in each league's own website; read them from the league site when testing.

## Known gaps in the live data (script should fill)
- Abbotsford, Petes, Generals, Giants results start mid-October, not opening night.
- About 40 played games lack a tracked player's stat line (mostly Michigan, Denver, Marlies).
- Draft year/round/pick missing for Cootes, Rogowski, Malhotra, Dervin, Medvedev; pick number for Romani, Celebrini.

## First real run (2026-11-10, GitHub Actions) 
- Green, 0 warnings. All six feed teams loaded from opening night; ids resolved by name
  (ABB 440, Marlies 335, Giants 223, Petes 6, Generals 4; Cootes 11363, Novotný 9638, Rogowski 9126,
  Medvedev 8983, Räty 8753). HockeyTech field names in update.py are confirmed working.
- Compared with the hand-checked data from the Claude-run page: no score differences on any game.
  "shots" is shots on goal (matches a box score). Game times now come from the feeds; a few differ from the
  old page by an hour (old ones were converted by hand).
- Bug found: division standing label. stat=conference standings rows are grouped by conference and their
  division/rank fields are not the team's division rank. Fixed by taking the division from teamsbyseason and
  ranking inside it (AHL by points percentage, junior by points).
- probe.json now keeps the first 3 rows of each list (the first standings row is a header).

## College players added (2026-11-11)
- update.py reads College Hockey News: /schedules/team/<School>/<id> for schedule and scores, and each
  /box/final/... page once per game for tracked players' lines (marker "bxp" on the game = players already read).
  Worked on the first real run: 4 schools, 38/35/35/37 games, all box scores parsed (38 skater rows).
- CHN times have no AM/PM (hours below 11 are treated as PM). Exhibition games "(ex)" are shown but not counted
  in season totals. Ties show as T.
- A footnote number can come before the result ("31 Sat 1 W 5 - 3 vs. North Dakota", a special-event game); it's
  dropped before reading the score (fixed 2026-11-14: that game had shown the score as its opponent).
- Totals match the hand-checked numbers except Romani: 7 GP 5-5-10 here vs 8 GP 12 pts before, because
  CHN lists MSU's Oct 2 game vs Boston College as an exhibition.
- User allowed small fixes to go straight to main (2026-11-11). Workflow can be started with
  gh api -X POST repos/timtruong495/prospect-watch/actions/workflows/414203236/dispatches -f ref=main

## World Juniors tab (2026-11-13)
- Source: Hockey Canada's tournament pages (Next.js built-in data, "__NEXT_DATA__"):
  /en-ca/team-canada/men/junior/<season>/world-championship/stats/schedule, where <season> is 2026-27 for the
  2027 tournament. modelTournament.dateGames[].games[] has GameOverview (id, gameNumber, round, status,
  home/away abbr name score, overtime, shootout, startDateTime with offset, venue "City, ST") and GameDetail.
- Hockey Canada only enters player stats for Canada's games. Those games have full box scores for both teams
  (homeSkaterStats/awaySkaterStats, GoalieStats, Scratches). Other games: score only. Its tournament player-stats
  list is built from Canada's games only (Novotný: 2 GP in 2026 instead of 7). The HockeyTech official game
  report is empty for non-Canada games too.
- Single-game pages (/stats/game-summary/<id>, gameData.GameDetail) list both lineups as "Scratches" for
  non-Canada games; update.py reads each finished game once (8 per run, "scanned") to find which country a
  followed player is on.
- Ruled out: iihf.com (403 to automated requests), Elite Prospects (403), Flashscore (page is a shell; the
  stats come from an internal feed; terms forbid automated use). Checked in 5 test runs, 2026-11-13.
- Missing lines: Claude's news task reads data.json wjc.missing and writes wjc_lines.json
  {playerKey: {gameNumber: {"g":1,"a":0} | {"sv":25,"ga":2} | {"dnp":true}}}. update.py marks them "via news".
- Country before games start: follow.json "wjc": "CZE" on a player (IIHF three-letter code). Lineups found in
  games take priority.
- The tab and the update run from Dec 1 to Jan 12 (wjc_year in update.py). Outside it, data.json has no "wjc".
- Group standings are worked out from preliminary-round games (3/2/1/0 points; ties by goal difference, then
  goals for, not the IIHF head-to-head rule). Groups are named after the city where they play.
- Tested against the 2026 tournament's real data (saved during the tests, then deleted).
