# Changelog

## 0.7.0 - 2026-07-06

- Add a full per-slot dashboard package on top of the v0.6.0 slot title sensors
  (reusing the existing sticky `scene_id` → slot mapping; the slot logic is
  unchanged).
- Add per-slot dashboard media players (`media_player.stash_slot_1` …
  `_slot_4`): display-only, `supported_features=0`, no play/pause/seek/volume —
  they never pretend to control the stream. Active slot → `state=playing`,
  title/performers/studio/cover; empty slot → `state=idle`, title
  "Kein Stream aktiv", no cover.
- Add per-slot cover image entities (`image.stash_slot_1_cover` … `_slot_4`);
  empty slots show no image. Cover fetch/NSFW handling is shared with the global
  cover.
- Add per-slot studio, performers, tags and display-text sensors
  (`sensor.stash_slot_N_studio` / `_performers` / `_tags` / `_display_text`).
  Display text is a compact "Title — Studio" line.
- Slot title sensors now show the fixed placeholder "Kein Stream aktiv" for empty
  slots instead of None/"Unbekannt" (meant for the Title Classifier ignore
  list). Title sensors also expose `tags` now.
- The global `media_player.stash`, the global cover image, Currently Playing and
  Active Streams are unchanged. No media player control, no collage yet.

## 0.6.0 - 2026-07-06

- Add fixed Stash slot title sensors (`sensor.stash_slot_1_title` …
  `sensor.stash_slot_4_title`) for multiple simultaneously-active scenes.
- Enables the Title Classifier to watch each active stream as a separate source
  (one observable entity state per slot).
- Uses a sticky `scene_id` → slot mapping so a scene keeps its slot until it
  stops; scene reordering (last_played_at) never moves an existing slot (no
  flapping). New scenes take the lowest free slot; more than four active scenes
  fill only the four slots (no crash, no dynamic entities).
- Empty slots report no title (`native_value = None`) instead of an idle string,
  so no bogus `idle` catalog entry is created.
- Each slot exposes scene attributes when occupied (scene_id, title, cover_url,
  studio, performers, last_played_at, resume_time).
- Currently Playing, Active Streams, the cover image and the media player are
  unchanged; no media player redesign yet.

## 0.5.1 - 2026-07-06

- Fix: the Currently Playing sensor no longer joins multiple active Stash scene
  titles into a combined `A | B` state; it now reports the most-recently-active
  single title.
- Keeps the separate title/scene data available in the sensor attributes
  (`titles`, `scene_ids`, `count`).
- Prevents Title Classifier from storing combined `A | B` catalog entries.
- First public `0.x` release of the standalone `stash_ha` integration: lands the
  reviewable baseline and removes the superseded `stash_player` legacy.

## 0.5.0 - 2026-05-27

- Extracted `stash_ha` from `bennis_toolbox/modules/stash_ha/` into this standalone HACS repository.
- Switched Home Assistant domain, services, webhook path, and unique ID helpers to `stash_ha`.
- Added standalone config flow, platform setup files, service metadata, README, and tests.
