# AGENTS.md — Stash HA

**Status:** Eigenständige HACS-Repo, enthält alten Code. **Wird im Hybrid-Pivot mit aktuellem Stand aus `bennis_toolbox/modules/stash_ha/` überschrieben (Codex-Aufgabe).**
**Toolbox-Modul-ID (alt):** `stash_ha`
**Letzte Aktualisierung:** 2026-05-27

---

## Was ist dieses Modul

Stash-Mediaplayer-Integration. Bietet Mediaplayer-Slots, deren Status (`playing`/`paused`/`stopped`) für die `private_time`-Erkennung im Activity State konsumiert wird.

## Architektur-Kontext

Eigene HACS-Custom-Integration. Foundation lebt in `bennis_toolbox`, dieses Modul wird eigenständig.

**Pendant-Briefings:**
- `bennis_toolbox/AGENTS.md` — Foundation + Pattern
- `einhornzentrale/AGENTS.md` — YAML + Cut-Over-Status
- `einhornzentrale/docs/roadmap.md` — Phase 2 (Pivot)

## Aktueller Stand

- Code im Repo: alt
- Aktueller produktiver Code: `bennis_toolbox/modules/stash_ha/` — Status READY, 0.5.0
- HACS: aktuell über `bennis_toolbox`-Umbrella

## Migration im Hybrid-Pivot

Siehe `codex.md`. Reihenfolge: nach `title_classifier` (Pilot) und `wake_planner`.
