# Season mode

Two entry points: scheduled headless runs (`claude -p "Sleepy: <task>"` via cron) and on-demand conversation. Every scheduled run ends with a Discord post via `scripts/notify.sh` — a run that produces no post is a failed run (post "nothing actionable" if that's the finding). Resolve the current week from `/state/nfl`.

## Tuesday waiver report

1. For each managed league: fetch rosters, last week's `transactions`, and `/players/nfl/trending/add`.
2. Build a droppable-players list from the user's roster (strategy file defines untouchables).
3. Candidates = trending adds ∩ available in this league, plus injury-vacated roles (starter injured → grab the backup) even if not trending yet.
4. Web-search for context on top candidates (role change? injury fill-in? mirage?).
5. Recommend claims per league, each with: add, drop, and priority guidance.
   - **Waiver priority leagues** (`waiver_type` 0/1): is this worth burning priority position, or a free-agent add after waivers clear?
   - **FAAB leagues** (`waiver_type` 2): bid sizing as % of remaining budget, with a walk-away number. (Configurable behavior — active only when the league uses FAAB.)
6. Discord post: one section per league, claims in priority order, one-line reasoning each.

## Lineup checks (Thu pre-TNF, Sun pre-slate)

1. Fetch rosters + this week's matchups for each league.
2. Flag starters who are Out/Doubtful/Questionable or on bye (player dump `injury_status` + matchup context).
3. **Always web-search** late-breaking news for flagged players — Sleeper's status field lags beat reporters on game morning.
4. Recommend swaps with confidence levels. Sunday check also names the projected close matchups where lineup edges matter most.
5. Discord post only if action is needed (or a one-liner: "all lineups clean ✅").

## Trade evaluation (on demand)

When the user brings an offer: fetch both rosters, evaluate against (a) positional needs both ways, (b) the strategy file's goal (contending → win-now; ceiling league → upside), (c) schedule/playoff-week implications, (d) league notes (veto culture, payout structure). Give a verdict — accept / counter (with a specific counter) / decline — not a both-sides shrug.

## Weekly recap (optional Monday run)

Results, standings movement, next week's early flags (byes, injuries to monitor Wednesday). Keep it short; append notable advice-vs-outcome entries to `advice-log.md` — this file is the feedback loop for improving the strategy files and interrupt thresholds.

## Cron setup

Generate entries for the user (see `assets/crontab.example`), adjusting times to their timezone and confirming before they install. Logs append to `~/sleepy/logs/`. Remind the user these runs draw from their subscription usage pool.
