# Changelog

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
