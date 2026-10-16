# Discovery Watch

**Exploration intelligence for Elite Dangerous — offline-first, private and built for commanders.**

Discovery Watch is a companion application that quietly monitors the journal
created by Elite Dangerous and helps you notice discoveries that can easily be
missed while exploring.

You fly normally. Discovery Watch watches the journal, provides a concise
pop up when something interesting appears, and saves the supporting
information so you can review it later.

> **Explore normally. Discovery Watch keeps an eye on the journal.**

## What can Discovery Watch find?

- Megaships and installations
- Notable Stellar Phenomena
- Titans, tourist beacons and listening posts
- Nonhuman signal sources
- Guardian and Thargoid surface signals
- Biological, geological and human activity
- Stratum Tectonicas leads and confirmations
- Earth-like, water, valuable and terraformable worlds
- High-gravity bodies and unusual orbital configurations
- Interesting rings, moons and binary systems
- Experimental possible Green Gas Giant candidates
- Useful exploration and engineering-material opportunities

Notifications are kept short so they do not overload you during flight. Every
finding is saved in **Discovery History**, where you can review the system,
body, journal event, reason for the alert and original evidence.

Notification categories can be enabled or disabled individually, allowing each
commander to decide what matters to them.

## Designed for exploration

Discovery Watch includes:

- Clear popup notifications with selectable position and text size
- Compact and content-fitting Windows overlay layouts
- Optional cascaded Windows alerts that do not take control away from the game
- Discovery History with search, notes and evidence review
- System Explorer for previously recorded journal information
- Surface-signal intelligence for biological, geological, human, Guardian and
  Thargoid activity
- Explainable anomaly and notable-world detection
- Experimental exploration leads that are clearly labelled
- Configurable alert rules and diagnostic tools

## Offline-first and private

The main detection system works locally by reading Elite Dangerous journal
files. Discovery Watch does not:

- Read game memory
- Modify Elite Dangerous
- Require an online commander account
- Upload your journal to an online service
- Continue running after the application is closed

Optional **EDSM enrichment** can add secondary community catalogue information
after local detection. It can be disabled completely and requires no EDSM
account or API key. If EDSM or your internet connection is unavailable, the
core application continues working normally.

Your Discovery History, preferences and journal evidence remain on your own
computer.

## Windows and Linux

Discovery Watch currently runs on **Windows and Linux**.

The public testing version requires **Python 3.9 or newer** with Tkinter.
Packaged standalone editions are planned for the full public release.

### Windows

1. Download and extract the latest testing ZIP from
   [GitHub Releases](https://github.com/fus10n75/Discovery-Watch/releases).
2. Open the extracted folder.
3. Run:

   ```powershell
   py discovery_watch.py
   ```

### Linux

1. Install Python and Tkinter if they are not already available.
2. Download and extract the latest testing ZIP.
3. Open a terminal in the extracted folder and run:

   ```bash
   python3 discovery_watch.py
   ```

Linux commanders running Elite through Steam/Proton may need to browse to the
journal folder inside the game's Proton prefix.

## Getting started

1. Open Discovery Watch.
2. Select the folder containing the game's `Journal.*.log` files.
3. Choose **Start monitoring**.
4. Return to Elite Dangerous and explore as normal.

Discovery Watch remembers your selected journal location for the next launch.

The interface is divided into four straightforward areas:

- **Home** — monitoring status and the latest useful intelligence
- **Discovery History** — saved findings and their supporting evidence
- **System Explorer** — recorded systems and searchable journal information
- **Settings** — notification choices, experimental rules and data tools

## Important journal limitation

Discovery Watch can only react to information that Elite Dangerous writes to
its journal. Some contacts shown in the navigation panel may not be published
immediately, and certain surface discoveries require FSS or DSS scanning first.

The application uses cautious wording. Experimental results are presented as
possible leads rather than proof of rarity, first discovery or a confirmed
phenomenon.

## Current testing release

The current public beta is **v1.33.3**.

The project is undergoing real in-game testing on Windows and Linux. Feedback
about missed discoveries, duplicate alerts, incorrect classifications, popup
behaviour and display compatibility is extremely valuable.

Please report problems or suggestions through
[GitHub Issues](https://github.com/fus10n75/Discovery-Watch/issues).

When reporting a problem, include:

- Your operating system
- What you expected to happen
- What actually happened
- The relevant journal event, if available
- A Discovery Watch diagnostic report where appropriate

Please review diagnostic files and journal extracts before sharing them, as
local paths or commander-related information may be present.

## Running the tests

Discovery Watch includes an automated regression suite. From the project
folder, run:

```bash
python3 -m unittest discover -v
```

The v1.33.3 suite contains **197 automated tests** covering detection,
suppression rules, journal context, database compatibility, popup presentation
and Windows overlay behaviour.

## Project status

Discovery Watch is open-source and actively improving through real commander
feedback. The dependable offline journal detector remains the heart of the
project, while optional community intelligence and experimental rules add extra
context without replacing local evidence.

Contributions, test reports and constructive ideas are welcome.

## Licence

Discovery Watch is released under the **GNU General Public License v3.0**.

Elite Dangerous is a trademark of Frontier Developments plc. Discovery Watch is
an independent community project and is not affiliated with or endorsed by
Frontier Developments.

---

**Fly safe, Commander — and enjoy the discoveries.**
