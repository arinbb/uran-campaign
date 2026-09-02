# Uran — Уран

A persistent, historically-grounded IL-2 Sturmovik: Battle of Stalingrad co-op campaign.

**Live site:** https://arinbb.github.io/uran-campaign/

Two pilots — Sloan and Olorin — fly VVS fighters out of Pichuga against real
Luftwaffe units on their real November 1942 bases. Every mission gets graded
from the game's own log file, never from self-report. Results move a real
front line toward the historical positions it actually reached, never past
them. The story updates itself from what happened. Getting shot down isn't
the end of a career — only a kill with no bailout is.

## How it works

1. Missions are generated from real PWCG historical data (airfields, dated
   front-line snapshots, unit basing) — see `engine/`.
2. Download this turn's pack from `missions/` and fly it — install steps
   are in each pack's `INSTALL.txt`.
3. Drop your `missionReport(...).txt` log file(s) into the site's submit
   form. It opens a pre-filled GitHub issue with your log attached —
   nothing is uploaded anywhere else, no server, no token.
4. Once both pilots have flown and submitted, the campaign engine
   (`engine/campaign_engine.py`) is run by hand: it reads the new issues,
   grades each mission against the OBJID it recorded at generation time,
   updates the front line and pilot roster, writes a story chapter, and
   republishes `data/campaign_state.json` — the one file that is the
   entire state of the war. There's no scheduled job; it runs on request.
5. The site (`index.html`) is a static page that renders straight from
   that file. It is never hand-edited.

## Repo layout

- `index.html` — the campaign site (front-line map, roster, story, missions, log submission)
- `data/campaign_state.json` — the single source of truth for the whole campaign
- `data/frontlines/` — real dated Stalingrad front-line snapshots (PWCG data)
- `engine/` — the mission generator and turn-resolution engine (Python)
- `missions/` — downloadable mission packs for the current turn (added per turn)

## Status

Turn 0 is live: four missions over Rynok, Marinovka, Gumrak, and Pitomnik,
dated 19–23 November 1942 — the opening days of Operation Uran. Waiting on
Sloan and Olorin's first logs.
