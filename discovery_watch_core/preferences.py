"""Persistent user preferences and local data-maintenance helpers."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import (
    DB_PATH,
    POPUP_MONITOR_VALUES,
    POPUP_POSITION_CHOICES,
    POPUP_FONT_CHOICES,
    WINDOWS_POPUP_LAYOUT_CHOICES,
    WINDOWS_POPUP_FLOW_CHOICES,
    POPUP_TIMEOUT_CHOICES,
    WINDOWS_NOTIFICATION_MODES,
)
from .exploration_criteria import EXPLORATION_CRITERIA


__all__ = (
    'SURFACE_POPUP_DEFAULTS', 'first_run_pending', 'complete_first_run',
    'detection_preferences', 'save_detection_preferences',
    'anomaly_alert_preference', 'save_anomaly_alert_preference',
    'planetary_mining_popup_preference',
    'save_planetary_mining_popup_preference',
    'surface_signal_popup_preferences',
    'save_surface_signal_popup_preferences', 'stratum_popup_preference',
    'save_stratum_popup_preference', 'biological_material_popup_preferences',
    'save_biological_material_popup_preferences', 'before_leave_preference',
    'save_before_leave_preference', 'popup_above_game_preference',
    'save_popup_above_game_preference', 'popup_sound_preference',
    'save_popup_sound_preference', 'popup_monitor_preference',
    'save_popup_monitor_preference', 'windows_notification_mode_preference',
    'popup_appearance_preferences', 'save_popup_appearance_preferences',
    'windows_popup_layout_preference', 'save_windows_popup_layout_preference',
    'windows_popup_flow_preference', 'save_windows_popup_flow_preference',
    'save_windows_notification_mode_preference',
    'known_poi_arrival_preference', 'save_known_poi_arrival_preference',
    'arrival_discovery_status_preference',
    'save_arrival_discovery_status_preference',
    'edsm_enabled_preference', 'save_edsm_enabled_preference',
    'general_alert_preferences', 'save_general_alert_preferences',
    'exploration_criteria_preferences', 'save_exploration_criteria_preferences',
    'interface_preferences', 'save_interface_preferences', 'reset_database',
    'clear_discovery_history',
)


SURFACE_POPUP_DEFAULTS = {
    'thargoid': True, 'guardian': True, 'biological': False,
    'geological': False, 'human': False, 'other': False,
}


@contextmanager
def _preference_connection(db_path):
    """Commit or roll back preference work and always close the connection."""
    db=sqlite3.connect(str(db_path))
    try:
        with db:
            yield db
    finally:
        db.close()


def first_run_pending(db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        row=db.execute("SELECT value FROM preferences WHERE key='first_run_complete'").fetchone()
    return not row or row[0]!='1'


def complete_first_run(db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('first_run_complete','1')")


def detection_preferences(db_path=DB_PATH):
    """Load detection switches; the experimental contact estimate is opt-in."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        for key in ('detect_megaships','detect_installations'):
            db.execute('INSERT OR IGNORE INTO preferences(key,value) VALUES(?,?)',(key,'1'))
        # INSERT OR IGNORE preserves the choice saved by earlier releases while
        # ensuring a genuinely new installation starts with this estimate off.
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('detect_unresolved_signals','0')")
        values=dict(db.execute("SELECT key,value FROM preferences WHERE key IN "
                               "('detect_megaships','detect_installations','detect_unresolved_signals')"))
    return (values.get('detect_megaships','1')=='1',
            values.get('detect_installations','1')=='1',
            values.get('detect_unresolved_signals','0')=='1')


def save_detection_preferences(megaships, installations, unresolved_signals, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)',
                   ('detect_megaships','1' if megaships else '0'))
        db.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)',
                   ('detect_installations','1' if installations else '0'))
        db.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)',
                   ('detect_unresolved_signals','1' if unresolved_signals else '0'))


def anomaly_alert_preference(db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('alert_anomalies','0')")
        return db.execute("SELECT value FROM preferences WHERE key='alert_anomalies'").fetchone()[0]=='1'


def save_anomaly_alert_preference(enabled, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('alert_anomalies',?)",
                   ('1' if enabled else '0',))


def planetary_mining_popup_preference(db_path=DB_PATH):
    """Planetary Mining Location popups are opt-in; their evidence is still stored."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('planetary_mining_popups','0')")
        return db.execute("SELECT value FROM preferences WHERE key='planetary_mining_popups'").fetchone()[0]=='1'


def save_planetary_mining_popup_preference(enabled, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('planetary_mining_popups',?)",
                   ('1' if enabled else '0',))


def surface_signal_popup_preferences(db_path=DB_PATH):
    """Popup choices for surface intelligence; every category is still recorded."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        values={}
        legacy_other=db.execute(
            "SELECT value FROM preferences WHERE key='surface_popup_other'").fetchone()
        for category,default in SURFACE_POPUP_DEFAULTS.items():
            key=f'surface_popup_{category}'
            # v1.31.3 and earlier grouped Geological, Human and Other under the
            # ``other`` preference.  Preserve that choice when the two new
            # independent settings are first introduced.
            inherited=(legacy_other[0]=='1' if legacy_other and category in ('geological','human')
                       else default)
            db.execute('INSERT OR IGNORE INTO preferences(key,value) VALUES(?,?)',
                       (key,'1' if inherited else '0'))
            values[category]=db.execute('SELECT value FROM preferences WHERE key=?',(key,)).fetchone()[0]=='1'
    return values


def save_surface_signal_popup_preferences(values, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        for category in SURFACE_POPUP_DEFAULTS:
            db.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)',
                       (f'surface_popup_{category}','1' if values.get(category,False) else '0'))


def exploration_criteria_preferences(db_path=DB_PATH):
    """Load individual built-in exploration criteria; all start enabled."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        values={}
        for rule in EXPLORATION_CRITERIA:
            key='exploration_criterion_'+rule.casefold()
            db.execute('INSERT OR IGNORE INTO preferences(key,value) VALUES(?,?)',(key,'1'))
            values[rule]=db.execute('SELECT value FROM preferences WHERE key=?',(key,)).fetchone()[0]=='1'
    return values


def save_exploration_criteria_preferences(values, db_path=DB_PATH):
    """Persist individual built-in exploration criteria choices."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        for rule in EXPLORATION_CRITERIA:
            db.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)',
                       ('exploration_criterion_'+rule.casefold(),
                        '1' if values.get(rule,False) else '0'))


def stratum_popup_preference(db_path=DB_PATH):
    """Stratum leads and Tectonicas confirmations popup by default."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('stratum_popups','1')")
        return db.execute("SELECT value FROM preferences WHERE key='stratum_popups'").fetchone()[0]=='1'


def save_stratum_popup_preference(enabled, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('stratum_popups',?)",
                   ('1' if enabled else '0',))


def biological_material_popup_preferences(db_path=DB_PATH):
    """Confirmed Brain Trees alert by default; speculative material leads are opt-in."""
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('brain_tree_popups','1')")
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('bio_material_candidate_popups','0')")
        values=dict(db.execute("SELECT key,value FROM preferences WHERE key IN "
                               "('brain_tree_popups','bio_material_candidate_popups')"))
    return (values.get('brain_tree_popups','1')=='1',
            values.get('bio_material_candidate_popups','0')=='1')


def save_biological_material_popup_preferences(confirmed,candidates,db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.executemany('INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)',(
            ('brain_tree_popups','1' if confirmed else '0'),
            ('bio_material_candidate_popups','1' if candidates else '0'),
        ))


def before_leave_preference(db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('before_leave_warning','1')")
        return db.execute("SELECT value FROM preferences WHERE key='before_leave_warning'").fetchone()[0]=='1'


def save_before_leave_preference(enabled,db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('before_leave_warning',?)",
                   ('1' if enabled else '0',))


def popup_above_game_preference(db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('popup_above_game','1')")
        return db.execute("SELECT value FROM preferences WHERE key='popup_above_game'").fetchone()[0]=='1'


def save_popup_above_game_preference(enabled, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('popup_above_game',?)",
                   ('1' if enabled else '0',))


def popup_sound_preference(db_path=DB_PATH):
    """Return whether a sound should accompany a displayed discovery popup."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('popup_sound','1')")
        return db.execute("SELECT value FROM preferences WHERE key='popup_sound'").fetchone()[0]=='1'


def save_popup_sound_preference(enabled, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('popup_sound',?)",
                   ('1' if enabled else '0',))


def popup_monitor_preference(db_path=DB_PATH):
    """Return the user-facing monitor choice used for alert placement."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('popup_monitor','primary')")
        value=db.execute("SELECT value FROM preferences WHERE key='popup_monitor'").fetchone()[0]
    reverse={stored:label for label,stored in POPUP_MONITOR_VALUES.items()}
    return reverse.get(value,'Main monitor')


def save_popup_monitor_preference(choice, db_path=DB_PATH):
    if choice not in POPUP_MONITOR_VALUES:
        raise ValueError('Unknown popup monitor choice')
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('popup_monitor',?)",
                   (POPUP_MONITOR_VALUES[choice],))


def popup_appearance_preferences(db_path=DB_PATH):
    """Return portable popup placement and text-size choices."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('popup_position','Bottom right')")
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('popup_font_size','Normal')")
        values=dict(db.execute("SELECT key,value FROM preferences WHERE key IN "
                               "('popup_position','popup_font_size')"))
    position=values.get('popup_position','Bottom right')
    font=values.get('popup_font_size','Normal')
    return (position if position in POPUP_POSITION_CHOICES else 'Bottom right',
            font if font in POPUP_FONT_CHOICES else 'Normal')


def save_popup_appearance_preferences(position,font_size,db_path=DB_PATH):
    if position not in POPUP_POSITION_CHOICES:
        raise ValueError('Unknown popup position')
    if font_size not in POPUP_FONT_CHOICES:
        raise ValueError('Unknown popup text size')
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('popup_position',?)",(position,))
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('popup_font_size',?)",(font_size,))


def windows_popup_layout_preference(db_path=DB_PATH):
    """Return the Windows overlay density without affecting Linux popups."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('windows_popup_layout','Standard')")
        value=db.execute("SELECT value FROM preferences WHERE key='windows_popup_layout'").fetchone()[0]
    return value if value in WINDOWS_POPUP_LAYOUT_CHOICES else 'Standard'


def save_windows_popup_layout_preference(choice,db_path=DB_PATH):
    if choice not in WINDOWS_POPUP_LAYOUT_CHOICES:
        raise ValueError('Unknown Windows popup layout')
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('windows_popup_layout',?)",(choice,))


def windows_popup_flow_preference(db_path=DB_PATH):
    """Return whether Windows overlays are sequential or visibly cascaded."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('windows_popup_flow','Cascaded stack')")
        value=db.execute("SELECT value FROM preferences WHERE key='windows_popup_flow'").fetchone()[0]
    return value if value in WINDOWS_POPUP_FLOW_CHOICES else 'Cascaded stack'


def save_windows_popup_flow_preference(choice,db_path=DB_PATH):
    if choice not in WINDOWS_POPUP_FLOW_CHOICES:
        raise ValueError('Unknown Windows popup flow')
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('windows_popup_flow',?)",(choice,))


def windows_notification_mode_preference(db_path=DB_PATH):
    """Load the Windows delivery mode and migrate the retired Tk overlay choice."""
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('windows_notification_mode','overlay')")
        value=db.execute("SELECT value FROM preferences WHERE key='windows_notification_mode'").fetchone()[0]
        if value=='custom':
            db.execute("UPDATE preferences SET value='overlay' WHERE key='windows_notification_mode'")
            value='overlay'
    return WINDOWS_NOTIFICATION_MODES[1] if value in ('overlay','custom') else WINDOWS_NOTIFICATION_MODES[0]


def save_windows_notification_mode_preference(choice,db_path=DB_PATH):
    if choice not in WINDOWS_NOTIFICATION_MODES:
        raise ValueError('Unknown Windows notification mode')
    value='overlay' if choice==WINDOWS_NOTIFICATION_MODES[1] else 'native'
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('windows_notification_mode',?)",(value,))


def known_poi_arrival_preference(db_path=DB_PATH):
    """Return whether previously recorded POIs should be recalled on arrival."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('known_pois_on_arrival','1')")
        return db.execute("SELECT value FROM preferences WHERE key='known_pois_on_arrival'").fetchone()[0]=='1'


def save_known_poi_arrival_preference(enabled, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('known_pois_on_arrival',?)",
                   ('1' if enabled else '0',))


def arrival_discovery_status_preference(db_path=DB_PATH):
    """Return whether arrival-star discovery status should be announced."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('arrival_discovery_status','0')")
        return db.execute(
            "SELECT value FROM preferences WHERE key='arrival_discovery_status'").fetchone()[0]=='1'


def save_arrival_discovery_status_preference(enabled, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('arrival_discovery_status',?)",
                   ('1' if enabled else '0',))


def edsm_enabled_preference(db_path=DB_PATH):
    """EDSM is an explicit opt-in; local journal monitoring remains the default."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('edsm_enabled','0')")
        return db.execute("SELECT value FROM preferences WHERE key='edsm_enabled'").fetchone()[0]=='1'


def save_edsm_enabled_preference(enabled, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('edsm_enabled',?)",
                   ('1' if enabled else '0',))


def general_alert_preferences(db_path=DB_PATH):
    defaults={'detect_phenomena':'1','detect_unknown_signals':'1','popup_alerts':'1'}
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        for key,value in defaults.items():
            db.execute('INSERT OR IGNORE INTO preferences(key,value) VALUES(?,?)',(key,value))
        values=dict(db.execute("SELECT key,value FROM preferences WHERE key IN "
                               "('detect_phenomena','detect_unknown_signals','popup_alerts')"))
    return tuple(values.get(key,value)=='1' for key,value in defaults.items())


def save_general_alert_preferences(phenomena, unknown, popups, db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        for key,enabled in (('detect_phenomena',phenomena),('detect_unknown_signals',unknown),
                            ('popup_alerts',popups)):
            db.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)',
                       (key,'1' if enabled else '0'))


def interface_preferences(db_path=DB_PATH):
    """Load folder/startup/popup behaviour used by the interface."""
    defaults={'journal_folder':'','auto_start_monitoring':'0',
              'popup_auto_close':'1','popup_timeout_seconds':'15'}
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        for key,value in defaults.items():
            db.execute('INSERT OR IGNORE INTO preferences(key,value) VALUES(?,?)',(key,value))
        placeholders=','.join('?' for _ in defaults)
        values=dict(db.execute(f'SELECT key,value FROM preferences WHERE key IN ({placeholders})',tuple(defaults)))
    try: timeout=int(values.get('popup_timeout_seconds','15'))
    except (TypeError,ValueError): timeout=15
    if timeout not in POPUP_TIMEOUT_CHOICES: timeout=15
    return (values.get('journal_folder',''),values.get('auto_start_monitoring','0')=='1',
            values.get('popup_auto_close','1')=='1',timeout)


def save_interface_preferences(folder,auto_start,popup_auto_close,popup_timeout,db_path=DB_PATH):
    timeout=int(popup_timeout)
    if timeout not in POPUP_TIMEOUT_CHOICES:
        raise ValueError('Popup timeout must be 5, 10, 15, 30 or 60 seconds')
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with _preference_connection(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        for key,value in (
            ('journal_folder',str(folder or '')),
            ('auto_start_monitoring','1' if auto_start else '0'),
            ('popup_auto_close','1' if popup_auto_close else '0'),
            ('popup_timeout_seconds',str(timeout))):
            db.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)',(key,value))


def reset_database(db_path=DB_PATH):
    """Permanently remove only Discovery Watch's database and SQLite sidecars."""
    database=Path(db_path)
    removed=[]
    for target in (database, Path(str(database)+'-wal'), Path(str(database)+'-shm'),
                   Path(str(database)+'-journal')):
        if target.exists():
            target.unlink()
            removed.append(target)
    return removed


def clear_discovery_history(db_path=DB_PATH,connection=None):
    """Delete alert history only; preserve exploration, anomalies and preferences."""
    database=Path(db_path)
    if connection is None and not database.exists():
        return 0
    owned=connection is None
    db=sqlite3.connect(str(database)) if owned else connection
    try:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='alerts'").fetchone()
        if not exists:
            return 0
        count=db.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]
        db.execute('DELETE FROM alerts')
        links_exist=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                               "AND name='structure_identity_links'").fetchone()
        if links_exist:
            db.execute('DELETE FROM structure_identity_links')
        contacts_exist=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                  "AND name='contact_reconciliations'").fetchone()
        if contacts_exist:
            db.execute('DELETE FROM contact_reconciliations')
        try: db.execute("DELETE FROM sqlite_sequence WHERE name='alerts'")
        except sqlite3.OperationalError: pass
        db.commit()
        return count
    finally:
        if owned: db.close()
