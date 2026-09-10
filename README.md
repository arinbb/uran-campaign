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

## Installing and flying a mission

Full step-by-step instructions ship inside every mission pack's
`INSTALL.txt` (built fresh per-turn from the mission's own briefing), but
here's the same information up front so it's checkable without downloading
anything first.

### 0. One-time setup: turn on mission logging

The entire grading system depends on IL-2 writing a mission log file, and
that's **off by default**. Before either of you flies a single Uran
mission:

1. Open `<IL-2 Sturmovik Great Battles install>\Data\Startup.cfg` in a text
   editor.
2. Find (or add) the line `mission_text_log = 1` and make sure it's set to
   `1`. Save the file.

If this isn't set, the mission will fly normally but no log will be
written afterward — there will be nothing to submit, and no way to grade
the sortie.

### 1. Install the mission pack

Download the current turn's `.zip` from `missions/` and unpack every file
in it into your game's **cooperative** mission folder — not the
single-player Missions folder:

```
<IL-2 Sturmovik Great Battles install>\data\Multiplayer\Cooperative\Uran\
```

(The `Uran` subfolder name doesn't matter, but keep the `.Mission` file
together with its language files — they share a filename and the game
reads both.)

### 2. Host and join

Launch IL-2 and open the Multiplayer → Coop screen. One pilot hosts
(create/host a session) and browses to the `Uran` folder to select the
mission file; the other joins that session from the server list, or by
direct IP on a LAN. Exact menu labels can vary a little by game version —
look for the cooperative multiplayer screen, not the single-player
campaign browser, if the wording doesn't match exactly.

Playing over the internet rather than a shared LAN? The host needs these
ports forwarded to their machine: **TCP 28000, 28100** and **UDP 28000**.

### 3. Fly, then submit your log

Once you land (or don't), find your mission log:

```
Documents\1C SoftClub\il-2 sturmovik great battles\data\logs\
```

as one or more `missionReport(<timestamp>)[N].txt` files from the session
you just flew. (If `Startup.cfg`'s `text_log_folder` setting has been
changed, check there instead.) Use "Submit a result" on the site to attach
it — that log is graded directly against what actually happened, so
nobody has to self-report a win or a loss.

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
