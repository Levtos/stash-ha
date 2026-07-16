# CLAUDE.md — Stash HA

## GitLab Workflow

- GitLab project `ha-platform/control` is the central workflow truth.
- Relevant work requires a GitLab issue in `ha-platform/control`.
- Before work starts, read the issue description and all issue notes.
- Document current state, decisions, scope changes, tests, commits, merge requests, blockers, and completion in the issue.
- Code changes happen in the matching GitLab repository. `origin` must point to GitLab.
- GitHub is only the public distribution and HACS mirror. Do not develop directly on GitHub and do not push manually to GitHub.
- Plane and Forgejo are historical sources only and are not used for active work.
- Full rules live in `ha-platform/control/AGENTS.md`, `ha-platform/control/CLAUDE.md`, and `ha-platform/control/docs/workflow/`.

## Project-Memory Bootstrap

- Before significant work, read the matching GitLab issue description and all notes, then `ha-platform/control/docs/workflow/README.md`, its linked workflow documents, and relevant `ha-platform/control` wiki pages.
- GitLab is the workflow truth. GitHub is only the distribution/HACS mirror; do not develop there directly. Plane is frozen historical context, and Forgejo is out of service.
- Stay inside the decided issue scope: no side quests and no overwriting foreign branches or dirty worktrees.
- Use the smallest sufficient verification for the risk tier. Stable changes to behavior, contracts, operations, or rules belong in the wiki; use live evidence when runtime behavior must be proved. Completion notes must document wiki impact, verification/tests, release state where applicable, and required live evidence.

## Safety

- Do not put secrets in issues, commits, logs, or reports.
- Do not touch production Home Assistant systems without explicit approval.
- No admin, delete, runner, or bulk actions without explicit approval.

**Status:** Eigenständige HACS-Repo, enthält alten Code. **Wird im Hybrid-Pivot mit aktuellem Stand aus `bennis_toolbox/modules/stash_ha/` überschrieben (Codex-Aufgabe).**
**Toolbox-Modul-ID (alt):** `stash_ha`
**Letzte Aktualisierung:** 2026-05-27

---

## Was ist dieses Modul

Stash-Mediaplayer-Integration. Bietet Mediaplayer-Slots, deren Status (`playing`/`paused`/`stopped`) für die `private_time`-Erkennung im Activity State konsumiert wird.

## Architektur-Kontext

Eigene HACS-Custom-Integration. Foundation lebt in `bennis_toolbox`, dieses Modul wird eigenständig.

**Pendant-Briefings:**
- `bennis_toolbox/CLAUDE.md` — Foundation + Pattern
- `einhornzentrale/CLAUDE.md` — YAML + Cut-Over-Status
- `einhornzentrale/docs/roadmap.md` — Phase 2 (Pivot)

## Aktueller Stand

- Code im Repo: alt
- Aktueller produktiver Code: `bennis_toolbox/modules/stash_ha/` — Status READY, 0.5.0
- HACS: aktuell über `bennis_toolbox`-Umbrella

## Migration im Hybrid-Pivot

Siehe `codex.md`. Reihenfolge: nach `title_classifier` (Pilot) und `wake_planner`.
