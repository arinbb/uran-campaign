"""
log_parser.py — reads IL-2 Great Battles mission text logs and turns them
into structured turn results for the Uran campaign engine.

Reference for the AType: grammar: PWCGCampaign
  src/main/java/pwcg/core/logfiles/event/AType*.java   (per-event field layout)
  src/main/java/pwcg/core/logfiles/LogFileSetFactory.java (multi-file grouping)
  src/main/java/pwcg/mission/mcu/McuMissionObjective.java (AType:8 field meaning)

This format is produced identically for solo flights and hosted/co-op
sessions once `mission_text_log=1` is set in startup.cfg — that is the
whole trust mechanism behind "the server knows if you won or lost": we
never trust a player's self-report, we read the game's own log.

------------------------------------------------------------------------
Event types actually used (see AType.java for the full enum):

  AType:0   Mission Start   — GDate/GTime/MFile header, once per file set
  AType:3   Kill            — AID (victor) killed TID (victim)
  AType:5   Take Off        — PID = top-level vehicle id
  AType:6   Landing         — PID = top-level vehicle id
  AType:7   Mission End     — no fields, marks the end of the file set
  AType:8   Mission Complete/Objective — OBJID/COAL/RES tied to a specific
            MCU_TR_MissionObjective the mission generator placed. RES is
            the *static* Success flag of that particular node (1 = this is
            the "success" objective, 0 = this is a "failure" objective) —
            NOT a live pass/fail bit. Whether the campaign engine counts
            the mission as won is "did an AType:8 line appear for the
            OBJID recorded as this mission's success_obj_id".
  AType:10  Player Spawn    — human-flown aircraft only. PLID = top-level
            vehicle id (matches AType:12 id with PID:-1), PID = the bot/
            pilot entity inside it, LOGIN = stable per-Steam-account uuid,
            NAME = in-game callsign.
  AType:12  Object Spawn    — every object (aircraft, vehicle, bot, etc.)
            with ID/TYPE/COUNTRY/NAME/PID (PID:-1 for a top-level object,
            otherwise the id of its parent — e.g. a pilot bot's PID is its
            aircraft's id).
  AType:18  Bail out        — BOTID/PARENTID.

All AID/TID/PID references in kill and take-off/landing events point at
the *top-level* vehicle id (the AType:12 entry whose own PID is -1), which
is the same id AType:10 calls PLID for human-flown planes. That is the key
that ties a human pilot to their kills, deaths, takeoffs and landings.
------------------------------------------------------------------------
"""

import glob
import os
import re
from collections import defaultdict


# ---------------------------------------------------------------------------
# Low level line parsing
# ---------------------------------------------------------------------------

def _kv(line, key, stop_chars=" "):
    """Pull the value that follows 'key:' up to whitespace (default) out of a line."""
    idx = line.find(key)
    if idx == -1:
        return None
    start = idx + len(key)
    end = len(line)
    for i in range(start, len(line)):
        if line[i] in stop_chars:
            end = i
            break
    return line[start:end]


def _between(line, start_tag, end_tag):
    s = line.find(start_tag)
    if s == -1:
        return None
    s += len(start_tag)
    e = line.find(end_tag, s)
    if e == -1:
        return line[s:].strip()
    return line[s:e]


def _pos(line, start_tag="POS("):
    """Parse a POS(x,y,z) or (x,y,z) tuple following start_tag. Tolerant of
    both the compact "144633.891,377.281,66917.492" and the spaced
    "146349.281, 105.671, 65344.523" forms seen in real logs."""
    s = line.find(start_tag)
    if s == -1:
        return None
    s = line.find("(", s)
    if s == -1:
        return None
    e = line.find(")", s)
    if e == -1:
        return None
    parts = [p.strip() for p in line[s + 1:e].split(",")]
    if len(parts) != 3:
        return None
    try:
        return tuple(float(p) for p in parts)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Log-set discovery: real logs are split across missionReport(TS)[N].txt
# files that share a timestamp and must be read in [N] order (per
# LogFileSetFactory.java).
# ---------------------------------------------------------------------------

_FILE_RE = re.compile(r"missionReport\(([^)]+)\)\[(\d+)\]\.txt$")


def discover_log_sets(directory):
    """Group every missionReport(...)[N].txt file in `directory` by its
    timestamp. Returns {timestamp: [sorted filepaths]}."""
    sets = defaultdict(dict)
    for path in glob.glob(os.path.join(directory, "missionReport(*.txt")):
        m = _FILE_RE.search(os.path.basename(path))
        if not m:
            continue
        ts, idx = m.group(1), int(m.group(2))
        sets[ts][idx] = path
    return {ts: [files[i] for i in sorted(files)] for ts, files in sets.items()}


def read_log_set(filepaths):
    """Concatenate a log set's files, in [N] order, into one list of lines."""
    lines = []
    for path in filepaths:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines.extend(l.rstrip("\n").rstrip("\r") for l in f if l.strip())
    return lines


# ---------------------------------------------------------------------------
# Parsing a single log set into structured data
# ---------------------------------------------------------------------------

class ParsedLog:
    def __init__(self):
        self.mission_file = None
        self.date = None                 # "1942.11.19" from GDate, or None
        self.entities = {}               # id -> {type, country, name, pid}
        self.players = {}                # plid -> {login, name, type, country, pid}
        self.kills = []                  # [{t, victor, victim, pos}]
        self.takeoffs = defaultdict(list)   # vehicle_id -> [t, ...]
        self.landings = defaultdict(list)   # vehicle_id -> [t, ...]
        self.bailouts = []               # [{t, bot_id, vehicle_id, pos}]
        self.objectives = []             # [{t, obj_id, coalition, task_type, result, icon_type}]
        self.mission_end_t = None
        self.warnings = []


def parse_lines(lines):
    log = ParsedLog()

    for line in lines:
        if " AType:0 " in line or line.startswith("T:0 AType:0"):
            gdate = _kv(line, "GDate:")
            if gdate:
                log.date = gdate
            mfile = _between(line, "MFile:", " MID:")
            if mfile:
                log.mission_file = mfile
            continue

        if " AType:12 " in line:
            eid = _kv(line, "ID:")
            etype = _between(line, " TYPE:", " COUNTRY:")
            country = _kv(line, "COUNTRY:")
            name = _between(line, "NAME:", " PID:")
            pid = _kv(line, "PID:")
            if eid is not None:
                log.entities[eid] = {
                    "type": etype,
                    "country": country,
                    "name": (name or "").strip(),
                    "pid": pid,
                }
            continue

        if " AType:10 " in line:
            plid = _kv(line, "PLID:")
            pid = _kv(line, "PID:")
            login = _kv(line, "LOGIN:")
            name = _kv(line, "NAME:")
            etype = _between(line, " TYPE:", " COUNTRY:")
            country = _kv(line, "COUNTRY:")
            pos = _pos(line, "RCT:")
            if plid is not None:
                log.players[plid] = {
                    "pid": pid,
                    "login": login,
                    "name": name,
                    "type": etype,
                    "country": country,
                    "pos": pos,
                }
                # AType:10 is also a full object spawn for the vehicle
                log.entities.setdefault(plid, {
                    "type": etype, "country": country, "name": name, "pid": "-1",
                })
            continue

        if " AType:3 " in line:
            t = _kv(line, "T:")
            aid = _kv(line, "AID:")
            tid = _kv(line, "TID:")
            pos = _pos(line)
            log.kills.append({"t": _to_int(t), "victor": aid, "victim": tid, "pos": pos})
            continue

        if " AType:5 " in line:
            t = _kv(line, "T:")
            pid = _kv(line, "PID:", stop_chars=" ,")
            log.takeoffs[pid].append(_to_int(t))
            continue

        if " AType:6 " in line:
            t = _kv(line, "T:")
            pid = _kv(line, "PID:", stop_chars=" ,")
            log.landings[pid].append(_to_int(t))
            continue

        if " AType:18 " in line:
            t = _kv(line, "T:")
            bot = _kv(line, "BOTID:")
            parent = _kv(line, "PARENTID:")
            pos = _pos(line)
            log.bailouts.append({"t": _to_int(t), "bot_id": bot, "vehicle_id": parent, "pos": pos})
            continue

        if " AType:8 " in line:
            t = _kv(line, "T:")
            obj_id = _kv(line, "OBJID:")
            coal = _kv(line, "COAL:")
            task_type = _kv(line, "TYPE:")
            res = _kv(line, "RES:")
            ic = _kv(line, "ICTYPE:")
            log.objectives.append({
                "t": _to_int(t), "obj_id": obj_id,
                "coalition": _to_int(coal), "task_type": _to_int(task_type),
                "result": _to_int(res), "icon_type": ic,
            })
            continue

        if " AType:7 " in line or line.rstrip().endswith("AType:7"):
            t = _kv(line, "T:")
            log.mission_end_t = _to_int(t)
            continue

    return log


def _to_int(s):
    if s is None:
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except (TypeError, ValueError):
            return None


def parse_directory(directory, timestamp=None):
    """Parse every log set in `directory`. If `timestamp` is given, parse
    only that set. Returns {timestamp: ParsedLog}."""
    sets = discover_log_sets(directory)
    if timestamp is not None:
        sets = {timestamp: sets[timestamp]} if timestamp in sets else {}
    return {ts: parse_lines(read_log_set(paths)) for ts, paths in sets.items()}


# ---------------------------------------------------------------------------
# Turning a ParsedLog into per-pilot results, given the campaign roster
# ---------------------------------------------------------------------------

def match_pilots(parsed, roster):
    """roster: {slug: {"login_uuids": [...], "callsign_names_seen": [...]}}

    Returns {slug: {vehicle_id, name_seen, took_off, landed, died, bailed_out,
                     kills, unmatched: False}}, plus a list of unmatched
    AType:10 entries (new logins the engine has never seen, keyed by the
    slug it *guesses* from the callsign prefix, or None if it can't guess).
    """
    results = {}
    unmatched = []

    # index roster by login uuid for O(1) lookup
    login_to_slug = {}
    for slug, info in roster.items():
        for uuid in info.get("login_uuids", []):
            login_to_slug[uuid] = slug

    for plid, pdata in parsed.players.items():
        login = pdata.get("login")
        slug = login_to_slug.get(login)
        if slug is None:
            guess = _guess_slug_from_callsign(pdata.get("name"), roster)
            unmatched.append({
                "plid": plid, "login": login, "name": pdata.get("name"),
                "guessed_slug": guess,
            })
            if guess is None:
                continue
            slug = guess

        died = any(k["victim"] == plid for k in parsed.kills)
        kills = sum(1 for k in parsed.kills if k["victor"] == plid)
        bailed = any(b["vehicle_id"] == plid for b in parsed.bailouts)

        results[slug] = {
            "vehicle_id": plid,
            "name_seen": pdata.get("name"),
            "login": login,
            "took_off": len(parsed.takeoffs.get(plid, [])) > 0,
            "landed": len(parsed.landings.get(plid, [])) > 0,
            "died": died,
            "bailed_out": bailed,
            "kills": kills,
        }

    return results, unmatched


def _guess_slug_from_callsign(name, roster):
    if not name:
        return None
    # convention used by the Uran generator: "CANARY_Arin" -> slug "arin"
    tail = name.rsplit("_", 1)[-1].lower()
    for slug, info in roster.items():
        if slug == tail:
            return slug
        if tail in [n.lower() for n in info.get("callsign_names_seen", [])]:
            return slug
    return None


def mission_result(parsed, mission_meta):
    """mission_meta: {"success_obj_id": "...", "failure_obj_id": "..." or None}

    Returns "success" | "failure" | "not_flown".
    """
    # mission_meta.json comes from json.load (ints); the log's own OBJID
    # fields are parsed as strings — normalize both to str before comparing.
    success_id = mission_meta.get("success_obj_id")
    failure_id = mission_meta.get("failure_obj_id")
    success_id = str(success_id) if success_id is not None else None
    failure_id = str(failure_id) if failure_id is not None else None

    fired_ids = {o["obj_id"] for o in parsed.objectives}

    if success_id is not None and success_id in fired_ids:
        return "success"
    if failure_id is not None and failure_id in fired_ids:
        return "failure"
    if parsed.mission_end_t is None and not parsed.players:
        return "not_flown"
    return "failure"


# ---------------------------------------------------------------------------
# Self-test against real captured fixtures (RoF-era, but same AType: grammar
# — see the module docstring). This is a smoke test, not a BoS validation:
# there is no BoS-era fixture available to test against in this environment.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    fixture_dir = sys.argv[1] if len(sys.argv) > 1 else \
        "/home/claude/PWCGCampaign/testData/data"

    sets = discover_log_sets(fixture_dir)
    print(f"discovered {len(sets)} log sets in {fixture_dir}")

    total_kills = total_players = total_objectives = 0
    errors = 0
    for ts, paths in sorted(sets.items()):
        try:
            lines = read_log_set(paths)
            log = parse_lines(lines)
        except Exception as e:
            errors += 1
            print(f"  [ERROR] {ts}: {e}")
            continue

        total_kills += len(log.kills)
        total_players += len(log.players)
        total_objectives += len(log.objectives)

        # sanity: every kill's AID/TID that also appears as a top-level
        # entity (PID:-1) should resolve to a known entity type
        unresolved = 0
        for k in log.kills:
            for eid in (k["victor"], k["victim"]):
                if eid not in log.entities and eid != "-1":
                    unresolved += 1

        print(f"  {ts}: {len(paths)} files, {len(lines)} lines, "
              f"{len(log.entities)} entities, {len(log.players)} human players, "
              f"{len(log.kills)} kills ({unresolved} unresolved ids), "
              f"{len(log.objectives)} objective events, "
              f"mission_end_t={log.mission_end_t}, date={log.date}")

    print()
    print(f"TOTAL: {len(sets)} sets, {errors} errors, "
          f"{total_kills} kills, {total_players} player spawns, "
          f"{total_objectives} objective events")

    if errors:
        sys.exit(1)
