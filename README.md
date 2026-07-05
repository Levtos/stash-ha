# Stash HA

Standalone Home Assistant custom integration for Stash playback and library state.

This repository was extracted from `bennis_toolbox/modules/stash_ha/` on 2026-05-27 as part of the Hybrid Pivot. The integration exposes Stash library sensors, playback sensors, a cover image entity, a display-only media player, optional webhook refresh, and Stash metadata services.

## Services

Services are registered under the standalone domain:

- `stash_ha.metadata_scan`
- `stash_ha.metadata_clean`
- `stash_ha.metadata_generate`
- `stash_ha.metadata_auto_tag`
- `stash_ha.metadata_identify`
- `stash_ha.generate_screenshot`
- `stash_ha.save_activity`

Older service calls from the umbrella integration used `bennis_toolbox.stash_ha_*` and must be migrated manually.

## Migration Notes

- Domain: `bennis_toolbox` -> `stash_ha`
- Webhook path: `/api/stash_ha/stash_ha/webhook/<entry_id>`
- Unique IDs now use the `stash_ha` prefix, so existing entity registry entries may need migration.
