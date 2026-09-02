#!/usr/bin/env python3
"""
campaign_engine.py — turn resolution for the Uran persistent campaign.

This is the only code that writes data/campaign_state.json. Everything else
(the website, the missions) is generated FROM that file, never edited by
hand. One call to resolve_turn() is "Sunday night": read whatever mission
logs were submitted this week, grade them with log_parser.py against the
OBJID each mission recorded at generation time, update sectors/pilots/front,
write a story chapter, and generate next turn's missions.

Design recap (see SCHEMA.md for the full field list):
  - Sectors accumulate "pressure" from mission results. Turn resolution
    nudges the front line at a sector toward the NEXT real historical
    snapshot when the sector's net pressure favors the Allied player side,
    and holds it when it doesn't. The historical snapshots are guardrails,
    never a script: the front can lag behind history, but it can never
    move past where it actually reached on a given date.
  - Pilots are keyed by a human-chosen slug, matched to a real person via
    the LOGIN uuid the game log records. A brand-new uuid is guessed from
    its NAME callsign prefix (see log_parser._guess_slug_from_callsign);
    a guess miss is reported, not silently dropped.
  - Nothing is ever deleted. Old turns, old missions, old story chapters
    stay in the file — the site reads the whole history straight out of it.

CURRENT SCOPE: this first version generates next turn's missions by
re-running the same fixed mission set (missions.py's mission_01..04)
re-dated and re-tagged to the new turn/sector state. It proves the whole
loop end to end (log in -> graded -> front moves -> story written -> next
missions exist with valid meta). Actually varying mission content per
sector pressure/front position turn over turn is follow-on work, flagged
in NEXT_STEPS.md.
"""
import copy
import json
import os
import glob

from log_parser import (discover_log_sets, read_log_set, parse_lines,
                        match_pilots, mission_result)

HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN_DIR = os.path.dirname(HERE)
DATA_DIR = os.path.join(CAMPAIGN_DIR, "data")
STATE_PATH = os.path.join(DATA_DIR, "campaign_state.json")
FRONTLINES_DIR = os.path.join(DATA_DIR, "frontlines")
TURNS_DIR = os.path.join(CAMPAIGN_DIR, "turns")

DAYS_PER_TURN = 6          # in-fiction date advance per weekly resolution
FRONT_ADVANCE_FRACTION = 0.20   # how far a winning sector's line moves
                                 # toward the next historical snapshot, per turn
MATCH_RADIUS_M = 20000.0        # how far a sector searches for "its" front points


# --------------------------------------------------------------------- I/O

def load_state(path=STATE_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state, path=STATE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=False)
    os.replace(tmp, path)


def load_frontline_snapshot(date_str):
    """date_str like '1942-11-23' -> data/frontlines/19421123.json"""
    fname = date_str.replace("-", "") + ".json"
    path = os.path.join(FRONTLINES_DIR, fname)
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    allied, axis = [], []
    for loc in raw["locations"]:
        pt = [loc["position"]["xPos"], loc["position"]["zPos"]]
        (allied if loc["name"] == "AlliedFrontLine" else axis).append(pt)
    return {"allied": allied, "axis": axis}


# ------------------------------------------------------------- turn intake

def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def ingest_logs(state, log_dir, roster):
    """Parse every log set in log_dir, match it to a pending mission by its
    MFile basename, grade it, and fold the result into sectors/pilots.
    Returns a list of per-mission summary dicts for the story writer."""
    missions_by_id = {m["id"]: m for m in state["missions"]}
    summaries = []

    for ts, paths in discover_log_sets(log_dir).items():
        log = parse_lines(read_log_set(paths))
        if not log.mission_file:
            summaries.append({"log_set": ts, "error": "no MFile in log header"})
            continue

        mission_id = os.path.splitext(os.path.basename(
            log.mission_file.replace("\\", "/")))[0]
        mission = missions_by_id.get(mission_id)
        if mission is None:
            summaries.append({"log_set": ts, "error": f"unknown mission '{mission_id}'"})
            continue
        if mission["status"] == "resolved":
            summaries.append({"log_set": ts, "mission": mission_id,
                              "note": "already resolved, log ignored"})
            continue

        meta = {"success_obj_id": mission.get("success_obj_id"),
                "failure_obj_id": mission.get("failure_obj_id")}
        result = mission_result(log, meta)
        pilot_results, unmatched = match_pilots(log, roster)

        mission["status"] = "resolved"
        mission["result"] = result
        mission["log_sets_applied"] = mission.get("log_sets_applied", []) + [ts]

        sector = state["sectors"].get(mission["sector"])
        if sector is not None:
            delta = {"success": 1, "failure": -1, "not_flown": 0}[result]
            sector["pressure"] = sector.get("pressure", 0) + delta
            sector["history"].append({
                "turn": state["campaign"]["turn"], "mission": mission_id,
                "result": result})

        for slug, pdata in pilot_results.items():
            pilot = state["pilots"].get(slug)
            if pilot is None:
                continue
            if pdata["login"] and pdata["login"] not in pilot["login_uuids"]:
                pilot["login_uuids"].append(pdata["login"])
            if pdata["name_seen"] and pdata["name_seen"] not in pilot["callsign_names_seen"]:
                pilot["callsign_names_seen"].append(pdata["name_seen"])
            pilot["kills"] = pilot.get("kills", 0) + pdata["kills"]
            # A logged kill against your own aircraft fires for both enemy
            # kills and plain crashes/collisions -- it does not by itself
            # mean the pilot was killed. If the same log also shows you
            # bailing out of that aircraft, you got out: shot down/crash-
            # landed, but back on the roster next mission. Only a destroyed
            # aircraft with NO recorded bailout is a confirmed KIA -- there
            # was no time or altitude to get out.
            confirmed_kia = pdata["died"] and not pdata["bailed_out"]
            if confirmed_kia:
                pilot["deaths"] = pilot.get("deaths", 0) + 1
                pilot["status"] = "kia"
            elif pdata["died"] and pdata["bailed_out"]:
                pilot["times_downed"] = pilot.get("times_downed", 0) + 1
            pilot["missions_flown"] = pilot.get("missions_flown", 0) + 1
            pilot["sorties"].append({
                "turn": state["campaign"]["turn"], "mission": mission_id,
                "result": result, "kills": pdata["kills"],
                "died": pdata["died"], "bailed_out": pdata["bailed_out"],
                "confirmed_kia": confirmed_kia,
                "took_off": pdata["took_off"], "landed": pdata["landed"]})

        summaries.append({
            "log_set": ts, "mission": mission_id, "sector": mission["sector"],
            "result": result, "pilots": list(pilot_results.keys()),
            "unmatched_logins": unmatched,
        })

    return summaries


# ------------------------------------------------------------ front advance

def advance_front(state):
    """Nudge the front line toward the next historical snapshot at every
    sector whose net pressure favors the Allied side this turn. Guardrail:
    a point is never moved past its position in that next snapshot."""
    theater = state["theaters"][state["campaign"]["theater"]]
    dates = theater["frontline_dates"]
    current_as_of = state["front"]["as_of"]

    upcoming = [d for d in dates if d > current_as_of]
    if not upcoming:
        return {"moved": False, "reason": "already at the last historical snapshot"}
    next_snapshot = load_frontline_snapshot(upcoming[0])

    moved_sectors = []
    for sname, sector in state["sectors"].items():
        pressure = sector.get("pressure", 0)
        if pressure <= 0:
            continue   # holds; no ground given either direction this turn
        spos = sector["pos"]
        for coalition in ("allied", "axis"):
            line = state["front"]["coalitions"][coalition]
            for i, pt in enumerate(line):
                if _dist(pt, spos) > MATCH_RADIUS_M:
                    continue
                target_line = next_snapshot[coalition]
                nearest = min(target_line, key=lambda p: _dist(p, pt))
                frac = min(1.0, FRONT_ADVANCE_FRACTION * (1 + 0.1 * (pressure - 1)))
                new_pt = [pt[0] + (nearest[0] - pt[0]) * frac,
                          pt[1] + (nearest[1] - pt[1]) * frac]
                # guardrail: never overshoot the historical target point
                if _dist(new_pt, spos) <= max(_dist(pt, spos), _dist(nearest, spos)):
                    line[i] = new_pt
        moved_sectors.append(sname)
        sector["pressure"] = 0   # consumed this turn

    return {"moved": bool(moved_sectors), "sectors": moved_sectors,
            "toward": upcoming[0]}


# --------------------------------------------------------------- narrative

def write_story_chapter(state, summaries, front_result):
    turn = state["campaign"]["turn"]
    date = state["campaign"]["date"]

    wins = [s for s in summaries if s.get("result") == "success"]
    losses = [s for s in summaries if s.get("result") == "failure"]

    lines = []
    if wins:
        won_sectors = ", ".join(sorted({s["sector"] for s in wins if s.get("sector")}))
        lines.append(f"27 IAP held the sky over {won_sectors} this turn.")
    if losses:
        lost_sectors = ", ".join(sorted({s["sector"] for s in losses if s.get("sector")}))
        lines.append(f"The line did not hold at {lost_sectors}.")
    if not wins and not losses:
        lines.append("No missions were flown this turn. The front waited.")

    downed = []
    kia = []
    for slug, pilot in state["pilots"].items():
        for sortie in pilot.get("sorties", []):
            if sortie["turn"] != turn:
                continue
            if sortie.get("confirmed_kia"):
                kia.append(pilot["display_name"])
            elif sortie.get("bailed_out"):
                downed.append(pilot["display_name"])
    if kia:
        lines.append(f"{', '.join(sorted(set(kia)))} did not come back this turn.")
    if downed:
        lines.append(f"{', '.join(sorted(set(downed)))} went down and walked out, "
                      f"and will fly again.")

    if front_result.get("moved"):
        lines.append(f"The front line shifted toward the {front_result['toward']} "
                     f"positions at {', '.join(front_result['sectors'])}.")
    else:
        lines.append("The front held its ground this week.")

    title = f"Turn {turn} — {date}"
    text = " ".join(lines)
    state["story"].append({"turn": turn, "date": date, "title": title, "text": text})
    return {"title": title, "text": text}


# -------------------------------------------------------------- turn driver

def _advance_date(date_str, days):
    y, m, d = (int(x) for x in date_str.split("-"))
    import datetime
    dt = datetime.date(y, m, d) + datetime.timedelta(days=days)
    return dt.isoformat()


def resolve_turn(state, log_dir, roster):
    """One full weekly turn: ingest logs -> update sectors/pilots -> move
    the front -> write a story chapter -> advance the turn counter/date.
    Does NOT generate next turn's missions (see generate_next_missions) —
    kept separate so resolution can be tested without the mission-generator
    dependency graph."""
    summaries = ingest_logs(state, log_dir, roster)
    front_result = advance_front(state)
    chapter = write_story_chapter(state, summaries, front_result)

    state["campaign"]["turn"] += 1
    state["campaign"]["date"] = _advance_date(state["campaign"]["date"], DAYS_PER_TURN)

    return {"summaries": summaries, "front": front_result, "chapter": chapter}


if __name__ == "__main__":
    import sys
    state = load_state()
    print(json.dumps(state["campaign"], indent=2))
    print(f"{len(state['sectors'])} sectors, {len(state['pilots'])} pilots, "
          f"{len(state['missions'])} missions on file, "
          f"{len(state['story'])} story chapters")
