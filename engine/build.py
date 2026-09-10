#!/usr/bin/env python3
"""
Builds the "Uran" four-mission IL-2 Great Battles co-op series.

Everything is generated from one place so that once mission 01 is confirmed to
load, the other three are structurally identical and should load too.
"""

import json
import os
import math

from il2lib import *   # noqa: F401,F403

HERE = os.path.dirname(os.path.abspath(__file__))
AIRFIELDS = json.load(open(os.path.join(
    HERE, "AirfieldLocations.json")))["locations"]
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ aircraft

def P(name):
    return "LuaScripts\\WorldObjects\\Planes\\%s.txt" % name


def PM(name):
    return "graphics\\planes\\%s\\%s.mgm" % (name, name)


LAGG3 = ("lagg3s29", P("lagg3s29"), PM("lagg3s29"))
YAK1 = ("yak1s69", P("yak1s69"), PM("yak1s69"))
IL2 = ("il2m42", P("il2m42"), PM("il2m42"))
JU87 = ("ju87d3", P("ju87d3"), PM("ju87d3"))
JU52 = ("ju523mg4e", P("ju523mg4e"), PM("ju523mg4e"))
BF109F = ("bf109f4", P("bf109f4"), PM("bf109f4"))
BF109G = ("bf109g2", P("bf109g2"), PM("bf109g2"))

# callsigns (Callsign enum, shared USSR/German range)
CS_CANARY = 9      # 27th Fighter Air Regiment
CS_HAWK = 20       # 62nd Ground Attack Air Regiment
CS_RAVEN = 3       # II./St.G.2
CS_FINCH = 7       # II./JG52
CS_SWIFT = 14      # I./JG3
CS_PELICAN = 13    # KGrzbV 800

# vehicles
def V(script, model):
    return ("LuaScripts\\WorldObjects\\vehicles\\%s.txt" % script,
            "graphics\\%s.mgm" % model)


OPEL = V("opel-blitz", "vehicles\\opel\\opel-blitz")
HORCH = V("horch830", "vehicles\\horch\\horch830")
SDKFZ251 = V("sdkfz251-1c", "vehicles\\sdkfz251\\sdkfz251-1c")
PZIII = V("pziii-h", "vehicles\\pziii-h\\pziii-h")
SDKFZ_FLAK = V("sdkfz10-flak38", "vehicles\\sdkfz10-flak38\\sdkfz10-flak38")
FLAK38 = V("flak38", "artillery\\flak38\\flak38")
MG34AA = V("mg34-aa", "artillery\\mg34-aa\\mg34-aa")


# --------------------------------------------------------------- build tools

class Builder:
    """One mission under construction."""

    def __init__(self, m):
        self.m = m
        self.begin = m.idx()          # MCU_TR_MissionBegin
        self.begin_timer = m.idx()    # MCU_Timer fired by MissionBegin
        self.go = m.idx()             # MCU_Counter — "the flight is away"
        self.go_targets = []          # MCUs fired once, when `go` trips
        self.begin_targets = [self.begin_timer]
        self.begin_timer_targets = []
        self.coop_entities = []       # player entities, for the took-off gate
        self.origin = (0.0, 100.0, 0.0)   # where housekeeping MCUs get parked
        # Campaign turn metadata: filled in as objectives are added, written
        # out alongside the .Mission file so log_parser.py knows which
        # OBJID in the game's own log means "this mission succeeded" without
        # ever having to trust a player's self-report.
        self.meta = {
            "success_obj_id": None,
            "failure_obj_id": None,
            "objective_coalition": None,
        }

    # -- deferred wiring ------------------------------------------------------

    def on_go(self, index):
        self.go_targets.append(index)

    def on_begin(self, index):
        self.begin_timer_targets.append(index)

    def on_begin_after(self, index, seconds):
        """Fire `index` `seconds` after mission start, independent of the gate."""
        ox, oy, oz = self.origin
        t = self.m.idx()
        mcu(self.m, "MCU_Timer", t, "Start Delay %ds" % seconds,
            ox, oy, oz, targets=[index],
            extra=[("Time", seconds), ("Random", 100)])
        self.begin_timer_targets.append(t)
        return t

    def finish(self, x, y, z, fallback_seconds):
        """
        Emit the start graph.

          MissionBegin -> Timer(1) -> [fallback timer, anything on_begin]
          fallback timer(N s) --.
          player took off -------+-> Counter(1) -> everything on_go

        The counter means the AI launches on whichever happens first: a human
        actually getting airborne, or the fallback timer expiring.  Without it
        the AI taxis out and leaves while you are still priming the engine.
        """
        fb = self.m.idx()
        self.begin_timer_targets.append(fb)

        mcu(self.m, "MCU_TR_MissionBegin", self.begin, "Mission Begin",
            x, y, z, targets=self.begin_targets,
            extra=[("Enabled", 1)])
        mcu(self.m, "MCU_Timer", self.begin_timer, "Begin Timer",
            x, y, z, targets=sorted(set(self.begin_timer_targets)),
            extra=[("Time", 1), ("Random", 100)])
        mcu(self.m, "MCU_Timer", fb, "Launch Fallback",
            x, y, z, targets=[self.go],
            extra=[("Time", fallback_seconds), ("Random", 100)])
        mcu(self.m, "MCU_Counter", self.go, "Launch Gate",
            x, y, z, targets=sorted(set(self.go_targets)),
            extra=[("Counter", 1), ("Dropcount", 0)])


def add_flight(b, *, name, plane_def, count, coop_slots, country, callsign,
               ai_level, wingman_ai, payload_id, wm_mask,
               field, route, cruise_speed, formation_type=1, formation_density=1,
               parked=True, air_start_pos=None, air_alt=1500.0,
               attack=None, land_at_field=True, activate=False,
               fuel=1.0, on_target_report=None, kill_report=None,
               ramp_slot=0, launch_delay=0, name_offset=0):
    """
    Emit one flight: `count` Plane blocks, an MCU_TR_Entity on the leader, and
    the command/waypoint graph that flies the route.

    route: list of (x, z, alt, area) tuples flown in order.
    attack: (x, z, radius, seconds, air, ground) or None.
    Returns dict with the leader entity index.
    """
    m = b.m
    _, script, model = plane_def

    # ---- positions -------------------------------------------------------
    if parked:
        af = AIRFIELDS[field]
        rw = af["runways"][0]
        park = rw["parkingLocation"]
        px, pz = park["position"]["xPos"], park["position"]["zPos"]
        py = park["position"]["yPos"]
        pyori = park["orientation"]["yOri"]
        offset_hdg = ramp_offset_heading(px, pz, pyori,
                                         rw["startPos"]["xPos"],
                                         rw["startPos"]["zPos"])
        spots = []
        for i in range(count):
            sx, sz = move(px, pz, offset_hdg, 22.0 * (ramp_slot + i))
            spots.append((sx, py, sz, pyori))
    else:
        ax, az, ahdg = air_start_pos
        spots = []
        for i in range(count):
            # echelon right, 60 m spacing, slight stack
            sx, sz = move(ax, az, (ahdg + 135.0) % 360.0, 60.0 * i)
            spots.append((sx, air_alt + 15.0 * i, sz, ahdg))

    # ---- planes ----------------------------------------------------------
    leader_entity = m.idx()
    plane_indices = []
    for i in range(count):
        sx, sy, sz, syori = spots[i]
        pidx = m.idx()
        plane_indices.append(pidx)
        plane(m, pidx,
              "%s %d" % (name, name_offset + i + 1),
              leader_entity if i == 0 else 0,
              sx, sy, sz, syori, script, model, country,
              ai_level if i == 0 else wingman_ai,
              1 if i < coop_slots else 0,
              i,
              START_PARKED if parked else START_AIR,
              payload_id, wm_mask, callsign, name_offset + i + 1,
              fuel=fuel,
              ai_rtb=1)

    # ---- command graph ---------------------------------------------------
    ex, ey, ez, _ = spots[0]
    wp_indices = [m.idx() for _ in route]
    takeoff_idx = m.idx() if parked else None
    activate_idx = m.idx() if activate else None
    formation_idx = m.idx()
    formation_timer = m.idx()
    attack_idx = m.idx() if attack else None
    land_idx = m.idx() if (parked and land_at_field) else None

    tookoff_relay = m.idx() if (parked and coop_slots) else None

    on_reports = []
    on_events = []
    if parked:
        on_reports.append((RP_TOOK_OFF, takeoff_idx, wp_indices[0]))
        # One event, one relay: the relay splits "we are off the ground" into
        # the formation order and the enemy-activation gate.  Hanging two
        # OnEvent entries of the same type off one entity is avoided.
        on_events.append((EV_PLANE_TOOK_OFF,
                          tookoff_relay if tookoff_relay else formation_timer))
        if coop_slots:
            b.coop_entities.append(leader_entity)
    if attack and on_target_report:
        on_reports.append((RP_AREA_ATTACKED, attack_idx, on_target_report))

    entity(m, leader_entity, "%s entity" % name, ex, ey, ez, plane_indices[0],
           enabled=0 if activate else 1,
           on_events=on_events or None,
           on_reports=on_reports or None)

    if parked:
        mcu(m, "MCU_CMD_TakeOff", takeoff_idx, "Take off %s" % name,
            AIRFIELDS[field]["runways"][0]["startPos"]["xPos"],
            AIRFIELDS[field]["runways"][0]["startPos"]["yPos"],
            AIRFIELDS[field]["runways"][0]["startPos"]["zPos"],
            targets=[], objects=[leader_entity],
            extra=[("NoTaxiTakeoff", 0)])
        # Issued off MissionBegin, NOT off the launch gate.  Gating the
        # player flight's own takeoff order on the player having taken off is
        # circular: the AI wingman would sit cold until the fallback expired.
        # PWCG issues it unconditionally ~30 s in and the wingmen wait for a
        # human leader to move; that is the proven behaviour.
        b.on_begin_after(takeoff_idx, 30 + launch_delay)
    else:
        if activate:
            mcu(m, "MCU_Activate", activate_idx, "Activate %s" % name,
                ex, ey, ez, targets=[wp_indices[0], formation_timer],
                objects=[leader_entity])
        else:
            b.on_go(wp_indices[0])
            b.on_go(formation_timer)

    # formation
    if tookoff_relay is not None:
        mcu(m, "MCU_Timer", tookoff_relay, "Airborne Relay %s" % name,
            ex, ey, ez, targets=[formation_timer, b.go],
            extra=[("Time", 1), ("Random", 100)])
    mcu(m, "MCU_Timer", formation_timer, "Formation Timer %s" % name,
        ex, ey, ez, targets=[formation_idx],
        extra=[("Time", 20), ("Random", 100)])
    mcu(m, "MCU_CMD_Formation", formation_idx, "Formation %s" % name,
        ex, ey, ez, targets=[], objects=[leader_entity],
        extra=[("FormationType", formation_type),
               ("FormationDensity", formation_density)])

    # waypoints
    for i, (wx, wz, walt, warea) in enumerate(route):
        tgts = []
        if i + 1 < len(route):
            tgts.append(wp_indices[i + 1])
        elif land_idx is not None:
            tgts.append(land_idx)
        if attack_idx is not None and i == len(route) // 2:
            tgts.append(attack_idx)
        mcu(m, "MCU_Waypoint", wp_indices[i], "WP%d %s" % (i + 1, name),
            wx, walt, wz, targets=tgts, objects=[leader_entity],
            extra=[("Area", warea), ("Speed", cruise_speed), ("Priority", 1)])

    if attack:
        axx, azz, arad, asec, aair, agnd = attack
        mcu(m, "MCU_CMD_AttackArea", attack_idx, "Attack %s" % name,
            axx, route[len(route) // 2][2], azz,
            targets=[], objects=[leader_entity],
            extra=[("AttackGround", agnd), ("AttackAir", aair),
                   ("AttackGTargets", agnd), ("AttackArea", arad),
                   ("Time", asec), ("Priority", 1)])

    if land_idx is not None:
        rw = AIRFIELDS[field]["runways"][0]
        # PWCG's Airfield.getLandingStart: sit at the rollout end, facing back
        # down the strip.  Leaving YOri at 0 makes the AI fly a north-aligned
        # pattern across a runway that is not aligned north.
        land_hdg = bearing(rw["endPos"]["xPos"], rw["endPos"]["zPos"],
                           rw["startPos"]["xPos"], rw["startPos"]["zPos"])
        mcu(m, "MCU_CMD_Land", land_idx, "Land %s" % name,
            rw["endPos"]["xPos"], rw["endPos"]["yPos"], rw["endPos"]["zPos"],
            targets=[], objects=[leader_entity],
            extra=[("Priority", 1)], yori=land_hdg)

    return {"entity": leader_entity, "planes": plane_indices,
            "activate": activate_idx, "wps": wp_indices}


def add_airfield_object(b, field, country):
    """fakefield + taxi Chart at the parking spot (required for AI taxi)."""
    af = AIRFIELDS[field]
    rw = af["runways"][0]
    park = rw["parkingLocation"]
    ox, oz = park["position"]["xPos"], park["position"]["zPos"]
    oy = park["position"]["yPos"]
    oyori = park["orientation"]["yOri"]
    chart = build_chart(rw, ox, oz, oyori)
    airfield(b.m, b.m.idx(), "Fake %s" % field, ox, oy, oz, oyori,
             country, chart)


def add_ground_group(b, *, name, items, country, route=None, speed=20,
                     kill_report=None, formation_type=None):
    """
    items: list of (vehicle_def, x, z, y, yori)
    The first item leads; the rest are formation members.  If `route` is given
    the group drives it.
    """
    m = b.m
    leader_entity = m.idx()
    idxs = []
    for i, (vdef, vx, vz, vy, vyori) in enumerate(items):
        vidx = m.idx()
        idxs.append(vidx)
        vehicle(m, vidx, "%s %d" % (name, i + 1),
                leader_entity if i == 0 else 0,
                vx, vy, vz, vyori, vdef[0], vdef[1], country,
                number_in_formation=i)

    ex, ez, ey = items[0][1], items[0][2], items[0][3]

    wp_idx = []
    if route:
        wp_idx = [m.idx() for _ in route]
    entity(m, leader_entity, "%s entity" % name, ex, ey, ez, idxs[0],
           enabled=1)

    if route:
        for i, (wx, wz) in enumerate(route):
            tgts = [wp_idx[i + 1]] if i + 1 < len(route) else []
            mcu(m, "MCU_Waypoint", wp_idx[i], "WP%d %s" % (i + 1, name),
                wx, ey, wz, targets=tgts, objects=[leader_entity],
                extra=[("Area", 100), ("Speed", speed), ("Priority", 1)])
        b.on_begin(wp_idx[0])

    if formation_type is not None:
        fidx = m.idx()
        mcu(m, "MCU_CMD_Formation", fidx, "Formation %s" % name,
            ex, ey, ez, targets=[], objects=[leader_entity],
            extra=[("FormationType", formation_type),
                   ("FormationDensity", 1)])
        b.on_begin(fidx)
    return {"entity": leader_entity, "vehicles": idxs}


def add_statics(b, items, country):
    """Individually-entitied static vehicles (flak, guns)."""
    m = b.m
    out = []
    for vdef, vx, vz, vy, vyori, nm in items:
        vidx = m.idx()
        eidx = m.idx()
        vehicle(m, vidx, nm, eidx, vx, vy, vz, vyori, vdef[0], vdef[1],
                country)
        entity(m, eidx, "%s entity" % nm, vx, vy, vz, vidx, enabled=1)
        out.append(vidx)
    return out


def add_route_icons(b, points, coalition, colour, label_lc):
    """Chain MCU_Icons so the briefing map draws the route."""
    m = b.m
    idxs = [m.idx() for _ in points]
    for i, (px, pz, palt) in enumerate(points):
        tgts = [idxs[i + 1]] if i + 1 < len(points) else []
        icon(m, idxs[i], px, palt, pz,
             label_lc if i == 0 else m.text(""), m.text(""),
             ICON_WAYPOINT, [coalition], targets=tgts,
             line_type=LINE_POSITION0, rgb=colour)
    return idxs


def add_kill_trigger(b, *, x, z, y, radius, object_script, country,
                     check_planes, target_mcu, name="Kill Watch"):
    """
    A wide-radius MCU_TR_ComplexTrigger filtered to one object script and
    country, firing `target_mcu` on OnObjectKilled (event 70).

    This is how the series scores kills.  Scoring off individual entities is
    not possible here: aircraft flying as formation members (NumberInFormation
    > 0) have no MCU_TR_Entity of their own, so only the leader could ever be
    counted.  The complex trigger sees every object of that type in the zone.
    """
    m = b.m
    idx = m.idx()
    L = ["MCU_TR_ComplexTrigger", "{",
         "  Index = %d;" % idx,
         '  Name = "%s";' % name,
         '  Desc = "";',
         "  Targets = [];",
         "  Objects = [];",
         "  XPos = %s;" % f3(x),
         "  YPos = %s;" % f3(y),
         "  ZPos = %s;" % f3(z),
         "  XOri = 0.00;",
         "  YOri = 0.00;",
         "  ZOri = 0.00;",
         "  Enabled = 1;",
         "  Cylinder = 1;",
         "  Radius = %d;" % radius,
         "  DamageThreshold = 1;",
         "  DamageReport = 50;",
         "  CheckVehicles = %d;" % (0 if check_planes else 1),
         "  CheckPlanes = %d;" % (1 if check_planes else 0)]
    for flt in ("Spawned", "EnteredSimple", "EnteredAlive", "LeftSimple",
                "LeftAlive", "FinishedSimple", "FinishedAlive",
                "StationaryAndAlive", "FinishedStationaryAndAlive",
                "TookOff", "Damaged", "CriticallyDamaged", "Repaired",
                "Killed", "DropedBombs", "FiredFlare", "FiredRockets",
                "DroppedCargoContainers", "DeliveredCargo",
                "ParatrooperJumped", "ParatrooperLandedAlive"):
        L.append("  EventsFilter%s = %d;" % (flt, 1 if flt == "Killed" else 0))
    L.append("  Country = %d;" % country)
    L.append('  ObjectScript = "%s";' % object_script.lower())
    L.append("  OnEvents")
    L.append("  {")
    L.append("    OnEvent")
    L.append("    {")
    L.append("      Type = 70;")
    L.append("      TarId = %d;" % target_mcu)
    L.append("    }")
    L.append("  }")
    L.append("}")
    L.append("")
    m._blocks.append("\n".join(L))
    return idx


def add_kill_corridor(b, *, from_xz, to_xz, y, object_script, country,
                      check_planes, target_mcu, name, radius=8000,
                      spacing=16000):
    """
    A line of kill triggers covering a corridor.

    One enormous trigger is not an option: the largest Radius in any real
    mission file is 13000, so a 40-60 km cylinder is well outside anything the
    engine has been shown to handle.  Circles are spaced at 2*radius so they
    tile the corridor without overlapping, which would double-count kills.
    """
    (x1, z1), (x2, z2) = from_xz, to_xz
    total = distance(x1, z1, x2, z2)
    hdg = bearing(x1, z1, x2, z2)
    n = max(1, int(round(total / spacing)) + 1)
    out = []
    for i in range(n):
        cx, cz = move(x1, z1, hdg, min(i * spacing, total))
        out.append(add_kill_trigger(
            b, x=cx, z=cz, y=y, radius=radius, object_script=object_script,
            country=country, check_planes=check_planes,
            target_mcu=target_mcu, name="%s %d" % (name, i + 1)))
    return out


def add_message_trigger(b, *, x, z, y, radius, country, object_script,
                        target_mcu, name="Callout Zone"):
    """
    A ComplexTrigger that fires `target_mcu` the moment a living aircraft
    matching `object_script`/`country` enters the zone -- OnObjectEnteredAlive,
    event type 59. Event-type table confirmed from PylGBMiMec's
    envent_definitions.py (event_name['MCU_TR_ComplexTrigger']), the same
    source that OnObjectKilled=70 in add_kill_trigger above comes from.

    This is how a scripted radio/subtitle message gets cued off the
    player's actual position instead of elapsed time: point it at a spot
    on the player's own route and target a subtitle() MCU.
    """
    m = b.m
    idx = m.idx()
    L = ["MCU_TR_ComplexTrigger", "{",
         "  Index = %d;" % idx,
         '  Name = "%s";' % name,
         '  Desc = "";',
         "  Targets = [];",
         "  Objects = [];",
         "  XPos = %s;" % f3(x),
         "  YPos = %s;" % f3(y),
         "  ZPos = %s;" % f3(z),
         "  XOri = 0.00;",
         "  YOri = 0.00;",
         "  ZOri = 0.00;",
         "  Enabled = 1;",
         "  Cylinder = 1;",
         "  Radius = %d;" % radius,
         "  DamageThreshold = 1;",
         "  DamageReport = 50;",
         "  CheckVehicles = 0;",
         "  CheckPlanes = 1;"]
    for flt in ("Spawned", "EnteredSimple", "EnteredAlive", "LeftSimple",
                "LeftAlive", "FinishedSimple", "FinishedAlive",
                "StationaryAndAlive", "FinishedStationaryAndAlive",
                "TookOff", "Damaged", "CriticallyDamaged", "Repaired",
                "Killed", "DropedBombs", "FiredFlare", "FiredRockets",
                "DroppedCargoContainers", "DeliveredCargo",
                "ParatrooperJumped", "ParatrooperLandedAlive"):
        L.append("  EventsFilter%s = %d;" % (flt, 1 if flt == "EnteredAlive" else 0))
    L.append("  Country = %d;" % country)
    L.append('  ObjectScript = "%s";' % object_script.lower())
    L.append("  OnEvents")
    L.append("  {")
    L.append("    OnEvent")
    L.append("    {")
    L.append("      Type = 59;")
    L.append("      TarId = %d;" % target_mcu)
    L.append("    }")
    L.append("  }")
    L.append("}")
    L.append("")
    m._blocks.append("\n".join(L))
    return idx


def add_radio_callout(b, *, x, z, y, radius, country, object_script, text,
                      duration=8, name="Callout"):
    """
    Convenience: register `text` as a subtitle and wire a position trigger
    to it in one call. Returns the subtitle's own MCU index (harmless if
    unused). See add_message_trigger for the zone/event semantics.
    """
    m = b.m
    sub_idx = m.idx()
    subtitle(m, sub_idx, x, y, z, m.text(text), duration, [COALITION_ALLIES])
    add_message_trigger(b, x=x, z=z, y=y, radius=radius, country=country,
                        object_script=object_script, target_mcu=sub_idx,
                        name=name)
    return sub_idx


def add_success_objective(b, *, x, z, y, need, name_lc, desc_lc,
                          coalition=COALITION_ALLIES, role="success",
                          name_text=None, desc_text=None):
    """MCU_Counter(need) -> MCU_TR_MissionObjective(Success=1).

    `role` is "success" or "failure" — which side of the campaign result
    this particular objective node represents. Its Index (`obj`, the
    MCU_TR_MissionObjective's own index — NOT the counter's) is what shows
    up as OBJID in the game's AType:8 log line when it fires, so it is
    recorded on the Builder's `meta` dict for write_mission_meta() to pick
    up. Recall from McuMissionObjective (PWCG): the in-game "Success" field
    on the node is a static label, not a live pass/fail bit — the campaign
    engine's actual signal is simply "did AType:8 fire for this OBJID".

    `name_text`/`desc_text`: the same strings already passed to m.text()
    for name_lc/desc_lc, kept here in plain form so make.py can assert the
    decoded .eng briefing actually matches what THIS call wrote -- not
    some other LC string that landed at the same index because a stray
    m.text() call earlier in the mission shifted everything after it (a
    real bug this project hit once: a radio callout's own m.text() calls,
    made before this one, silently pushed the objective text off its
    expected index).
    """
    m = b.m
    obj = m.idx()
    cnt = m.idx()
    mcu(m, "MCU_Counter", cnt, "Objective Counter", x, y, z,
        targets=[obj], extra=[("Counter", need), ("Dropcount", 0)])
    objective(m, obj, x, y, z, name_lc, desc_lc, coalition, 1,
              icon_type=0)
    if role == "failure":
        b.meta["failure_obj_id"] = obj
    else:
        b.meta["success_obj_id"] = obj
    b.meta["objective_coalition"] = coalition
    if name_text is not None:
        b.meta["_expected_objective_short"] = name_text
    if desc_text is not None:
        b.meta["_expected_objective_detail"] = desc_text
    return cnt


def write_mission_meta(b, path, *, mission_id, sector=None, date=None,
                       coalition=None, player_flight_prefix="CANARY",
                       turn=None, extra=None):
    """Write the <mission>.mission_meta.json sidecar the campaign engine's
    log_parser.py needs: which OBJID means success/failure, which coalition
    the objective is judged from, and the flight-name prefix used to spot
    this mission's own log lines (CANARY -> AType:10 NAME starts CANARY_).

    This is the whole bridge between "a generated .Mission file" and "the
    campaign engine can grade what happened when someone flew it" — nothing
    here is inferred from gameplay, it is exported at generation time from
    the same MCU indices the mission itself was built with.
    """
    meta = dict(b.meta)
    meta.update({
        "mission_id": mission_id,
        "sector": sector,
        "date": date,
        "turn": turn,
        "coalition": coalition if coalition is not None else meta.get("objective_coalition"),
        "player_flight_prefix": player_flight_prefix,
    })
    if extra:
        meta.update(extra)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
    return meta


# ------------------------------------------------------------------ helpers

def leg(from_x, from_z, to_x, to_z, frac):
    return (from_x + (to_x - from_x) * frac,
            from_z + (to_z - from_z) * frac)


def leg3(from_x, from_z, to_x, to_z, frac, alt, area):
    x, z = leg(from_x, from_z, to_x, to_z, frac)
    return (x, z, alt, area)


def delay(b, target_index, seconds):
    """Fire `target_index` `seconds` after the launch gate trips."""
    if target_index is None:
        return None
    t = b.m.idx()
    ox, oy, oz = b.origin
    mcu(b.m, "MCU_Timer", t, "Delay %ds" % seconds,
        ox, oy, oz, targets=[target_index],
        extra=[("Time", seconds), ("Random", 100)])
    b.on_go(t)
    return t


def briefing_icons(b, m, route, label):
    """Draw the planned route on the briefing map for the Allied coalition."""
    pts = [(x, z, alt) for (x, z, alt, _) in route]
    lc = m.text(label)
    add_route_icons(b, pts, COALITION_ALLIES, (40, 120, 220), lc)
    b.meta["_expected_target_name"] = label


def af_pos(name):
    a = AIRFIELDS[name]["position"]
    return a["xPos"], a["zPos"], a["yPos"]


WIND_CALM = [(0, 0, 0), (500, 0, 0), (1000, 0, 0), (2000, 0, 0), (5000, 0, 0)]


def wind(direction, speed):
    return [(0, direction, max(1, speed - 2)),
            (500, direction, speed),
            (1000, direction, speed),
            (2000, direction, speed + 2),
            (5000, direction, speed + 4)]
