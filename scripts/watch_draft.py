#!/usr/bin/env python3
"""Block until a Sleeper draft's state changes, then print a JSON delta and exit.

Usage:
    watch_draft.py DRAFT_ID [--interval 15] [--mock] [--slot N] [--timeout 900] [--baseline]

Behavior:
  - Polls /draft/{id}/picks every --interval seconds while the draft is live
    (default 15s, floor 10s — real drafts run 60–90s clocks). While the draft is
    pre_draft or paused, polls every 30s regardless.
  - --mock: CPU drafters pick instantly, so poll every 5s while live.
  - Exits 0 with a JSON report when: new picks appear, the draft starts/pauses/
    completes, or the user goes on the clock.
  - Exits 3 on --timeout with a status report (caller can just re-invoke).
  - Exits 1 after 3 consecutive fetch failures (caller should alert the user).
  - Polls every --fast-interval (default 5s) while the user is within
    --near-picks (default 2) of the clock and the draft is live, so advice can
    be prepared before the pick arrives.
  - --baseline: print current state immediately without waiting (for preflight
    and crash recovery).
  - State persists in ~/sleepy/state/draft_{id}.json between invocations, so
    each call reports only genuinely new picks.

The user's slot comes from --slot, else config.json leagues[] entry matching
this draft_id, else the draft's draft_order + config user_id.
"""
import argparse, json, os, sys, time, urllib.request

# macOS python.org builds ship without root certs; fall back to certifi if present.
if not os.environ.get("SSL_CERT_FILE"):
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass

BASE = "https://api.sleeper.app/v1"
SLEEPY_HOME = os.environ.get("SLEEPY_HOME", os.path.expanduser("~/sleepy"))


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


def report(draft, picks, prev_count, slot):
    teams = int(draft.get("settings", {}).get("teams") or 0)
    rounds = int(draft.get("settings", {}).get("rounds") or 0)
    reversal = int(draft.get("settings", {}).get("reversal_round") or 0)
    count = len(picks)
    nxt = next_user_pick(count, slot, teams, rounds, reversal) if teams else None
    picks_until = (nxt - count - 1) if nxt else None
    return {
        "status": draft.get("status"),
        "type": draft.get("type"),
        "teams": teams,
        "rounds": rounds,
        "reversal_round_unsupported": bool(reversal),
        "total_picks_made": count,
        "new_picks": [summarize_pick(p) for p in picks[prev_count:]],
        "user_slot": slot,
        "user_next_pick_no": nxt,
        "picks_until_user": picks_until,
        "on_clock": picks_until == 0 if picks_until is not None else False,
        "draft_complete": draft.get("status") == "complete",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft_id")
    ap.add_argument("--interval", type=int, default=15,
                    help="poll interval (s) while the draft is live; floor 10")
    ap.add_argument("--mock", action="store_true",
                    help="mock draft with instant CPU picks: poll every 5s while live")
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--fast-interval", type=int, default=5,
                    help="poll interval (s) when within --near-picks of the user's pick and draft is live")
    ap.add_argument("--near-picks", type=int, default=2)
    a = ap.parse_args()
    interval = 5 if a.mock else max(10, a.interval)
    a.fast_interval = max(5, a.fast_interval)
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
                sys.exit(1)
            time.sleep(interval)
            continue

        slot = user_slot(draft, cfg, a.draft_id, a.slot)
        rep = report(draft, picks, prev["pick_count"], slot)
        new_on_clock = rep["on_clock"] and prev.get("on_clock_reported_at") != len(picks)
        changed = (
            len(picks) > prev["pick_count"]
            or draft.get("status") != prev["status"]
            or new_on_clock
        )
        if a.baseline or changed or time.time() >= deadline:
            with open(state_path, "w") as f:
                json.dump({
                    "pick_count": len(picks),
                    "status": draft.get("status"),
                    "on_clock_reported_at": len(picks) if rep["on_clock"] else prev.get("on_clock_reported_at"),
                }, f)
            print(json.dumps(rep, indent=2))
            sys.exit(0 if (a.baseline or changed) else 3)
        # 3. Adaptive polling: tighten when the user's pick is imminent and the draft is live.
        near = rep["picks_until_user"] is not None and rep["picks_until_user"] <= a.near_picks
        live = draft.get("status") == "drafting"
        if not live:
            time.sleep(IDLE_INTERVAL)
        else:
            time.sleep(min(interval, a.fast_interval) if near else interval)


if __name__ == "__main__":
    main()
