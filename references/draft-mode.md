# Draft mode (real and mock)

**The clock is the enemy, not the board.** Sleeper autopicks the moment the timer expires (60s in mocks, 60–90s in most real drafts), and CPU teams in mocks pick instantly — so the user is often *already on the clock* the first time you hear about a pick. Everything below is built to make the on-clock response take seconds, and to make a missed clock harmless.

## Preflight (before polling starts)

1. Load the league's `strategy/<slug>.md` and `notes/<slug>.md`. Missing strategy file → run onboarding first; missing notes on a keeper league → at minimum get keeper costs and expected keepers now.
2. `scripts/sleeper.sh /draft/<draft_id>` — confirm status, type, teams, rounds, `pick_timer`, and the user's slot. Auction → not supported (see sleeper-api.md). `reversal_round` set → warn and degrade gracefully.
3. Ensure `cache/players.json` is fresh (≤7 days); refresh if not.
4. If keepers exist, mark kept players as off-board before pick 1.
5. **Model check.** Live drafts need sustained multi-step reasoning under a clock; confirm the session is on Fable or Opus (`/model`). Sonnet has dropped the loop in a live mock — it works, but warn the user and lean harder on the Monitor (step 6) and queue instruction.
6. **Arm the watcher.** Draft mode is a background process that wakes you, never a loop you promise to keep running yourself:
   ```
   Monitor({
     command: "python3 <skill>/scripts/watch_draft.py <draft_id> --loop [--mock] --baseline",
     description: "Sleeper draft <draft_id> — picks / on-clock",
     persistent: true, timeout_ms: 3600000
   })
   ```
   Each stdout line is one short JSON event (new picks, status change, user on the clock, or `{"error":…}` after 3 failed fetches). Monitor notifications truncate at roughly 500 characters, so the line is a headline only: `new_picks` as `"74 Brian Thomas WR"` strings (`*` marks the user's own pick), the on-clock fields, and — when the board is attached — `roster`, `runs`, `top` (6 names) and `event_file`, the path of the full report (`~/sleepy/state/draft_<id>_last.json`). If the notification still looks cut off, or you need TE/K/DEF or more than 6 names, read `event_file` once — never `board.py`. `--baseline` emits the current state immediately so you can confirm the watcher is alive. The process exits by itself when the draft completes. If a Monitor is unavailable, fall back to calling `watch_draft.py <draft_id> [--mock]` (one-shot) in a chain — **and never end your turn while status is `drafting`**; end-of-turn with no watcher armed is how picks get missed.
7. **Mock timer.** If the user created the mock, suggest a 90–120s pick timer. The rehearsal is for the loop and the strategy, not for beating a 60s CPU sprint.
8. Confirm ready state in 2–3 lines: draft, slot, watcher armed (quote the baseline event's `total_picks_made`), plan headline — e.g. "Slot 4, watcher live at 0 picks, plan: best RB/WR through rd 3, QB in rd 5–6 if a top-tier one is there."

**Hands off the tooling once the draft is live.** Do not edit, rebuild, or re-test any Sleepy script while status is `drafting`. If something is broken, say so, use the one-shot fallback, and fix it after the draft or between mocks. (Lesson learned the hard way: six picks went to autopick in one mock while a poller was being written mid-draft.)

## The event handler

Every Monitor event (or one-shot result) is a JSON report. When `picks_until_user ≤ 3` or `on_clock` is true it already carries the board headline, and `event_file` holds the full board — roster, position counts, last 5, `position_runs`, top-N available with injury tags, and `by_position` (best 4 QB / 6 RB / 6 WR / 4 TE / 3 K / 3 DEF). **Do not call `board.py` separately**; one `cat` of `event_file` is the only extra round trip allowed on the clock (a rank-sorted top-N is all RB/WR/QB — `by_position` exists so TE/K/DEF never need a separate call).

React per the interrupt rules, then end the turn — the Monitor will wake you again:

- **`on_clock` true → one line, immediately.** You already posted the shortlist for this pick at the user's *previous* pick (see below). Confirm it: "Still #1: X — take him. (Y gone → Z is #2.)" Post to Discord with `notify.sh` in the same breath. Only re-rank if a listed player was taken or a strategy trigger changed.
- **`picks_until_user` ≤ 3 → ranked shortlist** (format below), Discord first, then terminal.
- **User just picked (their `pick_no` in `new_picks`) → pre-stage the *next* pick now.** Post a 3-deep shortlist for the user's next pick number ("At 46: QB A if there, else RB B, else WR C"). In mocks the next on-clock event can arrive within seconds; in real drafts this buys the user a full round of thinking time. This is the primary shortlist, not a courtesy. The event at the user's own pick has no board (they're 9 out), so pre-stage from the previous board plus what just went — don't wait for the ≤3 event. This includes the K/DEF rounds: the last two picks can land with no shortlist if you wait for a ≤3-out event that never comes — queue the DEF and K at the user's third-to-last pick.
- A strategy-file target/fade was just picked → one-line note ("Target WR sniped at 18 — pivot options: …").
- `position_runs` non-empty and it threatens the plan → short warning with the adjustment.
- A player falling ≥1.5 rounds past the strategy file's stated value → flag once.
- `{"error": …}` event → `scripts/notify.sh "⚠️ Sleepy: draft polling failing — check the terminal"` and tell the user what failed. The loop keeps retrying on its own.
- Otherwise: say nothing and end the turn. Silence is a feature *only* because the Monitor is armed.

If the user typed a question between events, answer with full board context.

**Injury gate:** never put an 🚑-tagged player (Out/IR/PUP/Doubtful) in a shortlist without the tag and a timeline; in starter rounds, don't recommend them unless the user opts in. ⚠️ Questionable in preseason is a note, not a veto.

## Shortlist format (≤3 picks out / on the clock / pre-staged next pick)

Keep it scannable — it is always mirrored to Discord and may be read on a phone. Post the same block in both places (`scripts/notify.sh` first, then the terminal). **Always end with the queue line** — Sleeper's autopick takes from the user's queue first, so a queued shortlist turns a missed clock into the right pick.

```
🕐 2 picks out (pick 27 next)
1. **Player A (RB, DAL)** — fills RB2, survives the run; strategy: "RB by 30" ✅
2. **Player B (WR, MIA)** — best value on board (ADP 19), but WR3 is a luxury here
3. **Player C (QB, BUF)** — the plan's QB anchor; safe to wait one more turn (2 QBs left in tier)
Risk: QB run active (3 in last 5). If A and C are both gone, take B.
📋 Queue A, B, C in Sleeper now.
```

Each option gets **one short line**: the reason, then a strategy tag — ✅ on plan ("rd 3–5 starters"), ⚠️ deviation + why ("QB a round early — top-6 QB fell"), 🚑/⚠️ injury if any. No paragraphs. Roster fit, scoring, and the strategy file inform the line but don't get restated. Example:

```
1. **RB A (RB, TEAM)** — best ceiling RB left ✅ completes elite RB+WR
2. **RB B (RB, TEAM)** — safer, but 32 and low-catch in PPR ⚠️ floor over ceiling
3. **WR C (WR, TEAM)** — zero-RB fallback ✅ allowed if RBs run
📋 Queue RB A, RB B, WR C now.
```

## Mock drafts

Same loop. Differences:

- Find the mock's draft_id via `/user/<user_id>/drafts/nfl/<season>` if the user doesn't have it handy.
- `league_id` may be null → use the draft's own settings; ask which real league to simulate and load that strategy/notes pair.
- Pass `--mock` to the watcher (5s polling; CPU picks are instant).
- Purpose is rehearsal: tooling validation (clock detection, no missed picks) *and* strategy stress-testing.
- **Debrief is mandatory** at mock end: what the board did vs. expectations, where the strategy held/broke, which interrupt rules fired correctly or wrongly, **which of the user's picks landed without a shortlist and why**, and proposed strategy-file edits (apply only with sign-off). Append a summary to `~/sleepy/advice-log.md`.

## Crash recovery

All draft state is reconstructable from the API — nothing is lost when a session dies. On "resume draft <draft_id>" (or if you detect a draft mid-flight during preflight):

1. Re-run preflight steps 1–2 and 6 (re-arm the Monitor; `--baseline` gives you the current state and board in one event).
2. Report position in one line ("Resumed at pick 41; you're up in 6; nothing critical missed / here's what changed: …") and pre-stage the next shortlist.

Rehearse this at least once before a real draft by killing the session mid-mock and resuming.

## After the draft

The watcher exits on `complete`. Post a Discord summary: final roster, grade against the strategy file, immediate waiver watchlist (undrafted players the strategy liked). Append to `advice-log.md`.
