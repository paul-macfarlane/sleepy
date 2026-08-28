#!/usr/bin/env python3
"""Watch a Sleeper draft and report state changes as JSON.

Usage:
    watch_draft.py DRAFT_ID [--loop] [--mock] [--slot N] [--near-picks 3] [--board]
                            [--interval 15] [--timeout 900] [--baseline] [--top 15]

Two modes:

  One-shot (default): block until the draft's state changes, print one JSON
  report (pretty), exit. State persists in ~/sleepy/state/draft_{id}.json so
  each call reports only genuinely new picks.

  --loop: never exit while the draft is live. Print one compact JSON line per
  change (new picks / status change / user comes on the clock) and flush, so
  a Monitor can turn each line into a wake-up. Exits 0 when the draft
  completes. Fetch failures are reported as {"error": ...} lines after 3
  consecutive misses and polling continues — the loop never dies silently.

Board: whenever the user is within --near-picks of the clock (or on it), or
--board is passed, the report includes "board": the user's roster, position
counts league-wide, the last 5 picks, position-run flags, and the top --top
available skill players with injury tags. One call, one round trip, no need
to run board.py separately.

Polling: 15s (floor 10) while live in a real draft; 5s with --mock (CPU picks
land instantly); 5s whenever the user is within --near-picks; 30s while
pre_draft or paused. --baseline prints the current state immediately.

The user's slot comes from --slot, else config.json leagues[] matching this
draft_id, else the draft's draft_order + config user_id.
"""
import argparse, json, os, sys, time, urllib.request
from collections import Counter

# macOS python.org builds ship without root certs; fall back to certifi if present.
if not os.environ.get("SSL_CERT_FILE"):
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass

BASE = "https://api.sleeper.app/v1"
SLEEPY_HOME = os.environ.get("SLEEPY_HOME", os.path.expanduser("~/sleepy"))
SKILL_POS = ("QB", "RB", "WR", "TE")
HARD_INJURY = ("Out", "IR", "PUP", "Doubtful", "NA", "Sus")


def fetch(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "sleepy-skill"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def load_config():
    try:
        with open(os.path.join(SLEEPY_HOME, "config.json")) as f:
            return json.load(f)
    except OSError:
        return {}


_players = None


def load_players():
    global _players
    if _players is None:
        try:
            with open(os.path.join(SLEEPY_HOME, "cache", "players.json")) as f:
                _players = json.load(f)
        except OSError:
            _players = {}
    return _players


def user_slot(draft, cfg, draft_id, cli_slot):
    if cli_slot:
        return cli_slot
    for lg in cfg.get("leagues", []):
        if str(lg.get("draft_id")) == str(draft_id) and lg.get("slot"):
            return int(lg["slot"])
    order = draft.get("draft_order") or {}
    uid = str(cfg.get("user_id", ""))
    if uid and uid in order:
        return int(order[uid])
    return None


def next_user_pick(pick_count, slot, teams, rounds, reversal_round=0):
    """Smallest user pick_no > pick_count. Snake math; None if slot unknown/exhausted."""
    if not slot:
        return None
    for r in range(1, rounds + 1):
        if reversal_round and r >= reversal_round:
            return None  # 3RR not supported — caller must warn
        pos = slot if r % 2 == 1 else teams - slot + 1
        pick_no = (r - 1) * teams + pos
        if pick_no > pick_count:
            return pick_no
    return None


def short_name(first, last):
    """'J. Williams' — surname alone is ambiguous on a phone (two RB Williams in mock #5)."""
    first = (first or "").strip()
    last = (last or "").strip()
    return f"{first[0]}. {last}" if first and last else (last or first)


def summarize_pick(p):
    md = p.get("metadata") or {}
    return {
        "pick_no": p.get("pick_no"),
        "round": p.get("round"),
        "player": " ".join(x for x in (md.get("first_name"), md.get("last_name")) if x),
        "position": md.get("position"),
        "team": md.get("team"),
        "picked_by": p.get("picked_by"),
    }


def injury(p):
    st = p.get("injury_status")
    if not st:
        return None
    return {
        "tag": "🚑" if st in HARD_INJURY else "⚠️",
        "status": st,
        "body_part": p.get("injury_body_part"),
        "notes": p.get("injury_notes") or None,
    }


def build_board(picks, slot, top_n):
    """Roster / counts / runs / top-N available — the same data board.py prints, as JSON."""
    players = load_players()
    gone = {p.get("player_id") for p in picks}
    mine = [p for p in picks if p.get("draft_slot") == slot]

    def label(p):
        md = p.get("metadata") or {}
        name = md.get("last_name") if md.get("position") == "DEF" else short_name(md.get("first_name"), md.get("last_name"))
        return f"{md.get('position')} {name}"

    last5 = picks[-5:]
    run_counts = Counter((p.get("metadata") or {}).get("position") for p in last5)
    runs = sorted(pos for pos, c in run_counts.items() if pos and c >= 3)

    avail = [
        p for p in players.values()
        if p.get("active") and p.get("search_rank") and p["search_rank"] < 9999
        and p.get("position") in SKILL_POS and p.get("team") and p.get("player_id") not in gone
    ]
    avail.sort(key=lambda p: p["search_rank"])
    top = [
        {
            "rank": p["search_rank"],
            "player": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "position": p["position"],
            "team": p["team"],
            "age": p.get("age"),
            "injury": injury(p),
        }
        for p in avail[:top_n]
    ]
    return {
        "my_roster": [label(p) for p in mine],
        "my_counts": dict(Counter((p.get("metadata") or {}).get("position") for p in mine)),
        "league_counts": dict(Counter((p.get("metadata") or {}).get("position") for p in picks)),
        "last_5": [label(p) for p in last5],
        "position_runs": runs,  # 3+ of a position in the last 5 picks
        "top_available": top,
        "players_cache_loaded": bool(players),
    }


def report(draft, picks, prev_count, slot, near_picks, want_board, top_n):
    teams = int(draft.get("settings", {}).get("teams") or 0)
    rounds = int(draft.get("settings", {}).get("rounds") or 0)
    reversal = int(draft.get("settings", {}).get("reversal_round") or 0)
    count = len(picks)
    nxt = next_user_pick(count, slot, teams, rounds, reversal) if teams else None
    picks_until = (nxt - count - 1) if nxt else None
    on_clock = picks_until == 0 if picks_until is not None else False
    rep = {
        "status": draft.get("status"),
        "type": draft.get("type"),
        "teams": teams,
        "rounds": rounds,
        "pick_timer": draft.get("settings", {}).get("pick_timer"),
        "reversal_round_unsupported": bool(reversal),
        "total_picks_made": count,
        "new_picks": [summarize_pick(p) for p in picks[prev_count:]],
        "user_slot": slot,
        "user_next_pick_no": nxt,
        "picks_until_user": picks_until,
        "on_clock": on_clock,
        "draft_complete": draft.get("status") == "complete",
    }
    near = picks_until is not None and picks_until <= near_picks
    if want_board or (near and draft.get("status") == "drafting"):
        rep["board"] = build_board(picks, slot, top_n)
    return rep


def emit(rep, compact):
    print(json.dumps(rep, separators=(",", ":")) if compact else json.dumps(rep, indent=2))
    sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft_id")
    ap.add_argument("--loop", action="store_true",
                    help="never exit while live; one compact JSON line per change (for Monitor)")
    ap.add_argument("--interval", type=int, default=15,
                    help="poll interval (s) while the draft is live; floor 10")
    ap.add_argument("--mock", action="store_true",
                    help="mock draft with instant CPU picks: poll every 5s while live")
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=900, help="one-shot mode only")
    ap.add_argument("--baseline", action="store_true",
                    help="print current state immediately and exit")
    ap.add_argument("--board", action="store_true",
                    help="always include the board (default: only within --near-picks)")
    ap.add_argument("--top", type=int, default=15, help="board size")
    ap.add_argument("--fast-interval", type=int, default=5,
                    help="poll interval (s) when within --near-picks of the user's pick")
    ap.add_argument("--near-picks", type=int, default=3)
    a = ap.parse_args()
    interval = 5 if a.mock else max(10, a.interval)
    fast = max(5, a.fast_interval)
    IDLE_INTERVAL = 30  # pre_draft / paused: nothing moves fast, be polite

    cfg = load_config()
    state_dir = os.path.join(SLEEPY_HOME, "state")
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, f"draft_{a.draft_id}.json")
    try:
        with open(state_path) as f:
            prev = json.load(f)
    except OSError:
        prev = {"pick_count": 0, "status": None, "on_clock_reported_at": None}
    prev.setdefault("on_clock_reported_at", None)

    def save(picks, draft, rep):
        prev.update({
            "pick_count": len(picks),
            "status": draft.get("status"),
            "on_clock_reported_at": len(picks) if rep["on_clock"] else prev.get("on_clock_reported_at"),
        })
        with open(state_path, "w") as f:
            json.dump(prev, f)

    deadline = time.time() + a.timeout
    failures = 0
    while True:
        try:
            draft = fetch(f"/draft/{a.draft_id}")
            picks = fetch(f"/draft/{a.draft_id}/picks") or []
            failures = 0
        except Exception as e:
            failures += 1
            print(f"fetch error ({failures}/3): {e}", file=sys.stderr)
            if failures >= 3:
                if a.loop:
                    # Fail loudly on stdout so the Monitor wakes the session, then keep trying.
                    emit({"error": f"{failures} consecutive fetch failures: {e}", "draft_id": a.draft_id}, True)
                    failures = 0
                    time.sleep(IDLE_INTERVAL)
                    continue
                sys.exit(1)
            time.sleep(interval)
            continue

        slot = user_slot(draft, cfg, a.draft_id, a.slot)
        rep = report(draft, picks, prev["pick_count"], slot, a.near_picks, a.board, a.top)
        new_on_clock = rep["on_clock"] and prev.get("on_clock_reported_at") != len(picks)
        changed = (
            len(picks) > prev["pick_count"]
            or draft.get("status") != prev["status"]
            or new_on_clock
        )

        if a.loop:
            if changed or a.baseline:
                a.baseline = False
                save(picks, draft, rep)
                emit(rep, compact=True)
                if rep["draft_complete"]:
                    sys.exit(0)
        elif a.baseline or changed or time.time() >= deadline:
            save(picks, draft, rep)
            emit(rep, compact=False)
            sys.exit(0 if (a.baseline or changed) else 3)

        near = rep["picks_until_user"] is not None and rep["picks_until_user"] <= a.near_picks
        live = draft.get("status") == "drafting"
        if not live:
            time.sleep(IDLE_INTERVAL)
        else:
            time.sleep(min(interval, fast) if near else interval)


if __name__ == "__main__":
    main()
