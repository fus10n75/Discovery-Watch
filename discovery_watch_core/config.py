"""Application constants and stable configuration defaults."""

from pathlib import Path


__all__ = (
    'APP_DIR', 'DB_PATH', 'DEFAULT_JOURNAL', 'APP_VERSION', 'SCHEMA_VERSION',
    'PRIMARY_TAB_LABELS', 'SETTINGS_TAB_LABELS', 'FINDING_TYPE_CHOICES',
    'SETTINGS_SCROLLABLE', 'SETTINGS_KEYBOARD_NAVIGATION',
    'HOME_OVERVIEW_SCROLLABLE', 'HOME_OVERVIEW_KEYBOARD_NAVIGATION',
    'DEFAULT_WINDOW_GEOMETRY', 'HOME_OVERVIEW_LOWER_LAYOUT',
    'POPUP_RIGHT_MARGIN', 'POPUP_TOP_MARGIN', 'POPUP_EDGE_MARGIN',
    'QUICK_SIGNAL_KEYS', 'POPUP_TIMEOUT_CHOICES', 'POPUP_MONITOR_CHOICES',
    'POPUP_MONITOR_VALUES', 'POPUP_POSITION_CHOICES', 'POPUP_FONT_CHOICES',
    'POPUP_FONT_SCALES', 'WINDOWS_NOTIFICATION_MODES',
    'WINDOWS_POPUP_LAYOUT_CHOICES',
    'WINDOWS_DEFAULT_NOTIFICATION_MODE', 'POPUP_TEST_SCENARIOS',
    'LOCATION_CONTEXT_EVENTS', 'EDSM_CACHE_HOURS', 'EDSM_BODIES_URL',
    'EDSM_SYSTEM_URL', 'KNOWN_POI_RULES', 'KNOWN_POI_PLURALS',
)


APP_DIR = Path.home() / '.discovery_watch'
DB_PATH = APP_DIR / 'discoveries.sqlite3'
DEFAULT_JOURNAL = Path.home() / 'Saved Games' / 'Frontier Developments' / 'Elite Dangerous'
APP_VERSION = '1.33.1'
SCHEMA_VERSION = 5
PRIMARY_TAB_LABELS = ('Home','Discovery history','System Explorer','Settings')
SETTINGS_TAB_LABELS = ('Basic alerts','Advanced alert rules','Data & diagnostics')
FINDING_TYPE_CHOICES = ('All findings','Signals and POIs','Notable worlds','Surface signals',
                        'Biological discoveries','Exploration reminders','Anomalies')
SETTINGS_SCROLLABLE = True
SETTINGS_KEYBOARD_NAVIGATION = True
HOME_OVERVIEW_SCROLLABLE = True
HOME_OVERVIEW_KEYBOARD_NAVIGATION = True
DEFAULT_WINDOW_GEOMETRY = '1280x860'
HOME_OVERVIEW_LOWER_LAYOUT = 'side_by_side_resizable'
POPUP_RIGHT_MARGIN = 100
POPUP_TOP_MARGIN = 60
POPUP_EDGE_MARGIN = 32
QUICK_SIGNAL_KEYS = ('titan','touristbeacon','nonhumanuss','listeningpost')
POPUP_TIMEOUT_CHOICES = (5,10,15,30,60)
POPUP_MONITOR_CHOICES = ('Main monitor','Discovery Watch monitor','Mouse pointer monitor')
POPUP_MONITOR_VALUES = {'Main monitor':'primary','Discovery Watch monitor':'application',
                        'Mouse pointer monitor':'pointer'}
POPUP_POSITION_CHOICES = ('Top right','Top left','Bottom right','Bottom left','Centre')
POPUP_FONT_CHOICES = ('Small','Normal','Large')
POPUP_FONT_SCALES = {'Small':0.88,'Normal':1.0,'Large':1.2}
WINDOWS_POPUP_LAYOUT_CHOICES = ('Compact','Standard','Fit content')
WINDOWS_NOTIFICATION_MODES = ('Native Windows notification','Windows game overlay')
WINDOWS_DEFAULT_NOTIFICATION_MODE = WINDOWS_NOTIFICATION_MODES[1]
POPUP_TEST_SCENARIOS = ('Megaship discovery','Surface biology','Anomaly review')
LOCATION_CONTEXT_EVENTS = ('FSDJump','Location','CarrierJump','LoadGame')
EDSM_CACHE_HOURS = 168
EDSM_BODIES_URL = 'https://www.edsm.net/api-system-v1/bodies'
EDSM_SYSTEM_URL = 'https://www.edsm.net/api-v1/system'
KNOWN_POI_RULES = {
    'MEGASHIP':'Megaship', 'INSTALLATION':'Installation',
    'ANCIENT_PROBE':'Ancient Probe',
    'SIGNAL_TYPE_TOURISTBEACON':'Tourist beacon', 'SIGNAL_TYPE_TITAN':'Titan',
    'NONHUMAN_USS':'Nonhuman signal source', 'LISTENING_POST':'Listening post',
    'COMMS_BEACON':'Unregistered Comms Beacon',
}
KNOWN_POI_PLURALS = {
    'Megaship':'Megaships', 'Installation':'Installations',
    'Ancient Probe':'Ancient Probes',
    'Tourist beacon':'Tourist beacons', 'Titan':'Titans',
    'Nonhuman signal source':'Nonhuman signal sources',
    'Listening post':'Listening posts',
    'Unregistered Comms Beacon':'Unregistered Comms Beacons',
}
