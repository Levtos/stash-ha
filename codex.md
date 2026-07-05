# Codex Instructions — Stash HA

Lies zuerst `CLAUDE.md` in diesem Repo. Plus `Entity-Title-Mapper/codex.md` als Extraction-Pattern-Referenz (Pilot).

## MCP-Server

`einhornzentrale`. Nicht `haos_benni`.

## Deine Aufgabe (Hybrid-Pivot Phase 2)

**Extraction aus `bennis_toolbox/modules/stash_ha/` in dieses Repo.** Pattern wie beim Pilot `Entity-Title-Mapper` (title_classifier).

### Kurzfassung Schritte

1. Code in `bennis_toolbox/.../modules/stash_ha/` analysieren
2. 1:1 in `custom_components/stash_ha/` dieses Repos kopieren, Imports + Domain umstellen (`bennis_toolbox` → `stash_ha`)
3. Eigene `storage.py`, `services.py` falls nötig
4. manifest.json + hacs.json + Tests + CHANGELOG + README
5. Folge-PR in bennis_toolbox: Modul-Ordner löschen, Registry kürzen

### Detaillierte Schritte

→ Siehe `codex.md` im `Entity-Title-Mapper`-Repo (Pilot-Doku).

## Anti-Patterns

- ❌ Cross-Repo-Imports
- ❌ Lastenheft-Konsolidierung
- ❌ Auf alter VM Features bauen
