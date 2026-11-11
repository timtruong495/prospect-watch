# Prospect Watch

Schedules, scores and stats for Vancouver Canucks prospects, other players worth following,
and the Canucks, Abbotsford Canucks and Vancouver Giants. All times are Vancouver time.

## How it works

- `index.html` is the page. It reads `data.json`.
- `update.py` runs on a schedule (see `.github/workflows/update.yml`), pulls the latest
  schedules, scores and stats from the NHL, AHL, OHL and WHL data feeds, and rewrites `data.json`.
- `follow.json` is the list of players and teams to follow. This is the only file you edit by hand.

College (NCAA) players are not updated by the script yet. Their numbers stay as they were
when last entered.

## Add or remove a player

Open `follow.json`, click the pencil icon, and copy an existing player block inside `"players"`.
Change these fields:

- `key`: any short unique id, for example `p-smith`
- `name`: the player's name as the league spells it
- `list`: `canucks` for a Canucks prospect, `other` for anyone else
- `pos`: C, LW, RW, D or G
- `league`: NHL, AHL, OHL or WHL
- `team`: the full team name, for example `Kelowna Rockets`
- `teamKey`: a short id for the team, the same for every player on that team
- `tags`: optional labels, for example `["2027 draft"]`

Save with "Commit changes". The next scheduled update finds the player on the team's roster
and fills in the schedule and stats. To remove a player, delete their block.

## Run an update right now

Go to the Actions tab, choose "Update data", and click "Run workflow".
