#!/usr/bin/env python3
"""
Static checks on a generated .Mission file.

The Mission Editor will not tell you which link is broken — it just refuses to
load the file — so everything cheap enough to check here gets checked here.
"""

import re
import sys
import os

BLOCK_RE = re.compile(r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*$')


def parse(path):
    """Returns (blocks, text). blocks = list of dicts with kind/index/fields."""
    lines = open(path, encoding="utf-8").read().split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        m = BLOCK_RE.match(lines[i])
        if m and i + 1 < len(lines) and lines[i + 1].strip() == "{":
            kind = m.group(2)
            depth = 0
            j = i + 1
            body = []
            while j < len(lines):
                body.append(lines[j])
                depth += lines[j].count("{") - lines[j].count("}")
                if depth == 0:
                    break
                j += 1
            blocks.append({"kind": kind, "body": "\n".join(body),
                           "line": i + 1})
            i = j + 1
        else:
            i += 1
    return blocks


def field(body, name):
    m = re.search(r'^\s*%s\s*=\s*(.+?);\s*$' % re.escape(name), body, re.M)
    return m.group(1) if m else None


def check(path):
    errs = []
    warns = []
    text = open(path, encoding="utf-8").read()
    blocks = parse(path)

    # --- braces balance
    if text.count("{") != text.count("}"):
        errs.append("brace mismatch: %d '{' vs %d '}'"
                    % (text.count("{"), text.count("}")))

    # --- collect indices
    indices = {}
    for b in blocks:
        if b["kind"] in ("Options", "OnEvent", "OnEvents", "OnReport",
                         "OnReports", "SubtitleInfo", "WindLayers",
                         "Countries", "Chart", "Point", "Planes", "Damaged"):
            continue
        idx = field(b["body"], "Index")
        if idx is None:
            continue
        idx = int(idx)
        if idx in indices:
            errs.append("duplicate Index %d (%s at line %d and %s at line %d)"
                        % (idx, indices[idx]["kind"], indices[idx]["line"],
                           b["kind"], b["line"]))
        indices[idx] = b

    # --- every referenced index must exist
    def refs(pattern, label):
        for m in re.finditer(pattern, text):
            for tok in re.findall(r'-?\d+', m.group(1)):
                v = int(tok)
                if v == 0:
                    continue
                if v not in indices:
                    errs.append("%s references missing Index %d" % (label, v))

    refs(r'Targets\s*=\s*\[([^\]]*)\]', "Targets")
    refs(r'Objects\s*=\s*\[([^\]]*)\]', "Objects")
    refs(r'TarId\s*=\s*(\d+)\s*;', "TarId")
    refs(r'CmdId\s*=\s*(\d+)\s*;', "CmdId")
    refs(r'MisObjID\s*=\s*(\d+)\s*;', "MisObjID")
    refs(r'LinkTrId\s*=\s*(\d+)\s*;', "LinkTrId")

    # --- co-op rules
    if field(text, "MissionType") != "1":
        errs.append("MissionType is not 1 (cooperative)")

    coop_planes = 0
    for b in blocks:
        if b["kind"] != "Plane":
            continue
        ai = field(b["body"], "AILevel")
        cs = field(b["body"], "CoopStart")
        nm = field(b["body"], "Name")
        if ai == "0":
            errs.append("plane %s has AILevel = 0 (Player) — illegal in a "
                        "cooperative mission" % nm)
        if cs == "1":
            coop_planes += 1
            if field(b["body"], "LinkTrId") == "0" and \
                    field(b["body"], "NumberInFormation") == "0":
                warns.append("coop plane %s is a leader with no entity" % nm)
    if coop_planes == 0:
        errs.append("no plane has CoopStart = 1 — nothing to select in the "
                    "lobby")

    # --- entity/plane back-references agree
    for b in blocks:
        if b["kind"] != "MCU_TR_Entity":
            continue
        mo = field(b["body"], "MisObjID")
        me = field(b["body"], "Index")
        if mo and int(mo) in indices:
            owner = indices[int(mo)]
            lt = field(owner["body"], "LinkTrId")
            if lt != me:
                errs.append("entity %s claims MisObjID %s, but that object's "
                            "LinkTrId is %s" % (me, mo, lt))

    # --- localisation
    base = os.path.splitext(path)[0]
    eng = base + ".eng"
    if not os.path.exists(eng):
        errs.append("missing %s" % os.path.basename(eng))
    else:
        raw = open(eng, "rb").read()
        if not raw.startswith(b"\xff\xfe"):
            errs.append(".eng is missing the UTF-16LE BOM")
        loc = set()
        for line in raw.decode("utf-16").split("\r\n"):
            if ":" in line:
                loc.add(int(line.split(":", 1)[0]))
        for name in ("LCName", "LCDesc", "LCAuthor", "LCText"):
            for m in re.finditer(r'%s\s*=\s*(\d+)\s*;' % name, text):
                v = int(m.group(1))
                if v not in loc:
                    errs.append("%s = %d has no entry in the .eng file"
                                % (name, v))

    # --- sanity on positions
    for b in blocks:
        x = field(b["body"], "XPos")
        z = field(b["body"], "ZPos")
        if x is None or z is None:
            continue
        if not (0 < float(x) < 360000) or not (0 < float(z) < 360000):
            warns.append("%s at line %d is off the map (X=%s Z=%s)"
                         % (b["kind"], b["line"], x, z))

    return errs, warns


if __name__ == "__main__":
    total_err = 0
    for p in sys.argv[1:]:
        errs, warns = check(p)
        total_err += len(errs)
        status = "FAIL" if errs else "ok  "
        print("%s  %s   (%d errors, %d warnings)"
              % (status, os.path.basename(p), len(errs), len(warns)))
        for e in errs:
            print("      ERROR: %s" % e)
        for w in warns[:12]:
            print("      warn : %s" % w)
        if len(warns) > 12:
            print("      warn : ... and %d more" % (len(warns) - 12))
    sys.exit(1 if total_err else 0)
