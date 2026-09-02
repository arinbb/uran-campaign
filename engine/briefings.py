"""
briefings.py — decode a mission's .eng localization file into the fields the
site and mission packs actually want to show a player.

IL-2 Great Battles language files are UTF-16 text with a BOM, one
"index : text" line per LC* string the .Mission file references by number
(LCName, LCDesc, ...). The Uran mission generator (missions.py/build.py)
always writes indices 0-5 in this order: name, briefing, series, objective
short line, objective detail, target name. This module only reads that
convention back out -- it does not touch the .Mission file itself.
"""
import os

FIELDS = {
    0: "name",
    1: "briefing",
    2: "series",
    3: "objective_short",
    4: "objective_detail",
    5: "target_name",
}


def decode_eng(path):
    """Return {"name":..., "briefing":..., "objective_short":..., ...} from
    a mission's .eng file. Missing indices are simply absent from the dict."""
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-16")
    out = {}
    for line in text.split("\n"):
        line = line.strip("\r").strip("﻿")
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if not key.isdigit():
            continue
        idx = int(key)
        if idx in FIELDS:
            value = value.strip()
            if value:
                out[FIELDS[idx]] = value
    return out


def briefing_for_mission(out_dir, mission_id):
    """Convenience: decode <out_dir>/<mission_id>.eng, or {} if it's missing
    (never fails the caller -- a missing briefing is cosmetic, not fatal)."""
    path = os.path.join(out_dir, mission_id + ".eng")
    if not os.path.exists(path):
        return {}
    try:
        return decode_eng(path)
    except (UnicodeDecodeError, OSError):
        return {}
