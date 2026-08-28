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

**Test on a mock first:** join a Sleeper mock draft, then:

```
> Sleepy: mock draft mode, simulate <league name>
```

**Draft day:**

```
> Sleepy: draft mode for <league name>. I'm at the keyboard.
```

Draft mode arms a background watcher through Claude Code's `Monitor` tool, so Sleepy is woken by picks rather than polling by hand. Use a top-tier model (Fable/Opus via `/model`) for live drafts — smaller models have dropped the loop under a clock. Say "stepping away" to route on-the-clock alerts to Discord. If the session dies, `Sleepy: resume draft <draft_id>` rebuilds everything from the API.

**Season:** install the cron entries (Sleepy will generate them — see `assets/crontab.example`) for Tuesday waiver reports and Thursday/Sunday lineup checks, each posting a summary to Discord. Or just open a session and ask about trades, start/sits, anything.

## Etiquette & limits

- Sleeper's API is public and unofficial: Sleepy polls every 15s during a live draft (5s for CPU mocks, which pick instantly, and 5s whenever you are within 3 picks of the clock) and 30s while idle — far under the platform limit. Be a good citizen.
- Draft sessions and cron runs draw from your Claude subscription usage. Draft day is the heavy session — budget for it.
- Not supported: auction drafts, third-round-reversal snake math (Sleepy warns and degrades gracefully). English-language NFL leagues only.

## Privacy

`~/sleepy/` contains your strategy, league notes, and Discord webhook URL. The webhook is a secret — anyone with it can post to your channel. Keep it out of version control.

## Changelog

- **v0.2** (2026-08-28) — Monitor-driven draft watcher (`watch_draft.py --loop`) with compact per-event lines and a full-report event file; by-position board incl. TE/K/DEF; pre-staged shortlists and queue instruction; docs stripped of user-specific data.
- **v0.1** (2026-08-24) — Initial release: onboarding, draft/mock mode, season-mode cron tasks, Discord notifications.

## License

MIT
