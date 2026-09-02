#!/usr/bin/env python3
"""
package_missions.py — zips each turn's missions into a ready-to-fly pack:
the .Mission file, every language file next to it, and an INSTALL.txt
written from that mission's own decoded briefing (see briefings.py).

Run after make.py (which produces engine/out/<id>.Mission + language files)
and after seed.py/resolve_turn (which puts the same briefing text into
campaign_state.json — this script re-decodes independently so it never
depends on state.json existing yet).

Output: engine/out/packs/<id>.zip -- these are what the site's mission
download buttons link to (as missions/<id>.zip once pushed to the repo).
"""
import glob
import os
import zipfile

from build import OUT
from briefings import briefing_for_mission

PACKS_DIR = os.path.join(OUT, "packs")
SITE_URL = "https://arinbb.github.io/uran-campaign/"

INSTALL_TEMPLATE = """Uran — {name}
{series}

INSTALL
-------
1. Copy every file in this folder into your game's mission folder:

     <IL-2 Sturmovik Great Battles install>\\data\\Missions\\Uran\\

   (Create the "Uran" folder the first time -- any name works, it's just
   for tidiness. Keep the .Mission file together with its language files
   -- they share the same name and the game reads both.)

2. Launch IL-2, open Multiplayer -> Coop, and Host/Create a session.
   Browse to the Uran folder and select {mission_file}.
   (Menu wording can vary a little by game version -- if you don't see
   "Coop" under Multiplayer, check the main Missions/Campaign browser --
   this is a text .Mission file like any other.)

3. Pick one of the two player slots and fly. {briefing_line}

BRIEFING
--------
{briefing}

Objective: {objective_short}
{objective_detail}

Target: {target_name}

AFTER YOU FLY
-------------
Find your mission log -- IL-2 writes it automatically, you don't need to
turn anything on:

  Documents\\1C SoftClub\\il-2 sturmovik great battles\\data\\logs\\

as one or more files named missionReport(<timestamp>)[N].txt from the
session you just flew. Go back to the campaign site and use "Submit a
result" to attach it. That log is graded directly against what actually
happened in the mission -- nobody has to self-report a win or a loss.

  {site_url}
"""


def build_pack(mission_id):
    mission_file = mission_id + ".Mission"
    src_mission = os.path.join(OUT, mission_file)
    if not os.path.exists(src_mission):
        raise FileNotFoundError(f"{src_mission} -- run make.py first")

    briefing = briefing_for_mission(OUT, mission_id)
    briefing_line = "Cold start." if "cold start" in briefing.get("briefing", "").lower() else ""

    install_txt = INSTALL_TEMPLATE.format(
        name=briefing.get("name", mission_id),
        series=briefing.get("series", "Uran series - Stalingrad co-op"),
        mission_file=mission_file,
        briefing_line=briefing_line,
        briefing=briefing.get("briefing", "(no briefing text found)"),
        objective_short=briefing.get("objective_short", ""),
        objective_detail=briefing.get("objective_detail", ""),
        target_name=briefing.get("target_name", ""),
        site_url=SITE_URL,
    )

    os.makedirs(PACKS_DIR, exist_ok=True)
    zip_path = os.path.join(PACKS_DIR, mission_id + ".zip")
    lang_files = sorted(glob.glob(os.path.join(OUT, mission_id + ".*")))
    lang_files = [f for f in lang_files if not f.endswith((".mission_meta.json",))]

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in lang_files:
            z.write(f, arcname=os.path.basename(f))
        z.writestr("INSTALL.txt", install_txt)

    return zip_path


if __name__ == "__main__":
    ids = sorted({
        os.path.basename(p)[:-len(".Mission")]
        for p in glob.glob(os.path.join(OUT, "*.Mission"))
    })
    for mid in ids:
        path = build_pack(mid)
        size = os.path.getsize(path)
        print(f"{mid} -> {path} ({size:,} bytes)")
