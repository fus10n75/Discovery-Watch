# Discovery Watch

A separate, standard-library Python/Tkinter application for monitoring Elite Dangerous journal files. 

## Run

Python 3.9+ with Tkinter is required. On Linux, install your distribution's `python3-tk` package if necessary. Run `python3 discovery_watch.py` from this folder (Windows: `py discovery_watch.py`). Choose the folder containing `Journal.*.log`, then click **Start monitoring**. The default is `~/Saved Games/Frontier Developments/Elite Dangerous`; browse if yours differs.

Monitoring begins at the **end of existing journal files** to avoid replaying old discoveries. New journal files are read from the beginning. It checks every second while the window is open. Detection is conservative: keyword/name matching in selected journal events and stellar phenomena Codex categories. It cannot detect objects the game hasn't written to the journal; a match is not confirmation of rarity.

Alerts and raw journal JSON are stored independently in `~/.discovery_watch/discoveries.sqlite3` (Windows: your user home `.discovery_watch` folder). Duplicate alerts from the same journal file/line/rule are ignored. Double-click a history row to view original JSON. You can disable popups and individual detection categories. No network, audio, tray service or background operation after closing the app.

The current interface has four main areas: **Home** for live status and recent discoveries, **Discovery history** for reviewing every saved finding (including anomaly leads), **System Explorer** for recorded systems and journal search, and **Settings** for basic alerts, advanced rules, data tools and diagnostics. Press **Ctrl+F** to focus the search box on the current searchable page and **F5** to refresh all views.

## v1.1 additions

- Search/filter the latest 200 history entries in the window (searches evidence and provenance too).
- Export **all** stored alerts as UTF-8 CSV or JSON, including original raw journal JSON, journal filename, line number, rule and timestamps. Exports are user-selected files; nothing is uploaded.
- Track system context independently for each journal file, preventing cross-file system misattribution.
- Detect journal file replacement by filesystem identity and reset its read position. Handle truncated files by clearing stale buffered data and system context.
- Added automated tests for multi-file system context and both export formats.

Run tests with `python3 -m unittest discover -v` from this directory. Exports contain original journal data and may include commander-identifying information: review before sharing. Search filters the on-screen 200-row history only; export includes the entire database. This version still does not establish that a name match is a rare or unique discovery.

## v1.2 — Journal Monitor

The **Journal Monitor** tab displays every *new* valid journal event read after Start, regardless of discovery filters. It shows receiving/idle/error status, journal file count and active file, event count, last reception time, event names and timestamps, and full JSON for a selected event. Invalid JSON and unreadable files are reported in the error line. The feed keeps up to 2,000 recent events in memory and is not a historical archive; clearing the display does not erase discovery evidence. Starting monitoring intentionally skips existing lines in already-present files; newly created journal files are read from their beginning. Perform an in-game action after clicking Start to confirm reception. On Linux, select the actual journal folder (often inside a Wine/Proton prefix) if the Windows default does not exist.

## v1.3 — Discovery Intelligence

The **System Explorer** tab lists systems with recorded exploration events, distinct scanned bodies, distinct mapped bodies, organic scan events and total stored exploration events. Select a system to see the last 500 relevant journal events; double-click an event to inspect its original JSON and journal provenance. Export all stored exploration events to JSON or CSV independently of discovery-alert exports.

The new `exploration_events` SQLite table stores journal-reported FSDJump, Location, CarrierJump, Scan, SAAScanComplete, ScanOrganic, FSSDiscoveryScan, FSSAllBodiesFound and FSSBodySignals events. Duplicate re-polling is ignored using file identity, line and original event content. Existing alert data remains intact. No internet access or external dependencies are added.

**Important limitations:** Existing journals are skipped at startup as before; only events arriving after Start are captured. System context is established by a new Location/FSDJump/CarrierJump or explicit system fields, so early scans can be unattributed until the game writes a location event. Body counts represent distinct recorded scan/mapping body names, not the system's full body inventory or first-discovery awards. Organic counts are event counts, not unique species. Replacing an old journal with a different file identity intentionally allows its events to be ingested again. The event details view shows the latest 500 per system; exports contain all stored exploration events. Exports may contain commander-identifying information; review before sharing.

Run the six automated tests using `python3 -m unittest discover -v`.

## v1.4 — Exploration Intelligence & Data Integrity

- Import a folder of historical `Journal.*.log` files with visible progress and an import summary.
- Stable content-based event keys suppress duplicate events across repeated imports, restarts, copied files and renamed journals. Existing v1.3 records are migrated automatically.
- Search System Explorer by system, body name or event type, with an **Incomplete only** filter.
- Exploration status is evidence-based: **Complete** requires `FSSAllBodiesFound`; **Incomplete** means an `FSSDiscoveryScan` exists without that marker; otherwise status remains **Unknown**.
- Run a SQLite integrity check that also validates stored raw JSON and required event fields.
- Create a consistent SQLite backup while the application is running.
- Import runs are audited in the local `import_history` table.

Historical import records the journal evidence available; it does not prove first discovery, guarantee that every body was scanned or infer facts absent from the journal. Backups and exports can contain commander-identifying data and should be reviewed before sharing.

Run the eight automated tests using `python3 -m unittest discover -v`.

## v1.5 — Anomaly Detection Engine

The **Anomalies** tab highlights explainable observations such as high-gravity bodies, valuable world classes, terraformable bodies, compact stars and signal-rich bodies. Every finding retains the original JSON, names the exact evidence field and has a transparent priority score. Findings can be marked reviewed or dismissed. These are review leads, not claims of rarity and not evidence of Raxxla.

## v1.6 — Live Exploration Assistant

The **Live Assistant** tab summarises the current system, recorded scans, mappings, signal events, unresolved anomalies and evidence-based completion status. It recommends follow-up only when the journal supports it—for example, completing an unfinished FSS scan or mapping a scanned body. A persistent session timeline records every event received while monitoring, with raw JSON available by double-clicking.

## v1.7 — Historical Journal Intelligence

Historical import now indexes **every valid journal event**, not only exploration events. The **Historical Intelligence** tab searches the full record by free text, system, body, source journal, event type and date range. Results retain the source journal/session, line number and complete raw JSON. Session summaries and import audit reports are stored locally, while stable keys make repeated imports safe. Live events are added to the same historical index automatically.

v1.7 includes eleven automated tests covering monitoring, imports, deduplication, anomaly rules, live assistance, complete historical indexing, session reconstruction, date filtering, backups and integrity checks.

## v1.7.1 — Megaship detection correction

Megaships are now detected directly when a journal event contains `"signalType": "Megaship"` or `"SignalType": "Megaship"`, regardless of the displayed signal name. Name-based detection remains as a fallback. Direct field matches are labelled **Megaship detected** and retain the complete original journal event as evidence.

## v1.7.2 — Fleet Carrier exclusion

Events classified by the journal as `"SignalType": "FleetCarrier"` or `"signalType": "FleetCarrier"` are explicitly excluded before megaship name matching. On startup, the application also removes Fleet Carrier false positives previously stored as megaship alerts in Discovery History. Fleet Carrier events remain available in Journal Monitor and Historical Intelligence.

## v1.7.3 — Installation detection correction

Installations are now detected directly when a journal event contains `"SignalType": "Installation"` or `"signalType": "Installation"`, regardless of the displayed signal name. Direct matches appear in Discovery History as **Installation detected**, retain their complete original journal evidence and continue to respect the Fleet Carrier exclusion.

## v1.8 — Configurable Signal Intelligence

The **Signal Rules** tab catalogues every distinct journal `SignalType`. Unknown types safely default to **Record**, while each type can be changed to **Alert**, **Record** or **Ignore** with a 0–100 priority and independent popup setting. Megaships and Installations default to Alert; Fleet Carriers remain explicitly ignored. The catalogue records observation counts, first and last sightings, event type and last system. Custom Alert rules include the exact matched field, policy and priority in their evidence.

## v1.9 — Review and usability workflow

Discovery History now supports acknowledgement, dismissal, editable investigator notes and JSON/CSV export of only the selected findings. Status and notes remain attached to their original journal evidence. Per-signal popup controls prevent routine recorded types from interrupting play, while the global popup option remains available as a master switch. The live dashboard, historical index, anomaly review and database migration remain compatible with existing v1.4–v1.7 databases.

v1.9 includes sixteen automated tests covering the full application history plus configurable signal policies, unknown-type handling, popup suppression, alert review, notes and selected-evidence export.

## v1.9.1 — Legacy database startup correction

Fixed startup with databases created by releases before v1.9. Discovery History now opens the database through the migration layer before reading the new alert status and notes fields. Existing findings and evidence are preserved; missing columns receive safe defaults of `new` and an empty note.

## v1.9.2 — System context recovery

When monitoring starts, the application now recovers the latest system name and address from each existing journal before moving its read position to the end. Historical entries are not replayed and do not create alerts. This allows new signals to receive the correct system name even when Discovery Watch was launched after the commander had already entered the system. Explicit `StarSystem`, `SystemName`, `StarSystemName` and compatible `System` fields are supported.

## v1.9.3 — Unregistered Comms Beacon detection

The application now detects the compound journal signature `"SignalName_Localised": "Unregistered Comms Beacon"` with `"SignalType": "Generic"`. It creates an **Unregistered Comms Beacon detected** finding and popup while leaving other Generic signals as record-only observations. The original event, matched name, type, system and journal provenance are preserved.

## v1.10.0 — Generic Signal Intelligence

The **Generic Signal Review** tab catalogues compound identities using `SignalName_Localised` and the internal `SignalName`. Previously unseen names default to **Review** and can optionally produce one first-seen notice. Each observed identity can be assigned Alert, Record, Ignore or Review; Exact or Contains matching; Off, Once per system or Always popup behaviour; an editable match pattern; and a 0–100 priority. Contains rules can cover variable or numbered names without converting every Generic journal signal into an alert. Unregistered Comms Beacon remains a built-in alert using a conservative name rule. Historical imports populate the catalogue without generating live review notifications.

v1.10.0 includes twenty-four automated tests, including first-seen handling, internal-name preservation, editable contains rules, variant matching, per-system popup suppression and disabling review notifications.

## v1.10.1 — Login journal system handover

Fixed the first finding after logging into Elite Dangerous being recorded as `Unknown system`. When the game creates a new journal, Discovery Watch now carries forward the last confirmed system name and address until the new journal supplies its own Location event. A SystemAddress-to-name database lookup provides a second safeguard. If a signal genuinely arrives before any system context is available, a later Location event in the same journal backfills the stored finding and its returned popup before display. Historical evidence is not replayed.

## v1.10.2 — Jump destination address precedence

Fixed destination signals being attributed to the departure system after the v1.10.1 login handover. An event's own `SystemAddress` now takes priority over inherited journal context. If the address is already known, the destination name is used immediately. If it is new, inherited context is cleared and the following Location or FSDJump event backfills the finding. On startup, stored alerts whose own address resolves to a different known system are repaired automatically.

## v1.10.3 — Titan and TouristBeacon signals

Journal events with `"SignalType": "Titan"` or `"SignalType": "TouristBeacon"` now create Discovery History findings. The default popup is enabled for each. To turn one off, select Titan or TouristBeacon in **Signal Rules**, untick **Popup**, then click **Alert** to save the setting. The main **Popup alerts** checkbox also disables all popups. You can switch either type to **Record** or **Ignore** from Signal Rules. Existing saved signal policies and popup preferences are retained when upgrading.

## v1.10.4 — Surface signal anomaly repair

Anomaly detection now processes both `FSSBodySignals` and `SAASignalsFound`. A body with one or more recorded biological or geological signals gets its own review finding; the existing `SIGNAL_RICH_BODY` rule still highlights bodies with eight or more signals. Ring hotspot counts are not treated as planetary surface signals. `HIGH_GRAVITY` continues to require a `Scan` event reporting at least 2.5 Earth gravities. On first launch this version also checks exploration and historical events already in the database for missing anomalies. It retains existing review and dismissal choices, and does not replay old Discovery History alerts.

## v1.10.5 — Nonhuman USS alerts

When the journal reports an `FSSSignalDiscovered` event with `"USSType":"$USS_Type_NonHuman;"` or `"USSType_Localised":"Nonhuman signal source"`, Discovery Watch adds a **Nonhuman signal source detected** finding and shows a popup. The USS rule appears as **Nonhuman USS** in Signal Rules; change its Alert/Record/Ignore policy or untick Popup there to adjust its behaviour. The main Popup alerts switch still controls all popups. The finding keeps the journal event and its resolved system address/name. Detection occurs when Elite Dangerous writes the signal event; a jump without that event cannot trigger an alert.

## v1.10.6 — Listening Post alerts

Discovery Watch now detects navigation entries containing either `"Type":"$ListeningPost:#index=...;"` or `"Type_Localised":"Listening Post"`. It adds a **Listening Post detected** finding with the resolved system and displays a popup by default. The matching is not tied to a single journal event name, so it also covers variations in how Elite publishes the navigation entry. Use **Listening Post** in Signal Rules to change its Alert/Record/Ignore policy or popup setting. The complete source event is retained in Discovery History as evidence.

## v1.10.7 — Separate Megaship and Installation switches

The former **Megaships / installations** checkbox has been split into independent **Megaships** and **Installations** checkboxes. Each switch controls new findings and popups only for its own category, and both choices are saved between launches. Both default to enabled when upgrading. Turning a category off does not remove findings already stored in Discovery History, and the unfiltered journal event remains visible in Journal Monitor.

## v1.10.8 — Unresolved non-body signal warnings

An **Unresolved signals** checkbox is now available and enabled by default. When an `FSSDiscoveryScan` event reports a positive `NonBodyCount`, Discovery Watch compares that number with individual `FSSSignalDiscovered` entries already received for the same system during the current visit. If contacts remain unaccounted for, it creates a popup and Discovery History finding showing the reported, observed and unresolved counts. This is a prompt to inspect the navigation panel or FSS, not evidence that any contact is rare or unusual. The warning requires a honk because Elite does not expose the complete navigation-panel list through the journal. The checkbox setting is remembered between launches.

## v1.10.9 — Recorded surface-signal anomaly repair

Every positive surface-signal count reported by `FSSBodySignals` or `SAASignalsFound` on a non-ring body now creates a **SURFACE_SIGNALS_RECORDED** entry in Anomalies. This includes Human, Guardian, Thargoid and other signal categories as well as Biological and Geological signals, even when only one signal is present. The explanation records the body, total, event type and per-category counts. Existing specialised Biological, Geological and eight-or-more **SIGNAL_RICH_BODY** findings remain available. Ring hotspot counts remain excluded. On startup, stored signal events are rechecked for the new rule while existing review states are preserved. Journal files that have never been monitored or imported still require **Historical Import** before their old events can be analysed.

## v1.11.0 — Delete all data and start fresh

The **System Explorer** database controls now include **Delete all data…**. After an explicit warning and confirmation, Discovery Watch stops monitoring, closes the database and permanently removes its stored discovery history, exploration records, imported history, anomalies, notes, review states, custom signal rules and preferences. Interface switches return to their fresh-install defaults and the next monitoring session creates a clean database. Elite Dangerous journal files, screenshots, settings and account data are never deleted. Use **Backup database…** first if the information may be needed later; the reset itself does not create a recovery copy.

## v1.11.1 — Optional anomaly history alerts

The **Discovery history** tab now includes an **Anomaly alerts** checkbox. It is off by default and its setting is remembered. When enabled, a new journal event with anomaly findings creates one combined Discovery History alert and one popup containing all matched anomaly rules and explanations for that event. The main **Popup alerts** switch still controls whether the popup is shown. When Anomaly alerts is disabled, findings continue to be stored normally in the Anomalies tab; only the extra Discovery History entry and popup are suppressed. Previously recorded anomalies are not replayed as new alerts when the checkbox is enabled.

## v1.12.0 — Usability and alert refinement

Discovery Watch now displays its version in the window title and main heading. A first-run guide explains folder selection, monitoring boundaries, journal limitations, honking and the quickest way to verify that live events are arriving. The guide remains available from **Alert Settings**.

The former **Signal Rules** tab is now **Alert Settings**. It groups the Megaship, Installation, unresolved-contact, stellar-phenomena, unknown-signal, anomaly, new-Generic-name and master popup controls above the existing per-signal policy table. The main notification choices are remembered between launches; advanced matching for individual Generic signals remains in **Generic Signal Review**.

Discovery History adds a **Level** column and filter. Findings are classified as **Important**, **Review** or **Informational** without changing their evidence or review state. Existing databases are migrated automatically and exports now include the level.

A compact banner continuously summarises the current system, stored findings, active anomalies, unresolved contacts and FSS completion. The Live Assistant retains its more detailed scan, mapping and follow-up information.

**Export diagnostic report…** in Alert Settings creates a support-oriented JSON report containing the application/runtime versions, database integrity and row counts, settings, journal filenames and sizes, current monitoring state and recent read errors. It deliberately excludes raw journal event contents. The report does contain local paths, settings and the current system name, so review it before sharing.

v1.12.0 includes forty-two automated tests. Linux binary/application packaging remains a separate future release so the standard-library Python edition stays portable and easy to audit.

## v1.12.1 — Megaship alert deduplication

Repeated journal reports for the same named Megaship during one system visit now create only one Discovery History finding and one popup. Differently named Megaships in the same system still produce separate alerts, and a Megaship can alert again after leaving and returning to the system. The same protection is applied to Installations, which can be repeated by the journal in the same way. When Elite provides no usable structure name, Discovery Watch conservatively keeps one alert of that type per visit because separate contacts cannot be identified reliably.

v1.12.1 includes forty-three automated tests.

## v1.13.0 — Interface Refresh

The main window now uses five primary tabs: **Home**, **Discovery history**, **System Explorer**, **Anomalies** and **Settings**. Existing specialist tools remain available in clearly labelled secondary pages instead of competing for space in the main navigation.

Home combines the former Live Assistant with an at-a-glance monitoring dashboard. Status cards show whether the journal is being received, the current system, active finding count and last event. Recent discoveries and the current-session timeline remain available with double-click access to the original evidence. Raw event monitoring is now under **Home → Journal diagnostics**.

Settings opens with plain-language switches for Megaships, Installations, Titans, Tourist Beacons, Nonhuman signal sources, Listening Posts, unidentified contacts, stellar phenomena, unknown names, anomaly history alerts, Generic review notices and the popup master switch. The full signal catalogue and Generic matching editors remain under Advanced pages. Alert, Record and Ignore are presented as **Alert**, **Save only** and **Ignore** without changing the stored policy values.

Historical journal search now sits inside System Explorer. Import, export, backup, database integrity, diagnostics, help and permanent reset actions are grouped under **Settings → Data & diagnostics**, with destructive reset controls visually separated from routine actions. Empty-state guidance, importance colouring, a recent-findings summary, scalable minimum window sizing, **Ctrl+F** search focus and **F5** refresh improve everyday use.

The monitoring engine, database format, migrations and existing preferences remain compatible with v1.12.1 and earlier databases. v1.13.0 includes forty-four automated tests.

## v1.13.1 — Remembered journals and live activity

Discovery Watch now remembers the last journal folder selected with **Browse** or successfully used to start monitoring. The saved path is restored on the next launch when it still exists. If it has moved or become unavailable, the application falls back to the normal journal location and asks the user to choose the new folder instead of repeatedly showing startup errors. The path is stored only in the local Discovery Watch preferences database.

**Settings → Basic alerts → Startup** adds an optional **Start monitoring automatically** switch. It is disabled by default and starts only when the remembered folder is available. Monitoring still begins at the end of existing journal files, so enabling automatic startup does not replay older discoveries.

The window header now contains a journal activity indicator with text as well as colour: grey means stopped, amber means monitoring and waiting, a short green pulse means new events are being read, and red reports a read/database error. The pulse stops automatically and does not run continuously while the journal is idle.

Discovery alerts now use a non-modal popup that closes after 15 seconds by default. The countdown pauses while the pointer is over the popup, **Keep open** disables the countdown for that window, and **Close now** closes it immediately. Settings can disable automatic closing or choose 5, 10, 15, 30 or 60 seconds. Closing a popup never dismisses or deletes its saved Discovery History finding. Help, evidence, error and confirmation windows remain open until closed manually.

Deleting all Discovery Watch data also clears the remembered folder and returns startup and popup controls to their defaults. v1.13.1 includes forty-five automated tests.

## v1.13.2 — Evidence window focus correction

Fixed Anomaly evidence opening minimised or behind the main application on some Linux window managers. User-requested evidence and editing windows are now attached to the Discovery Watch window, explicitly restored to normal state, raised after the desktop has mapped them and given a brief always-on-top hint before returning to normal stacking. This behaviour is also shared by Discovery History evidence, Home findings, live-session events, historical events, exploration evidence and the alert-note editor for consistency. Discovery alert countdown windows are unchanged.

v1.13.2 includes forty-six automated tests.

## v1.13.3 — Discovery popup redesign

Discovery alerts now use a compact dark information panel inspired by Elite Dangerous rather than a plain system list. Each finding is shown as its own card with a clear attention label, finding title, resolved system name and the journal-supported explanation. Up to three findings are shown in full; any additional findings are counted and remain available in Discovery History.

The popup includes an activity-style discovery icon, stronger visual hierarchy, an orange countdown progress bar and a prominent **Open history** action that restores Discovery Watch and selects the Discovery History page. It opens near the upper-right of the current display and briefly requests foreground placement without remaining permanently above other applications.

The existing behaviour is preserved: alerts are non-modal, saved before display, pause their countdown while hovered, close after the chosen timeout, and support **Keep open** and **Close**. Closing the panel never dismisses a saved finding. v1.13.3 includes forty-seven automated tests.

## v1.13.4 — Plotted destination context correction

Fixed the plotted or selected jump destination becoming the current system before the ship had actually jumped. Destination-reference events such as `FSDTarget` can still be indexed against the destination when its address is known, but they no longer replace the commander’s inherited location. Undocking and subsequent events therefore remain attached to the departure system until Elite writes a confirmed `FSDJump`, `Location`, `CarrierJump` or `LoadGame` event.

Startup context recovery applies the same rule, so a journal ending with an uncompleted plotted route restores the last confirmed location rather than the target. The existing event-address precedence for actual destination signal evidence and the later-Location backfill remain intact. v1.13.4 includes forty-nine automated tests.

## v1.14.0 — Known POIs on arrival

Discovery Watch can now remind you about points of interest it recorded on an earlier visit even when Elite Dangerous does not publish those signal events again. After a confirmed `FSDJump`, `CarrierJump`, `Location` or `LoadGame`, one clearly labelled **Known POIs on arrival** popup summarises previously saved Megaships, Installations, Tourist Beacons, Titans, Nonhuman signal sources, Listening Posts and Unregistered Comms Beacons for that system.

The reminder is cached local information rather than a fresh journal detection, does not create duplicate Discovery History entries, and appears only once per visit. A following `Location` event will not repeat a reminder already shown for the jump. Use **Settings → Basic alerts → Show known POIs when arriving in a system** to turn it off. The setting is enabled by default and the master popup switch still controls whether any popup is displayed. No network service or EDSM account is required. v1.14.0 includes fifty-two automated tests.

## v1.14.1 — Scrollable discovery popups

The findings area inside a discovery popup now scrolls while the heading, countdown and action buttons remain visible. Every finding is rendered instead of limiting the popup to three cards. Scroll with the mouse wheel on Linux or Windows, drag the scrollbar, or use the Up, Down, Page Up and Page Down keys. Long cached POI summaries and busy-system alert groups can therefore be read in full without enlarging the popup beyond the screen. v1.14.1 includes fifty-three automated tests.

## v1.14.2 — Named Generic findings

When the broad Generic signal type is configured to create alerts, its Discovery History finding now shows the actual signal name instead of only **Generic signal detected**. Discovery Watch prefers `SignalName_Localised`, falls back to the internal `SignalName`, and uses **Unnamed Generic signal** only when the journal provides neither field. The title retains **(Generic signal)** so its classification remains clear. If a more specific Generic rule already created a named finding, the broad signal-type policy does not add a duplicate. v1.14.2 includes fifty-four automated tests.

## v1.14.3 — Accurate Overview finding count

The **Home → Overview** discovery card now counts every non-dismissed Discovery History finding directly in the database. It is no longer calculated from the newest 200 rows loaded for display, which could incorrectly show exactly **200 active findings** when more records existed. The recent-findings panel remains deliberately limited for performance. New and acknowledged findings count as active; dismissed findings do not. v1.14.3 includes fifty-five automated tests.

## v1.14.4 — Current-system POI overview

The lifetime **Discoveries** counter on **Home → Overview** has been replaced by a more useful **Known POIs here** card. While monitoring, it summarises the POIs Discovery Watch has previously recorded in the commander’s current system, including a total and category breakdown such as **4 known POIs — 2 Megaships · 1 Tourist beacon · 1 Listening post**. It updates as the current system changes, reports **No known POIs** when appropriate and shows a clear waiting or stopped state when no live location is available. The Recent discoveries panel and full Discovery History remain unchanged. v1.14.4 includes fifty-six automated tests.

## v1.15.0 — Optional EDSM Community Intelligence

**Home → Overview** now includes a separate **Community Intelligence (EDSM)** section. EDSM access is disabled by default and can be enabled under **Settings → Basic alerts → Online community data**. After a confirmed `FSDJump`, `CarrierJump`, `Location` or `LoadGame`, Discovery Watch performs the public lookup on a background thread so journal monitoring and the interface remain responsive. Only the confirmed system name is sent; no commander name, journal event, API key or account credential is used.

Successful EDSM responses are cached in the local Discovery Watch database for seven days. Fresh cached responses avoid repeat requests. Stale data is displayed while a refresh is attempted, and remains available if EDSM or the internet is unavailable. Lookup errors never stop local journal monitoring. **Open system on EDSM** opens the current system in the default browser.

The panel reports EDSM's stated body count, the number of detailed catalogue bodies returned, locally recorded body names, catalogue completeness and primary-star information. It also compares local body names with EDSM and assigns conservative scores to possible leads such as incomplete community records, locally known bodies missing from the returned catalogue, unusual stellar types, complex multi-star systems and notable world types. Every such result is explicitly labelled **Possible leads (inferred, verify in game)**; it is not treated as proof of rarity, discovery ownership or a mystery connection.

Discovery Watch remains offline-first: all journal detection, history, anomaly analysis and known-POI reminders work with EDSM disabled or unavailable. Curated astronomical POI services such as the Galactic Exploration Catalog are intentionally left for a later, separately controlled integration. v1.15.0 includes sixty automated tests.

## v1.15.1 — Optional surface-signal popups

**Settings → Basic alerts → Review prompts** now includes **Surface-signal anomaly popups**. Turn it off to suppress popup and Discovery History interruption for `SURFACE_SIGNALS_RECORDED`, `SIGNAL_RICH_BODY`, `BIOLOGICAL_SIGNALS` and `GEOLOGICAL_SIGNALS`. These observations continue to be analysed and stored in the Anomalies tab, so no evidence is lost. Other enabled anomaly alerts—such as `HIGH_GRAVITY`—continue to create their normal combined finding and popup. The new setting is remembered and defaults to enabled for compatibility. v1.15.1 includes sixty-one automated tests.

## v1.15.2 — Planetary Mining Location popup control

This release corrects the overly broad v1.15.1 interpretation. Normal biological, geological, signal-rich and recorded-surface-signal anomaly popups again follow the main anomaly-alert setting without a separate surface-signal filter.

**Settings → Basic alerts → Review prompts** now contains the precise option **Show Planetary Mining Location popups**. It is off by default. When an event contains the exact journal classification `"Type_Localised":"Planetary Mining Location"`, Discovery Watch continues to catalogue the signal, index the source event and create any applicable Discovery History finding, but suppresses popup interruption. Enable the option if those specific mining-location findings should popup normally. v1.15.2 includes sixty-two automated tests.

## v1.16.0 — Notification Control & Field Reliability

The former **Advanced signal rules** page is now a clearer **Notification matrix**. Each signal type displays its effective behaviour as **Alert + popup**, **Alert silently**, **Catalogue only** or **Ignore**, alongside priority, popup state, observation count and provenance. Existing signal policies are retained during upgrade.

**Settings → Basic alerts → Notifications** adds **Keep alert popups above the game**, enabled by default. When enabled, discovery popups retain their always-on-top hint until closed without deliberately requesting keyboard focus. Disable it to restore the brief foreground hint used in earlier versions. Borderless or windowed game mode remains more reliable than exclusive fullscreen, and some Wayland compositors may still restrict cross-application stacking.

New Discovery History records store **Source** and **Notification decision** metadata. Opening evidence now explains the rule detail, whether the source was the live journal, and why its popup was requested or suppressed. Existing records migrate safely and are labelled as legacy when their historical popup decision cannot be reconstructed. JSON and CSV exports include the new explanation fields.

**Settings → Data & diagnostics → Replay journal test…** analyses one or more copied `Journal.*.log` files inside a disposable temporary database using fresh-install detection defaults. It reports event and system counts, findings, potential popups, suppressed structure duplicates, anomalies, unknown-system findings, event types and parsing errors. The replay cannot alter live Discovery Watch history, settings or the selected source journals, and its report can be saved as JSON. v1.16.0 includes sixty-five automated tests.

## v1.16.1 — Windows popup reliability

Alert popups are no longer transient children when **Keep alert popups above the game** is enabled. This prevents Windows from hiding a new alert with the minimized Discovery Watch main window. The popup is restored, raised and its always-on-top hint reinforced on the following interface cycle, without deliberately taking keyboard focus from Elite Dangerous.

**Settings → Basic alerts → Notifications** now includes **Play a sound with alert popups** and **Test popup and sound**. Windows uses its native warning sound; Linux and other platforms retain Tk's desktop bell. Popup construction errors are contained and reported in the application status instead of stopping the journal polling callback. v1.16.1 includes sixty-six automated tests.

## v1.16.2 — Home alert panel

The **Current session activity** journal-event table on Home has been replaced by **Latest discovery alerts**. This panel mirrors the newest popup group, including each finding's importance, title, system and full explanation in a scrollable view. It updates for every popup-eligible discovery even when the master popup switch is disabled, and remains visible after a timed popup closes. **Open Discovery History** provides direct access to the saved evidence. The detailed event timeline remains available through Journal diagnostics and Historical search. v1.16.2 includes sixty-six automated tests.

## v1.16.3 — Consolidated advanced alert rules

The separate **Notification matrix** and **Generic signal rules** Settings tabs are now one top-level **Advanced alert rules** page. Its **Signal types** view controls broad journal categories, while **Generic signal names** handles named contacts reported under `SignalType: Generic`. A plain-language introduction explains the difference and one shared search box filters both rule lists. All existing policies, match patterns, priorities, popup modes, observation counts and saved preferences are retained. v1.16.3 includes sixty-seven automated tests.

## v1.16.4 — Multi-monitor popup placement

**Settings → Basic alerts → Notifications → Popup monitor** now offers **Main monitor**, **Discovery Watch monitor** and **Mouse pointer monitor**. Main monitor is the default. On Windows, popup placement uses the selected display's usable work area rather than the width of the complete virtual desktop, preventing alerts from appearing at the far-right edge of a second monitor and keeping them clear of the taskbar. The selected monitor is remembered and the existing **Test popup and sound** button uses the same placement path. v1.16.4 includes sixty-eight automated tests.

## v1.16.5 — Simpler Home alerts

The duplicate **Recent discoveries** table has been removed from Home. **Latest discovery alerts** now uses the complete lower area, providing more room for the full popup explanation and multi-finding alert groups. The panel shows when the latest alert was received and retains **Open Discovery History** for reviewing all earlier findings and their evidence. A saved popup-eligible finding is still restored when Discovery Watch starts. v1.16.5 includes sixty-nine automated tests.

## v1.16.6 — Compact, non-focus-stealing alerts

Discovery popups now show only the field information needed during play: importance, signal name, signal type, journal event and system. The longer rule explanation remains available on Home and in Discovery History. Anomalies and specialist contacts use their body, USS or localised type fields when ordinary signal fields are unavailable; cached arrival reminders are explicitly identified as previously recorded information.

On Linux the alert is created hidden, marked as a desktop notification before it is mapped and excluded from keyboard focus. It can remain visible above Elite Dangerous without deliberately taking flight controls away from the game. Mouse actions for **Close**, **Keep open** and **Open history** remain available. v1.16.6 includes seventy automated tests.

## v1.16.7 — Linux popup visibility and larger Home

This release corrects a v1.16.6 Linux regression in which some desktop environments refused to display a Tk window marked with the `notification` type. Linux alerts now use a visible override-redirect window: it is not managed as a normal application window, does not deliberately request keyboard focus and remains available for mouse interaction. The compact signal-name, signal-type, event and system presentation is unchanged.

The main application now opens at 1280×860 with a 1000×680 minimum, providing enough initial height to see the **Latest discovery alerts** panel without manually enlarging the window. v1.16.7 includes seventy-one automated tests.

## v1.16.8 — Linux compositor compatibility

Linux popup handling now avoids both window modes found unreliable during field testing: some desktops hid `notification` windows, while some Wayland/XWayland compositors suppressed override-redirect windows. Alerts now use a managed `splash` window that does not request keyboard focus. After mapping, Discovery Watch verifies that Tk considers the alert viewable; if not, it retries as a normal topmost window. Compact popup content, monitor selection and automatic closing remain unchanged. v1.16.8 includes seventy-two automated tests.

## v1.16.9 — Native Wayland notifications

Discovery Watch now detects Wayland automatically and sends popup-eligible findings through the Linux desktop notification service. The compositor can therefore display the notification above a borderless Elite Dangerous window without permitting Discovery Watch to seize keyboard focus. Native notifications contain the same compact importance, signal name, signal type, journal event and system information. The Latest Alerts panel continues to receive the full explanation.

`notify-send` is used when available; it is supplied by the common `libnotify` package on most Linux desktops. If it is unavailable, Discovery Watch safely falls back to its Tk popup. Windows and X11 retain the custom scrollable popup. Desktop notification placement and timeout can still be governed by the user's compositor settings or Do Not Disturb mode. v1.16.9 includes seventy-three automated tests.

## v1.17.0 — Improved popup screen position

Custom Discovery Watch popups on Windows and X11 are now positioned 100 pixels inward from the selected monitor's right edge and 60 pixels below its top edge. This replaces the previous tight 30×40 pixel placement, keeping the alert in the upper-right area without making it look pinned against the display boundary. Monitor selection and Wayland-native notification placement are unchanged. v1.17.0 includes seventy-four automated tests.

## v1.17.1 — Windows DPI-aware popup placement

Windows monitor work areas are now converted from Win32 physical pixels into the logical coordinates used by Tk before popup placement is calculated. This corrects alerts that remained partly beyond the right edge on displays using 125%, 150% or other scaling levels. Negative coordinates used by monitors positioned to the left of the primary display are converted consistently. The 100-pixel right inset and 60-pixel top inset remain applied after scaling. v1.17.1 includes seventy-five automated tests.

## v1.18.0 — Surface Signal Intelligence

`SAASignalsFound` and `FSSBodySignals` entries are now presented as clear, first-class findings instead of only broad anomaly records. Each finding includes the system, body, localised signal type, count and source journal event. Thargoid and Guardian surface signals are marked **Important** and popup by default. Biological, Geological, Human and previously unknown categories are also recorded in Discovery History, but their popup behaviour is independently controlled under **Settings → Basic alerts → Surface-signal popups**. Disabling a popup never discards the journal evidence.

The original anomaly records—including `SURFACE_SIGNALS_RECORDED`, biological/geological observations and signal-rich bodies—remain available in the Anomalies tab. When a dedicated surface finding is created, Discovery Watch avoids producing a second broad anomaly popup for the same event. Ring hotspot entries remain excluded from planetary surface-signal detection. v1.18.0 includes seventy-eight automated tests.

## v1.18.1 — Cross-platform popup reliability

On Windows, **Main monitor** placement now uses Tk's own logical primary-screen dimensions instead of converting Win32 physical coordinates. The alert is additionally shown through Windows' native topmost/no-activation path, improving visibility above Elite Dangerous without deliberately taking keyboard focus.

On Wayland, Discovery Watch now requests the desktop notification ID and explicitly closes that notification when the selected popup timer expires. This works around desktop services that display notifications correctly but ignore `notify-send` expiry requests. Turning off automatic closing requests a persistent notification as before. Older notification tools remain supported through a safe fallback, although the desktop may control dismissal when no notification ID is available. v1.18.1 includes seventy-nine automated tests.

## v1.19.0 — Early FSS Surface Intelligence

`FSSBodySignals` is now presented explicitly as an early surface-intelligence stage. When the completed FSS reports a category such as Thargoid, Guardian, Biological or Geological, Discovery Watch creates a **Possible … surface signal** finding with the body, category and count before Detailed Surface Scanner mapping is required.

If mapping later produces `SAASignalsFound`, Discovery Watch saves a separate **… surface signal confirmed** record as stronger journal evidence. When the matching FSS alert was already shown for that body and category during the current system visit, the confirmation is recorded silently rather than producing a duplicate popup. A direct `SAASignalsFound` event still pops normally when no corresponding FSS alert was shown. Existing per-category popup choices continue to apply. v1.19.0 includes eighty automated tests.

## v1.19.1 — Stratum Tectonicas Watch

Discovery Watch now checks the `Genuses` list in `SAASignalsFound`. A mapped body reporting the Stratum genus creates an Important **Stratum genus detected — possible Tectonicas** lead. The wording deliberately stops short of claiming the species because the mapping event identifies only the genus.

When `ScanOrganic` later reports `Species_Localised: "Stratum Tectonicas"`—or its internal journal identifier—the app creates **Stratum Tectonicas confirmed**. Only the first Log/Sample/Analyse event observed for that body during the current visit creates the confirmation, preventing three repeated alerts while sampling. **Settings → Basic alerts → Surface-signal popups → Stratum leads and Tectonicas confirmations** controls interruption for both stages; disabling it still records the findings. v1.19.1 includes eighty-two automated tests.

## v1.20.0 — Discovery Case Engine

Related FSS, DSS and organic evidence now becomes a persistent investigation rather than an isolated stream of alerts. Cases progress through **Lead**, **Identified**, **Confirmed**, **Completed** or **Abandoned**, retaining their system, body, confidence, suggested next action and evidence count. The Home overview includes **Current investigations**, showing active work for the present system.

The optional **Warn before leaving unfinished discoveries** setting examines the departure system when a hyperspace `StartJump` event is written. If active investigations remain, Discovery Watch creates one reminder listing them without changing or cancelling the plotted jump. Once the actual jump completes, unfinished cases in the departed system are marked Abandoned. Completed Stratum sampling closes its case automatically.

## v1.21.0 — Commander Watchlists

**Settings → Advanced alert rules → Commander watchlists** lets commanders create personal targets without editing code. Each target has a name, a case-insensitive journal-text pattern, enable state, popup state and priority. Matching events create evidence-backed Discovery History findings; disabling a target stops matching, while disabling only its popup preserves the record. Controls allow targets to be added, enabled or disabled, switched between popup and silent recording, and deleted.

Watchlists complement the built-in explainable rules. For example, a commander can watch for `Ancient Test Beacon`, `$SAA_SignalType_Thargoid;` or another exact phrase found in copied journal evidence. Matching remains fully offline and uses only newly received journal events. v1.21.0 includes eighty-four automated tests.

## v1.21.1 — Popup clarity and diagnostics

**Unidentified system contacts** is now labelled **Experimental** and described as an explorer-focused review prompt that may include ordinary unresolved contacts. Its detection and remembered setting are unchanged.

The popup-monitor selector is now labelled **Windows/X11 only**. During a Wayland session it is disabled and the interface explains that the Linux desktop controls native-notification placement. Windows and X11 retain the existing Main monitor, Discovery Watch monitor and Mouse pointer monitor choices.

**Settings → Basic alerts → Notifications → Popup diagnostics…** reports the operating system, session type, effective notification method, whether monitor selection applies, automatic-close timer, always-above and sound settings, availability of `notify-send` and `gdbus`, and the calculated custom-popup work area where applicable. The same privacy-safe information is included in exported diagnostic reports; no raw journal events are added. v1.21.1 includes eighty-five automated tests.

## v1.21.2 — Windows-friendly Home layout

The Home overview no longer stacks **Current investigations** above **Latest discovery alerts**. They now share a resizable side-by-side lower area, substantially reducing the vertical space needed on Windows displays using interface scaling. Drag the divider to give either panel more width. Both panels expand with the main window; Current investigations has its own vertical scrollbar and Latest discovery alerts retains its existing scrollbar. v1.21.2 includes eighty-six automated tests.

## v1.21.3 — Focus-safe Windows popups

Windows popups now receive the native non-activating window style before they are shown. The Windows popup path no longer uses Tk `lift()` or topmost calls that could foreground Discovery Watch and take keyboard or controller input away from Elite Dangerous. Popup placement is centred on the selected Windows monitor and clamped to its reported bounds, avoiding the right-edge clipping seen with Windows display scaling and multi-monitor layouts. Linux popup behaviour is unchanged. v1.21.3 includes eighty-seven automated tests.

## v1.21.4 — Native Windows popup correction

Windows alerts are now displayed with the native `SW_SHOWNOACTIVATE` operation rather than Tk's mapping operation. Their final position is calculated from the actual Win32 wrapper dimensions and physical monitor work area, eliminating the remaining logical-DPI mismatch that could leave the right side clipped. Windows alerts are also never attached as transient children of the Discovery Watch main window. These changes prevent either the alert or main window being activated when an alert appears over Elite Dangerous. Linux behaviour is unchanged. v1.21.4 includes eighty-seven automated tests.

## v1.21.5 — Python 3.13 Windows monitor compatibility

Both Windows monitor operations now share one `MONITORINFO` ctypes structure and explicitly register the matching native signatures. This corrects the Python 3.13 `LP_MONITORINFO` callback exception that prevented v1.21.4 from reaching its native non-activating display and positioning operations. v1.21.5 includes eighty-seven automated tests.

## v1.21.6 — Visible non-activating Windows alerts

The Windows no-activation style is now applied to both the Tk content handle and its native top-level wrapper. Tk then maps the alert contents before the native code performs physical-monitor positioning and topmost reinforcement. This corrects the invisible-alert result in v1.21.5 while retaining the successful protection against taking focus from Elite Dangerous. v1.21.6 includes eighty-seven automated tests.

## v1.21.7 — Persistent above-game Windows alerts

Windows alerts with **Keep alert popups above the game** enabled now retain both Tk's topmost state and a recurring native `HWND_TOPMOST` reinforcement every 500 milliseconds. The native calls continue to use `SWP_NOACTIVATE`, and both popup handles retain `WS_EX_NOACTIVATE`, so the alert can remain above a borderless Elite Dangerous window without taking keyboard or controller focus. v1.21.7 includes eighty-seven automated tests.

## v1.21.8 — Remove Windows Tk focus regression

The Windows popup no longer calls Tk's `-topmost` operation, which field testing showed could activate Discovery Watch and take control away from Elite Dangerous. Above-game behaviour now relies exclusively on the recurring native `HWND_TOPMOST` request combined with `SWP_NOACTIVATE` and `WS_EX_NOACTIVATE`. Linux behaviour is unchanged. v1.21.8 includes eighty-seven automated tests.

## v1.21.9 — Windows source-encoding hardening

The executable Python source now contains ASCII characters only and includes an explicit UTF-8 source declaration. User-facing em dashes, bullets, arrows, ellipses and divider glyphs have been replaced with safe ASCII equivalents. This prevents Windows extraction or file-transfer tools from converting part of a UTF-8 sequence into an invalid legacy byte and causing Python's `Non-UTF-8 code` startup error. Popup behaviour is unchanged from v1.21.8. v1.21.9 includes eighty-seven automated tests.

## v1.22.0 — Accessible Settings navigation

Every Settings section now has its own vertical scrollbar and supports the mouse wheel, Page Up/Page Down and Home/End navigation. Basic Alerts no longer forces Discovery contacts, Review prompts and Notifications into three fixed columns; these sections are stacked vertically so controls remain reachable on narrower Windows displays and with increased display scaling. Surface-signal options are stacked for the same reason. A navigation reminder appears above Settings, `Ctrl+1` through `Ctrl+5` select the five main pages, and `Ctrl+Alt+1` through `Ctrl+Alt+3` open the three Settings sections directly. v1.22.0 includes eighty-eight automated tests.

## v1.23.0 — Native Windows notifications and experimental overlay

Windows now defaults to a native desktop notification delivered through the installed Windows PowerShell runtime. This dependable mode does not create or activate a Discovery Watch window, so it cannot remove keyboard or controller focus from Elite Dangerous. The notification uses the same compact Signal name, Signal type, journal event and system information as the existing alerts; Discovery History and the Home alert panel remain unchanged. Windows controls notification placement and final dismissal, and Focus Assist or Do Not Disturb may suppress notifications according to the commander's operating-system settings.

**Settings > Basic alerts > Notifications > Windows notification mode** can switch to **Experimental custom overlay**. This retains the styled Tk popup for continued development, with the known limitation that some borderless Windows games may remain above it. If native delivery is unavailable, Discovery Watch records that status and falls back to the custom overlay. Linux X11 and Wayland behaviour is unchanged. v1.23.0 includes ninety-one automated tests.

## v1.23.1 — Windows notification-area delivery

Native Windows mode now uses `Shell_NotifyIcon` and `NIF_INFO` as its primary delivery path. Discovery Watch temporarily adds a notification-area icon, asks Windows to display the alert, and removes the icon automatically after delivery. This route uses the running application's real window handle, requires no registered application identity and creates no focusable alert window. The PowerShell toast remains as a fallback if the Windows shell rejects notification-area delivery. Popup diagnostics and the status line identify the method that succeeded. The experimental custom overlay remains available unchanged. v1.23.1 includes ninety-two automated tests.

## v1.24.0 — Windows Overlay Preview

Settings now offers **Windows overlay preview**, a purpose-built Win32/GDI alert launched in an isolated child process. It is not a Tk window and is not owned by the Discovery Watch interface. The borderless overlay uses `WS_EX_NOACTIVATE`, `WS_EX_TOPMOST`, `WS_EX_TOOLWINDOW`, `WS_EX_LAYERED` and `WS_EX_TRANSPARENT`: it is designed to remain above a borderless game without entering Alt-Tab, accepting input or taking keyboard/controller focus. It uses the selected physical monitor's work area, appears near the bottom-right corner, displays compact discovery identity information and closes automatically after the selected timeout.

The native Windows notification remains the default stable choice. **Windows overlay preview** must be selected under **Settings > Basic alerts > Notifications > Windows notification mode**. If the overlay process cannot start, Discovery Watch tries native notification delivery before falling back to the legacy custom Tk overlay. Linux and Wayland paths are unchanged. v1.24.0 includes ninety-three automated tests.

## v1.24.1 — Windows Overlay Text Fix

The Win32 overlay now declares the full 64-bit-safe ctypes signatures used by its GDI painting path. This prevents Windows from truncating the drawing-context handle—a failure that could display the correctly positioned, non-activating overlay box without any text. The overlay also forces its initial paint after becoming visible, supports wrapped body text correctly and treats ampersands as ordinary discovery text. Focus protection, click-through behaviour, monitor placement and automatic closing are unchanged.

## v1.24.2 — Corrected Native Text Binding

The overlay's `TextOutW` heading call is now correctly bound to `gdi32`, rather than `user32`. The earlier incorrect binding explained both observed Windows results: v1.24.0 reached the paint handler and showed an empty box, while v1.24.1's strict startup binding stopped the child process before its window appeared. Unexpected child-process startup failures are now written to `windows_overlay_error.log` in the Discovery Watch data folder instead of being completely hidden by the no-console launch mode.

## v1.25.0 — Notification Reliability and Consolidation

The successfully field-tested Win32 option is now named **Windows game overlay** and is the default for new Windows configurations. Existing native-notification choices are preserved, while the retired experimental Tk mode automatically migrates to the game overlay. The working overlay remains click-through, non-activating, topmost over borderless Elite Dangerous and automatically dismissed by the selected timer.

Popup testing now offers realistic Megaship, surface-biology and anomaly examples so commanders can verify meaningful content before playing. Each notification attempt records a privacy-conscious delivery audit containing its method, launch result, source, finding count and compact title/system summary—never raw journal JSON. Popup diagnostics and exported diagnostics include this history, and the Windows overlay error log can be viewed directly from Settings.

A new built-in reliability check runs entirely in temporary files. It verifies that a plotted destination does not replace the current system, duplicate installations are suppressed, FSS and DSS surface-signal stages do not notify twice, known POIs are recalled on a return arrival, and findings retain a valid system name. The existing copied-journal replay tool remains available for testing a commander's own data. v1.25.0 includes ninety-six automated tests.

## v1.25.1 — Notable Stellar Phenomena Popup Fix

Notable Stellar Phenomena reported through `FSSSignalDiscovered` can also carry `SignalType: Generic`. The Generic signal catalogue's default record-only policy was incorrectly suppressing the dedicated Stellar phenomena popup after the finding had already been saved to Discovery History. Dedicated phenomenon and unidentified-signal rules now follow their own Basic alerts switches; signal-catalogue popup policy applies only to findings actually created by the signal-type catalogue. Multiple phenomena in the same system remain separate findings and are combined into the same notification batch. v1.25.1 includes ninety-seven automated tests.

## v1.25.2 — Calm Popup Summaries and History Reset

All popup delivery methods now receive the same concise, category-only summary. Repeated findings are collapsed to one line per category and system, quantities are never shown, and technical journal fields are omitted. Categories include Notable Stellar Phenomena, Thargoid and Guardian signals, Stratum Tectonicas, biological and geological signals, terraformable worlds, Earth-like worlds, water worlds, high-gravity worlds, structures and other configured discoveries. The popup exists only to draw attention and directs the commander to Discovery History for complete evidence. Individual database findings, journal evidence and the detailed Home alert panel are unchanged.

Discovery History now includes **Clear Discovery History...**. A confirmation explains the exact scope before deleting alert rows and clearing the Home latest-alert panel. Elite Dangerous journals, recorded exploration events, anomalies, preferences, custom signal rules, Commander Watchlists, notification diagnostics and EDSM cache data remain untouched. v1.25.2 includes ninety-nine automated tests.

## v1.26.0 — Unified Discovery Intelligence

The separate **Anomalies** main tab has been retired. Explainable anomaly analysis remains fully active behind the scenes, but its commander-facing records now appear in **Discovery History** with the same acknowledge, dismiss, notes, export and journal-evidence tools as every other finding. A new **Type** filter separates Signals and POIs, Notable worlds, Surface signals, Biological discoveries, Exploration reminders and Anomalies. Double-clicking an anomaly finding shows every matched rule, score, explanation, evidence field and the original journal JSON.

Anomaly recording and popup delivery are now independent. New anomaly and notable-world observations are always saved to Discovery History; **Settings → Basic alerts → Popup for notable worlds and anomalies** controls only whether they produce a notification. Existing anomaly rows migrate into Discovery History once, retain reviewed or dismissed state where possible, and never replay as popups or duplicate on later starts. The internal anomaly table remains intact for compatibility, diagnostics and future analysis.

First-observation Generic review notifications are also saved as Discovery History findings, so a popup no longer exists without a corresponding review record. Popups remain the concise, quantity-free category summaries introduced in v1.25.2, while full evidence stays in the unified history. v1.26.0 includes 102 automated tests.

## v1.27.0 — Reliability and Architecture

The standalone launcher has been divided into conservative internal modules without changing the commander's workflow. Configuration, journal detection rules, saved preferences, optional EDSM enrichment and popup wording now live in the private `discovery_watch_core` package. `discovery_watch.py` remains the launcher and compatibility layer, so existing startup commands and imports continue to work.

The stateful journal/database monitor and Tkinter interface deliberately remain together for this release. This avoids a high-risk UI lifecycle rewrite while creating clean boundaries for later maintenance. Architecture tests verify that the internal modules import independently, that the public compatibility API exposes the same functions, and that `Monitor`, `AlertPopup` and `App` retain their established entry points. See `ARCHITECTURE.md` for the module map. v1.27.0 includes 105 automated tests.

## v1.27.1 — Signal Identity Popups

Signal-based notifications now show the journal's useful identity in the concise form **Signal type — Signal name**, for example **Megaship — Generation Ship Artemis**. Localised names are preferred, followed by the internal signal name; when no distinct name exists, the popup safely displays only the signal type. Repeated records with the same system, type and name are collapsed, while differently named signals remain visible as separate lines.

The format applies consistently to Megaships, Installations, Generic contacts, Tourist Beacons, Titans, USS contacts and Listening Posts, and is shared by the Linux popup, native notification and Windows game-overlay paths. Non-signal findings retain their clear category wording, such as **Water world** or **Terraformable world**. Notifications remain quantity-free, and complete journal evidence remains in Discovery History. v1.27.1 includes 109 automated tests.

## v1.27.2 — Clearer Journal Evidence

Double-clicking a Discovery History finding now opens with a compact journal summary in the form **Event — Signal name — Signal type**, for example **FSSSignalDiscovered — Generation Ship Artemis — Megaship**. Localised names are preferred and unavailable fields are omitted cleanly, so non-signal events can appear simply as **Scan** rather than a block of JSON.

Data integrity is unchanged. The database still retains the complete original journal event, timestamp, system address, journal filename and line number. A new **Show raw journal data** button opens the full formatted JSON in a separate scrollable window whenever detailed verification or troubleshooting is needed. Exports continue to include the original evidence. v1.27.2 includes 112 automated tests.

## v1.27.3 — Arrival-to-Scan Popup Deduplication

Known Megaships and Installations announced by **Known POIs on arrival** are now remembered for the whole confirmed system visit. If a later discovery or FSS event reports the same named structure, Discovery Watch stores the fresh journal evidence and creates its Discovery History record, but suppresses the second popup. Its notification decision clearly records why the live alert was not shown.

Identity matching uses the confirmed system visit plus normalised localised and internal names. Differently named structures remain eligible for their own popup, disabling Known POIs on arrival leaves live alerts unaffected, and a genuine departure and return starts a fresh visit with a new arrival reminder. `FSDTarget` and other plotted-destination events still cannot change the current-system context. v1.27.3 includes 115 automated tests.

## v1.28.0 — System Visit Intelligence

The Home overview now presents **Current visit intelligence** rather than a list limited to unfinished investigations. Evidence from `FSSBodySignals`, `SAASignalsFound` and `ScanOrganic` is linked by system, body and investigation target for the confirmed visit. Each row shows its strongest stage and the number of distinct supporting journal events, while the summary separates Leads, Identified, Confirmed and Completed work. Completed discoveries remain visible until departure so the current visit can be understood as a whole.

Organic sampling now advances the matching Biological surface-signal investigation: Log and Sample events confirm the biological lead, and Analyse completes it. Stratum retains its more specific parallel investigation. Repeated copies of identical journal evidence do not inflate the visit counts. A confirmed jump or location change starts a clean visit view without deleting earlier Discovery History or exploration records.

**Ancient Probe** is now a first-class Important POI. Discovery Watch recognises localised and internal Ancient Probe names across relevant journal events, records the full evidence, produces the existing calm category-only popup, and includes the POI in later **Known POIs on arrival** reminders. Detection remains fully offline. v1.28.0 includes 119 automated tests.

## v1.28.1 — Megaship Identity Fix

Arrival-to-FSS popup deduplication now compares every usable Megaship identity supplied by the journal rather than only the preferred display name. Internal identifiers such as `$MULTIPLAYER_SCENARIO14_TITLE;` and a corresponding localised name such as **Generation Ship Artemis** are retained as aliases for the same contact. If either alias matches a later FSS report during the visit, its fresh journal evidence is saved to Discovery History without showing the Megaship popup again.

Stored Known POIs are merged by overlapping aliases as well. One Megaship can therefore no longer appear twice in the arrival count merely because one record contains its internal name and another contains its localised name. Contacts with genuinely different internal and localised identities remain separate and popup eligible. Installations use the same safer identity machinery. v1.28.1 includes 121 automated tests.

## v1.29.0 — Interface Unification

The main application now uses the same visual language as the discovery popup: a dark graphite background, raised charcoal panels, orange interaction accents, cyan intelligence text, high-contrast evidence text and consistent status colours. Home cards, navigation tabs, tables, form fields, scrollbars, Settings sections and user-requested evidence windows are styled from one shared theme definition rather than unrelated operating-system defaults.

The Home header has a clearer monitoring-console presentation, the primary **Start monitoring** action uses the popup orange, and current-system information uses the same cyan language as popup evidence. Discovery History now distinguishes Important, Review, Informational, acknowledged and dismissed rows against the dark table surface. Destructive history and database-reset actions have a consistent warning treatment. A duplicate Dismiss button in Discovery History has also been removed.

The shared `discovery_watch_core/theme.py` module is the single source for interface and popup colours. It uses portable `ttk` styling with a controlled fallback when a platform theme is unavailable; native confirmation and file-selection dialogs remain native. This release changes presentation only: journal detection, database schema, stored evidence, popup timing, notification delivery and navigation behaviour are unchanged. v1.29.0 includes 123 automated tests.

## v1.29.1 — Megaship Duplicate Reconciliation

Megaship and Installation arrival reminders can now reconcile the remaining journal-name mismatch: one event may expose only an internal scenario token while a later FSS event exposes only the readable name. When there is exactly one unmatched cached structure and one side lacks a stable display name, Discovery Watch links those same-system identities and suppresses the second popup. The fresh FSS event is still retained in Discovery History.

Learned identity links are scoped to the structure type and star system, survive later visits, and merge the corresponding Known POI records. The fallback is deliberately conservative: two clearly and differently named ships stay separate, and after one ambiguous cached identity has been matched, another newly named Megaship remains popup eligible. Clearing Discovery History also clears these derived links. The built-in reliability check now exercises this mismatch directly. v1.29.1 includes 126 automated tests.

## v1.29.2 — Settings Checkbox Reliability

**Show Planetary Mining Location popups** now recognises the location across the journal's localised type and signal-name fields, including a `SignalName_Localised`-only Generic signal. With the checkbox unticked, the event remains recorded in Discovery History but cannot enter the popup batch; its saved notification decision explicitly reports that Planetary Mining Location popups are disabled. Ticking the option restores the popup.

The remaining Settings checkboxes were traced through preference persistence, live monitor options and notification delivery. Existing automated coverage confirms independent Megaship and Installation controls, signal-category policies, anomaly, surface-signal, Stratum, known-POI and before-departure switches, plus popup sound, placement, timeout and EDSM preferences. The master popup checkbox still acts only at delivery time, so disabling it does not discard findings. The built-in reliability check now includes the real SignalName-only mining case. v1.29.2 includes 128 automated tests.

## v1.29.3 — Nested Planetary Signal Suppression

Planetary Mining Locations reported inside the `Signals` list of `FSSBodySignals` or `SAASignalsFound` are now governed by **Show Planetary Mining Location popups** before the broader **Geological, Human and other** surface-signal setting is applied. With mining popups disabled, these entries remain recorded as Other surface-signal evidence but do not interrupt the user.

Suppression is decided per finding rather than per journal event. If one event contains both a Planetary Mining Location and a Guardian, Thargoid or another enabled signal, only the mining popup is removed; the other important signal can still alert normally. Both the early FSS and confirmed SAA paths are covered, and the built-in reliability check uses the nested journal representation. v1.29.3 includes 130 automated tests.

## v1.29.4 — Planetary Mining Classification

Planetary Mining Locations now have the dedicated `SURFACE_MINING` classification instead of appearing as **Other surface signals**. FSS evidence is labelled **Planetary Mining Location reported** and a Detailed Surface Scanner result is labelled **Planetary Mining Location confirmed**. The record remains in Discovery History at Informational level, and its independent popup checkbox continues to work even when the broader Other surface-signal popup setting is disabled.

Mining locations no longer create investigation leads, contribute to signal-rich anomaly scoring or generate a before-departure unfinished-discovery warning. When an existing database is opened, obsolete `surface:other` cases supported only by mining-location evidence are removed automatically; real unknown Other cases are retained. Mixed journal events continue to preserve and alert on non-mining evidence independently. v1.29.4 includes 131 automated tests.

## v1.30.0 — Unified Detection Engine

Discovery Watch now resolves every finding through a shared operational policy that independently answers four questions: should the evidence be recorded, should it create or progress an investigation, which setting owns its popup, and what attention level should it receive? Discovery History categories and importance labels read from the same policy registry, preventing the interface, investigation engine and notification path from assigning contradictory meanings to one journal event.

Double-clicking a Discovery History entry now shows the effective policy alongside the existing rule evidence and popup decision: **Record**, **Investigation**, **Popup control** and a plain-language reason. The master popup switch is formally applied only at delivery time, so it cannot change recording or investigation state. Surface-signal case creation and per-category popup routing now use the shared policy rather than maintaining separate category assumptions.

Settings → Data & diagnostics adds **Run Settings behaviour check**. It validates the record/lead/popup invariants, documents twenty visible controls and runs selected live journal scenarios in temporary files without touching the commander's database. The existing broader reliability check remains available separately.

Database changes now use the `schema_migrations` ledger. Migration 1 safely removes obsolete mining-only Other investigations once, while keeping the original evidence. Diagnostic reports expose the current and expected schema version. The new `discovery_watch_core/intelligence.py` module remains interface-independent and uses only the Python standard library. v1.30.0 includes 136 automated tests.

## v1.30.1 — Experimental Contact Reconciliation

**Experimental: Unidentified system contacts** is now opt-in and disabled by default on a new installation. An existing saved choice is preserved during an upgrade. When enabled, the feature tracks each confirmed system visit independently using the system address and visit identity rather than the journal filename.

The discovery-scan `NonBodyCount` is reconciled against unique `FSSSignalDiscovered` contacts received during that visit. A short settling delay allows accompanying journal events to arrive before a reminder is created, repeated honks update the same observation, and duplicate persistent contacts do not inflate the identified count. Temporary USS contacts retain separate identities.

Only one notification is eligible per visit. Its concise wording says **System contacts need review** without displaying a quantity. Discovery History retains the reported, identified and remaining counts, clearly labels them as an experimental estimate, and updates the same record when later signals resolve the difference. Leaving with contacts outstanding marks that observation **Incomplete** without creating another popup. A fully reconciled visit is marked **Resolved**. These observations never create anomaly or body-investigation leads.

Schema migration 2 adds the visit reconciliation ledger without changing original journal evidence. Clearing Discovery History also clears these derived contact observations. v1.30.1 includes 139 automated tests.

## v1.30.2 — Laptop Home Navigation

Home → Overview is now vertically scrollable, ensuring **Current visit intelligence** and **Latest discovery alerts** remain reachable on laptop-sized Windows displays and at increased display scaling. A visible scrollbar, mouse wheel, Page Up/Page Down, Home and End can navigate the complete page. The existing side-by-side lower panels and their independent content scrollbars remain unchanged on larger displays.

The application now chooses its initial window size from the available screen dimensions instead of always requesting 1280x860. A 1440p display retains the established 1280x860 presentation; smaller screens receive a safely reduced window, and maximising it uses the available desktop area. The minimum window size is also clamped so Windows cannot enforce a larger height than the laptop can comfortably display. Settings retains its existing scrolling and keyboard navigation. v1.30.2 includes 141 automated tests.

## v1.31.0 - Built-in Exploration Criteria

Discovery Watch now evaluates the 23 astronomical criteria shown in the Elite Observatory Explorer checklist using only local Elite Dangerous journal evidence. The checks cover landable terraformable and atmospheric bodies, high gravity, large and ringed landables, close orbits, shepherd and nested moons, wide rings, close ring proximity, close and colliding binaries, small bodies, fast rotation and orbit, high eccentricity, uncommon secondary stars, diverse biological signals, premium FSD materials, complete system material sets, Codex discoveries and high-value bodies.

Relationship checks correlate the latest `Scan` evidence by `SystemAddress` and `BodyID`. System-material checks combine recorded bodies in the current system, while Codex and biological checks use `CodexEntry`, `FSSBodySignals` and `SAASignalsFound`. Findings never claim first discovery and do not assume an incompletely scanned system is complete. Repeated scans of the same body and criterion are suppressed without discarding the original journal evidence.

**Settings -> Basic alerts -> Built-in exploration criteria** provides a remembered checkbox for every criterion. All are enabled on a new installation. Matches are stored in unified Discovery History; **Popup for notable worlds and anomalies** independently decides whether they interrupt play. Popup summaries remain concise and quantity-free, while the full matched rule, measurements and journal evidence remain available from Discovery History.

The definitions use the established Elite Observatory Explorer meanings, including an eight-hour fast-orbit/rotation threshold, eccentricity above 0.9, large landables above 18,000 km radius, and five of six premium FSD materials for a good injection body. See `THIRD_PARTY_NOTICES.md` for attribution. v1.31.0 includes 148 automated tests.

## v1.31.1 - Green Gas Giant Intelligence

**Settings -> Basic alerts -> Built-in exploration criteria** now includes **Green Gas Giant**, enabled by default. A `CodexEntry` whose localised or internal identifier explicitly names a Green Gas Giant creates a high-confidence confirmed finding. The match works with the internal journal identifier as well as English localised text, so it does not depend on the game language.

The Elite journal does not record the rendered colour of an ordinary `Scan`. Discovery Watch therefore also provides one deliberately conservative offline lead: a `Sudarsky class IV gas giant` at approximately `1150 K`, the documented temperature marker shared by the currently known Class IV green variants. This is labelled **Possible Green Gas Giant** and asks the commander to verify the body visually in the FSS or system map; it is never presented as confirmed from temperature alone. Other gas-giant temperatures are not guessed, avoiding a broad stream of false alerts.

Confirmed and possible findings are stored under **Notable worlds**. The normal **Popup for notable worlds and anomalies** switch controls interruption, while the individual Green Gas Giant checkbox controls detection and recording. To avoid clutter when Codex and scan evidence arrive together, the popup simply says **Green Gas Giant**; confidence and measurements remain in Discovery History. v1.31.1 includes 151 automated tests.

## v1.31.2 - Mixed Surface Popup Correction

Planetary Mining Locations remain recorded but are now excluded from popup content whenever **Show Planetary Mining Location popups** is disabled, including `FSSBodySignals` and `SAASignalsFound` events that also contain Biological, Geological, Guardian, Thargoid, Human or other surface findings. Each popup now receives metadata only for its own surface category instead of inheriting every signal type from the shared journal event.

Eligible companion findings still popup normally. For example, an event containing a Planetary Mining Location and a Guardian signal records both findings but presents only **Guardian signals** in the notification. Mixed Biological and Geological events are covered by the same isolation rule. The complete unmodified journal evidence remains available in Discovery History. v1.31.2 includes 152 automated tests.

## v1.31.3 - Exploration Criteria Cleanup

**Landable w/ Atmosphere** has been removed from Settings and from live detection. Its unused saved preference may remain harmlessly in an upgraded database, while previously recorded Discovery History findings and original journal evidence are preserved.

The Green Gas Giant option is now labelled **Experimental: Green Gas Giant** to make its limitations clear. Direct Green Gas Giant Codex matches remain high-confidence, while the Class IV temperature check remains a possible lead requiring visual confirmation.

**Landable w/ Ring** has been renamed **Landable Ring**. Its rule identifier, behaviour, remembered preference and existing history remain unchanged. The built-in list now contains 23 criteria. v1.31.3 includes 152 automated tests.

## v1.31.4 - Field Testing Refinements

Surface-signal popup controls are now independent for **Geological**, **Human** and **Other / unclassified** evidence. Every category continues to be recorded in Discovery History even when its popup is disabled. During upgrade, Geological and Human inherit the commander's previous combined **Geological, Human and other** choice; they can then be changed separately.

The general **High Gravity** anomaly now requires the journal to report `"Landable": true` as well as at least 2.5 Earth gravities. High-gravity bodies that cannot be landed on no longer create that alert. Existing Discovery History records are preserved.

An optional **Show arrival-star discovery status (experimental)** setting is available under Notifications and is disabled by default. After an `FSDJump`, Discovery Watch waits for a matching arrival-star `Scan`. `WasDiscovered: false` produces **Possible undiscovered system**, while `WasDiscovered: true` produces **Arrival star previously discovered**. The notification occurs once per visit and explicitly describes only the arrival star; it never claims that every body in the system has the same status. This feature works from the local journal without EDSM.

Experimental Green Gas Giant intelligence now also recognises the supplied narrow marker for a **Gas giant with water based life** at approximately `176.666656 K`. It remains a possible lead requiring visual confirmation; other bodies rounded broadly to 177 K are not matched. v1.31.4 includes 159 automated tests.

## v1.31.5 - Notification Reliability

The Windows game overlay now uses an application-managed queue. Rapid journal findings no longer launch several overlapping overlay processes at once: one notification is displayed for the selected timeout, then the next queued notification is launched. Findings detected in the same polling cycle remain combined. The overlays retain their click-through, non-activating behaviour so Elite Dangerous keeps keyboard and controller focus. Linux notification delivery is unchanged.

Arrival discovery status is now focused on useful opportunities. An arrival star reporting `WasDiscovered: false` remains popup eligible and displays the full caution: **Scan: Arrival star reports WasDiscovered=false. This is a possible first-discovery opportunity, not proof that every body is undiscovered.** An arrival star reporting `WasDiscovered: true` is recorded silently in Discovery History without producing a popup.

Listening Post detection now accepts both journal layouts: `Type` / `Type_Localised` and `SignalName` / `SignalName_Localised`. This fixes real `FSSSignalDiscovered` events such as the LHS 1596 Listening Post, where Elite reports `SignalType: Generic` and carries the identity in the SignalName fields. A recognised Listening Post is no longer duplicated as a Generic-signal review. v1.31.5 includes 162 automated tests.

## v1.31.6 - Experimental Green Gas Giant Density Intelligence

Discovery Watch now calculates gas-giant bulk density directly from the local journal's `MassEM` and `Radius` values. Density is stored in the explanation for every possible Green Gas Giant lead when those measurements are available, alongside planet class and precise surface temperature. The supplied `176.666656 K` water-life candidate therefore records approximately `1829.2 kg/m³` in Discovery History.

Two deliberately narrow community-observed cloud-layer signatures have been added: a `Sudarsky class I gas giant` near `133.998352 K` and `1061.9 kg/m³`, and a `Gas giant with water based life` near `242.000015 K` and `3352.0 kg/m³`. Both produce **Possible Green Gas Giant** leads and still require visual verification in the FSS or system map. Planet class, temperature and density must all agree; Discovery Watch does not apply a broad universal density band or claim that the underlying game algorithm is proven.

The detector remains fully offline. Codex confirmation remains the only high-confidence journal match, existing temperature markers are preserved, and the popup stays concise while all measurements remain available in Discovery History. v1.31.6 includes 165 automated tests.

## v1.31.7 - Startup Performance

Discovery Watch now constructs and displays the application shell before loading saved database views. Discovery History and Recorded Systems share one read-only startup database connection instead of repeatedly creating a complete monitor for each panel. Read-only interface access no longer creates artificial live-session records.

The heavier Journal Search, signal catalogue, generic-signal rules and commander watchlist tables are loaded only when their relevant tabs are opened. Each lazy view is populated once and then retained for the session. Legacy alert-importance normalisation has moved to a one-time schema migration, while the Fleet Carrier and system-name integrity repairs remain active without being repeated separately for every startup panel.

Diagnostic exports now include startup-performance timings for window construction, database initialisation, saved-view loading and individually loaded panels. This makes slow installations easier to investigate without including raw journal contents. Detection, popup delivery, offline operation and existing history remain unchanged. v1.31.7 includes 168 automated tests.

## v1.31.8 - Indexed Startup Maintenance

The startup database work identified by Linux and Windows diagnostic reports has been reduced further. Exploration records now have a dedicated `SystemAddress` index for system-name resolution and a composite summary index for System Explorer. Legacy Fleet Carrier cleanup uses an indexed rule lookup, while alert system-name repair uses a saved alert-ID checkpoint. Subsequent starts therefore avoid reparsing the complete Discovery History.

**Recorded Systems** is now genuinely lazy-loaded: opening Discovery Watch loads the lightweight Home and Discovery History information, while the system aggregation runs only when **System Explorer -> Recorded systems** is opened. Journal Search and advanced rule tables retain the lazy-loading introduced in v1.31.7.

The schema migration also removes obsolete artificial sessions created by old read-only interface openings. Cleanup is deliberately restricted to closed sessions with no recorded events that lasted no more than five seconds; longer, active or evidence-bearing sessions are preserved. Detection behaviour, saved findings and journal evidence are unchanged. v1.31.8 includes 171 automated tests.

## v1.31.9 - Discovery History Clarity

The **Details** column now presents short, human-readable summaries rather than diagnostic rule identifiers, scores and repeated body names. Examples include **Water world • Terraformable world**, **Human surface signal • SAASignalsFound**, and **Detected by FSSSignalDiscovered**. Arrival-star status retains its actionable meaning, while experimental Green Gas Giant candidates keep their useful temperature and calculated-density measurements.

This is a presentation-only change. The original explanation, matched rules and scores, notification decision, journal location, compact evidence and complete raw JSON remain available by opening the finding. Existing records are cleaned up immediately when displayed; no database rewrite or loss of evidence is involved. Search continues to inspect the original stored information. v1.31.9 includes 175 automated tests.

## v1.31.10 - Discovery History Noise Reduction

Arrival-star discovery status now records only an actionable `WasDiscovered: false` result as **Possible undiscovered system**. A matching arrival-star scan reporting `WasDiscovered: true` silently resolves the pending check and produces neither a popup nor a Discovery History row. The Notifications setting has been renamed **Alert possible undiscovered arrival stars (experimental)** to reflect this narrower behaviour.

Schema migration 5 removes existing **Arrival star previously discovered** findings, including legacy rows identified by `WasDiscovered=true`. The cleanup is restricted to the `SYSTEM_DISCOVERY_STATUS` rule. Possible-undiscovered findings remain intact, and the underlying `Scan` events remain available in Journal Search and the original Elite journal files. v1.31.10 includes 176 automated tests.

## v1.32.0 - Public Beta Reliability

Compact notifications now include the most useful local measurement when the journal provides one. A high-gravity alert shows the body and gravity in Earth `g`; fast rotation and fast orbit alerts show readable periods; highly eccentric, large-landable, wide-ring and close-orbit findings show their relevant value. Experimental Green Gas Giant notifications show temperature and calculated bulk density when available. Each card is deliberately limited to one short measurement line, while the complete explanation and journal evidence remain in Discovery History.

Body-based findings now use the concise form **Category — Body name**, making the location immediately visible. Named signals retain the established **Signal type — Signal name** wording. Windows game overlays, Windows native notifications, Wayland notifications and the cross-platform Discovery Watch popup all use the same summary source, so their information no longer differs by delivery method.

The Windows overlay queue remains serialised so rapid discoveries stay readable, Planetary Mining Locations remain independently suppressible in mixed surface-signal events, and existing duplicate-structure, surface-confirmation and arrival-status protections are retained. The release includes realistic regression coverage for high gravity, fast rotation, fast orbit, Green Gas Giant measurements and uncluttered named signals. v1.32.0 includes 180 automated tests.

## v1.32.1 - Pre-arrival Megaship Reliability

Elite can report a fixed Megaship as `SignalType: StationMegaShip`. Discovery Watch now treats this as the normal **Megaship** category, applies the existing Megaship notification checkbox and policy, and presents the compact identity **Megaship — Signal name**. The complete original `StationMegaShip` value remains unchanged in journal evidence.

Some arrivals place that location-less `FSSSignalDiscovered` line immediately before the matching `FSDJump` line. Discovery Watch now processes the confirmed arrival context first while retaining the signal's original journal line number. If Elite flushes those two lines in separate reads, the structure signal is held briefly for the matching arrival rather than inheriting the system the commander just left. The supplied HIP 74116 sequence now records and alerts **Megaship — Zero Squared** in **HIP 74116**. v1.32.1 includes 183 automated tests.

## v1.32.2 - DW Application Icon

Discovery Watch now has a dedicated **DW** application icon: an orange **D** and cyan **W** on the interface's dark charcoal background with an orange rounded border. The supplied asset set includes a high-resolution master, Linux/application PNGs from 16 through 512 pixels and a multi-resolution Windows ICO.

The source application loads the PNG as its Tk window and taskbar icon on supported desktops. The Windows portable build includes the icon assets and embeds the ICO into `DiscoveryWatch.exe`. Icon loading is deliberately non-critical: a missing or unsupported desktop icon can never prevent journal monitoring from starting. Detection, notification and popup behaviour are unchanged. v1.32.2 includes 184 automated tests.

## v1.32.3 - Python 3.13 Build Cleanliness

All short-lived preference and notification-audit database connections now commit or roll back as appropriate and then close explicitly. This removes the repeated `ResourceWarning: unclosed database` messages reported by Python 3.13 during the Windows portable test stage. Test-only SQLite connections have received the same correction.

These warnings did not indicate failed detection or a failed PyInstaller build, but leaving cleanup to garbage collection made the build output misleading and could retain file handles longer than necessary on Windows. The complete suite now passes with `ResourceWarning` promoted to a test error. Detection rules, stored data and database schema are unchanged. v1.32.3 includes 184 automated tests.

## v1.33.0 - Public Beta Foundation

Popup presentation can now be tailored without changing detection behaviour.
Settings offers Top right, Top left, Bottom right, Bottom left and Centre
placement, plus Small, Normal and Large text. The choices are remembered and
are shared by the cross-platform Discovery Watch popup and the focus-safe
Windows game overlay. Wayland native notifications remain positioned and sized
by the Linux desktop, which the interface now states explicitly.

Popup geometry is clamped to the selected monitor's usable work area, including
negative coordinates used by monitors placed to the left of the primary
display. Windows overlays retain their serial queue, click-through behaviour and
non-activating presentation. Diagnostic exports now include the chosen popup
appearance and a summary of stored notification decisions, making tester reports
more useful without including raw journal contents.

The earlier Linux scaling safeguard remains available in source builds but is
no longer presented as a separate AppImage release. Detection rules, offline
operation, EDSM's optional secondary role and the v1.32.3 database format remain
compatible. v1.33.0 includes 188 automated tests.
