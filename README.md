# Sleepy 😴🏈

A Sleeper fantasy football assistant that runs as a [Claude Code](https://claude.com/claude-code) skill on your own Claude subscription. Live draft advice (real drafts and mocks), waiver and lineup analysis on a schedule, and strategy coaching — with proactive alerts to your Discord.

No backend, no API keys, no hosting. Your data never leaves your machine (except the messages Sleepy posts to *your* Discord webhook).

## Prerequisites

- Claude Code with a Claude Pro/Max subscription (Sleepy's brain)
- `jq`, `python3`, `curl`
- A Sleeper account, and a Discord server you control (for a webhook)

## Install

```bash
git clone https://github.com/paul-macfarlane/sleepy.git ~/.claude/skills/sleepy
```

Then in Claude Code:

```
> Sleepy: onboard me
```

Onboarding resolves your Sleeper user ID, discovers your leagues, sets up your Discord webhook, interviews you about strategy per league, and asks about rules the Sleeper API can't see (keeper formulas, payouts, house rules). Everything it learns is stored in `~/sleepy/` — never in the skill folder.

## Use

**Start every session from `~/sleepy`:**

```bash
cd ~/sleepy && claude
```

That's where your config, strategy files, and draft state live, so anything Sleepy reads or writes lands in the right place, and Claude Code's per-project memory and permission settings accumulate in one spot. Don't launch from the skill folder itself (`~/.claude/skills/sleepy`, or a dev clone of this repo): the skill's own rule is never to change its tooling during a live draft, and keeping the source out of the working directory makes that the default. If you develop Sleepy, keep a separate clone for that and update the installed skill with `git -C ~/.claude/skills/sleepy pull` after merging.

**Test on a mock first:** join a Sleeper mock draft, then:

```
> Sleepy: mock draft mode, simulate <league name>
```

**Draft day:**

```
> Sleepy: draft mode for <league name>. I'm at the keyboard.
```

Draft mode arms a background watcher through Claude Code's `Monitor` tool, so Sleepy is woken by picks rather than polling by hand. Use a top-tier model (Fable/Opus via `/model`) for live drafts — smaller models have dropped the loop under a clock. Say "stepping away" to route on-the-clock alerts to Discord. If the session dies, `Sleepy: resume draft <draft_id>` rebuilds everything from the API.

**Season:** schedule Tuesday waiver reports and Thursday/Sunday lineup checks, each posting a summary to Discord. On a Mac:

```bash
~/.claude/skills/sleepy/assets/launchd/install.sh --test
```

That loads three launchd agents (local time, so no daylight-saving drift) and fires a smoke test that should land in your Discord within a minute or two. Edit the plist templates in `assets/launchd/` to change times and re-run the installer; `--uninstall` removes them. On Linux, use `assets/crontab.example`. Both paths go through `scripts/scheduled_run.sh`, which runs Claude headless with permission prompts off — a bare `claude -p` silently denies every tool call when nobody is there to approve it — and posts a Discord alert if a run crashes. A run missed while the Mac was asleep fires when it wakes; one missed while it was shut down is skipped.

Or just open a session and ask about trades, start/sits, anything.

## Etiquette & limits

- Sleeper's API is public and unofficial: Sleepy polls every 15s during a live draft (5s for CPU mocks, which pick instantly, and 5s whenever you are within 3 picks of the clock) and 30s while idle — far under the platform limit. Be a good citizen.
- Draft sessions and scheduled runs draw from your Claude subscription usage. Draft day is the heavy session — budget for it.
- Not supported: auction drafts, third-round-reversal snake math (Sleepy warns and degrades gracefully). English-language NFL leagues only.

## Privacy

`~/sleepy/` contains your strategy, league notes, and Discord webhook URL. The webhook is a secret — anyone with it can post to your channel. Keep it out of version control.

## Changelog

- **v0.4** (2026-09-02) — Scheduled runs that actually run: `scripts/scheduled_run.sh` wraps the headless `claude -p` call with the permission bypass it needs unattended (the old crontab example silently denied every tool call and never posted), fixes PATH, and posts a Discord alert on crash. launchd is the macOS default (`assets/launchd/install.sh`, with `--test` smoke test and `--uninstall`); cron example rewritten for Linux. Mock drafts poll at 5s even before the draft starts, and shortlists pre-stage both picks of a snake turn.
- **v0.3** (2026-08-30) — Team defenses are now ranked (Sleeper's player dump has no DEF rank, so the board previously listed them alphabetically as "rank 0"): order comes from `~/sleepy/def_ranks.json` if present, else `assets/def_ranks.json`; onboarding and draft preflight tell you to reorder it.
- **v0.2** (2026-08-28) — Monitor-driven draft watcher (`watch_draft.py --loop`) with compact per-event lines and a full-report event file; by-position board incl. TE/K/DEF; pre-staged shortlists and queue instruction; docs stripped of user-specific data.
- **v0.1** (2026-08-24) — Initial release: onboarding, draft/mock mode, season-mode cron tasks, Discord notifications.

## License

MIT
