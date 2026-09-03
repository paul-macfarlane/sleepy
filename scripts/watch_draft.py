#!/usr/bin/env python3
"""Watch a Sleeper draft and report state changes as JSON.

Usage:
    watch_draft.py DRAFT_ID [--loop] [--mock] [--slot N] [--near-picks 3] [--board]
                            [--interval 15] [--fast-interval 5] [--timeout 900]
                            [--baseline] [--top 15]

Two modes:

  One-shot (default): block until the draft's state changes, print one JSON
  report (pretty), exit. State persists in ~/sleepy/state/draft_{id}.json so
  each call reports only genuinely new picks.

  --loop: never exit while the draft is live. Print one compact JSON line per
  change (new picks / status change / user comes on the clock) and flush, so
  a Monitor can turn each line into a wake-up. Exits 0 when the draft
  completes. Fetch failures are reported as {"error": ...} lines after 3
  consecutive misses and polling continues — the loop never dies silently.

  Monitor notifications truncate long lines (~500 chars), so the loop line is
  deliberately small: status, counts, new picks as short strings ("6 Jonathan
  Taylor RB *" — * marks the user's own pick), on-clock flags, and when the
  board is attached only its headline (roster, runs, top 6). The full report —
  including the whole board with by-position groups — is written to
  ~/sleepy/state/draft_{id}_last.json first; "event_file" in the line points
  at it. Read that file, not board.py, when you need more than the headline.

Board: whenever the user is within --near-picks of the clock (or on it), or
--board is passed, the report includes "board": the user's roster, position
counts league-wide, the last 5 picks, position-run flags, the top --top
available skill players with injury tags, and "by_position" — the best few
at every position including TE, K and DEF, which a rank-sorted top-N hides
(so TE/K/DEF never need a separate board.py call). One call, one
round trip, no need to run board.py separately. Team DEFs have no Sleeper
search_rank; they are ordered by ~/sleepy/def_ranks.json (user override) or
assets/def_ranks.json, and their "rank" is the position in that list.

Polling: 15s (floor 10) while live in a real draft; 5s with --mock, even while pre_draft (CPU picks
land instantly); 5s whenever the user is within --near-picks; 30s while
pre_draft or paused in real drafts. --baseline prints the current state immediately.

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
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_POS = ("QB", "RB", "WR", "TE")
# Sleeper gives team defenses no search_rank, so DEFs are ranked from an ordered
# team list: ~/sleepy/def_ranks.json if the user made one, else assets/def_ranks.json.
DEF_RANK_FILES = (os.path.join(SLEEPY_HOME, "def_ranks.json"),
                  os.path.join(SKILL_DIR, "assets", "def_ranks.json"))
DEF_UNRANKED = 99  # teams missing from the list sort last (then alphabetical)
# Best-N per position always shipped with the board, so TE/K/DEF are visible
# even when the rank-sorted top list is all RB/WR/QB.
BY_POSITION_N = {"QB": 4, "RB": 6, "WR": 6, "TE": 4, "K": 3, "DEF": 3}
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


_def_ranks = None


def load_def_ranks():
    """{team: rank} from the first readable DEF_RANK_FILES entry; {} if none (all DEFs unranked)."""
    global _def_ranks
    if _def_ranks is None:
        _def_ranks = {}
        for path in DEF_RANK_FILES:
            try:
                with open(path) as f:
                    order = json.load(f).get("order") or []
            except (OSError, ValueError, AttributeError):
                continue
            _def_ranks = {str(t).upper(): i + 1 for i, t in enumerate(order)}
            break
    return _def_ranks


def rank_of(p):
    """Sort key / display rank: Sleeper search_rank for players, def_ranks position for team DEFs."""
    if p.get("position") == "DEF":
        return load_def_ranks().get((p.get("team") or "").upper(), DEF_UNRANKED)
    return p.get("search_rank") or 0


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
    """'J. Williams' — surname alone is ambiguous on a phone (several RB Williams exist)."""
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


def avail_entry(p):
    name = p.get("last_name") if p.get("position") == "DEF" else f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    return {
        "rank": rank_of(p),
        "player": name,
        "position": p["position"],
        "team": p["team"],
        "age": p.get("age"),
        "injury": injury(p),
    }


def available(players, gone, positions):
    """Active, rostered, undrafted players at these positions, best rank first.
    Players sort by Sleeper search_rank; team DEFs (no search_rank in the dump) sort by
    def_ranks.json order — see load_def_ranks — so DEF rank 1 means "first in that list"."""
    def ranked(p):
        if p.get("position") == "DEF":
            return True
        return bool(p.get("search_rank")) and p["search_rank"] < 9999
    avail = [
        p for p in players.values()
        if p.get("active") and ranked(p)
        and p.get("position") in positions and p.get("team") and p.get("player_id") not in gone
    ]
    avail.sort(key=lambda p: (rank_of(p), p.get("last_name") or ""))
    return avail


def build_board(picks, slot, top_n):
    """Roster / counts / runs / top-N available / by-position — the same data board.py prints, as JSON."""
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

    pool = available(players, gone, tuple(BY_POSITION_N))
    top = [avail_entry(p) for p in pool if p["position"] in SKILL_POS][:top_n]
    by_pos = {
        pos: [avail_entry(p) for p in pool if p["position"] == pos][:n]
        for pos, n in BY_POSITION_N.items()
    }
    return {
        "my_roster": [label(p) for p in mine],
        "my_counts": dict(Counter((p.get("metadata") or {}).get("position") for p in mine)),
        "league_counts": dict(Counter((p.get("metadata") or {}).get("position") for p in picks)),
        "last_5": [label(p) for p in last5],
        "position_runs": runs,  # 3+ of a position in the last 5 picks
        "top_available": top,
        "by_position": by_pos,  # best few at every position incl. TE/K/DEF
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


def short_avail(p):
    inj = p["injury"]
    tag = f" {inj['tag']}{inj['status'][0]}:{inj['body_part'] or '?'}" if inj else ""
    return f"{p['rank']} {p['player']} {p['position']} {p['team']} {p['age']}{tag}"


def compact_report(rep, uid, event_file):
    """Headline only — must survive a ~500-char notification truncation."""
    c = {k: rep[k] for k in ("status", "total_picks_made", "user_next_pick_no",
                             "picks_until_user", "on_clock", "draft_complete") if k in rep}
    c["new_picks"] = [
        f"{p['pick_no']} {p['player']} {p['position']}" + (" *" if uid and p.get("picked_by") == uid else "")
        for p in rep.get("new_picks", [])
    ]
    if rep.get("reversal_round_unsupported"):
        c["reversal_round_unsupported"] = True
    b = rep.get("board")
    if b:
        c["roster"] = ", ".join(b["my_roster"]) or "(empty)"
        c["runs"] = b["position_runs"]
        c["top"] = [short_avail(p) for p in b["top_available"][:6]]
    c["event_file"] = event_file
    return c


def emit(rep, compact):
    print(json.dumps(rep, separators=(",", ":"), ensure_ascii=False) if compact else json.dumps(rep, indent=2, ensure_ascii=False))
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
    IDLE_INTERVAL = 5 if a.mock else 30  # pre_draft / paused: mocks go live with instant CPU picks, so stay quick; real drafts can be polite

    cfg = load_config()
    state_dir = os.path.join(SLEEPY_HOME, "state")
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, f"draft_{a.draft_id}.json")
    event_path = os.path.join(state_dir, f"draft_{a.draft_id}_last.json")
    uid = str(cfg.get("user_id", ""))

    def emit_loop(rep):
        """Full report to disk, headline to stdout (Monitor truncates long lines)."""
        with open(event_path, "w") as f:
            json.dump(rep, f, indent=1, ensure_ascii=False)
        emit(compact_report(rep, uid, event_path), compact=True)
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
                emit_loop(rep)
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
