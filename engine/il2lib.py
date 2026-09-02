"""
il2lib.py — minimal, dependency-free writer for IL-2 Sturmovik: Great Battles
`.Mission` text files.

Field names, field order, numeric enumerations and the Chart/taxi transform in
this module were taken from real Mission-Editor-saved `.Mission` files and from
the serializers in PWCGCampaign / PylGBMiMec / SturmovikCampaign.  Nothing here
is guessed; see NOTES.md for provenance.

Coordinate convention (confirmed):
    XPos = northing (metres, increases north)
    ZPos = easting  (metres, increases east)
    YPos = altitude (metres AMSL)
    YOri = heading in degrees, 0 = north (+X), 90 = east (+Z)
"""

import math

# ---------------------------------------------------------------- enumerations

COUNTRY_NEUTRAL = 0
COUNTRY_USSR = 101
COUNTRY_GERMANY = 201

COALITION_NEUTRAL = 0
COALITION_ALLIES = 1
COALITION_AXIS = 2

MISSION_SINGLE = 0
MISSION_COOP = 1
MISSION_DOGFIGHT = 2

# AILevel — 0 (Player) is ILLEGAL in a cooperative mission
AI_PLAYER = 0
AI_NOVICE = 1
AI_NORMAL = 2
AI_VETERAN = 3
AI_ACE = 4

# StartInAir
START_AIR = 0        # airborne / engine running
START_RUNWAY = 1     # on the runway, engine warm
START_PARKED = 2     # parked, engine cold

# MCU_TR_Entity OnEvent types
EV_PILOT_KILLED = 0
EV_PLANE_CRASHED = 2
EV_PLANE_DESTROYED = 4
EV_PLANE_LANDED = 5
EV_PLANE_TOOK_OFF = 6
EV_DAMAGED = 12
EV_KILLED = 13
EV_PLANE_SPAWNED = 20

# MCU_TR_Entity OnReport types
RP_SPAWNED = 0
RP_TARGET_ATTACKED = 1
RP_AREA_ATTACKED = 2
RP_TOOK_OFF = 3
RP_LANDED = 4

# MCU_Icon IconId
ICON_NONE = 0
ICON_ATTACK_ARMOR_COLUMN = 502
ICON_ATTACK_AA = 504
ICON_ATTACK_ARTILLERY = 505
ICON_ATTACK_BUILDINGS = 507
ICON_COVER_BOMBERS = 152
ICON_WAYPOINT = 901
ICON_ACTION_POINT = 902
ICON_TAKEOFF = 903
ICON_LAND = 904
ICON_AIRFIELD = 905

LINE_NORMAL = 0
LINE_BOLD = 1
LINE_BORDER = 2
LINE_POSITION0 = 13

# Waypoint trigger radii used by PWCG
AREA_INITIAL_CLIMB = 1000
AREA_ROUTE = 3000
AREA_TARGET = 500
AREA_LAND = 300


# ------------------------------------------------------------------ geometry

def move(x, z, heading_deg, dist):
    """Advance from (x, z) on `heading_deg` for `dist` metres."""
    a = math.radians(heading_deg)
    return x + dist * math.cos(a), z + dist * math.sin(a)


def bearing(x1, z1, x2, z2):
    """Heading in degrees from point 1 to point 2."""
    return math.degrees(math.atan2(z2 - z1, x2 - x1)) % 360.0


def distance(x1, z1, x2, z2):
    return math.hypot(x2 - x1, z2 - z1)


def angdiff(a, b):
    """Smallest absolute difference between two headings, in degrees."""
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def f3(v):
    s = "%.3f" % v
    return "0.000" if s == "-0.000" else s


def f2(v):
    s = "%.2f" % v
    return "0.00" if s == "-0.00" else s


def fnum(v):
    """Format a number the way the Mission Editor does: 1 not 1.0."""
    if isinstance(v, str):
        return v
    if float(v) == int(float(v)):
        return str(int(float(v)))
    return ("%.2f" % float(v)).rstrip("0").rstrip(".")


# -------------------------------------------------------------------- writer

class Mission:
    """Accumulates blocks and hands out unique Index values."""

    def __init__(self, options_text):
        self._next = 2                      # ME starts object indices at 2
        self._blocks = []
        self._options = options_text
        self._loc = {}                      # localisation index -> text
        self._next_loc = 3                  # 0/1/2 are name/desc/author

    # -- index + localisation -------------------------------------------------

    def idx(self):
        i = self._next
        self._next += 1
        return i

    def text(self, s):
        """Register a localised string; returns its LC index."""
        i = self._next_loc
        self._next_loc += 1
        self._loc[i] = s
        return i

    def set_header(self, name, desc, author):
        self._loc[0] = name
        self._loc[1] = desc
        self._loc[2] = author

    # -- raw block emit -------------------------------------------------------

    def emit(self, kind, fields):
        """fields: list of (key, value_already_formatted) or raw strings."""
        out = [kind, "{"]
        for f in fields:
            if isinstance(f, tuple):
                out.append("  %s = %s;" % f)
            else:
                out.append(f)
        out.append("}")
        out.append("")
        self._blocks.append("\n".join(out))

    # -- rendering ------------------------------------------------------------

    def mission_text(self):
        parts = ["# Mission File Version = 1.0;", "", self._options, ""]
        parts.extend(self._blocks)
        parts.append("# end of file")
        return "\n".join(parts)

    def loc_text(self):
        lines = []
        for i in sorted(self._loc):
            lines.append("%d:%s" % (i, self._loc[i]))
        return "\r\n".join(lines) + "\r\n"

    def write(self, base_path):
        with open(base_path + ".Mission", "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write(self.mission_text())
        blob = self.loc_text().encode("utf-16-le")
        for ext in ("eng", "ger", "rus", "fra", "spa", "pol", "chs"):
            with open("%s.%s" % (base_path, ext), "wb") as fh:
                fh.write(b"\xff\xfe" + blob)


# ------------------------------------------------------------- Options block

MAPS = {
    # gui name             hmap folder            season prefix
    "stalingrad-winter": ("LANDSCAPE_Stalin_w", "wi", "stalingrad-1942"),
}


def options_block(mission, map_key, date, time, temperature, pressure,
                  cloud_config, cloud_level, cloud_height,
                  prec_level, prec_type, turbulence, haze,
                  wind_layers, mp_planes):
    folder, season, guimap = MAPS[map_key]
    L = []
    L.append("Options")
    L.append("{")
    L.append("  LCName = 0;")
    L.append("  LCDesc = 1;")
    L.append("  LCAuthor = 2;")
    L.append('  PlayerConfig = "";')
    for p in mp_planes:
        L.append('  MultiplayerPlaneConfig = "%s";' % p)
    L.append("  Time = %s;" % time)
    L.append("  Date = %s;" % date)
    L.append('  HMap = "graphics\\%s\\height.hini";' % folder)
    L.append('  Textures = "graphics\\%s\\textures.tini";' % folder)
    L.append('  Forests = "graphics\\%s\\trees\\woods.wds";' % folder)
    L.append('  Layers = "";')
    L.append('  GuiMap = "%s";' % guimap)
    L.append('  SeasonPrefix = "%s";' % season)
    L.append("  MissionType = %d;" % MISSION_COOP)
    L.append("  AqmId = 0;")
    L.append("  CloudLevel = %d;" % cloud_level)
    L.append("  CloudHeight = %d;" % cloud_height)
    L.append("  PrecLevel = %d;" % prec_level)
    L.append("  PrecType = %d;" % prec_type)
    L.append('  CloudConfig = "%s";' % cloud_config)
    L.append("  SeaState = 0;")
    L.append("  Turbulence = %d;" % turbulence)
    L.append("  TempPressLevel = 0;")
    L.append("  Temperature = %d;" % temperature)
    L.append("  Pressure = %d;" % pressure)
    L.append("  Haze = %s;" % haze)
    L.append("  WindLayers")
    L.append("  {")
    for alt, direction, speed in wind_layers:
        L.append("    %d :     %d :     %d;" % (alt, direction, speed))
    L.append("  }")
    L.append("  Countries")
    L.append("  {")
    for code, coalition in ((0, 0), (101, 1), (102, 1), (103, 1),
                            (201, 2), (202, 2), (203, 2),
                            (301, 3), (302, 3), (303, 3), (304, 3), (305, 3),
                            (401, 4), (402, 4)):
        L.append("    %d : %d;" % (code, coalition))
    L.append("  }")
    L.append("}")
    return "\n".join(L)


# ---------------------------------------------------------------- primitives

def pos_ori(x, y, z, yori=0.0, xori=0.0, zori=0.0):
    return [("XPos", f3(x)), ("YPos", f3(y)), ("ZPos", f3(z)),
            ("XOri", f2(xori)), ("YOri", f2(yori)), ("ZOri", f2(zori))]


def arr(vals):
    return "[" + ", ".join(str(v) for v in vals) + "]"


def entity(m, index, name, x, y, z, obj_index, enabled=1,
           on_events=None, on_reports=None):
    """MCU_TR_Entity — the handle every command/waypoint actually targets."""
    L = ["MCU_TR_Entity", "{",
         "  Index = %d;" % index,
         '  Name = "%s";' % name,
         '  Desc = "";',
         "  Targets = [];",
         "  Objects = [];"]
    L.append("  XPos = %s;" % f3(x))
    L.append("  YPos = %s;" % f3(y + 0.2))
    L.append("  ZPos = %s;" % f3(z))
    L.append("  XOri = 0.00;")
    L.append("  YOri = 0.00;")
    L.append("  ZOri = 0.00;")
    L.append("  Enabled = %d;" % enabled)
    L.append("  MisObjID = %d;" % obj_index)
    if on_events:
        L.append("  OnEvents")
        L.append("  {")
        for ev_type, tar in on_events:
            L.append("    OnEvent")
            L.append("    {")
            L.append("      Type = %d;" % ev_type)
            L.append("      TarId = %d;" % tar)
            L.append("    }")
        L.append("  }")
    if on_reports:
        L.append("  OnReports")
        L.append("  {")
        for rp_type, cmd, tar in on_reports:
            L.append("    OnReport")
            L.append("    {")
            L.append("      Type = %d;" % rp_type)
            L.append("      CmdId = %d;" % cmd)
            L.append("      TarId = %d;" % tar)
            L.append("    }")
        L.append("  }")
    L.append("}")
    L.append("")
    m._blocks.append("\n".join(L))


def plane(m, index, name, link_tr_id, x, y, z, yori, script, model, country,
          ai_level, coop_start, number_in_formation, start_in_air,
          payload_id, wm_mask, callsign, callnum, fuel=1.0, skin="",
          ai_rtb=1, spotter=-1, desc=""):
    m.emit("Plane", [
        ("Name", '"%s"' % name),
        ("Index", index),
        ("LinkTrId", link_tr_id),
        ("XPos", f3(x)), ("YPos", f3(y)), ("ZPos", f3(z)),
        ("XOri", "0.00"), ("YOri", f2(yori)), ("ZOri", "0.00"),
        ("Script", '"%s"' % script),
        ("Model", '"%s"' % model),
        ("Country", country),
        ("Desc", '"%s"' % desc),
        ("Skin", '"%s"' % skin),
        ("AILevel", ai_level),
        ("CoopStart", coop_start),
        ("NumberInFormation", number_in_formation),
        ("Vulnerable", 1),
        ("Engageable", 1),
        ("LimitAmmo", 1),
        ("StartInAir", start_in_air),
        ("Callsign", callsign),
        ("Callnum", callnum),
        ("Time", 60),
        ("DamageReport", 50),
        ("DamageThreshold", 1),
        ("PayloadId", payload_id),
        ("WMMask", wm_mask),
        ("AiRTBDecision", ai_rtb),
        ("DeleteAfterDeath", 1),
        ("Spotter", spotter),
        ("Fuel", fnum(fuel)),
        ("TCode", '""'),
        ("TCodeColor", '""'),
    ])


def vehicle(m, index, name, link_tr_id, x, y, z, yori, script, model, country,
            ai_level=AI_NORMAL, number_in_formation=0, desc=""):
    m.emit("Vehicle", [
        ("Name", '"%s"' % name),
        ("Index", index),
        ("LinkTrId", link_tr_id),
        ("XPos", f3(x)), ("YPos", f3(y)), ("ZPos", f3(z)),
        ("XOri", "0.00"), ("YOri", f2(yori)), ("ZOri", "0.00"),
        ("Script", '"%s"' % script),
        ("Model", '"%s"' % model),
        ("Desc", '"%s"' % desc),
        ("Country", country),
        ("NumberInFormation", number_in_formation),
        ("Vulnerable", 1),
        ("Engageable", 1),
        ("LimitAmmo", 1),
        ("AILevel", ai_level),
        ("DamageReport", 50),
        ("DamageThreshold", 1),
        ("DeleteAfterDeath", 0),
        ("CoopStart", 0),
        ("Spotter", -1),
        ("BeaconChannel", 0),
        ("Callsign", 0),
        ("PayloadId", 0),
        ("WMMask", 1),
        ("Fuel", 1),
        ("Callnum", 0),
        ("Skin", '""'),
        ("RepairFriendlies", 0),
        ("RehealFriendlies", 0),
        ("RearmFriendlies", 0),
        ("RefuelFriendlies", 0),
        ("RepairTime", 0),
        ("RehealTime", 0),
        ("RearmTime", 0),
        ("RefuelTime", 0),
        ("MaintenanceRadius", 0),
    ])


def airfield(m, index, name, x, y, z, yori, country, chart_points):
    """`fakefield` marker carrying the taxi/runway Chart the AI needs."""
    L = ["Airfield", "{",
         '  Name = "%s";' % name,
         "  Index = %d;" % index,
         "  LinkTrId = 0;",
         "  XPos = %s;" % f3(x),
         "  YPos = %s;" % f3(y),
         "  ZPos = %s;" % f3(z),
         "  XOri = 0.00;",
         "  YOri = %s;" % f2(yori),
         "  ZOri = 0.00;",
         '  Model = "graphics\\airfields\\fakefield.mgm";',
         '  Script = "LuaScripts\\WorldObjects\\Airfields\\fakefield.txt";',
         "  Country = %d;" % country,
         '  Desc = "";',
         "  Durability = 25000;",
         "  DamageReport = 50;",
         "  DamageThreshold = 1;",
         "  DeleteAfterDeath = 1;",
         "  Callsign = 0;",
         "  Callnum = 0;",
         "  Chart",
         "  {"]
    for ptype, px, py in chart_points:
        L.append("    Point")
        L.append("    {")
        L.append("      Type = %d;" % ptype)
        L.append("      X = %s;" % f3(px))
        L.append("      Y = %s;" % f3(py))
        L.append("    }")
    L.append("  }")
    L.append("  ReturnPlanes = 0;")
    L.append("  Hydrodrome = 0;")
    L.append("  RepairFriendlies = 0;")
    L.append("  RehealFriendlies = 0;")
    L.append("  RearmFriendlies = 0;")
    L.append("  RefuelFriendlies = 0;")
    L.append("  RepairTime = 0;")
    L.append("  RehealTime = 0;")
    L.append("  RearmTime = 0;")
    L.append("  RefuelTime = 0;")
    L.append("  MaintenanceRadius = 1000;")
    L.append("}")
    L.append("")
    m._blocks.append("\n".join(L))


def mcu(m, kind, index, name, x, y, z, targets=(), objects=(), extra=(),
        yori=0.0):
    fields = [("Index", index)]
    if name is not None:
        fields.append(("Name", '"%s"' % name))
        fields.append(("Desc", '""'))
    fields.append(("Targets", arr(targets)))
    fields.append(("Objects", arr(objects)))
    fields.extend([("XPos", f3(x)), ("YPos", f3(y)), ("ZPos", f3(z)),
                   ("XOri", "0.00"), ("YOri", f2(yori)), ("ZOri", "0.00")])
    fields.extend(extra)
    m.emit(kind, fields)


def subtitle(m, index, x, y, z, lc_text, duration, coalitions,
             r=255, g=255, b=255, targets=()):
    L = ["MCU_TR_Subtitle", "{",
         "  Index = %d;" % index,
         '  Name = "Subtitle";',
         '  Desc = "";',
         "  Targets = %s;" % arr(targets),
         "  Objects = [];",
         "  XPos = %s;" % f3(x),
         "  YPos = %s;" % f3(y),
         "  ZPos = %s;" % f3(z),
         "  XOri = 0.00;",
         "  YOri = 0.00;",
         "  ZOri = 0.00;",
         "  Enabled = 1;",
         "  SubtitleInfo",
         "  {",
         "    Duration = %d;" % duration,
         "    FontSize = 20;",
         "    HAlign = 1;",
         "    VAlign = 2;",
         "    RColor = %d;" % r,
         "    GColor = %d;" % g,
         "    BColor = %d;" % b,
         "    LCText = %d;" % lc_text,
         "  }",
         "  ",
         "  Coalitions = %s;" % arr(coalitions),
         "}",
         ""]
    m._blocks.append("\n".join(L))


def icon(m, index, x, y, z, lc_name, lc_desc, icon_id, coalitions,
         targets=(), line_type=LINE_NORMAL, rgb=(255, 255, 255)):
    L = ["MCU_Icon", "{",
         "  Index = %d;" % index,
         "  Targets = %s;" % arr(targets),
         "  Objects = [];",
         "  XPos = %s;" % f3(x),
         "  YPos = %s;" % f3(y),
         "  ZPos = %s;" % f3(z),
         "  XOri = 0.00;",
         "  YOri = 0.00;",
         "  ZOri = 0.00;",
         "  Enabled = 1;",
         "  LCName = %d;" % lc_name,
         "  LCDesc = %d;" % lc_desc,
         "  IconId = %d;" % icon_id,
         "  RColor = %d;" % rgb[0],
         "  GColor = %d;" % rgb[1],
         "  BColor = %d;" % rgb[2],
         "  LineType = %d;" % line_type,
         "  Coalitions = %s;" % arr(coalitions),
         "}",
         ""]
    m._blocks.append("\n".join(L))


def objective(m, index, x, y, z, lc_name, lc_desc, coalition, success,
              icon_type=0):
    L = ["MCU_TR_MissionObjective", "{",
         "  Index = %d;" % index,
         "  Targets = [];",
         "  Objects = [];",
         "  XPos = %s;" % f3(x),
         "  YPos = %s;" % f3(y),
         "  ZPos = %s;" % f3(z),
         "  XOri = 0.00;",
         "  YOri = 0.00;",
         "  ZOri = 0.00;",
         "  Enabled = 1;",
         "  LCName = %d;" % lc_name,
         "  LCDesc = %d;" % lc_desc,
         "  TaskType = 0;",
         "  Coalition = %d;" % coalition,
         "  Success = %d;" % success,
         "  IconType = %d;" % icon_type,
         "}",
         ""]
    m._blocks.append("\n".join(L))


# ------------------------------------------------------- airfield taxi chart

def build_chart(runway, origin_x, origin_z, origin_yori):
    """
    Convert a PWCG AirfieldLocations runway (world metres) into the local,
    rotated Chart the Airfield block wants.

        Point.X =  cos(t)*dx + sin(t)*dz
        Point.Y = -sin(t)*dx + cos(t)*dz     with t = origin_yori

    Order is a closed loop: park -> taxi out -> runway start -> runway end
    -> taxi in -> park.
    """
    t = math.radians(origin_yori)
    cos_t, sin_t = math.cos(t), math.sin(t)

    def conv(ptype, p):
        dx = p["xPos"] - origin_x
        dz = p["zPos"] - origin_z
        return (ptype,
                cos_t * dx + sin_t * dz,
                -sin_t * dx + cos_t * dz)

    park = runway["parkingLocation"]["position"]
    pts = [conv(0, park)]
    for p in runway["taxiToStart"]:
        pts.append(conv(1, p))
    pts.append(conv(2, runway["startPos"]))
    pts.append(conv(2, runway["endPos"]))
    for p in runway["taxiFromEnd"]:
        pts.append(conv(1, p))
    pts.append(conv(0, park))
    return pts


def ramp_offset_heading(park_x, park_z, park_yori, runway_start_x, runway_start_z):
    """
    Pick which side of the parking spot the flight lines up on, so the leader
    ends up nearest the runway.  (PWCG's own version of this has a
    radians/degrees bug; this is the corrected form.)
    """
    to_runway = bearing(park_x, park_z, runway_start_x, runway_start_z)
    plus90 = (park_yori + 90.0) % 360.0
    return (park_yori + 270.0) % 360.0 if angdiff(plus90, to_runway) < 90.0 \
        else plus90
