# Discovery Watch internal architecture

Discovery Watch v1.33.4 keeps `discovery_watch.py` as the launcher and public
compatibility layer. Existing imports, startup commands and user workflows
therefore continue to work.

The stateless or narrowly stateful implementation is separated into
`discovery_watch_core`:

- `config.py` — version, paths and stable defaults.
- `detection.py` — journal classification, surface-signal interpretation and
  explainable anomaly rules.
- `exploration_criteria.py` — 23 offline astronomical criteria, including
  cross-body orbital, ring and system-material correlation.
- `intelligence.py` — the unified finding-policy registry. It is the shared
  source for Discovery History category, attention level, investigation
  eligibility, popup ownership and the Settings behaviour matrix.
- `preferences.py` — SQLite-backed settings and local data-maintenance helpers.
- `community.py` — optional EDSM requests and lead scoring.
- `presentation.py` — concise popup categories and notification wording.
- `theme.py` — shared cross-platform palette and ttk component styling used by
  both the main interface and discovery popup.

`Monitor`, `AlertPopup` and `App` intentionally remain in `discovery_watch.py`.
They contain the stateful database/journal pipeline and Tkinter lifecycle; moving
them in the same release would add risk without changing the commander's
experience. Future refactors can use the module boundaries above without
breaking the public launcher.

Home Overview and the Settings sections share the same canvas-backed page
container. It keeps content at its natural vertical height, follows the
available window width and exposes a visible scrollbar plus mouse-wheel and
keyboard navigation whenever a smaller display cannot show the full page.
Startup geometry is clamped to the reported screen dimensions instead of
assuming that every system can display the preferred 1280x860 window.

Visit-scoped intelligence is coordinated by `Monitor`. The persistent
`discovery_case_evidence` table links distinct FSS, DSS and organic journal
events to an investigation without replacing the original alert or historical
evidence. The Home view reads only the active confirmed visit key, so progress
from another system cannot be mixed into the current visit.

Experimental unidentified-contact reconciliation is also visit-scoped. A
confirmed visit key owns the journal-reported non-body total, a set of unique
identified contacts, one optional notification decision and one mutable
Discovery History record. `contact_reconciliations` retains the reported,
identified and remaining counts plus the lifecycle state without treating the
estimate as an anomaly or investigation.

The automated suite verifies both existing behavior and these boundaries. All
modules use only the Python standard library, matching the standalone app.

## Unified decision flow

Journal parsing and operational policy are deliberately separate. Detection
establishes what the journal reported. `finding_policy()` then establishes four
independent consequences: record the finding, create or progress an
investigation, identify the controlling popup setting, and assign its attention
level. The popup master switch is applied only at final delivery, so disabling
popups never discards evidence or changes investigation state.

Discovery History's evidence window derives its policy explanation from this
same registry. The Settings behaviour check validates the registry and selected
live journal paths in temporary files, while the normal reliability check
continues to exercise system context, deduplication and visit behaviour.

## Schema migrations

Derived-data changes are registered in `schema_migrations` and run once in
version order. Schema migration 1 removes obsolete mining-only Other
investigations while preserving the original journal, historical and Discovery
History evidence. Migration 2 adds visit-scoped contact reconciliation.
Diagnostics report both the current and expected schema
version. Existing one-off column upgrades remain defensive for databases from
very early standalone releases.
