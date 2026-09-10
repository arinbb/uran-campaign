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

STEP 0 -- ONE-TIME SETUP (skip if you've already flown a Uran mission)
-----------------------------------------------------------------------
The whole campaign is graded from IL-2's own mission log, and log writing
is OFF by default. Turn it on once, before you fly anything:

  1. Open <IL-2 Sturmovik Great Battles install>\\Data\\Startup.cfg in a
     text editor.
  2. Find (or add) the line:

       mission_text_log = 1

     and make sure it's set to 1, not 0. Save the file.

If you skip this step, the mission will fly fine but no log file will be
written afterward, and there will be nothing to submit for grading.

INSTALL
-------
1. Copy every file in this folder into your game's COOPERATIVE mission
   folder (this is a coop mission -- it will not show up in the single-
   player Missions browser):

     <IL-2 Sturmovik Great Battles install>\\data\\Multiplayer\\Cooperative\\Uran\\

   (Create the "Uran" folder the first time -- any name works, it's just
   for tidiness. Keep the .Mission file together with its language files
   -- they share the same name and the game reads both.)

2. Launch IL-2 and open the Multiplayer -> Coop screen. One of you hosts
   (Create/Host a session) and browses to the Uran folder to select
   {mission_file}; the other joins that session from the server list (or
   by direct IP on a LAN). Exact menu wording can vary a little by game
   version -- if the labels don't match exactly, look for the coop/
   cooperative multiplayer screen rather than the single-player campaign
   browser.

   Playing over the internet (not the same LAN)? The host needs these
   ports forwarded to their machine: TCP 28000, 28100, and UDP 28000.

3. Pick one of the two player slots and fly. {briefing_line}

BRIEFING
--------
{briefing}

Objective: {objective_short}
{objective_detail}

Target: {target_name}

AFTER YOU FLY
-------------
Find your mission log (this only appears if Step 0 above was done before
you flew):

  Documents\\1C SoftClub\\il-2 sturmovik great battles\\data\\logs\\

as one or more files named missionReport(<timestamp>)[N].txt from the
session you just flew. (If you've redirected logs elsewhere via
Startup.cfg's text_log_folder setting, check there instead.) Go back to
the campaign site and use "Submit a result" to attach it. That log is
graded directly against what actually happened in the mission -- nobody
has to self-report a win or a loss.

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
