# Campaign state — schema

One file, `data/campaign_state.json`, is the entire truth of the war. Everything
else (site, missions, story) is generated from it. It is never hand-edited during
a live campaign — only `engine/campaign_engine.py` writes to it, once per turn.

```jsonc
{
  "meta": {
    "name": "Uran",
    "version": 1,                  // bump if the schema shape changes
    "created": "2026-08-19"
  },

  "theaters": {
    // one entry per map the war can be fought on. Only "stalingrad" is
    // active at launch; more can be added later without touching pilots
    // or history.
    "stalingrad": {
      "map_key": "stalingrad-winter",       // il2lib.MAPS key
      "display_name": "Stalingrad",
      "active": true,
      "frontline_dates": [                  // real dated snapshots available
        "1942-03-01", "1942-08-01", "1942-09-06", "1942-10-11",
        "1942-11-23", "1942-12-23", "1943-01-20"
      ]
    }
  },

  "campaign": {
    "turn": 3,                      // increments each resolution
    "date": "1942-11-25",           // in-fiction date, advances by story days per turn
    "theater": "stalingrad",
    "status": "active"              // active | concluded
  },

  "front": {
    // the CURRENT front line, one polyline per coalition, in world metres
    // (same coordinate space as .Mission files: XPos=north, ZPos=east).
    // Starts as a copy of the nearest real dated snapshot; turn resolution
    // nudges points toward the next historical snapshot based on how the
    // sector fights went (see campaign_engine.advance_front).
    "as_of": "1942-11-23",
    "coalitions": {
      "allied": [[x, z], ...],
      "axis":   [[x, z], ...]
    }
  },

  "sectors": {
    // named contested areas. Each mission targets a sector; sector
    // "pressure" accumulates from mission results and is what actually
    // moves the front line at turn resolution.
    "rynok_crossing":  { "pos": [x, z], "pressure": 0, "history": [] },
    "marinovka_road":  { "pos": [x, z], "pressure": 0, "history": [] },
    "gumrak":          { "pos": [x, z], "pressure": 0, "history": [] },
    "pitomnik_airlift":{ "pos": [x, z], "pressure": 0, "history": [] }
  },

  "pilots": {
    // keyed by a slug the person picks once; NOT by LOGIN uuid, because a
    // slug is what the story and site refer to. The uuid(s) seen in their
    // logs are recorded so future log submissions auto-match.
    "sloan": {
      "display_name": "Sloan",
      "side": "VVS",
      "status": "active",           // active | kia  (kia only on a confirmed
                                     // kill with no bailout -- see below)
      "login_uuids": ["580c2eb7-..."],
      "callsign_names_seen": ["CANARY_Sloan"],
      "kills": 3,
      "deaths": 0,                  // confirmed KIA count, not shootdown count
      "times_downed": 1,            // shot down or crashed but bailed out --
                                     // survives, flies again, no status change
      "missions_flown": 4,
      "sorties": [
        // one entry per mission the parser could attribute to this pilot
        {"turn": 1, "mission": "01_Frost_and_Smoke", "result": "success",
         "kills": 2, "died": false, "bailed_out": false,
         "confirmed_kia": false, "took_off": true, "landed": true}
      ]
    }
  },

  "missions": [
    // history of every mission generated, across all turns
    {
      "turn": 1,
      "id": "01_Frost_and_Smoke",
      "sector": "rynok_crossing",
      "date": "1942-11-19",
      "coalition": 1,                     // 1=Allied, 2=Axis (il2lib convention)
      "success_obj_id": 68,               // recorded from mission_meta.json at generation
      "failure_obj_id": null,
      "status": "resolved",               // pending | resolved
      "result": "success",                // success | failure | not_flown
      "log_sets_applied": ["missionReport(2026-08-20_21-00-00)"],
      "briefing": {                       // decoded from the mission's .eng file
        "name": "01 - Frost and Smoke", "briefing": "19 November 1942, ...",
        "objective_short": "Break up the attack on Rynok",
        "objective_detail": "Destroy at least three of the six Ju 87 D-3 ...",
        "target_name": "Rynok crossing"
      }
    }
  ],

  "story": [
    {"turn": 0, "date": "1942-11-19",
     "title": "Uran",
     "text": "..."},
    {"turn": 1, "date": "1942-11-25",
     "title": "The Crossing Holds",
     "text": "..."}
  ]
}
```

## Design notes

- **Sectors, not the whole front, are what missions score.** A mission's
  success/failure adds or removes "pressure" at one sector. Turn resolution
  looks at net pressure per sector and nudges *that stretch* of the front
  line toward the next historical snapshot (if the Allied player side is
  winning its sectors) or holds it (if not). The front can move faster or
  slower than history, but the historical snapshots act as guardrails —
  it never moves past where the real front actually reached on that date,
  and the campaign date itself is capped at the last snapshot (1943-01-20,
  days before the surrender).

- **Pilots are keyed by a slug, matched via LOGIN uuid.** First submission
  for a new uuid prompts a "who is this" resolution (the engine can guess
  from the `NAME:` callsign prefix, e.g. `CANARY_Arin` → `arin`, but a
  brand-new uuid with no name match needs a one-line manual confirmation —
  logged as a pending item in the turn summary, not a blocker).

- **Everything is additive.** Old turns, old missions, old story chapters
  are never deleted — the site's story arc and pilot careers are read
  straight out of this history.

- **A shootdown isn't automatically a death.** The log's Kill event fires
  the moment your aircraft is destroyed, whether by an enemy or a crash —
  it says nothing about whether you survived. The engine only marks a
  pilot permanently `kia` when that same log has no matching bailout
  event for their aircraft. If you bailed out, you're recorded as
  `times_downed` and fly again next turn; only a kill with no bailout
  (no time or altitude to get out) is a confirmed loss.
