#!/usr/bin/env python3
"""
Generates the four Uran missions AND their mission_meta.json sidecars, as a
proof that the meta-export mechanism (Builder.meta / write_mission_meta,
added in build.py) round-trips correctly: generate -> validate -> confirm
each meta file names a real MCU_TR_MissionObjective index that actually
exists in the compiled-to-text .Mission file.

This mirrors il2coop/make.py but is the campaign-engine copy, extended for
turn metadata. It stays a flat "generate the fixed 4" driver for now —
campaign_engine.py (turn resolution) is where per-sector, per-turn dynamic
mission selection will live; this script just proves the plumbing.
"""
import json
import os

from missions import mission_01, mission_02, mission_03, mission_04
from build import write_mission_meta, OUT

MISSIONS = [mission_01, mission_02, mission_03, mission_04]

# Historical date/sector tags for this fixed proof-of-concept batch — a real
# turn will pull these from campaign_state.json instead.
SECTOR_TAGS = {
    "01_Frost_and_Smoke": ("rynok_crossing", "1942-11-19"),
    "02_Hammer_at_Marinovka": ("marinovka_road", "1942-11-20"),
    "03_Sturmoviks": ("gumrak", "1942-11-21"),
    "04_The_Airlift": ("pitomnik_airlift", "1942-11-23"),
}


def main():
    for fn in MISSIONS:
        m, mission_id, b = fn()
        base = os.path.join(OUT, mission_id)
        m.write(base)

        sector, date = SECTOR_TAGS[mission_id]
        meta_path = base + ".mission_meta.json"
        meta = write_mission_meta(
            b, meta_path,
            mission_id=mission_id, sector=sector, date=date, turn=0,
            player_flight_prefix="CANARY")

        print(f"{mission_id}: success_obj_id={meta['success_obj_id']} "
              f"coalition={meta['coalition']} sector={sector}")

        # Prove the OBJID in the meta really is an MCU_TR_MissionObjective
        # index present in the generated .Mission text (not a stale/typo'd
        # index) -- the same file the game will actually read.
        with open(base + ".Mission", "r", encoding="utf-8") as f:
            text = f.read().replace("\r\n", "\n")   # files are CRLF on disk
        needle = f"MCU_TR_MissionObjective\n{{\n  Index = {meta['success_obj_id']};"
        assert needle in text, (
            f"{mission_id}: success_obj_id {meta['success_obj_id']} not "
            f"found as a real MCU_TR_MissionObjective in the .Mission file")

    print()
    print(f"Wrote {len(MISSIONS)} missions + meta sidecars to {OUT}")


if __name__ == "__main__":
    main()
