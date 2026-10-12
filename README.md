# Discovery-Watch
Offline-first exploration intelligence for Elite Dangerous

Discovery Watch monitors Elite Dangerous journal files while you play and
highlights discoveries that can easily be overlooked. Findings are presented
as concise unobtrusive notification pop-ups and retained in Discovery History for later review.

> **Project status:** Discovery Watch v1.32.3 is a testing release. Real
> in-game feedback about missed detections, incorrect findings, duplicate
> notifications and Windows or Linux behaviour is welcome.

## What Discovery Watch detects

- Megaships and installations
- If star system discovered.
- Notable Stellar Phenomena
- Titans, tourist beacons and listening posts
- Nonhuman signal sources
- Guardian and Thargoid surface signals
- Biological and geological activity
- Stratum Tectonicas leads and confirmations
- Valuable and terraformable worlds
- High-gravity and other unusual bodies
- Interesting rings, moons, binary systems and orbital configurations
- Experimental Green Gas Giant candidates
- Useful engineering-material combinations

Notification categories can be enabled or disabled individually. Each saved
finding records the system, body, journal event and reason that produced the
alert.

## Offline-first design

The primary detection system runs locally and reads the journal files written
by Elite Dangerous. It does not require an internet connection.

Discovery Watch does **not**:

- Read or modify game memory
- Modify Elite Dangerous files
- Require an online Discovery Watch account
- Upload a commander's journal to an online service

Optional EDSM integration can add community catalogue information after local
detection. It can be disabled completely, requires no EDSM account or API key,
and never replaces the local detection system. Discovery Watch continues to
operate normally whenever EDSM is disabled or unavailable.

## Supported platforms

- Windows
- Linux

The current testing release is a Python application. Python 3.9 or newer with
Tkinter is required. Standalone installers are planned for a later public
release but are not part of v1.32.3.

## Installation

### Windows

1. Install Python 3 from [python.org](https://www.python.org/downloads/).
2. During installation, enable **Add Python to PATH**.
3. Download and extract the Discovery Watch release ZIP.
4. Open a terminal in the extracted folder.
5. Run:

   ```powershell
   python discovery_watch.py
   ```

Tkinter is normally included with the standard Windows Python installer.

### Linux

1. Install Python 3 and Tkinter using the package manager for your
   distribution.
2. Download and extract the Discovery Watch release ZIP.
3. Open a terminal in the extracted folder.
4. Run:

   ```bash
   python3 discovery_watch.py
   ```

For Nobara or Fedora, Tkinter can normally be installed with:

```bash
sudo dnf install python3-tkinter
```

## First run

1. Open Discovery Watch.
2. Select the folder containing the Elite Dangerous journal files.
3. Review the notification categories in Settings.
4. Start monitoring if it is not configured to start automatically.
5. Play Elite Dangerous normally.

Discovery Watch remembers the selected journal location. Findings can be
reviewed in the **Discovery History** tab.

Typical Windows journal location:

```text
%USERPROFILE%\Saved Games\Frontier Developments\Elite Dangerous
```

Linux paths vary according to the Steam/Proton installation and selected
library location. Use the journal folder selector if automatic detection does
not find it.

## Data and privacy

Application data and preferences are stored locally in:

```text
~/.discovery_watch
```

Diagnostic exports and journal evidence can contain commander, system and
filesystem information. Review diagnostic files before posting them publicly.
Do not add personal journals, diagnostic exports or the Discovery Watch
database to GitHub issues.

## Testing and feedback

Useful reports include:

- The Discovery Watch version and operating system
- The journal event that should have produced a finding
- Whether the finding appeared in Discovery History
- Whether a popup and sound were produced
- Relevant notification settings
- Whether the problem can be reproduced

Before sharing journal evidence, remove information you do not want to make
public. Please use the repository's issue tracker for reproducible bugs and
feature requests.

## Known limitations

- Detection is limited to information Elite Dangerous writes to its journals.
- Some surface signals appear only after the relevant scan event.
- Experimental leads are possibilities, not confirmed discoveries.
- Windows and Linux manage overlay windows differently, so popup behaviour can
  vary between desktop environments and game display modes.
- EDSM information is secondary community context and may be incomplete or
  unavailable.

## Development

Run the automated tests from the project folder with:

```bash
python3 -m unittest -q
```

The v1.32.3 suite contains 184 tests. Detection logic is organised under
`discovery_watch_core`, while `discovery_watch.py` provides the desktop
interface and journal-monitoring application.

Please do not commit generated or personal files such as:

- `__pycache__/`
- SQLite databases
- Journal files
- Diagnostic exports
- Build environments
- `build/` and `dist/` output
- Executables, AppImages or release ZIP files

## Licence

Discovery Watch is licensed under the GNU General Public License,
version 3

## Disclaimer

Discovery Watch is an independent community project. It is not affiliated
with, endorsed by or sponsored by Frontier Developments. Elite Dangerous and
its associated names and assets belong to their respective owners.

---

**Explore normally. Discovery Watch keeps an eye on the journal.**
