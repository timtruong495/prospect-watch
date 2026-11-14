# Prospect Watch

A hockey tracking site: https://timtruong495.github.io/prospect-watch/ (GitHub Pages, main branch).
All times are Vancouver time. British Columbia stays on UTC-7 all year from 2026: convert via UTC.

## Working with the owner
- The owner is new to GitHub. Give step-by-step instructions for GitHub web tasks, but NOT for running
  workflows (they know how: Actions tab, pick the workflow, "Run workflow").
- When they report a problem: explain the cause and suggest a fix, then wait for approval or comments
  before committing. Only skip the wait when they've already said exactly what to change.
- Small fixes go straight to main (after approval). Bigger changes go as a pull request for them to merge.
- Test page changes in a browser (Playwright, phone width, light and dark) before committing.
- Explain in plain language; avoid jargon.

## Tabs
- **Canucks prospects** and **Other players**: player cards (season stats, last-5 totals, season pts/game,
  draft line, tags, news note; "Out:" notes show in red), a league filter (from each player's team, not
  tags), a tag filter, and a day-by-day schedule. Tap a game for the player's stat line.
- **Teams**: Vancouver Canucks (NHL), Abbotsford Canucks (AHL), Vancouver Giants (WHL).
- **World Juniors** (only Dec 1 to Jan 12): whole tournament schedule, group standings, cards for followed
  players on national teams, Canucks prospects / Other players filter. Regular cards link to it.

## Files
- `index.html`: the whole page (inline CSS and JS). Reads `data.json`.
- `follow.json`: players and teams to follow. The only file edited by hand (plus Claude tasks, below).
  Player fields: key, name, list (canucks/other), pos, league, team, teamKey, tags, draft, ids, pinTeam,
  wjc (IIHF code, e.g. "CZE", set when named to a World Juniors team).
- `notes.json`: one news note per player key (written by the news task).
- `wjc_lines.json`: World Juniors stat lines for games without Canada (written by the stat-lines tasks).
- `update.py`: pulls all data and rewrites `data.json` and `ids.json`. Python standard library only.
- `.github/workflows/update.yml`: runs `update.py --probe` at :07 past the hour, 4 PM to midnight plus
  6 AM and noon Vancouver time, and commits as prospect-watch-bot ("Update data"). Main gets these
  commits all the time, so fetch and rebase before pushing.
- `ids.json` (cached league ids), `probe.json` (raw feed shapes for debugging), `README.md` (owner-facing
  how-to), `NOTES.md` (detailed technical log: read it before changing data code).
- `__pycache__/update.cpython-313.pyc` is tracked by mistake: don't commit changes to it.

## Data sources (no Claude usage)
- NHL: api-web.nhle.com (schedule, standings, player game logs).
- AHL, OHL, WHL: HockeyTech feed lscluster.hockeytech.com with each league's public key (in update.py).
  2026-27 season ids: AHL 94, OHL 88, WHL 295.
- NCAA: College Hockey News pages (team schedule, each box score read once). Known schools:
  Boston-University/10, Michigan/31, Michigan-State/32, Denver/20; others need ids.chnTeam in follow.json.
  Exhibition games are shown but not counted. Ties show as T.
- World Juniors: Hockey Canada's tournament pages (built-in Next.js page data). They have every game and
  score, but player stats only for Canada's games (full box scores for both teams). Other games' stat
  lines come from wjc_lines.json. iihf.com, Elite Prospects and Flashscore were tested and ruled out:
  they refuse or don't allow automated access. Never work around a site's blocks or copy private headers.

## Claude sessions can't reach the data sites
This cloud environment's network blocks the hockey sites. To check a live source, add a temporary
probe script and a run-by-hand workflow that saves results to the repo, ask the owner to run it, then
read the results and delete the probe when done. Test code offline against saved samples.

## Scheduled Claude tasks (Sonnet, on the owner's account)
- "Prospect Watch news notes": Monday and Thursday 4:47 AM. Updates notes.json, moves players who change
  teams in follow.json, and from Dec 1 to Jan 12 sets "wjc" when national team rosters are announced.
  The owner created it in the routines form, so only they can edit it.
- "Prospect Watch WJC stat lines (Dec)" (Dec 26-31) and "(Jan)" (Jan 1-6), 4:47 AM: fill
  wjc_lines.json from data.json's wjc.missing list. Created by Claude; the owner attached the repository.

## Ideas list
- **Calendar feed (next):** one .ics file per tab (Canucks prospects, Other players, Teams), written by
  update.py next to data.json and subscribed to via webcal. Decided with the owner:
  - one event per game, 2.5 hours long; all-day if no time is set
  - titles like "Petes @ Oshawa · Novotný, Medvedev, Rogowski"; team calendar uses the matchup
  - after the game, the score goes in the title ("W 4–2 · ...") and stat lines in the notes
  - two followed teams playing each other: one event, not two
  - last 30 days plus the rest of the season; World Juniors games with followed players in the window
  - stable event ids so updates replace events; no alerts
  - a "Subscribe in your calendar" link at the bottom of each tab, with iPhone and Google steps
  - big enough to go as a pull request
- Draft details still missing for Cootes, Rogowski, Malhotra, Dervin and Medvedev (a "draft" block in
  follow.json).
- Option to count exhibition games (Romani shows 10 points in 7 games without MSU's Oct 2 exhibition).
- Check the World Juniors tab on Dec 1, its first run against this year's live Hockey Canada page.
