#!/usr/bin/env python3
"""Print the trigger graph of a .Mission so the wiring can be eyeballed."""
import sys, re
from validate import parse, field

def dump(path):
    blocks = parse(path)
    by = {}
    for b in blocks:
        i = field(b["body"], "Index")
        if i and b["kind"] not in ("OnEvent","OnReport","Point"):
            by[int(i)] = b
    def label(i):
        b = by.get(i)
        if not b: return "?%d" % i
        nm = field(b["body"], "Name") or ""
        return "%d:%s %s" % (i, b["kind"].replace("MCU_",""), nm.strip('"'))
    for i in sorted(by):
        b = by[i]
        t = field(b["body"], "Targets") or "[]"
        o = field(b["body"], "Objects") or "[]"
        tl = [int(x) for x in re.findall(r'\d+', t)]
        ol = [int(x) for x in re.findall(r'\d+', o)]
        ev = re.findall(r'Type = (\d+);\s*\n\s*TarId = (\d+);', b["body"])
        rp = re.findall(r'Type = (\d+);\s*\n\s*CmdId = (\d+);\s*\n\s*TarId = (\d+);', b["body"])
        if not (tl or ol or ev or rp): continue
        print(label(i))
        for x in tl: print("      -> %s" % label(x))
        for x in ol: print("      on %s" % label(x))
        for ty, tar in ev: print("      OnEvent(%s) -> %s" % (ty, label(int(tar))))
        for ty, cmd, tar in rp: print("      OnReport(%s of %s) -> %s" % (ty, label(int(cmd)), label(int(tar))))

for p in sys.argv[1:]:
    print("="*70); print(p); print("="*70)
    dump(p)
