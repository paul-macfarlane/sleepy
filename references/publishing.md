# Publishing checklist

Sleepy is designed to be shared: every user runs it under their own Claude account, so there is no shared backend, no API key, and no terms problem. Before publishing:

1. **No personal data in the skill.** The skill directory must contain zero user specifics — no league IDs, no strategy content, no webhook URLs, no league-mate names. All of that lives in `~/sleepy/`. Grep the skill dir for the author's username, league names, and `discord.com/api/webhooks` before every release.
2. **Assumptions are config, not constants.** Waiver type (priority vs. FAAB), keeper vs. redraft, roster shapes (superflex, 2QB), scoring variants — all behavior must key off the league object and `~/sleepy/` files, never hardcoded expectations.
3. **README** covers: prerequisites (Claude Code subscription, `jq`, `python3`, a Discord server they control), install (clone into `~/.claude/skills/sleepy/`), first-run onboarding, the draft-day and cron workflows, Sleeper API etiquette (15s live / 5s mock / 30s idle polling), usage-limit expectations, and the privacy note (all data stays on the user's machine; the Discord webhook is a secret).
4. **Known limitations stated**: no auction drafts, no third-round-reversal math, English-language NFL only.
5. **Versioned releases.** Tag releases; changelog in README. Users' `~/sleepy/` data must survive skill upgrades (never store data in the skill dir — same rule as #1).
6. **License**: pick a permissive license (MIT) so league-mates can fork.

Distribution: GitHub repo installable by clone, and/or packaged `.skill` file, and/or a skills marketplace listing once available.
