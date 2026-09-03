# Onboarding: config, strategy interview, league intake

Run this when the user asks to onboard, when `~/sleepy/config.json` is missing, or when advice is requested for a league that has no strategy file. Onboarding is conversational — a structured interview, not a form. Ask in small batches (2–3 questions), reflect answers back, and push back where answers conflict with the league's actual settings.

## 1. Config bootstrap

1. Create `~/sleepy/` with subdirs `strategy/ notes/ cache/ state/ logs/`.
2. Ask for the user's Sleeper username; resolve `.user_id` via `/user/<username>`.
3. Ask for (or create) a Discord webhook URL; store in config; send a test message via `scripts/notify.sh "Sleepy is connected ✅"` and confirm the user received it. If they don't have one: Discord → their private server → channel settings → Integrations → Webhooks → New Webhook → copy URL.
4. Discover leagues via `/user/<user_id>/leagues/nfl/<season>`; confirm which to manage; for each, find its draft via `/league/<league_id>/drafts` and record league_id, draft_id, slot (from `.draft_order` once posted), a short slug for filenames.
5. Write `~/sleepy/config.json` per `assets/config.template.json`.
6. Run `scripts/cache_players.sh`.
7. Copy `assets/def_ranks.json` to `~/sleepy/def_ranks.json` and ask the user to reorder it (or do it from their rankings doc) — Sleeper has no DEF rankings, so this list is the only thing ordering team defenses on the draft board.

## 2. Per-league strategy interview → `strategy/<slug>.md`

Cover, adapting to what the league's settings make relevant:

- **Goal**: championship-or-bust vs. consistent contender vs. fun. Winner-take-all payouts push ceiling over floor — check `notes/` or ask about payouts here.
- **Roster philosophy**: when they want QB/TE (streamers vs. elite), RB/WR balance, zero-RB tolerance, handcuff appetite.
- **Targets / fades / never-drafts**: named players with the rounds they'd pay. Record ADP context so "fell past value" alerts work.
- **Risk profile**: injury discounts, rookies, aging vets, bye-week stacking tolerance.
- **Existing materials**: if the user has a rankings/notes doc, ingest it and cite it as the source of specific calls.
- **Platform calibration**: note any known biases the user believes in (e.g., default rankings pushing certain positions early) — these shape run-detection thresholds.

**Push back** when the plan and the league disagree. Examples: late-round QB in a league whose scoring settings juice QBs; floor-heavy plan in a winner-take-all league; ignoring keepers in a keeper league. Name the tension, propose a resolution, let the user decide. Write down the *resolved* plan.

End by reading the finished file back in summary and getting explicit sign-off. Strategy files are living documents — mock-draft debriefs and in-season results propose edits, the user approves them.

## 3. Per-league context intake → `notes/<slug>.md`

Capture what the API can't provide:

- **Keeper rules**: cost formula, escalators, caps/limits, deadlines — and this year's expected keepers (which removes players from the draftable pool; encode them).
- **Money**: entry, payout split, weekly side pots (weekly high score changes optimal lineup risk).
- **House rules**: trade veto process, waiver customs beyond settings, IR/taxi conventions, punishment stakes (a last-place punishment changes late-season decisions).
- **League-mate intel**: who autodrafts, who reaches for a favorite team, who hoards a position, who's inactive on waivers. Display names only; keep it factual and non-personal.

Don't demand completeness upfront. Capture what the user knows now; when a missing rule becomes decision-relevant later ("keeper costs matter for this pick and I don't have the formula"), ask then and append the answer.

## 4. Wrap-up

Tell the user to start future sessions from `~/sleepy` (`cd ~/sleepy && claude`): that keeps Sleepy's reads and writes, Claude Code's per-project memory, and any permission rules in one place, and keeps the skill's source out of the working directory. If the current session was launched from the skill folder or a clone of the repo, say so and suggest switching. Then point them at a mock draft as the first real test (`references/draft-mode.md`).

## File format

Both file types start with YAML frontmatter (`league_id`, `slug`, `updated`) then freeform markdown with `##` sections matching the interview topics. Keep them concise enough to load whole into context during a draft.
