# Sleepy 😴🏈

A Sleeper fantasy football assistant that runs as a skill in [Claude Code](https://claude.com/claude-code) or [OpenAI Codex](https://developers.openai.com/codex/cli). Live draft advice (real drafts and mocks), waiver and lineup analysis on a schedule, and strategy coaching — with proactive alerts to your Discord.

No backend, no API keys, no hosting. Your data never leaves your machine (except the messages Sleepy posts to *your* Discord webhook).

## Prerequisites

- Claude Code or OpenAI Codex, installed and signed in (Sleepy's brain)
- `jq`, `python3`, `curl`
- A Sleeper account, and a Discord server you control (for a webhook)

## Install

Install Sleepy into your agent's skill directory:

```bash
# Claude Code
git clone https://github.com/paul-macfarlane/sleepy.git ~/.claude/skills/sleepy

# OpenAI Codex
git clone https://github.com/paul-macfarlane/sleepy.git ~/.codex/skills/sleepy
```

Then in your agent:

```
> Sleepy: onboard me
```

Onboarding resolves your Sleeper user ID, discovers your leagues, sets up your Discord webhook, interviews you about strategy per league, and asks about rules the Sleeper API can't see (keeper formulas, payouts, house rules). Everything it learns is stored in `~/sleepy/` — never in the skill folder.

## Use

**Start every session from `~/sleepy`:**

```bash
cd ~/sleepy
claude  # or: codex
```

That's where your config, strategy files, and draft state live, so anything Sleepy reads or writes lands in the right place, and the agent's per-project context and permissions accumulate in one spot. Don't launch from the installed skill folder (or a development clone): the skill's own rule is never to change its tooling during a live draft, and keeping the source out of the working directory makes that the default. If you develop Sleepy, keep a separate clone for that and update the installed skill after merging.

**Test on a mock first:** join a Sleeper mock draft, then:

```
> Sleepy: mock draft mode, simulate <league name>
```

**Draft day:**

```
> Sleepy: draft mode for <league name>. I'm at the keyboard.
```

Draft mode arms `watch_draft.py` with the agent's persistent background-command facility when one is available, so Sleepy is woken by picks rather than polling by hand. If the agent cannot surface background output after a turn ends, Sleepy uses the script's one-shot mode and keeps the session active while the draft is live. Use a strong reasoning model for live drafts; keeping a time-sensitive tool loop alive is more demanding than ordinary chat. Say "stepping away" to route on-the-clock alerts to Discord. If the session dies, `Sleepy: resume draft <draft_id>` rebuilds everything from the API.

**Season:** schedule Tuesday waiver reports and Thursday/Sunday lineup checks, each posting a summary to Discord. On a Mac:

```bash
# Use the path where you installed the skill:
~/.claude/skills/sleepy/assets/launchd/install.sh --test
# or ~/.codex/skills/sleepy/assets/launchd/install.sh --test
```

That loads three launchd agents (local time, so no daylight-saving drift) and fires a smoke test that should land in your Discord within a minute or two. Edit the plist templates in `assets/launchd/` to change times and re-run the installer; `--uninstall` removes them. On Linux, use `assets/crontab.example`. Both paths go through `scripts/scheduled_run.sh`, which delegates provider-specific CLI flags to `scripts/run_agent.sh` and posts a Discord alert if a run crashes. A run missed while the Mac was asleep fires when it wakes; one missed while it was shut down is skipped.

The default provider is `auto`, preferring Claude when both CLIs are installed to preserve existing setups. To select Codex, add this to `~/sleepy/config.json` (see `assets/config.template.json`):

```json
"agent": { "provider": "codex", "model": "" }
```

Environment variables override config: `SLEEPY_AGENT=claude|codex|auto`, `SLEEPY_AGENT_MODEL=<model>`, and `SLEEPY_AGENT_RUNNER=/path/to/adapter`. A custom adapter receives the complete prompt as its only argument, which lets other agents plug in without changing Sleepy.

Or just open a session and ask about trades, start/sits, anything.

## Etiquette & limits

- Sleeper's API is public and unofficial: Sleepy polls every 15s during a live draft (5s for CPU mocks, which pick instantly, and 5s whenever you are within 3 picks of the clock) and 30s while idle — far under the platform limit. Be a good citizen.
- Draft sessions and scheduled runs draw from the selected agent's subscription or API usage. Draft day is the heavy session — budget for it.
- Not supported: auction drafts, third-round-reversal snake math (Sleepy warns and degrades gracefully). English-language NFL leagues only.

## Privacy

`~/sleepy/` contains your strategy, league notes, and Discord webhook URL. The webhook is a secret — anyone with it can post to your channel. Keep it out of version control.

## Changelog

- **v0.5** (unreleased) — Added OpenAI Codex support and a provider-neutral agent runner. Scheduled jobs now select Claude, Codex, or a custom adapter without changing season logic; live-draft instructions use capabilities rather than Claude-specific tool names.
- **v0.4** (2026-09-02) — Scheduled runs that actually run: `scripts/scheduled_run.sh` wraps the headless `claude -p` call with the permission bypass it needs unattended (the old crontab example silently denied every tool call and never posted), fixes PATH, and posts a Discord alert on crash. launchd is the macOS default (`assets/launchd/install.sh`, with `--test` smoke test and `--uninstall`); cron example rewritten for Linux. Mock drafts poll at 5s even before the draft starts, and shortlists pre-stage both picks of a snake turn.
- **v0.3** (2026-08-30) — Team defenses are now ranked (Sleeper's player dump has no DEF rank, so the board previously listed them alphabetically as "rank 0"): order comes from `~/sleepy/def_ranks.json` if present, else `assets/def_ranks.json`; onboarding and draft preflight tell you to reorder it.
- **v0.2** (2026-08-28) — Monitor-driven draft watcher (`watch_draft.py --loop`) with compact per-event lines and a full-report event file; by-position board incl. TE/K/DEF; pre-staged shortlists and queue instruction; docs stripped of user-specific data.
- **v0.1** (2026-08-24) — Initial release: onboarding, draft/mock mode, season-mode cron tasks, Discord notifications.

## License

MIT
