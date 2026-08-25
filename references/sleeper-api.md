# Sleeper API reference

Base URL: `https://api.sleeper.app/v1`. Public, read-only, no auth, JSON. Be polite: 15s between polls during a live draft (5s for CPU mocks), 30s while idle; the hard platform limit is ~1000/min, so even 5s polling (2 req/poll = 24 req/min) is far under it. Official docs: https://docs.sleeper.com

## Endpoints Sleepy uses

| Endpoint | Returns | Notes |
|---|---|---|
| `/user/<username>` | user object | `.user_id` is the canonical ID used everywhere else |
| `/user/<user_id>/leagues/nfl/<season>` | league list | onboarding: discover the user's leagues |
| `/league/<league_id>` | league object | `.scoring_settings`, `.roster_positions`, `.settings` (waiver_type: 0=none/rolling, 1=reversed record, 2=FAAB; `waiver_budget` when FAAB) |
| `/league/<league_id>/rosters` | roster list | `.owner_id`, `.players`, `.starters` |
| `/league/<league_id>/users` | user list | map owner_id → display_name |
| `/league/<league_id>/matchups/<week>` | matchup list | pair by `.matchup_id`; `.points` |
| `/league/<league_id>/transactions/<week>` | transaction list | waivers/adds/drops/trades; `.type`, `.adds`, `.drops`, `.settings.waiver_bid` for FAAB |
| `/league/<league_id>/drafts` | drafts for league | most recent first |
| `/user/<user_id>/drafts/nfl/<season>` | drafts for user | includes mocks, which may have `league_id: null` |
| `/draft/<draft_id>` | draft object | see below |
| `/draft/<draft_id>/picks` | picks so far | `.pick_no`, `.round`, `.player_id`, `.picked_by`, `.metadata` (name/position/team) |
| `/players/nfl` | full player dict (~5MB) | keyed by player_id; cache via `scripts/cache_players.sh`, refresh weekly |
| `/players/nfl/trending/add?lookback_hours=24&limit=25` | trending pickups | waiver radar; also `/trending/drop` |
| `/state/nfl` | season state | `.week`, `.season` — use to resolve "this week" |

## Draft object essentials

- `.status`: `pre_draft` → `drafting` → `complete` (also `paused`)
- `.type`: `snake` | `linear` | `auction`
- `.settings.teams`, `.settings.rounds`, `.settings.pick_timer` (seconds)
- `.draft_order`: map of user_id → slot (1-indexed). May be null pre-draft or in some mocks — then ask the user their slot.
- `.slot_to_roster_id`: map slot → roster
- `.league_id`: null for unattached mocks — fall back to `.metadata.scoring_type` and the simulated league's strategy file.

## Snake pick math

For slot `s`, `teams` t, round `r` (1-indexed):

- odd `r`: `pick_no = (r-1)*t + s`
- even `r`: `pick_no = (r-1)*t + (t - s + 1)`

Picks until on the clock = (user's next pick_no) − (current picks made) − 1. `scripts/watch_draft.py` implements this; trust its output rather than recomputing. Limitation: third-round-reversal drafts aren't handled — if `.settings.reversal_round` is set and nonzero, warn the user and track proximity manually from the picks feed.

## Auction drafts

Not supported in v1. If `.type == "auction"`, say so and offer conversational advice without the polling loop.

## Player dump tips

`cache/players.json` is keyed by player_id. Useful fields: `full_name`, `position`, `team`, `age`, `injury_status`, `years_exp`, `depth_chart_order`. Don't load the whole file into context — grep/jq for the players you need:

```bash
jq -r '.["4046"] | "\(.full_name) \(.position) \(.team) \(.injury_status)"' ~/sleepy/cache/players.json
```

Sleeper's own player status can lag beat reporters on game day — season-mode lineup checks must supplement with a web search for late-breaking injury news.
