#!/usr/bin/env python3
"""Print the draft board for a human: user's roster, position counts, last 5 picks,
position runs, the top-N available skill players with injury tags, and the best
few at every position (TE/K/DEF included — a rank-sorted top list hides them).

Usage: board.py DRAFT_ID [N] [SLOT] [--pos TE,K] [--max-age 25]

  --pos      only list these positions (comma-separated), N deep each
  --max-age  drop players older than this (rd 9+ keeper-swing scans)

Thin wrapper over watch_draft.build_board — the same data ships inside
watch_draft.py's JSON as "board" (and in ~/sleepy/state/draft_{id}_last.json)
whenever the user is within --near-picks, so during a draft you normally don't
need this at all. Handy for ad-hoc questions.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from watch_draft import (BY_POSITION_N, avail_entry, available, build_board, fetch,  # noqa: E402
                         load_config, load_players, user_slot)

ap = argparse.ArgumentParser()
ap.add_argument("draft_id")
ap.add_argument("n", nargs="?", type=int, default=40)
ap.add_argument("slot", nargs="?", type=int, default=0)
ap.add_argument("--pos", default="", help="comma-separated positions, e.g. TE,K,DEF")
ap.add_argument("--max-age", type=int, default=0)
a = ap.parse_args()

draft = fetch(f"/draft/{a.draft_id}")
picks = fetch(f"/draft/{a.draft_id}/picks") or []
slot = user_slot(draft, load_config(), a.draft_id, a.slot)
b = build_board(picks, slot, a.n)


def line(p):
    inj = p["injury"]
    tag = f"  {inj['tag']} {inj['status']}: {inj['body_part'] or '?'} {inj['notes'] or ''}".rstrip() if inj else ""
    who = f"{p['player']} ({p['team']}, {p['age']})" if p["age"] is not None else f"{p['player']} ({p['team']})"
    return f"{p['rank']:3d} {p['position']:3s} {who}{tag}"


def keep(p):
    if not a.max_age or p["position"] == "DEF":
        return True
    return p["age"] is not None and p["age"] <= a.max_age


print("MY ROSTER:", ", ".join(b["my_roster"]) or "(empty)")
print("MY COUNTS:", b["my_counts"])
print("LEAGUE COUNTS:", b["league_counts"])
print("LAST 5:", ", ".join(b["last_5"]))
if b["position_runs"]:
    print("RUN:", ", ".join(b["position_runs"]), "(3+ in last 5)")

if a.pos:
    gone = {p.get("player_id") for p in picks}
    for pos in [x.strip().upper() for x in a.pos.split(",") if x.strip()]:
        rows = [avail_entry(p) for p in available(load_players(), gone, (pos,))]
        rows = [p for p in rows if keep(p)][:a.n]
        print(f"\n{pos} AVAILABLE (top {len(rows)}):")
        for p in rows:
            print(line(p))
else:
    rows = [p for p in b["top_available"] if keep(p)]
    print(f"\nTOP {len(rows)} AVAILABLE{' (age ≤ ' + str(a.max_age) + ')' if a.max_age else ''}:")
    for p in rows:
        print(line(p))
    print("\nBEST BY POSITION:")
    for pos, rows in b["by_position"].items():
        rows = [p for p in rows if keep(p)]
        if rows:
            print(f"  {pos}: " + " | ".join(
                (f"{p['player']} ({p['team']}, {p['age']})" if p["age"] is not None else f"{p['player']} ({p['team']})")
                + (" " + p["injury"]["tag"] if p["injury"] else "") for p in rows))

if not b["players_cache_loaded"]:
    print("⚠️ ~/sleepy/cache/players.json missing — run scripts/cache_players.sh", file=sys.stderr)
