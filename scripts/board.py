#!/usr/bin/env python3
"""Print the draft board for a human: user's roster, position counts, last 5 picks,
position runs, and the top-N available skill players with injury tags.

Usage: board.py DRAFT_ID [N] [SLOT]

Thin wrapper over watch_draft.build_board — the same data ships inside
watch_draft.py's JSON as "board" whenever the user is within --near-picks, so
during a draft you normally don't need this at all. Handy for ad-hoc questions.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from watch_draft import build_board, fetch, load_config, user_slot  # noqa: E402

did = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
cli_slot = int(sys.argv[3]) if len(sys.argv) > 3 else 0

draft = fetch(f"/draft/{did}")
picks = fetch(f"/draft/{did}/picks") or []
slot = user_slot(draft, load_config(), did, cli_slot)
b = build_board(picks, slot, n)

print("MY ROSTER:", ", ".join(b["my_roster"]) or "(empty)")
print("MY COUNTS:", b["my_counts"])
print("LEAGUE COUNTS:", b["league_counts"])
print("LAST 5:", ", ".join(b["last_5"]))
if b["position_runs"]:
    print("RUN:", ", ".join(b["position_runs"]), "(3+ in last 5)")
print(f"TOP {n} AVAILABLE:")
for p in b["top_available"]:
    inj = p["injury"]
    tag = f"  {inj['tag']} {inj['status']}: {inj['body_part'] or '?'} {inj['notes'] or ''}".rstrip() if inj else ""
    print(f"{p['rank']:3d} {p['position']:2s} {p['player']} ({p['team']}, {p['age']}){tag}")
if not b["players_cache_loaded"]:
    print("⚠️ ~/sleepy/cache/players.json missing — run scripts/cache_players.sh", file=sys.stderr)
