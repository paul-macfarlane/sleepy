# Draft mode (real and mock)

## Preflight (before polling starts)

1. Load the league's `strategy/<slug>.md` and `notes/<slug>.md`. Missing strategy file → run onboarding first; missing notes on a keeper league → at minimum get keeper costs and expected keepers now.
2. `scripts/sleeper.sh /draft/<draft_id>` — confirm status, type, teams, rounds, pick_timer, and the user's slot. Auction → not supported (see sleeper-api.md). `reversal_round` set → warn and degrade gracefully.
3. Ensure `cache/players.json` is fresh (≤7 days); refresh if not.
4. If keepers exist, mark kept players as off-board before pick 1.
5. Every shortlist (≤3 picks out / on the clock) is posted to Discord via `scripts/notify.sh` **and** shown in the terminal — always, whether the user is at the keyboard or away. Ask if they're stepping away only to know whether to expect replies in-terminal.
6. Confirm ready state to the user in 2–3 lines (draft, slot, plan headline, e.g. "Slot 7, anchor plan: QB at 27 — watching for early QB runs").

## The loop

Repeat until draft status is `complete`:

1. Run `scripts/watch_draft.py <draft_id>` — add `--mock` for mock drafts (CPU picks are instant; polls every 5s). Real drafts poll every 15s (60–90s clocks). (Blocks until new picks; prints JSON delta: new picks with names/positions/teams, current pick_no, `picks_until_user`, on_clock flag).
2. Update your working board: `scripts/board.py <draft_id> [N] [slot]` prints the user's roster, position counts, and the top-N available **with injury tags** — gone players, per-team roster needs, position run counters (a "run" = 3+ of a position in the last 5 picks).
   **Injury gate:** never put an 🚑-tagged player (Out/IR/PUP/Doubtful) in a shortlist without the tag and a timeline; in starter rounds, don't recommend them unless the user opts in. ⚠️ Questionable in preseason is a note, not a veto.
3. Decide whether to speak — **interrupt rules**:
   - `on_clock` true → full recommendation now, **plus a contingency plan for the user's next pick** ("at 46: X if there, else Y, else Z") so fast drafts (mocks with CPU picks land instantly) never leave the user waiting.
   - `picks_until_user` ≤ 3 → ranked shortlist (see format below).
   - A strategy-file target/fade was just picked → one-line note ("Puka sniped at 18 — pivot options: …").
   - Position run forming that threatens the plan → short warning with the adjustment.
   - A player falling ≥1.5 rounds past the strategy file's stated value → flag once.
   - Otherwise: print nothing. Silence is a feature.
4. If the user typed a question between polls, answer with full board context before resuming.

If `watch_draft.py` errors twice consecutively: `scripts/notify.sh "⚠️ Sleepy: draft polling broken — check the terminal"` and tell the user in-terminal what failed.

## Shortlist format (≤3 picks out / on the clock)

Keep it scannable — it is always mirrored to Discord and may be read on a phone. Post the same block in both places (`scripts/notify.sh` first, then the terminal):

```
🕐 2 picks out (pick 27 next)
1. **Player A (RB, DAL)** — fills RB2, survives the run; strategy: "RB by 30" ✅
2. **Player B (WR, MIA)** — best value on board (ADP 19), but WR3 is a luxury here
3. **Player C (QB, BUF)** — the plan's QB anchor; safe to wait one more turn (2 QBs left in tier)
Risk: QB run active (3 in last 5). If A and C are both gone, take B.
```

Each option gets **one short line**: the reason, then a strategy tag — ✅ on plan ("rd 3–5 starters"), ⚠️ deviation + why ("QB a round early — top-6 QB fell"), 🚑/⚠️ injury if any. No paragraphs. Roster fit, scoring, and the strategy file inform the line but don't get restated. Example:

```
1. **Jeanty (RB, LV)** — best ceiling RB left ✅ completes elite RB+WR
2. **Henry (RB, BAL)** — safer, but 32 and low-catch in PPR ⚠️ floor over ceiling
3. **A.J. Brown (WR, NE)** — zero-RB fallback ✅ allowed if RBs run
```

## Mock drafts

Same loop. Differences:

- Find the mock's draft_id via `/user/<user_id>/drafts/nfl/<season>` if the user doesn't have it handy.
- `league_id` may be null → use the draft's own settings; ask which real league to simulate and load that strategy/notes pair.
- Purpose is rehearsal: v1 validation (clock detection, no missed picks) *and* strategy stress-testing.
- **Debrief is mandatory** at mock end: what the board did vs. expectations, where the strategy held/broke, which interrupt rules fired correctly or wrongly, and proposed strategy-file edits (apply only with sign-off). Append a summary to `~/sleepy/advice-log.md`.

## Crash recovery

All draft state is reconstructable from the API — nothing is lost when a session dies. On "resume draft <draft_id>" (or if you detect a draft mid-flight during preflight):

1. Re-run preflight steps 1–2.
2. Fetch full `/draft/<draft_id>/picks`, rebuild the board from scratch.
3. Report position in one line ("Resumed at pick 41; you're up in 6; nothing critical missed / here's what changed: …") and re-enter the loop.

Rehearse this once per Phase 1 by killing the session mid-mock and resuming.

## After the draft

Post a Discord summary: final roster, grade against the strategy file, immediate waiver watchlist (undrafted players the strategy liked). Append to `advice-log.md`.
