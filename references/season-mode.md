# Season mode

Two entry points: scheduled headless runs (`scripts/scheduled_run.sh` via launchd or cron — see Scheduling below) and on-demand conversation. Every scheduled run ends with a Discord post via `scripts/notify.sh` — a run that produces no post is a failed run (post "nothing actionable" if that's the finding). Resolve the current week from `/state/nfl`.

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

## Scheduling

Every scheduled run goes through `scripts/scheduled_run.sh "<task>" <logname>`, never a bare `claude -p`. An unattended `claude -p` auto-denies every tool call, so the run ends with no Discord post and no error — exactly the silent failure this skill forbids. The wrapper sets PATH (launchd and cron start with almost none), runs `claude -p "Sleepy: <task>"` from `$SLEEPY_HOME` with permission prompts off, appends to `logs/<logname>.log`, and posts a Discord alert if claude exits non-zero. Turning prompts off is acceptable here because Sleepy only reads the public Sleeper API and writes to Discord and `~/sleepy/`.

- **macOS (default): launchd.** `assets/launchd/install.sh` renders the three plist templates for this machine and loads them; `--test` also fires a one-off smoke test that posts to Discord; `--uninstall` removes them. Schedules are local time (no DST drift). A job missed while the Mac was asleep runs at wake; one missed while it was shut down is skipped, so warn the user about Sunday mornings if the laptop may stay closed.
- **Linux: cron.** `assets/crontab.example`, adjusted to the user's timezone.

Before installing, confirm the times with the user and remind them the runs draw from their subscription usage pool. If they have Sleepy entries in an old crontab, remove them so runs don't double-post (`install.sh` warns about this).
