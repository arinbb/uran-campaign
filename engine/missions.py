#!/usr/bin/env python3
"""
The four missions.

Player unit throughout: 27th Fighter Air Regiment ("CANARY"), based at
Pichuga on the east bank of the Volga.  Two paras of two: each human leads
one, with an AI wingman.  Cold start on the ramp, Normal AI opposition.

Historical basing of every enemy unit named below is taken from PWCG's
squadron dataset for 23 November 1942.
"""

from build import *   # noqa: F401,F403

AUTHOR = "Uran series - Stalingrad co-op"

HOME = "Pichuga"
HOME_X, HOME_Z, HOME_Y = af_pos(HOME)

MP_FIGHTERS = [P("lagg3s29"), P("yak1s69")]


def new_mission(name, desc, date, time, temp, cloud_cfg, cloud_level,
                cloud_height, haze, wind_dir, wind_spd, mp_planes):
    m = Mission("")
    m.set_header(name, desc, AUTHOR)
    m._options = options_block(
        m, "stalingrad-winter", date, time, temp, 760,
        cloud_cfg, cloud_level, cloud_height, 0, 0, 0, haze,
        wind(wind_dir, wind_spd), mp_planes)
    return m


def player_flights(b, plane_def, payload_id, wm_mask, route, speed,
                   attack=None):
    """Two paras, both cold on the Pichuga ramp, two selectable slots."""
    add_airfield_object(b, HOME, COUNTRY_USSR)
    a = add_flight(
        b, name="CANARY", plane_def=plane_def, count=2, coop_slots=1,
        country=COUNTRY_USSR, callsign=CS_CANARY,
        ai_level=AI_VETERAN, wingman_ai=AI_NORMAL,
        payload_id=payload_id, wm_mask=wm_mask,
        field=HOME, route=route, cruise_speed=speed,
        attack=attack, ramp_slot=0, name_offset=0)
    # Second para: further down the ramp so the aircraft do not overlap, one
    # minute behind on the runway, and 200 m higher en route so the two pairs
    # are not trying to occupy the same block of air.
    route2 = [(x, z, alt + 200.0, area) for (x, z, alt, area) in route]
    bflt = add_flight(
        b, name="CANARY", plane_def=plane_def, count=2, coop_slots=1,
        country=COUNTRY_USSR, callsign=CS_CANARY,
        ai_level=AI_VETERAN, wingman_ai=AI_NORMAL,
        payload_id=payload_id, wm_mask=wm_mask,
        field=HOME, route=route2, cruise_speed=speed,
        attack=attack, ramp_slot=3, name_offset=2, launch_delay=60)
    return a, bflt


def climb_out(target_x, target_z, alt):
    """A short climb leg from Pichuga toward the target."""
    hdg = bearing(HOME_X, HOME_Z, target_x, target_z)
    cx, cz = move(HOME_X, HOME_Z, hdg, 9000.0)
    return (cx, cz, alt, AREA_INITIAL_CLIMB)


# =============================================================== MISSION 01

def mission_01():
    tgt_x, tgt_z, _ = af_pos("Rynok")          # the Volga crossing at Rynok
    m = new_mission(
        "01 - Frost and Smoke",
        "19 November 1942, 08:40. Operation Uran opens this morning in fog "
        "and blowing snow north-west of the city. While the guns work, "
        "II./St.G.2 is putting Stukas onto the Volga crossing at Rynok - the "
        "artery feeding 62nd Army in the factory district. 27 IAP is to be "
        "over Rynok at 2500 m and break up the attack before it reaches the "
        "ferries. Escort is expected: a Rotte of Bf 109 F-4 from II./JG52 out "
        "of Tuzov. Two paras. Cold start. Watch your throttle in this air - "
        "it is minus eighteen on the deck.",
        "19.11.1942", "8:40:0", -18,
        "winter\\02_Medium_06\\sky.ini", 600, 900, 1,
        300, 4, MP_FIGHTERS)
    b = Builder(m)
    b.origin = (HOME_X, HOME_Y + 150.0, HOME_Z)

    ingress = climb_out(tgt_x, tgt_z, 1800.0)
    route = [
        ingress,
        (tgt_x + 4000.0, tgt_z - 3000.0, 2500.0, AREA_ROUTE),
        (tgt_x, tgt_z, 2500.0, AREA_TARGET),
        (tgt_x - 4000.0, tgt_z + 3000.0, 2500.0, AREA_ROUTE),
        (tgt_x, tgt_z, 2400.0, AREA_TARGET),
        (HOME_X, HOME_Z, 700.0, AREA_LAND),
    ]
    player_flights(b, LAGG3, 0, 1, route, 330,
                   attack=(tgt_x, tgt_z, 8000, 900, 1, 0))

    # --- the Stukas: II./St.G.2, up from Skvorin, 45 km out to the south-west
    sk_x, sk_z, _ = af_pos("Skvorin")
    hdg_in = bearing(sk_x, sk_z, tgt_x, tgt_z)
    sx, sz = move(tgt_x, tgt_z, (hdg_in + 180.0) % 360.0, 46000.0)
    stuka_route = [
        (sx, sz, 2200.0, AREA_ROUTE),
        leg3(sx, sz, tgt_x, tgt_z, 0.55, 2200.0, AREA_ROUTE),
        (tgt_x, tgt_z, 1800.0, AREA_TARGET),
        leg3(tgt_x, tgt_z, sx, sz, 0.35, 1500.0, AREA_ROUTE),
        (sx, sz, 2000.0, AREA_ROUTE),
    ]
    stukas = add_flight(
        b, name="RAVEN", plane_def=JU87, count=6, coop_slots=0,
        country=COUNTRY_GERMANY, callsign=CS_RAVEN,
        ai_level=AI_VETERAN, wingman_ai=AI_NORMAL,
        payload_id=1, wm_mask="11",
        field=None, route=stuka_route, cruise_speed=300,
        parked=False, air_start_pos=(sx, sz, hdg_in), air_alt=2200.0,
        attack=(tgt_x, tgt_z, 1500, 600, 0, 1),
        land_at_field=False, activate=True, formation_type=1, formation_density=0)

    # --- escort: II./JG52 Rotte out of Tuzov, higher and behind
    ex_, ez_ = move(sx, sz, (hdg_in + 180.0) % 360.0, 4000.0)
    esc_route = [
        (ex_, ez_, 3400.0, AREA_ROUTE),
        leg3(ex_, ez_, tgt_x, tgt_z, 0.6, 3400.0, AREA_ROUTE),
        (tgt_x, tgt_z, 3200.0, AREA_TARGET),
        leg3(tgt_x, tgt_z, ex_, ez_, 0.4, 3000.0, AREA_ROUTE),
        (ex_, ez_, 3000.0, AREA_ROUTE),
    ]
    escort = add_flight(
        b, name="FINCH", plane_def=BF109F, count=2, coop_slots=0,
        country=COUNTRY_GERMANY, callsign=CS_FINCH,
        ai_level=AI_VETERAN, wingman_ai=AI_NORMAL,
        payload_id=0, wm_mask="10001",
        field=None, route=esc_route, cruise_speed=380,
        parked=False, air_start_pos=(ex_, ez_, hdg_in), air_alt=3400.0,
        attack=(tgt_x, tgt_z, 10000, 900, 1, 0),
        land_at_field=False, activate=True)

    # staggered launch once the flight is away
    delay(b, stukas["activate"], 30)
    delay(b, escort["activate"], 30)

    cnt = add_success_objective(
        b, x=tgt_x, z=tgt_z, y=1000.0, need=3,
        name_lc=m.text("Break up the attack on Rynok"),
        desc_lc=m.text("Destroy at least three of the six Ju 87 D-3 before "
                       "they reach the crossing."))
    add_kill_corridor(b, from_xz=(tgt_x, tgt_z), to_xz=(sx, sz), y=1500.0,
                      object_script=P("ju87d3"), country=COUNTRY_GERMANY,
                      check_planes=True, target_mcu=cnt, name="Stuka Watch")

    briefing_icons(b, m, route, "Rynok crossing")
    b.finish(HOME_X, HOME_Y + 100.0, HOME_Z, 300)
    return m, "01_Frost_and_Smoke", b


# =============================================================== MISSION 02

def mission_02():
    tgt_x, tgt_z, _ = af_pos("Marinovka")
    m = new_mission(
        "02 - Hammer at Marinovka",
        "21 November 1942, 10:15. The pincers are closing. Sixth Army's "
        "rear-area units are streaming west along the Marinovka road toward "
        "the Don crossing at Kalach, and 8th Air Army wants that road cut "
        "before dark. Each aircraft carries two FAB-50 under the wings. Make "
        "one pass with the bombs, then work the column with guns - but be "
        "quick about it: there is 2 cm flak on the halftracks, and a Rotte of "
        "Bf 109 G-2 has been reported over the road most of the morning. "
        "Bombs are on the release you use for rockets. Two paras. Cold start.",
        "21.11.1942", "10:15:0", -14,
        "winter\\00_clear_00\\sky.ini", 2500, 200, 0,
        250, 3, MP_FIGHTERS)
    b = Builder(m)
    b.origin = (HOME_X, HOME_Y + 150.0, HOME_Z)

    ingress = climb_out(tgt_x, tgt_z, 2000.0)
    route = [
        ingress,
        leg3(HOME_X, HOME_Z, tgt_x, tgt_z, 0.6, 2400.0, AREA_ROUTE),
        (tgt_x + 6000.0, tgt_z + 4000.0, 2000.0, AREA_ROUTE),
        (tgt_x, tgt_z, 1400.0, AREA_TARGET),
        leg3(tgt_x, tgt_z, HOME_X, HOME_Z, 0.4, 1800.0, AREA_ROUTE),
        (HOME_X, HOME_Z, 700.0, AREA_LAND),
    ]
    player_flights(b, LAGG3, 7, "1001", route, 330,
                   attack=(tgt_x, tgt_z, 2500, 600, 0, 1))

    # --- the column, driving west along the road toward Kalach
    ka_x, ka_z, _ = af_pos("Kalach")
    road_hdg = bearing(tgt_x, tgt_z, ka_x, ka_z)
    col = []
    kinds = [HORCH, OPEL, OPEL, SDKFZ251, OPEL, OPEL, SDKFZ251, OPEL]
    for i, kind in enumerate(kinds):
        cx, cz = move(tgt_x, tgt_z, (road_hdg + 180.0) % 360.0, 45.0 * i)
        col.append((kind, cx, cz, 60.0, road_hdg))
    dx, dz = move(tgt_x, tgt_z, road_hdg, 14000.0)
    add_ground_group(b, name="COLUMN", items=col, country=COUNTRY_GERMANY,
                     route=[(tgt_x, tgt_z), (dx, dz)], speed=25,
                     formation_type=4)

    # --- flak escorting the column, plus a static pair on the road
    flak = []
    for i, (off_hdg, off_d) in enumerate([(90.0, 220.0), (270.0, 260.0),
                                          (90.0, 900.0), (270.0, 1100.0)]):
        fx, fz = move(tgt_x, tgt_z, (road_hdg + off_hdg) % 360.0, off_d)
        flak.append((SDKFZ_FLAK if i < 2 else FLAK38, fx, fz, 60.0,
                     road_hdg, "FLAK %d" % (i + 1)))
    for i in range(3):
        fx, fz = move(tgt_x, tgt_z, (road_hdg + 180.0) % 360.0, 500.0 * i)
        fx, fz = move(fx, fz, (road_hdg + 90.0) % 360.0, 140.0)
        flak.append((MG34AA, fx, fz, 60.0, road_hdg, "MG %d" % (i + 1)))
    add_statics(b, flak, COUNTRY_GERMANY)

    # --- Bf 109 G-2 CAP, I./JG52 out of Lipovsky
    li_x, li_z, _ = af_pos("Lipovsky")
    cap_hdg = bearing(li_x, li_z, tgt_x, tgt_z)
    cx0, cz0 = move(tgt_x, tgt_z, (cap_hdg + 180.0) % 360.0, 22000.0)
    cap_route = [
        (cx0, cz0, 3000.0, AREA_ROUTE),
        (tgt_x + 5000.0, tgt_z - 5000.0, 3000.0, AREA_ROUTE),
        (tgt_x, tgt_z, 2800.0, AREA_TARGET),
        (tgt_x - 5000.0, tgt_z + 5000.0, 2800.0, AREA_ROUTE),
        (tgt_x, tgt_z, 2600.0, AREA_TARGET),
    ]
    cap = add_flight(
        b, name="ROOK", plane_def=BF109G, count=2, coop_slots=0,
        country=COUNTRY_GERMANY, callsign=4,
        ai_level=AI_VETERAN, wingman_ai=AI_NORMAL,
        payload_id=0, wm_mask=1,
        field=None, route=cap_route, cruise_speed=380,
        parked=False, air_start_pos=(cx0, cz0, cap_hdg), air_alt=3000.0,
        attack=(tgt_x, tgt_z, 10000, 1200, 1, 0),
        land_at_field=False, activate=True)
    delay(b, cap["activate"], 20)

    cnt = add_success_objective(
        b, x=tgt_x, z=tgt_z, y=500.0, need=5,
        name_lc=m.text("Cut the Marinovka road"),
        desc_lc=m.text("Destroy at least five vehicles of the withdrawing "
                       "column."))
    for vdef in (OPEL, SDKFZ251, HORCH):
        add_kill_corridor(b, from_xz=(tgt_x, tgt_z), to_xz=(dx, dz), y=200.0,
                          object_script=vdef[0], country=COUNTRY_GERMANY,
                          check_planes=False, target_mcu=cnt,
                          name="Column Watch")

    briefing_icons(b, m, route, "Marinovka road")
    b.finish(HOME_X, HOME_Y + 100.0, HOME_Z, 300)
    return m, "02_Hammer_at_Marinovka", b


# =============================================================== MISSION 03

def mission_03():
    tgt_x, tgt_z, _ = af_pos("Gumrak")
    m = new_mission(
        "03 - Sturmoviks",
        "22 November 1942, 09:00. Sixth Army is being pressed back into the "
        "steppe west of the city and Gumrak has become its main forward "
        "field. 65th ShAP is sending a shestyorka of Il-2 against the "
        "dispersals; 27 IAP provides close escort. The Sturmoviks will form "
        "up over Pichuga as you climb out - stay with them. I./JG3 'Udet' is "
        "at Golubinskiy and they are good. Do not chase. If you leave the "
        "Il-2 to go hunting, they will be shot down behind you. Yak-1 today. "
        "Two paras. Cold start.",
        "22.11.1942", "9:00:0", -16,
        "winter\\02_Medium_06\\sky.ini", 600, 900, 1,
        280, 5, MP_FIGHTERS)
    b = Builder(m)
    b.origin = (HOME_X, HOME_Y + 150.0, HOME_Z)

    ingress = climb_out(tgt_x, tgt_z, 1600.0)
    route = [
        ingress,
        leg3(HOME_X, HOME_Z, tgt_x, tgt_z, 0.6, 2200.0, AREA_ROUTE),
        (tgt_x + 3000.0, tgt_z + 3000.0, 2200.0, AREA_ROUTE),
        (tgt_x, tgt_z, 2000.0, AREA_TARGET),
        leg3(tgt_x, tgt_z, HOME_X, HOME_Z, 0.4, 1800.0, AREA_ROUTE),
        (HOME_X, HOME_Z, 700.0, AREA_LAND),
    ]
    player_flights(b, YAK1, 0, 1, route, 340,
                   attack=(tgt_x, tgt_z, 10000, 900, 1, 0))

    # Scoring: this one is not a body count.  The Il-2 leader's AttackArea
    # command reporting "area attacked" (OnReport type 2) is the mission being
    # done, so that report is wired straight to the objective counter, which
    # needs only one hit.  It has to exist before the flight that reports to
    # it, hence the ordering here.
    cnt = add_success_objective(
        b, x=tgt_x, z=tgt_z, y=1000.0, need=1,
        name_lc=m.text("Bring the Sturmoviks home"),
        desc_lc=m.text("The Il-2 of 65th ShAP must complete their attack on "
                       "Gumrak."))
    # Two independent ways to satisfy it, because the primary one leans on an
    # OnReport type that appears in no reference mission: either the Il-2
    # leader reports its area attack complete, or three of the vehicles it was
    # sent to kill actually die.  Either alone trips the objective.
    vcnt = m.idx()
    mcu(m, "MCU_Counter", vcnt, "Gumrak Damage Counter",
        tgt_x, 200.0, tgt_z, targets=[cnt],
        extra=[("Counter", 3), ("Dropcount", 0)])
    for vdef in (OPEL, SDKFZ251):
        add_kill_trigger(b, x=tgt_x, z=tgt_z, y=200.0, radius=6000,
                         object_script=vdef[0], country=COUNTRY_GERMANY,
                         check_planes=False, target_mcu=vcnt,
                         name="Gumrak Watch")

    # --- the Il-2s: air start over Pichuga so the escort can actually join up
    il_hdg = bearing(HOME_X, HOME_Z, tgt_x, tgt_z)
    ix, iz = move(HOME_X, HOME_Z, (il_hdg + 180.0) % 360.0, 5000.0)
    il_route = [
        (ix, iz, 900.0, AREA_ROUTE),
        leg3(ix, iz, tgt_x, tgt_z, 0.55, 1400.0, AREA_ROUTE),
        (tgt_x, tgt_z, 900.0, AREA_TARGET),
        leg3(tgt_x, tgt_z, HOME_X, HOME_Z, 0.5, 1000.0, AREA_ROUTE),
        (HOME_X, HOME_Z, 800.0, AREA_ROUTE),
    ]
    ils = add_flight(
        b, name="HAWK", plane_def=IL2, count=4, coop_slots=0,
        country=COUNTRY_USSR, callsign=CS_HAWK,
        ai_level=AI_VETERAN, wingman_ai=AI_NORMAL,
        payload_id=14, wm_mask=1,
        field=None, route=il_route, cruise_speed=300,
        parked=False, air_start_pos=(ix, iz, il_hdg), air_alt=900.0,
        attack=(tgt_x, tgt_z, 1800, 600, 0, 1),
        land_at_field=False, activate=True, formation_type=1, formation_density=0,
        on_target_report=cnt)
    delay(b, ils["activate"], 15)

    # --- I./JG3 up from Golubinskiy
    go_x, go_z, _ = af_pos("Golubinskiy")
    jg_hdg = bearing(go_x, go_z, tgt_x, tgt_z)
    jx, jz = move(tgt_x, tgt_z, (jg_hdg + 180.0) % 360.0, 26000.0)
    jg_route = [
        (jx, jz, 3600.0, AREA_ROUTE),
        leg3(jx, jz, tgt_x, tgt_z, 0.6, 3600.0, AREA_ROUTE),
        (tgt_x, tgt_z, 3200.0, AREA_TARGET),
        (tgt_x + 6000.0, tgt_z + 6000.0, 3000.0, AREA_ROUTE),
        (tgt_x, tgt_z, 2800.0, AREA_TARGET),
    ]
    jg3 = add_flight(
        b, name="SWIFT", plane_def=BF109G, count=4, coop_slots=0,
        country=COUNTRY_GERMANY, callsign=CS_SWIFT,
        ai_level=AI_VETERAN, wingman_ai=AI_NORMAL,
        payload_id=0, wm_mask=1,
        field=None, route=jg_route, cruise_speed=390,
        parked=False, air_start_pos=(jx, jz, jg_hdg), air_alt=3600.0,
        attack=(tgt_x, tgt_z, 10000, 1200, 1, 0),
        land_at_field=False, activate=True)
    delay(b, jg3["activate"], 90)

    # --- flak over Gumrak
    ff = []
    for i in range(6):
        a = 60.0 * i
        fx, fz = move(tgt_x, tgt_z, a, 1300.0)
        ff.append((FLAK38 if i % 2 else SDKFZ_FLAK, fx, fz, 130.0, a,
                   "GUMRAK FLAK %d" % (i + 1)))
    add_statics(b, ff, COUNTRY_GERMANY)

    # --- a few soft targets so the Il-2 attack has something to hit
    park = []
    for i in range(8):
        px, pz = move(tgt_x, tgt_z, 40.0 + 12.0 * i, 600.0 + 60.0 * i)
        park.append((OPEL if i % 2 else SDKFZ251, px, pz, 130.0, 40.0,
                     "GUMRAK PARK %d" % (i + 1)))
    add_statics(b, park, COUNTRY_GERMANY)

    briefing_icons(b, m, route, "Gumrak")
    b.finish(HOME_X, HOME_Y + 100.0, HOME_Z, 300)
    return m, "03_Sturmoviks", b


# =============================================================== MISSION 04

def mission_04():
    tgt_x, tgt_z, _ = af_pos("Pitomnik")
    m = new_mission(
        "04 - The Airlift",
        "25 November 1942, 13:00. The ring closed at Kalach two days ago. "
        "Sixth Army is inside it, and this morning the first transports came "
        "in from the Don airfields to Pitomnik. Goering has promised three "
        "hundred tons a day. 8th Air Army intends that he does not deliver "
        "it. This is a free hunt: no bombers to shepherd, no ground target, "
        "no schedule but the enemy's. A Kette of Ju 52 is inbound from the "
        "west-south-west at about 1500 m with a pair of Bf 109 F-4 somewhere "
        "above them. Find them before Pitomnik does. Yak-1. Two paras. "
        "Cold start.",
        "25.11.1942", "13:00:0", -20,
        "winter\\00_clear_00\\sky.ini", 3000, 200, 0,
        290, 6, MP_FIGHTERS)
    b = Builder(m)
    b.origin = (HOME_X, HOME_Y + 150.0, HOME_Z)

    # the transports run in from Tatsinskaya, WSW of the pocket
    ta_x, ta_z, _ = af_pos("Tatsinskaya")
    in_hdg = bearing(ta_x, ta_z, tgt_x, tgt_z)
    sx, sz = move(tgt_x, tgt_z, (in_hdg + 180.0) % 360.0, 52000.0)

    # intercept box: half-way down the transport track
    ix, iz = leg(sx, sz, tgt_x, tgt_z, 0.5)

    ingress = climb_out(ix, iz, 2200.0)
    route = [
        ingress,
        leg3(HOME_X, HOME_Z, ix, iz, 0.6, 3000.0, AREA_ROUTE),
        (ix, iz, 3000.0, AREA_TARGET),
        leg3(ix, iz, sx, sz, 0.35, 2800.0, AREA_ROUTE),
        (ix, iz, 2600.0, AREA_TARGET),
        leg3(ix, iz, HOME_X, HOME_Z, 0.5, 2000.0, AREA_ROUTE),
        (HOME_X, HOME_Z, 700.0, AREA_LAND),
    ]
    player_flights(b, YAK1, 0, 1, route, 340,
                   attack=(ix, iz, 10000, 1500, 1, 0))

    ju_route = [
        (sx, sz, 1500.0, AREA_ROUTE),
        leg3(sx, sz, tgt_x, tgt_z, 0.5, 1500.0, AREA_ROUTE),
        leg3(sx, sz, tgt_x, tgt_z, 0.85, 900.0, AREA_ROUTE),
        (tgt_x, tgt_z, 400.0, AREA_TARGET),
    ]
    ju = add_flight(
        b, name="PELICAN", plane_def=JU52, count=6, coop_slots=0,
        country=COUNTRY_GERMANY, callsign=CS_PELICAN,
        ai_level=AI_NORMAL, wingman_ai=AI_NORMAL,
        payload_id=0, wm_mask="11",
        field=None, route=ju_route, cruise_speed=230,
        parked=False, air_start_pos=(sx, sz, in_hdg), air_alt=1500.0,
        land_at_field=False, activate=True, formation_type=1,
        formation_density=0, fuel=0.7)
    delay(b, ju["activate"], 150)

    ex_, ez_ = move(sx, sz, (in_hdg + 180.0) % 360.0, 3000.0)
    esc_route = [
        (ex_, ez_, 2800.0, AREA_ROUTE),
        leg3(ex_, ez_, tgt_x, tgt_z, 0.5, 2800.0, AREA_ROUTE),
        leg3(ex_, ez_, tgt_x, tgt_z, 0.8, 2600.0, AREA_ROUTE),
        (tgt_x, tgt_z, 2400.0, AREA_TARGET),
    ]
    esc = add_flight(
        b, name="SWIFT", plane_def=BF109F, count=2, coop_slots=0,
        country=COUNTRY_GERMANY, callsign=CS_SWIFT,
        ai_level=AI_VETERAN, wingman_ai=AI_NORMAL,
        payload_id=0, wm_mask="10001",
        field=None, route=esc_route, cruise_speed=380,
        parked=False, air_start_pos=(ex_, ez_, in_hdg), air_alt=2800.0,
        attack=(ix, iz, 10000, 1500, 1, 0),
        land_at_field=False, activate=True)
    delay(b, esc["activate"], 150)

    # flak ring at Pitomnik, so diving on the last of them costs something
    ff = []
    for i in range(6):
        a = 60.0 * i + 15.0
        fx, fz = move(tgt_x, tgt_z, a, 1500.0)
        ff.append((FLAK38 if i % 2 else SDKFZ_FLAK, fx, fz, 140.0, a,
                   "PITOMNIK FLAK %d" % (i + 1)))
    add_statics(b, ff, COUNTRY_GERMANY)

    cnt = add_success_objective(
        b, x=ix, z=iz, y=1500.0, need=3,
        name_lc=m.text("Break the airlift"),
        desc_lc=m.text("Destroy at least three of the six Ju 52 before they "
                       "reach Pitomnik."))
    add_kill_corridor(b, from_xz=(sx, sz), to_xz=(tgt_x, tgt_z), y=1500.0,
                      object_script=P("ju523mg4e"), country=COUNTRY_GERMANY,
                      check_planes=True, target_mcu=cnt,
                      name="Transport Watch")

    briefing_icons(b, m, route, "Transport track")
    b.finish(HOME_X, HOME_Y + 100.0, HOME_Z, 300)
    return m, "04_The_Airlift", b
