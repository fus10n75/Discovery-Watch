# -*- coding: utf-8 -*-
import json
import base64
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from discovery_watch import (App, AlertPopup, Monitor, classify, detect_anomalies,
                             surface_signal_observations, surface_signal_findings,
                             stratum_findings, stratum_popup_preference,
                             save_stratum_popup_preference,
                             before_leave_preference, save_before_leave_preference,
                             detection_preferences, save_detection_preferences,
                             reset_database, anomaly_alert_preference,
                             save_anomaly_alert_preference, alert_level, finding_type,
                             general_alert_preferences, save_general_alert_preferences,
                             first_run_pending, complete_first_run, APP_VERSION,
                             PRIMARY_TAB_LABELS, SETTINGS_TAB_LABELS, FINDING_TYPE_CHOICES,
                             DEFAULT_WINDOW_GEOMETRY,
                             HOME_OVERVIEW_LOWER_LAYOUT, SETTINGS_SCROLLABLE,
                             SETTINGS_KEYBOARD_NAVIGATION, HOME_OVERVIEW_SCROLLABLE,
                             HOME_OVERVIEW_KEYBOARD_NAVIGATION,
                             add_scrollable_notebook_page, initial_window_geometry,
                             POPUP_RIGHT_MARGIN, POPUP_TOP_MARGIN, POPUP_EDGE_MARGIN,
                             popup_position, windows_popup_position,
                             prepare_windows_popup, show_windows_popup,
                             _windows_monitor_info_type, QUICK_SIGNAL_KEYS,
                             interface_preferences, save_interface_preferences,
                             POPUP_TIMEOUT_CHOICES, popup_attention_label,
                             LOCATION_CONTEXT_EVENTS, known_poi_arrival_preference,
                             save_known_poi_arrival_preference, edsm_enabled_preference,
                             arrival_discovery_status_preference,
                             save_arrival_discovery_status_preference,
                             save_edsm_enabled_preference, fetch_edsm_system,
                             score_edsm_leads, edsm_system_url, EDSM_CACHE_HOURS,
                             planetary_mining_popup_preference,
                             save_planetary_mining_popup_preference,
                             surface_signal_popup_preferences,
                             save_surface_signal_popup_preferences,
                             popup_above_game_preference, save_popup_above_game_preference,
                             popup_sound_preference, save_popup_sound_preference,
                             popup_monitor_preference, save_popup_monitor_preference,
                             popup_appearance_preferences, save_popup_appearance_preferences,
                             POPUP_POSITION_CHOICES, POPUP_FONT_CHOICES,
                             WINDOWS_POPUP_LAYOUT_CHOICES,
                             WINDOWS_POPUP_FLOW_CHOICES,
                             windows_popup_layout_preference,
                             save_windows_popup_layout_preference,
                             windows_popup_flow_preference,
                             save_windows_popup_flow_preference,
                             POPUP_MONITOR_CHOICES, WINDOWS_NOTIFICATION_MODES,
                             WINDOWS_DEFAULT_NOTIFICATION_MODE, POPUP_TEST_SCENARIOS,
                             windows_notification_mode_preference,
                             save_windows_notification_mode_preference,
                             notification_behaviour, replay_journal_paths, play_alert_sound,
                             record_notification_delivery, notification_delivery_summary,
                             popup_test_scenario, run_reliability_self_check,
                             run_settings_behaviour_check,
                             popup_category_labels, simplify_popup_content,
                             discovery_history_detail_summary,
                             clear_discovery_history,
                             popup_identity, journal_evidence_summary,
                             is_planetary_mining_location,
                             is_wayland_session, native_notification_payload,
                             popup_diagnostics,
                             send_native_notification, close_native_notification,
                             send_windows_notification, close_windows_notification,
                             _send_windows_shell_notification,
                             send_windows_overlay, decode_windows_overlay_payload,
                             windows_overlay_dimensions,
                             windows_cascade_position,
                             windows_overlay_command,
                             reinforce_windows_popup, popup_work_area,
                             windows_work_area_to_tk, SCHEMA_VERSION,
                             finding_policy, policy_explanation,
                             popup_delivery_allowed, SETTINGS_BEHAVIOUR,
                             validate_policy_registry, EXPLORATION_CRITERIA,
                             exploration_criteria_preferences,
                             save_exploration_criteria_preferences,
                             bundled_resource, application_icon_paths,
                             ensure_linux_ui_scaling)
from discovery_watch_core.theme import THEME, THEME_VERSION, THEMED_STYLES, apply_app_theme
from discovery_watch_core.exploration_criteria import gas_giant_bulk_density

class DiscoveryWatchTests(unittest.TestCase):
    def test_v112_alert_levels_preferences_and_diagnostics(self):
        self.assertEqual(APP_VERSION,'1.33.3')
        self.assertEqual(alert_level('MEGASHIP'),'Important')
        self.assertEqual(alert_level('ANOMALY_ALERT'),'Review')
        self.assertEqual(alert_level('UNIDENTIFIED_SIGNAL'),'Informational')
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            self.assertEqual(general_alert_preferences(db_path),(True,True,True))
            save_general_alert_preferences(False,True,False,db_path)
            self.assertEqual(general_alert_preferences(db_path),(False,True,False))
            self.assertTrue(first_run_pending(db_path)); complete_first_run(db_path)
            self.assertFalse(first_run_pending(db_path))
            journal=folder/'Journal.diagnostic.log'; journal.write_text('')
            with Monitor(folder,db_path) as monitor:
                monitor.start_at_end()
                monitor.contact_reconcile_delay=0
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'Location','StarSystem':'Summary System','SystemAddress':99})+'\n')
                    output.write(json.dumps({'event':'FSSSignalDiscovered','SystemAddress':99,
                                             'SignalType':'Megaship','secret':'must-not-leak'})+'\n')
                    output.write(json.dumps({'event':'FSSDiscoveryScan','SystemAddress':99,
                                             'NonBodyCount':2})+'\n')
                monitor.poll((True,True,True,True,True))
                row=next(row for row in monitor.recent() if row[3]=='Megaship detected')
                self.assertEqual(row[10],'Important')
                summary=monitor.live_summary('Summary System')
                self.assertEqual((summary['findings'],summary['unresolved']),(2,1))
                report=monitor.diagnostic_report()
                encoded=json.dumps(report)
                self.assertEqual(report['application']['version'],'1.33.3')
                self.assertNotIn('must-not-leak',encoded)
                self.assertEqual(report['database']['row_counts']['alerts'],2)

    def test_optional_anomaly_alerts_are_combined_and_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            self.assertFalse(anomaly_alert_preference(db_path))
            save_anomaly_alert_preference(True,db_path)
            self.assertTrue(anomaly_alert_preference(db_path))
            journal=folder/'Journal.anomaly-alert.log'; journal.write_text('')
            with Monitor(folder,db_path) as monitor:
                monitor.start_at_end()
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'Location','StarSystem':'Alert System','SystemAddress':77})+'\n')
                    output.write(json.dumps({'event':'Scan','SystemAddress':77,'BodyName':'Alert System A 1',
                                             'SurfaceGravity':30.0,'Landable':True,
                                             'PlanetClass':'Water world'})+'\n')
                findings=monitor.poll((True,True,True,True,True,True))
                self.assertEqual(len(findings),1)
                self.assertEqual(findings[0][0],'Anomaly review: Alert System A 1')
                self.assertIn('HIGH_GRAVITY',findings[0][2])
                self.assertIn('VALUABLE_WORLD',findings[0][2])
                self.assertEqual(len(monitor.popup_findings),1)
                self.assertEqual(monitor.recent()[0][3],'Anomaly review: Alert System A 1')
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'Scan','SystemAddress':77,'BodyName':'Alert System A 2',
                                             'SurfaceGravity':31.0,'Landable':True})+'\n')
                disabled_findings=monitor.poll((True,True,True,True,True,False))
                self.assertEqual(len(disabled_findings),1)
                self.assertEqual(monitor.popup_findings,[])
                self.assertEqual(len(monitor.recent()),2)
                self.assertIn('anomaly popups are disabled',monitor.recent()[0][12])
                self.assertTrue(any(row[4]=='Alert System A 2' for row in monitor.anomalies()))

    def test_reset_database_removes_app_data_but_not_journals(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'discoveries.sqlite3'
            journal=folder/'Journal.keep.log'; journal.write_text('{"event":"Fileheader"}\n')
            with Monitor(folder,db_path) as monitor:
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,timestamp,detail,raw_json)
                    VALUES(?,?,?,?,?,?,?,?)''',('old.log',1,'TEST','Old finding','Old System',None,'old','{}'))
                monitor.db.commit()
            sidecar=Path(str(db_path)+'-journal'); sidecar.write_text('temporary sqlite data')
            removed=reset_database(db_path)
            self.assertEqual(set(removed),{db_path,sidecar})
            self.assertFalse(db_path.exists())
            self.assertFalse(sidecar.exists())
            self.assertTrue(journal.exists())
            with Monitor(folder,db_path) as monitor:
                self.assertEqual(monitor.recent(),[])

    def test_megaship_and_installation_switches_are_independent_and_saved(self):
        megaship={'event':'FSSSignalDiscovered','SignalType':'Megaship'}
        installation={'event':'FSSSignalDiscovered','SignalType':'Installation'}
        self.assertEqual(classify(megaship,True,False)[0][0],'MEGASHIP')
        self.assertEqual(classify(installation,True,False),[])
        self.assertEqual(classify(megaship,False,True),[])
        self.assertEqual(classify(installation,False,True)[0][0],'INSTALLATION')
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertEqual(detection_preferences(db_path),(True,True,False))
            save_detection_preferences(False,True,False,db_path)
            self.assertEqual(detection_preferences(db_path),(False,True,False))
            save_detection_preferences(True,False,True,db_path)
            self.assertEqual(detection_preferences(db_path),(True,False,True))

    def test_unresolved_non_body_signal_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.unresolved.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                monitor.contact_reconcile_delay=0
                events=[
                    {'event':'FSDJump','StarSystem':'Review System','SystemAddress':1234},
                    {'event':'FSSSignalDiscovered','SystemAddress':1234,'SignalName':'Known contact A'},
                    {'event':'FSSSignalDiscovered','SystemAddress':1234,'SignalName':'Known contact B'},
                    {'event':'FSSDiscoveryScan','SystemAddress':1234,'NonBodyCount':3,'BodyCount':7},
                ]
                with journal.open('a') as output:
                    output.writelines(json.dumps(event)+'\n' for event in events)
                findings=monitor.poll()
                unresolved=next(item for item in findings if item[0].startswith('System contacts need review'))
                self.assertEqual(unresolved[1],'Review System')
                self.assertIn('reported=3',unresolved[2])
                self.assertIn('remaining=1',unresolved[2])
                self.assertTrue(any(item[0].startswith('System contacts need review') for item in monitor.popup_findings))
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'FSDJump','StarSystem':'Complete System','SystemAddress':5678})+'\n')
                    output.write(json.dumps({'event':'FSSSignalDiscovered','SystemAddress':5678,'SignalName':'A'})+'\n')
                    output.write(json.dumps({'event':'FSSSignalDiscovered','SystemAddress':5678,'SignalName':'B'})+'\n')
                    output.write(json.dumps({'event':'FSSDiscoveryScan','SystemAddress':5678,'NonBodyCount':2})+'\n')
                self.assertEqual(monitor.poll(),[])
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'FSDJump','StarSystem':'Disabled System','SystemAddress':9012})+'\n')
                    output.write(json.dumps({'event':'FSSDiscoveryScan','SystemAddress':9012,'NonBodyCount':4})+'\n')
                self.assertEqual(monitor.poll((True,True,True,True,False)),[])

    def test_listening_post_after_jump_and_popup_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            journal=folder/'Journal.listening.log'
            journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'FSDJump','StarSystem':'Post System',
                                             'SystemAddress':84})+'\n')
                    output.write(json.dumps({'event':'FSSSignalDiscovered','SystemAddress':84,
                                             'Type':'$ListeningPost:#index=1;',
                                             'Type_Localised':'Listening Post'})+'\n')
                finding=monitor.poll()[0]
                self.assertEqual(finding[:2],('Listening Post detected','Post System'))
                self.assertEqual(monitor.popup_findings[0][:2],finding[:2])
                self.assertIn('$ListeningPost:#index=1;',monitor.recent()[0][5])
                monitor.set_signal_policy('listeningpost','record',popup=True)
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'NavBeaconScan','SystemAddress':84,
                                             'Type_Localised':'Listening Post'})+'\n')
                self.assertEqual(monitor.poll(),[])
                self.assertEqual(monitor.popup_findings,[])

    def test_listening_post_uses_real_signal_name_fields_without_generic_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.lhs1596.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'2026-09-30T19:40:00Z','event':'FSDJump',
                     'StarSystem':'LHS 1596','SystemAddress':7267487393177},
                    {'timestamp':'2026-09-30T19:42:33Z','event':'FSSSignalDiscovered',
                     'SystemAddress':7267487393177,
                     'SignalName':'$ListeningPost:#index=1;',
                     'SignalName_Localised':'Listening Post','SignalType':'Generic'},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                found=monitor.poll()
                self.assertEqual([item[0] for item in found],['Listening Post detected'])
                self.assertEqual([item[0] for item in monitor.popup_findings],
                                 ['Listening Post detected'])
                rules=[row[13] for row in monitor.recent()]
                self.assertEqual(rules,['LISTENING_POST'])
                self.assertIn('$ListeningPost:#index=1;',monitor.recent()[0][4])

    def test_nonhuman_uss_after_jump_and_popup_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            journal=folder/'Journal.uss.log'
            journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'event':'FSDJump','StarSystem':'New System','SystemAddress':42},
                    {'event':'FSSSignalDiscovered','SystemAddress':42,
                     'USSType':'$USS_Type_NonHuman;',
                     'USSType_Localised':'Nonhuman signal source'},
                ]
                with journal.open('a') as output:
                    output.writelines(json.dumps(event)+'\n' for event in events)
                self.assertEqual(monitor.poll()[0][:2],('Nonhuman signal source detected','New System'))
                self.assertEqual(monitor.popup_findings[0][1],'New System')
                self.assertEqual(monitor.recent()[0][2],'New System')
                self.assertEqual(monitor.poll(),[])
                monitor.set_signal_policy('nonhumanuss','alert',popup=False)
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'FSSSignalDiscovered','SystemAddress':42,
                        'USSType_Localised':'Nonhuman signal source'})+'\n')
                self.assertEqual(len(monitor.poll()),1)
                self.assertEqual(monitor.popup_findings,[])
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'FSSSignalDiscovered','SystemAddress':42,
                        'USSType':'$USS_Type_ValuableSalvage;',
                        'USSType_Localised':'High grade emissions'})+'\n')
                self.assertEqual(monitor.poll(),[])

    def test_classification(self):
        self.assertEqual(classify({'event':'FSSSignalDiscovered','SignalName':'Notable Stellar Phenomena'})[0][0], 'STELLAR_PHENOMENON')
        self.assertEqual(classify({'event':'FSSSignalDiscovered','SignalName':'Unknown signal'})[0][0], 'UNIDENTIFIED_SIGNAL')
        self.assertEqual(classify({'event':'FSSSignalDiscovered','SignalName':'Megaship'})[0][0], 'MEGASHIP')
        self.assertFalse(classify({'event':'FSSSignalDiscovered','SignalName':'Ordinary signal'}))

    def test_megaship_signal_type_field(self):
        lower_case = classify({'event':'FSSSignalDiscovered','SignalName':'Unrelated name','signalType':'Megaship'})
        title_case = classify({'event':'FSSSignalDiscovered','SignalType':'Megaship'})
        self.assertEqual(lower_case[0][0], 'MEGASHIP')
        self.assertEqual(lower_case[0][1], 'Megaship detected')
        self.assertIn('direct journal classification', lower_case[0][2])
        self.assertEqual(title_case[0][0], 'MEGASHIP')

    def test_fleet_carrier_is_excluded_from_discovery_history(self):
        event={'event':'FSSSignalDiscovered','SignalName':'Megaship-like contact','SignalType':'FleetCarrier'}
        self.assertEqual(classify(event), [])
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            with Monitor(folder,db_path) as monitor:
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,timestamp,detail,raw_json)
                    VALUES(?,?,?,?,?,?,?,?)''',('old.log',1,'MEGASHIP','Megaship reference','Test',None,'old false positive',json.dumps(event)))
                monitor.db.commit()
            with Monitor(folder,db_path) as monitor:
                self.assertEqual(monitor.recent(), [])

    def test_installation_signal_type_field(self):
        lower_case=classify({'event':'FSSSignalDiscovered','SignalName':'Unrelated name','signalType':'Installation'})
        title_case=classify({'event':'FSSSignalDiscovered','SignalType':'Installation'})
        self.assertEqual(lower_case[0][0],'INSTALLATION')
        self.assertEqual(lower_case[0][1],'Installation detected')
        self.assertIn('direct journal classification',lower_case[0][2])
        self.assertEqual(title_case[0][0],'INSTALLATION')

    def test_unregistered_comms_beacon_compound_fields(self):
        event={'event':'FSSSignalDiscovered','SignalName_Localised':'Unregistered Comms Beacon','SignalType':'Generic'}
        findings=classify(event)
        self.assertEqual(findings[0][0],'COMMS_BEACON')
        self.assertEqual(findings[0][1],'Unregistered Comms Beacon detected')
        self.assertIn('combined journal field match',findings[0][2])
        self.assertEqual(classify({'event':'FSSSignalDiscovered','SignalName_Localised':'Ordinary Signal','SignalType':'Generic'}),[])

    def test_all_systems_and_duplicate_suppression(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            file = folder / 'Journal.2026.log'
            file.write_text('')
            monitor = Monitor(folder, folder/'alerts.sqlite3')
            monitor.start_at_end()
            with file.open('a') as out:
                out.write(json.dumps({'event':'Location','StarSystem':'Untracked System'})+'\n')
                out.write(json.dumps({'event':'FSSSignalDiscovered','SignalName':'Notable Stellar Phenomena'})+'\n')
            self.assertEqual(len(monitor.poll()), 1)
            self.assertEqual(monitor.recent()[0][2], 'Untracked System')
            self.assertEqual(monitor.poll(), [])
            self.assertEqual(len(monitor.recent()), 1)
            monitor.db.close()

    def test_partial_line(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            file=folder/'Journal.test.log'
            file.write_text('')
            monitor=Monitor(folder,folder/'alerts.sqlite3')
            monitor.start_at_end()
            with file.open('a') as out: out.write('{"event":"FSSSignalDiscovered","SignalName":"Megaship"')
            self.assertEqual(monitor.poll(),[])
            with file.open('a') as out: out.write('}\n')
            self.assertEqual(len(monitor.poll()),1)
            monitor.db.close()

if __name__=='__main__': unittest.main()

class Version11Tests(unittest.TestCase):
    def test_per_file_system_and_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first, second = folder/'Journal.one.log', folder/'Journal.two.log'
            first.write_text('')
            second.write_text('')
            with Monitor(folder, folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                for file, system in ((first, 'Alpha'), (second, 'Beta')):
                    with file.open('a') as output:
                        output.write(json.dumps({'event':'Location','StarSystem':system})+'\n')
                        output.write(json.dumps({'event':'FSSSignalDiscovered','SignalName':'Megaship'})+'\n')
                self.assertEqual(len(monitor.poll()), 2)
                self.assertEqual({r[2] for r in monitor.recent()}, {'Alpha', 'Beta'})
                self.assertEqual(monitor.export(folder/'out.csv'), 2)
                self.assertEqual(monitor.export(folder/'out.json', 'json'), 2)
                self.assertEqual(len(json.loads((folder/'out.json').read_text())), 2)
                self.assertIn('raw_json', (folder/'out.csv').read_text())

class Version12Tests(unittest.TestCase):
    def test_all_events_and_partial_json_error(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            file = folder/'Journal.live.log'
            file.write_text('')
            with Monitor(folder, folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                with file.open('a') as stream:
                    stream.write('{bad}\n')
                    stream.write(json.dumps({'event':'FSDJump','StarSystem':'Test'})+'\n')
                    stream.write(json.dumps({'event':'Music','MusicTrack':'MainMenu'})+'\n')
                self.assertEqual(monitor.poll(), [])
                self.assertEqual(monitor.total_events, 2)
                self.assertEqual([e[3]['event'] for e in monitor.events], ['FSDJump','Music'])
                self.assertEqual(monitor.active_file, str(file))
                self.assertTrue(monitor.errors)
                self.assertEqual(monitor.poll(), [])
                self.assertEqual(monitor.total_events, 2)

class Version13Tests(unittest.TestCase):
    def test_exploration_persistence_and_deduplication(self):
        import tempfile
        from pathlib import Path
        from discovery_watch import Monitor
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            journal = folder / 'Journal.260919000000.01.log'
            events = [
                {'event':'FSDJump','StarSystem':'Test System','SystemAddress':123},
                {'event':'Scan','BodyName':'Test System A 1'},
                {'event':'Scan','BodyName':'Test System A 1'},
                {'event':'SAAScanComplete','BodyName':'Test System A 1'},
                {'event':'ScanOrganic','Body':'Test System A 1','ScanType':'Sample'},
            ]
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                with journal.open('w') as out:
                    for event in events:
                        out.write(json.dumps(event)+'\n')
                monitor.poll()
                summary = monitor.systems_summary()
                self.assertEqual(summary[0][1:5],(1,1,1,5))
                self.assertEqual(len(monitor.system_details('Test System')),5)
                monitor.poll()
                self.assertEqual(monitor.systems_summary()[0][4],5)
                self.assertEqual(monitor.export_exploration(folder/'export.json'),5)
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                self.assertEqual(monitor.systems_summary()[0][4],5)
                monitor.start_at_end()
                monitor.poll()
                self.assertEqual(monitor.systems_summary()[0][4],5)

class Version14Tests(unittest.TestCase):
    def test_historical_import_search_completion_and_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder/'old'; source.mkdir()
            events = [
                {'timestamp':'2026-01-01T00:00:00Z','event':'FSDJump','StarSystem':'Alpha','SystemAddress':1},
                {'timestamp':'2026-01-01T00:00:01Z','event':'FSSDiscoveryScan','BodyCount':4},
                {'timestamp':'2026-01-01T00:00:02Z','event':'Scan','BodyName':'Alpha A 1','BodyID':1},
            ]
            journal=source/'Journal.old.log'
            journal.write_text('\n'.join(json.dumps(e) for e in events)+'\n',encoding='utf-8')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                first=monitor.import_journals(source)
                second=monitor.import_journals(source)
                self.assertEqual(first['added'],3)
                self.assertEqual(second['added'],0)
                self.assertEqual(second['duplicates'],3)
                self.assertEqual(monitor.search_exploration('Alpha')[0][5],'Incomplete')
                self.assertEqual(len(monitor.search_exploration('A 1')),1)
                self.assertEqual(len(monitor.search_exploration('',True)),1)
                self.assertEqual(monitor.integrity_check()['sqlite'],'ok')
                monitor.backup_database(folder/'backup.sqlite3')
                self.assertTrue((folder/'backup.sqlite3').exists())

    def test_import_completion_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); source=folder/'old'; source.mkdir()
            journal=source/'Journal.old.log'
            journal.write_text('\n'.join(json.dumps(e) for e in [
                {'timestamp':'1','event':'Location','StarSystem':'Beta'},
                {'timestamp':'2','event':'FSSDiscoveryScan'},
                {'timestamp':'3','event':'FSSAllBodiesFound'},
            ])+'\n')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.import_journals(source)
                self.assertEqual(monitor.search_exploration('Beta')[0][5],'Complete')
                self.assertEqual(monitor.search_exploration('',True),[])

class Version15Tests(unittest.TestCase):
    def test_explainable_anomaly_detection_and_review(self):
        event={'timestamp':'1','event':'Scan','StarSystem':'Gamma','BodyName':'Gamma 1',
               'BodyID':1,'SurfaceGravity':30.0,'Landable':True,'PlanetClass':'Water world'}
        rules={row[0] for row in detect_anomalies(event)}
        self.assertEqual(rules,{'HIGH_GRAVITY','LANDABLE_HIGH_G','VALUABLE_WORLD','HIGH_VALUE_BODY'})
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); source=folder/'old'; source.mkdir()
            (source/'Journal.a.log').write_text(json.dumps({'timestamp':'0','event':'Location','StarSystem':'Gamma'})+'\n'+json.dumps(event)+'\n')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.import_journals(source); rows=monitor.anomalies('Gamma')
                self.assertEqual(len(rows),4)
                monitor.set_anomaly_status(rows[0][0],'reviewed')
                self.assertEqual(len(monitor.anomalies(status='reviewed')),1)

class Version16Tests(unittest.TestCase):
    def test_live_summary_suggestions_and_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.live.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Delta'},
                    {'timestamp':'2','event':'FSSDiscoveryScan'},
                    {'timestamp':'3','event':'Scan','BodyName':'Delta 1','BodyID':1},
                ]
                journal.write_text('\n'.join(json.dumps(e) for e in events)+'\n')
                monitor.poll(); summary=monitor.live_summary()
                self.assertEqual(summary['system'],'Delta')
                self.assertEqual(summary['complete'],'Incomplete')
                self.assertTrue(any('FSS' in item for item in summary['suggestions']))
                self.assertTrue(any('mapping' in item for item in summary['suggestions']))
                self.assertEqual(len(monitor.live_timeline()),3)

class Version17Tests(unittest.TestCase):
    def test_full_historical_index_search_and_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); source=folder/'old'; source.mkdir()
            events=[
                {'timestamp':'2025-01-02T10:00:00Z','event':'Location','StarSystem':'Epsilon'},
                {'timestamp':'2025-01-02T10:01:00Z','event':'Music','MusicTrack':'Exploration'},
                {'timestamp':'2025-01-02T10:02:00Z','event':'Scan','BodyName':'Epsilon A 1','BodyID':1},
            ]
            (source/'Journal.session.log').write_text('\n'.join(json.dumps(e) for e in events)+'\n')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                result=monitor.import_journals(source)
                self.assertEqual(result['historical_added'],3)
                self.assertEqual(len(monitor.historical_search(event_type='Music')),1)
                self.assertEqual(len(monitor.historical_search('A 1')),1)
                self.assertEqual(len(monitor.historical_search(date_from='2025-01-02',date_to='2025-01-02')),3)
                self.assertEqual(monitor.historical_sessions()[0][1],3)
                self.assertEqual(monitor.import_journals(source)['historical_added'],0)
                self.assertEqual(len(monitor.import_reports()),2)
                self.assertEqual(monitor.integrity_check()['historical_events'],3)

class Version18Tests(unittest.TestCase):
    def test_signal_catalogue_unknown_defaults_and_custom_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); source=folder/'old'; source.mkdir()
            old={'timestamp':'1','event':'FSSSignalDiscovered','StarSystem':'Zeta','SignalType':'CivilianOutpost'}
            (source/'Journal.old.log').write_text(json.dumps(old)+'\n')
            live=folder/'Journal.live.log'; live.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.import_journals(source)
                row=next(row for row in monitor.signal_catalog() if row[0]=='civilianoutpost')
                self.assertEqual(row[2],'record')
                monitor.set_signal_policy('civilianoutpost','alert',65,False)
                monitor.start_at_end()
                live.write_text(json.dumps({'timestamp':'2','event':'FSSSignalDiscovered','StarSystem':'Zeta','SignalType':'CivilianOutpost'})+'\n')
                findings=monitor.poll()
                self.assertEqual(findings[0][0],'CivilianOutpost signal detected')
                self.assertEqual(monitor.popup_findings,[])

class Version19Tests(unittest.TestCase):
    def test_alert_review_notes_and_selected_export(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.live.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                journal.write_text(json.dumps({'timestamp':'1','event':'FSSSignalDiscovered','StarSystem':'Eta','SignalType':'Megaship'})+'\n')
                monitor.poll(); alert=monitor.recent()[0]
                monitor.update_alert(alert[0],status='acknowledged',notes='Visited and checked')
                updated=monitor.recent()[0]
                self.assertEqual(updated[8:10],('acknowledged','Visited and checked'))
                destination=folder/'selected.json'
                self.assertEqual(monitor.export_selected_alerts([alert[0]],destination),1)
                exported=json.loads(destination.read_text())
                self.assertEqual(exported[0]['notes'],'Visited and checked')

    def test_pre_v19_alert_database_is_migrated_before_history_read(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'legacy.sqlite3'
            db=sqlite3.connect(db_path)
            db.execute('''CREATE TABLE alerts (
                id INTEGER PRIMARY KEY, journal_file TEXT NOT NULL, line_no INTEGER NOT NULL,
                rule TEXT NOT NULL, title TEXT NOT NULL, system_name TEXT,
                timestamp TEXT, detail TEXT NOT NULL, raw_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(journal_file,line_no,rule))''')
            db.execute('''INSERT INTO alerts
                (journal_file,line_no,rule,title,system_name,timestamp,detail,raw_json)
                VALUES(?,?,?,?,?,?,?,?)''',('legacy.log',1,'MEGASHIP','Old finding','Legacy',None,'old','{}'))
            db.commit(); db.close()
            with Monitor(folder,db_path) as monitor:
                row=monitor.recent()[0]
                self.assertEqual(row[8:10],('new',''))
                columns={item[1] for item in monitor.db.execute('PRAGMA table_info(alerts)')}
                self.assertTrue({'status','notes'}.issubset(columns))

class Version191Tests(unittest.TestCase):
    def test_startup_recovers_system_context_without_replaying_history(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.session.log'
            journal.write_text('\n'.join(json.dumps(event) for event in [
                {'timestamp':'1','event':'Location','StarSystem':'Correct System','SystemAddress':987},
                {'timestamp':'2','event':'Music','MusicTrack':'Exploration'},
            ])+'\n')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                self.assertEqual(monitor.current_system,'Correct System')
                self.assertEqual(monitor.total_events,0)
                with journal.open('a') as output:
                    output.write(json.dumps({'timestamp':'3','event':'FSSSignalDiscovered','SignalType':'Megaship','SystemAddress':987})+'\n')
                monitor.poll()
                self.assertEqual(monitor.recent()[0][2],'Correct System')

    def test_system_name_field_is_accepted_as_explicit_context(self):
        self.assertEqual(Monitor.event_system_name({'SystemName':'Named System'}),'Named System')

    def test_comms_beacon_alerts_without_alerting_all_generic_signals(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.live.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'Location','StarSystem':'Beacon System'},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SignalName_Localised':'Ordinary Signal','SignalType':'Generic'},
                    {'timestamp':'3','event':'FSSSignalDiscovered','SignalName_Localised':'Unregistered Comms Beacon','SignalType':'Generic'},
                ]
                journal.write_text('\n'.join(json.dumps(event) for event in events)+'\n')
                findings=monitor.poll()
                self.assertEqual(len(findings),2)
                self.assertTrue(any(item[0]=='Unregistered Comms Beacon detected' for item in findings))
                self.assertTrue(any(item[0]=='New Generic signal: Ordinary Signal' for item in findings))
                self.assertEqual(len(monitor.popup_findings),2)
                self.assertTrue(any(item[0].startswith('New Generic signal: Ordinary Signal') for item in monitor.popup_findings))
                self.assertEqual(monitor.recent()[0][2],'Beacon System')

class Version110Tests(unittest.TestCase):
    def test_new_generic_name_requests_review_only_once(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.live.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                first={'timestamp':'1','event':'FSSSignalDiscovered','StarSystem':'Review System',
                       'SignalName_Localised':'Previously Unseen Contact','SignalName':'$New_Contact;','SignalType':'Generic'}
                with journal.open('a') as output: output.write(json.dumps(first)+'\n')
                findings=monitor.poll()
                self.assertEqual(len(findings),1)
                self.assertEqual(findings[0][0],'New Generic signal: Previously Unseen Contact')
                self.assertEqual(len(monitor.popup_findings),1)
                row=next(row for row in monitor.generic_signals() if row[1]=='Previously Unseen Contact')
                self.assertEqual(row[3],'review')
                self.assertEqual(row[2],'$New_Contact;')
                second=dict(first,timestamp='2')
                with journal.open('a') as output: output.write(json.dumps(second)+'\n')
                self.assertEqual(monitor.poll(),[])
                self.assertEqual(monitor.popup_findings,[])

    def test_contains_rule_alerts_variants_and_popups_once_per_system(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); source=folder/'old'; source.mkdir()
            old={'timestamp':'1','event':'FSSSignalDiscovered','StarSystem':'Rule System',
                 'SignalName_Localised':'Research Contact 01','SignalType':'Generic'}
            (source/'Journal.old.log').write_text(json.dumps(old)+'\n')
            live=folder/'Journal.live.log'; live.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.import_journals(source)
                rule=next(row for row in monitor.generic_signals() if row[1]=='Research Contact 01')
                monitor.set_generic_rule(rule[0],'alert','contains','once_system',75,'research contact')
                monitor.start_at_end()
                events=[
                    {'timestamp':'2','event':'FSSSignalDiscovered','StarSystem':'Rule System','SignalName_Localised':'Research Contact 02','SignalType':'Generic'},
                    {'timestamp':'3','event':'FSSSignalDiscovered','StarSystem':'Rule System','SignalName_Localised':'Research Contact 03','SignalType':'Generic'},
                ]
                live.write_text('\n'.join(json.dumps(event) for event in events)+'\n')
                findings=monitor.poll()
                self.assertEqual(len(findings),2)
                self.assertEqual(len(monitor.popup_findings),1)
                self.assertTrue(all('Research Contact' in finding[0] for finding in findings))

    def test_first_seen_review_notification_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.live.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.generic_notify_once(False); monitor.start_at_end()
                journal.write_text(json.dumps({'timestamp':'1','event':'FSSSignalDiscovered',
                    'SignalName_Localised':'Silent Review Contact','SignalType':'Generic'})+'\n')
                monitor.poll()
                self.assertEqual(monitor.popup_findings,[])

class Version1101Tests(unittest.TestCase):
    def test_new_login_journal_inherits_last_known_system(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); old=folder/'Journal.001.log'
            old.write_text(json.dumps({'timestamp':'1','event':'Location','StarSystem':'Logout System','SystemAddress':444})+'\n')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                self.assertEqual(monitor.current_system,'Logout System')
                new=folder/'Journal.002.log'
                new.write_text(json.dumps({'timestamp':'2','event':'FSSSignalDiscovered','SignalType':'Megaship','SystemAddress':444})+'\n')
                findings=monitor.poll()
                self.assertEqual(findings[0][1],'Logout System')
                self.assertEqual(monitor.recent()[0][2],'Logout System')

    def test_later_location_backfills_earlier_unknown_login_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                journal=folder/'Journal.login.log'
                events=[
                    {'timestamp':'1','event':'FSSSignalDiscovered','SignalType':'Installation','SystemAddress':555},
                    {'timestamp':'2','event':'Location','StarSystem':'Login System','SystemAddress':555},
                ]
                journal.write_text('\n'.join(json.dumps(event) for event in events)+'\n')
                findings=monitor.poll()
                self.assertEqual(findings[0][1],'Login System')
                self.assertEqual(monitor.recent()[0][2],'Login System')
                historical=monitor.historical_search(event_type='FSSSignalDiscovered')
                self.assertEqual(historical[0][2],'Login System')

    def test_system_address_resolves_from_stored_exploration(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); source=folder/'old'; source.mkdir()
            (source/'Journal.old.log').write_text(json.dumps({'timestamp':'1','event':'Location',
                'StarSystem':'Address System','SystemAddress':666})+'\n')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.import_journals(source)
                monitor.current_system=None; monitor.current_system_address=None
                self.assertEqual(monitor.system_name_for_address(666),'Address System')

class Version1102Tests(unittest.TestCase):
    def test_destination_address_overrides_inherited_departure_system(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); source=folder/'history'; source.mkdir()
            history=[
                {'timestamp':'1','event':'Location','StarSystem':'Departure System','SystemAddress':1001},
                {'timestamp':'2','event':'FSDJump','StarSystem':'Destination System','SystemAddress':2002},
            ]
            (source/'Journal.history.log').write_text('\n'.join(json.dumps(event) for event in history)+'\n')
            old=folder/'Journal.001.log'; old.write_text(json.dumps(history[0])+'\n')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.import_journals(source); monitor.start_at_end()
                self.assertEqual(monitor.current_system,'Departure System')
                new=folder/'Journal.002.log'
                new.write_text(json.dumps({'timestamp':'3','event':'FSSSignalDiscovered',
                    'SignalType':'Installation','SystemAddress':2002})+'\n')
                findings=monitor.poll()
                self.assertEqual(findings[0][1],'Destination System')
                self.assertEqual(monitor.recent()[0][2],'Destination System')

    def test_unknown_destination_address_does_not_use_departure_name(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); old=folder/'Journal.001.log'
            old.write_text(json.dumps({'timestamp':'1','event':'Location','StarSystem':'Departure','SystemAddress':11})+'\n')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end(); new=folder/'Journal.002.log'
                events=[
                    {'timestamp':'2','event':'FSSSignalDiscovered','SignalType':'Megaship','SystemAddress':22},
                    {'timestamp':'3','event':'Location','StarSystem':'Actual Destination','SystemAddress':22},
                ]
                new.write_text('\n'.join(json.dumps(event) for event in events)+'\n')
                findings=monitor.poll()
                self.assertEqual(findings[0][1],'Actual Destination')
                self.assertEqual(monitor.recent()[0][2],'Actual Destination')

    def test_existing_mislabelled_alert_is_repaired_from_system_address(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); source=folder/'history'; source.mkdir(); db_path=folder/'db.sqlite3'
            location={'timestamp':'1','event':'Location','StarSystem':'Corrected System','SystemAddress':77}
            (source/'Journal.history.log').write_text(json.dumps(location)+'\n')
            wrong_event={'timestamp':'2','event':'FSSSignalDiscovered','SignalType':'Installation','SystemAddress':77}
            with Monitor(folder,db_path) as monitor:
                monitor.import_journals(source)
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,timestamp,detail,raw_json)
                    VALUES(?,?,?,?,?,?,?,?)''',('wrong.log',1,'INSTALLATION','Installation detected','Wrong System','2','wrong',json.dumps(wrong_event)))
                monitor.db.commit()
            with Monitor(folder,db_path) as monitor:
                self.assertEqual(monitor.recent()[0][2],'Corrected System')


class Version1103Tests(unittest.TestCase):
    def test_titan_and_tourist_beacon_popup_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            journal=folder/'Journal.new.log'
            journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                catalog={row[0]:row for row in monitor.signal_catalog()}
                self.assertEqual((catalog['titan'][2],catalog['titan'][4]),('alert',1))
                self.assertEqual((catalog['touristbeacon'][2],catalog['touristbeacon'][4]),('alert',1))
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'Location','StarSystem':'Test System','SystemAddress':42},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SignalType':'Titan','SystemAddress':42},
                    {'timestamp':'3','event':'FSSSignalDiscovered','SignalType':'TouristBeacon','SystemAddress':42},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                found=monitor.poll()
                self.assertEqual([item[0] for item in found],['Titan signal detected','TouristBeacon signal detected'])
                self.assertEqual(len(monitor.popup_findings),2)
                self.assertEqual({row[2] for row in monitor.recent()},{'Test System'})

                monitor.set_signal_policy('touristbeacon','alert',popup=False)
                with journal.open('a') as output:
                    output.write(json.dumps({'timestamp':'4','event':'FSSSignalDiscovered',
                        'signalType':'TouristBeacon','SystemAddress':42})+'\n')
                self.assertEqual(len(monitor.poll()),1)
                self.assertEqual(monitor.popup_findings,[])

            with Monitor(folder,folder/'db.sqlite3') as monitor:
                rule=next(row for row in monitor.signal_catalog() if row[0]=='touristbeacon')
                self.assertEqual((rule[2],rule[4]),('alert',0))
                monitor.set_signal_policy('titan','record')
                monitor.start_at_end()
                with journal.open('a') as output:
                    output.write(json.dumps({'timestamp':'5','event':'FSSSignalDiscovered',
                        'SignalType':'Titan','SystemAddress':42})+'\n')
                self.assertEqual(monitor.poll(),[])


class Version1121Tests(unittest.TestCase):
    def test_megaship_alerts_are_deduplicated_per_system_visit(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.megaships.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Alpha','SystemAddress':101},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SignalType':'Megaship',
                     'SignalName_Localised':'DSSA Hope','SignalName':'$DSSA_Hope;','SystemAddress':101},
                    {'timestamp':'3','event':'FSSSignalDiscovered','signalType':'Megaship',
                     'SignalName_Localised':'DSSA Hope','SignalName':'$DSSA_Hope;','SystemAddress':101},
                    {'timestamp':'4','event':'FSSSignalDiscovered','SignalType':'Megaship',
                     'SignalName_Localised':'Surveyor','SignalName':'$Surveyor;','SystemAddress':101},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                found=monitor.poll()
                self.assertEqual([item[0] for item in found],['Megaship detected','Megaship detected'])
                self.assertEqual(len(monitor.popup_findings),2)
                self.assertEqual(len([row for row in monitor.recent() if row[3]=='Megaship detected']),2)

                with journal.open('a') as output:
                    for event in (
                        {'timestamp':'5','event':'FSDJump','StarSystem':'Beta','SystemAddress':202},
                        {'timestamp':'6','event':'FSDJump','StarSystem':'Alpha','SystemAddress':101},
                        {'timestamp':'7','event':'FSSSignalDiscovered','SignalType':'Megaship',
                         'SignalName_Localised':'DSSA Hope','SignalName':'$DSSA_Hope;','SystemAddress':101},
                    ):
                        output.write(json.dumps(event)+'\n')
                self.assertEqual(len(monitor.poll()),1)
                self.assertEqual(len([row for row in monitor.recent() if row[3]=='Megaship detected']),3)


class Version113Tests(unittest.TestCase):
    def test_interface_refresh_navigation_and_quick_signal_policies(self):
        self.assertEqual(PRIMARY_TAB_LABELS,
                         ('Home','Discovery history','System Explorer','Settings'))
        self.assertEqual(QUICK_SIGNAL_KEYS,
                         ('titan','touristbeacon','nonhumanuss','listeningpost'))
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                for key in QUICK_SIGNAL_KEYS:
                    monitor.set_signal_policy(key,'record')
                policies={row[0]:row[2] for row in monitor.signal_catalog()}
                self.assertTrue(all(policies[key]=='record' for key in QUICK_SIGNAL_KEYS))
                for key in QUICK_SIGNAL_KEYS:
                    monitor.set_signal_policy(key,'alert')
                policies={row[0]:row[2] for row in monitor.signal_catalog()}
                self.assertTrue(all(policies[key]=='alert' for key in QUICK_SIGNAL_KEYS))


class Version1131Tests(unittest.TestCase):
    def test_interface_preferences_remember_folder_startup_and_popup_timeout(self):
        self.assertEqual(POPUP_TIMEOUT_CHOICES,(5,10,15,30,60))
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'preferences.sqlite3'
            self.assertEqual(interface_preferences(db_path),('',False,True,15))
            journal_folder=folder/'Elite Journals'; journal_folder.mkdir()
            save_interface_preferences(journal_folder,True,False,30,db_path)
            self.assertEqual(interface_preferences(db_path),(str(journal_folder),True,False,30))
            with self.assertRaises(ValueError):
                save_interface_preferences(journal_folder,False,True,12,db_path)
            with closing(sqlite3.connect(db_path)) as db, db:
                db.execute("UPDATE preferences SET value='broken' WHERE key='popup_timeout_seconds'")
            self.assertEqual(interface_preferences(db_path),(str(journal_folder),True,False,15))


class Version1132Tests(unittest.TestCase):
    def test_detail_windows_use_shared_linux_focus_policy(self):
        self.assertTrue(callable(getattr(App,'create_detail_window',None)))
        self.assertTrue(callable(getattr(App,'_release_detail_topmost',None)))


class Version1133Tests(unittest.TestCase):
    def test_popup_information_categories_and_history_action(self):
        self.assertEqual(popup_attention_label('Megaship detected'),'IMPORTANT')
        self.assertEqual(popup_attention_label('Anomaly review: High gravity'),'REVIEW')
        self.assertEqual(popup_attention_label('TouristBeacon signal detected'),'INFORMATION')
        self.assertTrue(callable(getattr(App,'open_discovery_history',None)))


class Version1134Tests(unittest.TestCase):
    def test_plotted_destination_does_not_replace_current_system_before_jump(self):
        self.assertIn('LoadGame',LOCATION_CONTEXT_EVENTS)
        self.assertNotIn('FSDTarget',LOCATION_CONTEXT_EVENTS)
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.route.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'Location','StarSystem':'Destination','SystemAddress':202},
                    {'timestamp':'2','event':'FSDJump','StarSystem':'Current System','SystemAddress':101},
                    {'timestamp':'3','event':'FSDTarget','Name':'Destination','SystemAddress':202},
                    {'timestamp':'4','event':'Undocked','StationName':'Test Station'},
                    {'timestamp':'5','event':'FSSSignalDiscovered','SignalType':'Installation',
                     'SignalName_Localised':'Current Installation'},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                findings=monitor.poll()
                self.assertEqual(monitor.current_system,'Current System')
                installation=next(item for item in findings if item[0]=='Installation detected')
                self.assertEqual(installation[1],'Current System')
                target=monitor.historical_search(event_type='FSDTarget')[0]
                self.assertEqual(target[2],'Destination')

    def test_startup_context_ignores_uncompleted_fsd_target(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.route.log'
            journal.write_text('\n'.join(json.dumps(event) for event in [
                {'timestamp':'1','event':'Location','StarSystem':'Still Here','SystemAddress':11},
                {'timestamp':'2','event':'FSDTarget','Name':'Plotted Destination','SystemAddress':22},
            ])+'\n')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                self.assertEqual((monitor.current_system,monitor.current_system_address),('Still Here',11))


class Version1140Tests(unittest.TestCase):
    def test_known_poi_arrival_preference_defaults_on_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertTrue(known_poi_arrival_preference(db_path))
            save_known_poi_arrival_preference(False,db_path)
            self.assertFalse(known_poi_arrival_preference(db_path))

    def test_return_visit_recalls_known_pois_without_new_history_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.known-pois.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                first_visit=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Sol','SystemAddress':10477373803},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SignalType':'Megaship',
                     'SignalName_Localised':'Tourist Megaship','SystemAddress':10477373803},
                    {'timestamp':'3','event':'FSSSignalDiscovered','SignalType':'TouristBeacon',
                     'SignalName_Localised':'Founders Memorial','SystemAddress':10477373803},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in first_visit))
                monitor.poll()
                saved_count=len(monitor.recent())
                with journal.open('a') as output:
                    for event in (
                        {'timestamp':'4','event':'FSDJump','StarSystem':'Alpha Centauri','SystemAddress':1},
                        {'timestamp':'5','event':'FSDJump','StarSystem':'Sol','SystemAddress':10477373803},
                        {'timestamp':'6','event':'Location','StarSystem':'Sol','SystemAddress':10477373803},
                    ):
                        output.write(json.dumps(event)+'\n')
                self.assertEqual(monitor.poll(),[])
                self.assertEqual(len(monitor.popup_findings),1)
                title,system,detail=monitor.popup_findings[0]
                self.assertEqual(system,'Sol')
                self.assertIn('Known POIs on arrival - 2 recorded',title)
                self.assertIn('Tourist Megaship',detail)
                self.assertIn('Founders Memorial',detail)
                self.assertIn('cached information',detail)
                self.assertEqual(len(monitor.recent()),saved_count)

    def test_known_poi_arrival_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.disabled.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,detail,raw_json)
                    VALUES(?,?,?,?,?,?,?)''',('old.log',1,'LISTENING_POST','Listening Post detected',
                    'Test System','old',json.dumps({'Type_Localised':'Listening Post'})))
                monitor.db.commit(); monitor.start_at_end()
                journal.write_text(json.dumps({'timestamp':'1','event':'FSDJump','StarSystem':'Test System',
                                               'SystemAddress':99})+'\n')
                monitor.poll((True,True,True,True,True,False,False))
                self.assertEqual(monitor.popup_findings,[])


class Version1141Tests(unittest.TestCase):
    def test_popup_exposes_scrollable_all_findings_view(self):
        self.assertTrue(AlertPopup.SCROLLABLE)
        self.assertTrue(callable(getattr(AlertPopup,'_scroll_cards',None)))
        self.assertTrue(callable(getattr(AlertPopup,'_scroll_cards_page',None)))
        self.assertTrue(callable(getattr(AlertPopup,'_resize_cards_width',None)))


class Version1142Tests(unittest.TestCase):
    def test_generic_signal_type_findings_use_the_signal_name(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); source=folder/'old'; source.mkdir()
            seed={'timestamp':'0','event':'FSSSignalDiscovered','StarSystem':'Seed',
                  'SignalName_Localised':'Seed Contact','SignalType':'Generic'}
            (source/'Journal.old.log').write_text(json.dumps(seed)+'\n')
            live=folder/'Journal.live.log'; live.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.import_journals(source)
                monitor.set_signal_policy('generic','alert',60,False)
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSSSignalDiscovered','StarSystem':'Names',
                     'SignalName_Localised':'Localised Contact','SignalName':'$Internal_Contact;',
                     'SignalType':'Generic'},
                    {'timestamp':'2','event':'FSSSignalDiscovered','StarSystem':'Names',
                     'SignalName':'$Internal_Only;','SignalType':'Generic'},
                    {'timestamp':'3','event':'FSSSignalDiscovered','StarSystem':'Names',
                     'SignalType':'Generic'},
                ]
                live.write_text(''.join(json.dumps(event)+'\n' for event in events))
                titles=[finding[0] for finding in monitor.poll()]
                self.assertEqual(titles,[
                    'Localised Contact (Generic signal)',
                    '$Internal_Only; (Generic signal)',
                    'Unnamed Generic signal (Generic signal)',
                ])
                self.assertEqual([row[3] for row in monitor.recent(3)],list(reversed(titles)))


class Version1143Tests(unittest.TestCase):
    def test_active_finding_count_is_not_limited_to_recent_200_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                for index in range(250):
                    monitor.db.execute('''INSERT INTO alerts
                        (journal_file,line_no,rule,title,system_name,detail,raw_json,status)
                        VALUES(?,?,?,?,?,?,?,?)''',(
                        'Journal.count.log',index+1,'TEST',f'Finding {index+1}','Count System',
                        'test finding','{}','dismissed' if index<25 else
                        ('acknowledged' if index<50 else 'new')))
                monitor.db.commit()
                self.assertEqual(len(monitor.recent()),200)
                self.assertEqual(monitor.active_alert_count(),225)


class Version1144Tests(unittest.TestCase):
    def test_home_poi_card_summarises_current_system_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                self.assertEqual(monitor.known_poi_overview_text(),'Waiting for location')
                self.assertEqual(monitor.known_poi_overview_text('Empty System'),'No known POIs')
                records=[
                    ('MEGASHIP','DSSA One'),('MEGASHIP','DSSA Two'),
                    ('SIGNAL_TYPE_TOURISTBEACON','Historic Beacon'),
                    ('LISTENING_POST','Listening Post'),
                ]
                for index,(rule,name) in enumerate(records,1):
                    raw={'SignalName_Localised':name}
                    if rule=='LISTENING_POST': raw={'Type_Localised':'Listening Post'}
                    monitor.db.execute('''INSERT INTO alerts
                        (journal_file,line_no,rule,title,system_name,detail,raw_json)
                        VALUES(?,?,?,?,?,?,?)''',('Journal.pois.log',index,rule,'Finding',
                        'Useful System','detail',json.dumps(raw)))
                monitor.db.commit()
                text=monitor.known_poi_overview_text('Useful System')
                self.assertEqual(text,'4 known POIs\n2 Megaships | 1 Tourist beacon | 1 Listening post')


class Version1150Tests(unittest.TestCase):
    class FakeResponse:
        def __init__(self,payload): self.payload=json.dumps(payload).encode('utf-8')
        def __enter__(self): return self
        def __exit__(self,*_args): return False
        def read(self): return self.payload

    def test_edsm_is_opt_in_and_public_urls_are_encoded(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertFalse(edsm_enabled_preference(db_path))
            save_edsm_enabled_preference(True,db_path)
            self.assertTrue(edsm_enabled_preference(db_path))
        calls=[]
        def opener(request,timeout=0):
            calls.append((request.full_url,timeout,request.headers.get('User-agent')))
            if 'api-system-v1' in request.full_url:
                return self.FakeResponse({'id':1,'name':'Test System','bodyCount':2,'bodies':[
                    {'name':'Test System A','type':'Star','subType':'G (White-Yellow) Star'}]})
            return self.FakeResponse({'id':1,'name':'Test System','primaryStar':{'type':'G'}})
        result=fetch_edsm_system('Test System',opener=opener,timeout=3)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(len(calls),2)
        self.assertTrue(all('systemName=Test+System' in call[0] for call in calls))
        self.assertTrue(all(call[1]==3 and call[2] for call in calls))
        self.assertIn('systemName=Test+System',edsm_system_url('Test System'))

    def test_edsm_cache_and_possible_lead_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            result={'status':'ok','system':'Lead System',
                    'fetched_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    'system_info':{'name':'Lead System'},
                    'body_data':{'name':'Lead System','bodyCount':5,'bodies':[
                        {'name':'Lead System A','type':'Star','subType':'Black Hole'},
                        {'name':'Lead System B','type':'Star','subType':'K Star'},
                        {'name':'Lead System C','type':'Star','subType':'M Star'},
                        {'name':'Lead System 1','type':'Planet','subType':'Earth-like world'},
                    ]}}
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.save_edsm_cache('Lead System',result)
                cached=monitor.edsm_cache_entry('lead system')
                self.assertFalse(cached['stale'])
                self.assertEqual(cached['payload']['body_data']['bodyCount'],5)
                leads=score_edsm_leads(result,['Lead System A','Lead System 2'])
                titles={lead[1] for lead in leads}
                self.assertEqual(titles,{'Incomplete EDSM body catalogue','Local bodies absent from EDSM',
                                         'Unusual stellar type recorded','Complex multi-star configuration',
                                         'Potentially valuable or notable worlds'})
                old=(datetime.now(timezone.utc)-timedelta(hours=EDSM_CACHE_HOURS+1)).isoformat()
                monitor.db.execute('UPDATE edsm_cache SET fetched_at=? WHERE system_name=?',(old,'Lead System'))
                monitor.db.commit()
                self.assertTrue(monitor.edsm_cache_entry('Lead System')['stale'])

    def test_edsm_partial_response_and_total_outage_are_contained(self):
        def partial_opener(request,timeout=0):
            if 'api-v1/system' in request.full_url:
                raise OSError('metadata endpoint offline')
            return self.FakeResponse({'id':9,'name':'Partial System','bodyCount':0,'bodies':[]})
        partial=fetch_edsm_system('Partial System',opener=partial_opener)
        self.assertEqual(partial['status'],'ok')
        self.assertTrue(partial['partial_errors'])
        def offline_opener(_request,timeout=0):
            raise OSError('network offline')
        with self.assertRaises(OSError):
            fetch_edsm_system('Offline System',opener=offline_opener)

    def test_confirmed_arrivals_feed_background_lookup_once(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.arrival.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                journal.write_text('\n'.join(json.dumps(event) for event in [
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Arrival','SystemAddress':5},
                    {'timestamp':'2','event':'Location','StarSystem':'Arrival','SystemAddress':5},
                    {'timestamp':'3','event':'FSDTarget','Name':'Not Arrived','SystemAddress':6},
                ])+'\n')
                monitor.poll()
                self.assertEqual(monitor.arrived_systems,['Arrival'])


class Version1152Tests(unittest.TestCase):
    def test_planetary_mining_location_popup_is_suppressed_but_finding_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            self.assertFalse(planetary_mining_popup_preference(db_path))
            journal=folder/'Journal.mining.log'; journal.write_text('')
            with Monitor(folder,db_path) as monitor:
                source=folder/'old'; source.mkdir()
                (source/'Journal.old.log').write_text(json.dumps({
                    'timestamp':'0','event':'FSSSignalDiscovered','StarSystem':'Seed',
                    'SignalName_Localised':'Seed','SignalType':'Generic'})+'\n')
                monitor.import_journals(source)
                monitor.set_signal_policy('generic','alert',60,True)
                monitor.start_at_end()
                event={'timestamp':'1','event':'FSSSignalDiscovered','StarSystem':'Mining System',
                       'SignalName_Localised':'Planetary Mining Location','SignalType':'Generic',
                       'Type_Localised':'Planetary Mining Location'}
                journal.write_text(json.dumps(event)+'\n')
                found=monitor.poll()
                self.assertEqual(found[0][0],'Planetary Mining Location (Generic signal)')
                self.assertEqual(monitor.popup_findings,[])
                self.assertEqual(monitor.recent()[0][3],'Planetary Mining Location (Generic signal)')
                self.assertEqual(monitor.historical_search(event_type='FSSSignalDiscovered')[0][2],'Mining System')

    def test_planetary_mining_popup_can_be_enabled_and_surface_anomalies_are_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            save_planetary_mining_popup_preference(True,db_path)
            self.assertTrue(planetary_mining_popup_preference(db_path))
            journal=folder/'Journal.options.log'; journal.write_text('')
            with Monitor(folder,db_path) as monitor:
                monitor.start_at_end()
                journal.write_text(json.dumps({'timestamp':'1','event':'FSSBodySignals',
                    'StarSystem':'Surface System','BodyName':'Surface System A 1',
                    'Signals':[{'Type':'$SAA_SignalType_Geological;','Count':9}]})+'\n')
                found=monitor.poll((True,True,True,True,True,True,True,False,
                                    True,True,False,True))
                self.assertEqual(len(found),1)
                self.assertEqual(len(monitor.popup_findings),1)
                self.assertEqual(found[0][0],'Possible Geological surface signals')
                self.assertIn('Signal type=$SAA_SignalType_Geological;',found[0][2])

    def test_planetary_mining_identity_accepts_each_journal_name_field(self):
        for key,value in (
                ('Type_Localised','Planetary Mining Location'),
                ('SignalName_Localised','Planetary Mining Location'),
                ('Name_Localised','Planetary Mining Location'),
                ('Type','$SAA_SignalType_PlanetaryMiningLocation;')):
            with self.subTest(field=key):
                self.assertTrue(is_planetary_mining_location({key:value}))
        self.assertFalse(is_planetary_mining_location(
            {'SignalName_Localised':'Planetary Settlement'}))
        self.assertTrue(is_planetary_mining_location({'event':'SAASignalsFound','Signals':[
            {'Type_Localised':'Planetary Mining Location','Count':1}]}))

    def test_signal_name_only_obeys_planetary_mining_popup_checkbox(self):
        for enabled in (False,True):
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as directory:
                folder=Path(directory); journal=folder/'Journal.mining-name.log'; journal.write_text('')
                with Monitor(folder,folder/'db.sqlite3') as monitor:
                    source=folder/'old'; source.mkdir()
                    (source/'Journal.old.log').write_text(json.dumps({
                        'timestamp':'0','event':'FSSSignalDiscovered','StarSystem':'Seed',
                        'SignalName_Localised':'Seed','SignalType':'Generic'})+'\n')
                    monitor.import_journals(source)
                    monitor.set_signal_policy('generic','alert',60,True)
                    monitor.start_at_end()
                    event={'timestamp':'1','event':'FSSSignalDiscovered',
                           'StarSystem':'Mining System',
                           'SignalName_Localised':'Planetary Mining Location',
                           'SignalType':'Generic'}
                    journal.write_text(json.dumps(event)+'\n')
                    found=monitor.poll((True,True,True,True,True,False,True,enabled,
                                        True,True,False,False,True,True))
                    self.assertEqual(len(found),1)
                    self.assertEqual(len(monitor.popup_findings),int(enabled))
                    decision=monitor.recent()[0][12]
                    self.assertIn('Popup eligible' if enabled else 'Planetary Mining Location popups are disabled',
                                  decision)

    def test_nested_planetary_mining_signal_obeys_its_own_checkbox(self):
        for event_kind in ('FSSBodySignals','SAASignalsFound'):
            for enabled in (False,True):
                with self.subTest(event=event_kind,enabled=enabled), \
                        tempfile.TemporaryDirectory() as directory:
                    folder=Path(directory); journal=folder/'Journal.nested-mining.log'
                    journal.write_text('')
                    with Monitor(folder,folder/'db.sqlite3') as monitor:
                        monitor.start_at_end()
                        event={'timestamp':'1','event':event_kind,'StarSystem':'Mining System',
                               'BodyName':'Mining System A 1','Signals':[{
                                   'Type':'$SAA_SignalType_PlanetaryMiningLocation;',
                                   'Type_Localised':'Planetary Mining Location','Count':1}]}
                        journal.write_text(json.dumps(event)+'\n')
                        found=monitor.poll((True,True,True,True,True,False,True,enabled,
                                            True,True,False,False,True,True))
                        self.assertEqual(len(found),1)
                        self.assertEqual(found[0][0],
                            'Planetary Mining Location reported' if event_kind=='FSSBodySignals'
                            else 'Planetary Mining Location confirmed')
                        self.assertEqual(len(monitor.popup_findings),int(enabled))
                        self.assertIn('Popup eligible' if enabled else
                                      'Planetary Mining Location popups are disabled',
                                      monitor.recent()[0][12])
                        self.assertEqual(monitor.db.execute(
                            'SELECT COUNT(*) FROM discovery_cases').fetchone()[0],0)
                        self.assertEqual(monitor.anomalies(),[])
                        self.assertEqual(monitor.recent()[0][13],'SURFACE_MINING')

    def test_mining_suppression_does_not_hide_other_signals_in_same_event(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.mixed-signals.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                event={'timestamp':'1','event':'SAASignalsFound','StarSystem':'Mixed System',
                       'BodyName':'Mixed System A 1','Signals':[
                           {'Type_Localised':'Planetary Mining Location','Count':1},
                           {'Type_Localised':'Guardian','Count':1}]}
                journal.write_text(json.dumps(event)+'\n')
                found=monitor.poll((True,True,True,True,True,False,True,False,
                                    True,True,False,True,True,True))
                self.assertEqual(len(found),2)
                self.assertEqual([item[0] for item in monitor.popup_findings],
                                 ['Guardian surface signal confirmed'])
                compact,metadata=simplify_popup_content(monitor.popup_findings,
                                                         monitor.popup_metadata)
                self.assertEqual([item[0] for item in compact],
                                 ['Guardian signals — Mixed System A 1'])
                self.assertNotIn('Planetary Mining Location',
                                 ' '.join(str(item) for item in compact+metadata))
                decisions={row[3]:row[12] for row in monitor.recent()}
                self.assertIn('Planetary Mining Location popups are disabled',
                              decisions['Planetary Mining Location confirmed'])
                self.assertIn('Popup eligible',decisions['Guardian surface signal confirmed'])

    def test_mining_is_absent_from_mixed_biological_and_geological_popup(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.mixed-bio-geo.log'
            journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                event={'timestamp':'1','event':'SAASignalsFound',
                       'StarSystem':'Mixed Bio Geo','BodyName':'Mixed Bio Geo A 1',
                       'Signals':[
                           {'Type_Localised':'Planetary Mining Location','Count':2},
                           {'Type':'$SAA_SignalType_Biological;',
                            'Type_Localised':'Biological','Count':4},
                           {'Type':'$SAA_SignalType_Geological;',
                            'Type_Localised':'Geological','Count':3},
                       ]}
                journal.write_text(json.dumps(event)+'\n')
                found=monitor.poll((True,True,True,True,False,False,True,False,
                                    True,True,True,True,True,True))
                self.assertEqual(len(found),3)
                self.assertEqual([item[0] for item in monitor.popup_findings],
                                 ['Biological surface signals confirmed',
                                  'Geological surface signals confirmed'])
                compact,metadata=simplify_popup_content(monitor.popup_findings,
                                                         monitor.popup_metadata)
                self.assertEqual([item[0] for item in compact],
                                 ['Biological signals — Mixed Bio Geo A 1',
                                  'Geological signals — Mixed Bio Geo A 1'])
                popup_text=' '.join(str(item) for item in compact+metadata)
                self.assertNotIn('Planetary Mining Location',popup_text)
                stored_titles={row[3] for row in monitor.recent()}
                self.assertIn('Planetary Mining Locations confirmed',stored_titles)

    def test_upgrade_removes_only_obsolete_mining_other_leads(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            mining_event={'event':'SAASignalsFound','BodyName':'Mining A 1','Signals':[
                {'Type_Localised':'Planetary Mining Location','Count':1}]}
            unknown_event={'event':'SAASignalsFound','BodyName':'Unknown A 1','Signals':[
                {'Type_Localised':'Unclassified Surface Contact','Count':1}]}
            with Monitor(folder,db_path) as monitor:
                for body,event in (('Mining A 1',mining_event),('Unknown A 1',unknown_event)):
                    cursor=monitor.db.execute('''INSERT INTO discovery_cases
                        (system_name,system_address,body_name,target_key,title,state,confidence,
                         next_action,evidence_count,status) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                        ('Test','1',body,'surface:other','Other surface signals','Identified',
                         'Confirmed','Review',1,'active'))
                    monitor.db.execute('''INSERT INTO discovery_case_evidence
                        (case_id,visit_key,event_key,stage,event_type,raw_json)
                        VALUES(?,?,?,?,?,?)''',(cursor.lastrowid,'old','event-'+body,'Identified',
                                               'SAASignalsFound',json.dumps(event)))
                monitor.db.execute('DELETE FROM schema_migrations')
                monitor.db.commit()
            with Monitor(folder,db_path) as monitor:
                remaining=monitor.db.execute(
                    "SELECT body_name FROM discovery_cases WHERE target_key='surface:other'").fetchall()
                self.assertEqual(remaining,[('Unknown A 1',)])


class Version1160Tests(unittest.TestCase):
    def test_above_game_preference_and_notification_matrix_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertTrue(popup_above_game_preference(db_path))
            save_popup_above_game_preference(False,db_path)
            self.assertFalse(popup_above_game_preference(db_path))
        self.assertEqual(notification_behaviour('alert',True),'Alert + popup')
        self.assertEqual(notification_behaviour('alert',False),'Alert silently')
        self.assertEqual(notification_behaviour('record',True),'Catalogue only')
        self.assertEqual(notification_behaviour('ignore',False),'Ignore')

    def test_popup_sound_preference_and_guarded_popup_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertTrue(popup_sound_preference(db_path))
            save_popup_sound_preference(False,db_path)
            self.assertFalse(popup_sound_preference(db_path))
        self.assertTrue(callable(play_alert_sound))
        self.assertTrue(callable(getattr(App,'show_alert_popup',None)))
        self.assertTrue(callable(getattr(App,'test_notification',None)))
        self.assertTrue(callable(getattr(App,'update_home_alert_panel',None)))

    def test_advanced_rule_pages_are_consolidated(self):
        self.assertEqual(SETTINGS_TAB_LABELS,
                         ('Basic alerts','Advanced alert rules','Data & diagnostics'))

    def test_popup_monitor_preference_defaults_to_main_and_persists(self):
        self.assertEqual(POPUP_MONITOR_CHOICES,
                         ('Main monitor','Discovery Watch monitor','Mouse pointer monitor'))
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertEqual(popup_monitor_preference(db_path),'Main monitor')
            save_popup_monitor_preference('Mouse pointer monitor',db_path)
            self.assertEqual(popup_monitor_preference(db_path),'Mouse pointer monitor')
            with self.assertRaises(ValueError):
                save_popup_monitor_preference('Monitor 99',db_path)

    def test_home_uses_latest_alert_panel_without_duplicate_recent_table(self):
        self.assertTrue(callable(getattr(App,'update_home_alert_panel',None)))
        self.assertFalse(hasattr(App,'show_home_finding'))

    def test_compact_popup_identity_and_non_focus_policy(self):
        identity=popup_identity({'event':'FSSSignalDiscovered','SignalType':'Megaship',
                                 'SignalName_Localised':'DSSA Hope'},'Megaship detected','MEGASHIP')
        self.assertEqual(identity['name'],'DSSA Hope')
        self.assertEqual(identity['signal_type'],'Megaship')
        self.assertEqual(identity['event'],'FSSSignalDiscovered')
        self.assertTrue(AlertPopup.NON_FOCUSING)

    def test_linux_popup_visibility_mode_and_larger_startup_window(self):
        self.assertEqual(AlertPopup.LINUX_WINDOW_MODE,'splash_with_normal_fallback')
        self.assertEqual(DEFAULT_WINDOW_GEOMETRY,'1280x860')

    def test_popup_has_compositor_visibility_fallback(self):
        self.assertTrue(callable(getattr(AlertPopup,'_ensure_visible',None)))

    def test_wayland_uses_native_desktop_notification_with_safe_fallback(self):
        self.assertTrue(is_wayland_session({'XDG_SESSION_TYPE':'wayland'},'Linux'))
        self.assertTrue(is_wayland_session({'WAYLAND_DISPLAY':'wayland-0'},'Linux'))
        self.assertFalse(is_wayland_session({'XDG_SESSION_TYPE':'x11'},'Linux'))
        findings=[('Megaship detected','Sol','full explanation')]
        metadata=[{'name':'DSSA Hope','signal_type':'Megaship','event':'FSSSignalDiscovered'}]
        title,body=native_notification_payload(findings,metadata)
        self.assertIn('discovery update',title)
        self.assertIn('DSSA Hope',body); self.assertIn('FSSSignalDiscovered',body)
        with patch('discovery_watch.shutil.which',return_value=None):
            self.assertFalse(send_native_notification(findings,metadata))
        completed=type('Completed',(),{'returncode':0,'stdout':'42\n'})()
        with patch('discovery_watch.shutil.which',return_value='/usr/bin/notify-send'), \
             patch('discovery_watch.subprocess.run',return_value=completed) as run:
            self.assertEqual(send_native_notification(findings,metadata,15),42)
            self.assertIn('--expire-time=15000',run.call_args.args[0])
            self.assertIn('--print-id',run.call_args.args[0])
        with patch('discovery_watch.shutil.which',return_value='/usr/bin/gdbus'), \
             patch('discovery_watch.subprocess.run',return_value=type('Completed',(),{'returncode':0})()) as run:
            self.assertTrue(close_native_notification(42))
            self.assertIn('org.freedesktop.Notifications.CloseNotification',run.call_args.args[0])
        self.assertFalse(close_native_notification(True))

    def test_windows_primary_popup_uses_tk_logical_screen_and_native_reinforcement_exists(self):
        widget=type('Widget',(),{
            'winfo_screenwidth':lambda self:1536,
            'winfo_screenheight':lambda self:864,
        })()
        with patch('discovery_watch.platform.system',return_value='Windows'):
            self.assertEqual(popup_work_area(widget,'primary'),(0,0,1536,864))
        self.assertTrue(callable(reinforce_windows_popup))

    def test_popup_is_inset_from_selected_monitor_edges(self):
        self.assertEqual(POPUP_RIGHT_MARGIN,100)
        self.assertEqual(POPUP_TOP_MARGIN,60)
        self.assertEqual(POPUP_EDGE_MARGIN,32)
        self.assertEqual(popup_position((0,0,1920,1080),600,545,'Windows'),(660,60))
        self.assertEqual(popup_position((0,0,800,600),900,700,'Windows'),(0,0))

    def test_windows_popup_style_is_non_activating_before_map(self):
        class User32:
            def __init__(self): self.saved=None; self.saved_all=[]
            def GetParent(self,_hwnd): return 22
            def GetWindowLongW(self,hwnd,index): return 0x10
            def SetWindowLongW(self,hwnd,index,value):
                self.saved=(hwnd,index,value); self.saved_all.append(self.saved); return 1
        user32=User32()
        widget=type('Widget',(),{'winfo_id':lambda self:11})()
        with patch('discovery_watch.platform.system',return_value='Windows'):
            self.assertTrue(prepare_windows_popup(widget,user32))
        self.assertEqual(user32.saved[:2],(22,-20))
        self.assertTrue(user32.saved[2] & 0x08000000)
        self.assertTrue(user32.saved[2] & 0x00000080)
        self.assertEqual([item[0] for item in user32.saved_all],[11,22])
        self.assertTrue(AlertPopup.WINDOWS_NO_ACTIVATE_BEFORE_MAP)
        self.assertFalse(AlertPopup.WINDOWS_TK_TOPMOST)
        self.assertEqual(AlertPopup.WINDOWS_TOPMOST_REINFORCEMENT_MS,500)
        self.assertTrue(callable(getattr(AlertPopup,'_windows_keep_above',None)))
        self.assertTrue(callable(show_windows_popup))
        self.assertIs(_windows_monitor_info_type(),_windows_monitor_info_type())
        self.assertEqual(windows_popup_position((0,0,1920,1040),(600,500)),(660,90))
        self.assertEqual(windows_popup_position((-1920,0,0,1040),(600,500)),(-1260,90))

    def test_windows_monitor_coordinates_are_converted_for_dpi_scaling(self):
        baseline=96.0/72.0
        self.assertEqual(windows_work_area_to_tk((0,0,1920,1080),baseline),(0,0,1920,1080))
        self.assertEqual(windows_work_area_to_tk((0,0,1920,1080),baseline*1.5),(0,0,1280,720))
        self.assertEqual(windows_work_area_to_tk((-1920,0,0,1080),baseline*1.5),(-1280,0,0,720))

    def test_linux_ui_scaling_corrects_small_bundled_tk_fonts(self):
        class Tcl:
            def __init__(self,value): self.value=value; self.set_to=None
            def call(self,*args):
                if len(args)==2: return self.value
                self.set_to=args[2]; return ''
        root=type('Root',(),{})(); root.tk=Tcl(1.0)
        with patch('discovery_watch.platform.system',return_value='Linux'):
            self.assertAlmostEqual(ensure_linux_ui_scaling(root,{}),96.0/72.0)
        self.assertAlmostEqual(root.tk.set_to,96.0/72.0)

        root.tk=Tcl(1.75)
        with patch('discovery_watch.platform.system',return_value='Linux'):
            self.assertEqual(ensure_linux_ui_scaling(root,{}),1.75)
        self.assertEqual(root.tk.set_to,1.75)

        root.tk=Tcl(1.0)
        with patch('discovery_watch.platform.system',return_value='Linux'):
            self.assertEqual(ensure_linux_ui_scaling(root,{'DISCOVERY_WATCH_UI_SCALE':'1.5'}),1.5)
        self.assertEqual(root.tk.set_to,1.5)

    def test_alert_records_source_and_popup_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.explain.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                journal.write_text(json.dumps({'timestamp':'1','event':'FSSSignalDiscovered',
                    'StarSystem':'Explain','SignalType':'Megaship','SignalName_Localised':'Explain Ship'})+'\n')
                monitor.poll()
                row=monitor.recent()[0]
                self.assertEqual(row[11],'Live journal')
                self.assertEqual(row[12],'Popup eligible under the matching rule; the interface master popup switch is applied separately')
                columns={item[1] for item in monitor.db.execute('PRAGMA table_info(alerts)')}
                self.assertTrue({'origin','popup_decision'}.issubset(columns))

    def test_journal_replay_is_isolated_and_reports_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.sample.log'
            events=[
                {'timestamp':'1','event':'FSDJump','StarSystem':'Replay','SystemAddress':7},
                {'timestamp':'2','event':'FSSSignalDiscovered','SignalType':'Megaship',
                 'SignalName_Localised':'Replay Ship','SystemAddress':7},
                {'timestamp':'3','event':'FSSSignalDiscovered','SignalType':'Megaship',
                 'SignalName_Localised':'Replay Ship','SystemAddress':7},
                {'timestamp':'4','event':'Scan','BodyName':'Replay A 1','SystemAddress':7,
                 'SurfaceGravity':30.0,'Landable':True},
            ]
            original=''.join(json.dumps(event)+'\n' for event in events)
            journal.write_text(original)
            report=replay_journal_paths([journal])
            self.assertEqual(report['events'],4)
            self.assertEqual(report['findings'],2)
            self.assertEqual(report['duplicate_findings_suppressed'],1)
            self.assertEqual(report['anomalies'],2)
            self.assertIn('fresh-install',report['policy_basis'])
            self.assertIn('temporary database',report['isolation_note'])
            self.assertEqual(journal.read_text(),original)
            self.assertFalse((folder/'replay.sqlite3').exists())


class Version1104Tests(unittest.TestCase):
    def test_surface_signals_from_both_journal_events_reach_anomalies(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.signals.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'Location','StarSystem':'Signal System','SystemAddress':123},
                    {'timestamp':'2','event':'Scan','BodyName':'Signal System A 1','BodyID':1,
                     'SystemAddress':123,'SurfaceGravity':29.41995,'Landable':True},
                    {'timestamp':'3','event':'SAASignalsFound','BodyName':'Signal System A 1',
                     'BodyID':1,'SystemAddress':123,'Signals':[
                         {'Type':'$SAA_SignalType_Biological;','Type_Localised':'Biological','Count':1}]},
                    {'timestamp':'4','event':'FSSBodySignals','BodyName':'Signal System A 2',
                     'BodyID':2,'SystemAddress':123,'Signals':[
                         {'Type':'$SAA_SignalType_Geological;','Count':9}]},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                monitor.poll()
                rules={row[2] for row in monitor.anomalies('Signal System')}
                self.assertEqual(rules,{'HIGH_GRAVITY','LANDABLE_HIGH_G','SURFACE_SIGNALS_RECORDED','BIOLOGICAL_SIGNALS',
                                        'GEOLOGICAL_SIGNALS','SIGNAL_RICH_BODY'})
                self.assertEqual(monitor.live_summary('Signal System')['signals'],2)

    def test_old_historical_events_are_backfilled_without_resetting_review(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            heavy={'timestamp':'1','event':'Scan','BodyName':'Legacy A 1',
                   'SurfaceGravity':32.0,'Landable':True}
            signals={'timestamp':'2','event':'SAASignalsFound','BodyName':'Legacy A 1',
                     'Signals':[{'Type':'$SAA_SignalType_Biological;','Count':1}]}
            with Monitor(folder,db_path) as monitor:
                for event in (heavy,signals):
                    monitor._store_historical(event,'Journal.legacy.log',1,'Legacy')
                # Simulate opening a database created before the backfill migration.
                monitor.db.execute("DELETE FROM preferences WHERE key='anomaly_backfill_version'")
                monitor.db.commit()
            with Monitor(folder,db_path) as monitor:
                rules={row[2] for row in monitor.anomalies('Legacy')}
                self.assertEqual(rules,{'HIGH_GRAVITY','LANDABLE_HIGH_G','SURFACE_SIGNALS_RECORDED','BIOLOGICAL_SIGNALS'})
                heavy_row=next(row for row in monitor.anomalies('Legacy') if row[2]=='HIGH_GRAVITY')
                monitor.set_anomaly_status(heavy_row[0],'reviewed')
            with Monitor(folder,db_path) as monitor:
                self.assertEqual(len(monitor.anomalies('Legacy')),4)
                self.assertEqual(monitor.anomalies(status='reviewed')[0][2],'HIGH_GRAVITY')

    def test_non_biological_surface_signal_always_creates_anomaly(self):
        event={'event':'FSSBodySignals','BodyName':'Example A 1','Signals':[
            {'Type':'$SAA_SignalType_Human;','Type_Localised':'Human','Count':1}]}
        findings=detect_anomalies(event)
        self.assertEqual([finding[0] for finding in findings],['SURFACE_SIGNALS_RECORDED'])
        self.assertIn('Human=1',findings[0][2])

    def test_ring_hotspots_are_not_planetary_surface_signals(self):
        ring={'event':'SAASignalsFound','BodyName':'Example A Ring',
              'Signals':[{'Type':'LowTemperatureDiamond','Count':12}]}
        self.assertEqual(detect_anomalies(ring),[])


class Version1180SurfaceIntelligenceTests(unittest.TestCase):
    def test_thargoid_saa_signal_becomes_clear_finding(self):
        event={'event':'SAASignalsFound','BodyName':'Test System A 2','Signals':[
            {'Type':'$SAA_SignalType_Thargoid;','Type_Localised':'Thargoid','Count':3}]}
        observations=surface_signal_observations(event)
        self.assertEqual(observations[0]['category'],'thargoid')
        finding=surface_signal_findings(event)[0]
        self.assertEqual(finding[0],'SURFACE_THARGOID')
        self.assertEqual(finding[1],'Thargoid surface signals confirmed')
        self.assertIn('Signal type=Thargoid; Count=3',finding[2])
        self.assertEqual(alert_level(finding[0]),'Important')

    def test_surface_popup_preferences_default_and_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'db.sqlite3'
            self.assertEqual(surface_signal_popup_preferences(db_path),{
                'thargoid':True,'guardian':True,'biological':False,
                'geological':False,'human':False,'other':False})
            save_surface_signal_popup_preferences({
                'thargoid':False,'guardian':True,'biological':True,
                'geological':True,'human':False,'other':True},db_path)
            self.assertEqual(surface_signal_popup_preferences(db_path),{
                'thargoid':False,'guardian':True,'biological':True,
                'geological':True,'human':False,'other':True})

    def test_old_combined_surface_choice_migrates_to_geological_and_human(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'db.sqlite3'
            with closing(sqlite3.connect(db_path)) as db, db:
                db.execute('CREATE TABLE preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                db.execute("INSERT INTO preferences VALUES('surface_popup_other','1')")
            values=surface_signal_popup_preferences(db_path)
            self.assertTrue(values['geological'])
            self.assertTrue(values['human'])
            self.assertTrue(values['other'])

    def test_all_surface_categories_record_but_popup_switches_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.surface.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'Location','StarSystem':'Surface Test','SystemAddress':91},
                    {'timestamp':'2','event':'SAASignalsFound','BodyName':'Surface Test A 1',
                     'SystemAddress':91,'Signals':[
                         {'Type':'$SAA_SignalType_Thargoid;','Type_Localised':'Thargoid','Count':1},
                         {'Type':'$SAA_SignalType_Biological;','Type_Localised':'Biological','Count':2},
                         {'Type':'$SAA_SignalType_Human;','Type_Localised':'Human','Count':1}]},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                found=monitor.poll()
                self.assertEqual({row[0] for row in found},{
                    'Thargoid surface signal confirmed','Biological surface signals confirmed',
                    'Human surface signal confirmed'})
                self.assertEqual([row[0] for row in monitor.popup_findings],
                                 ['Thargoid surface signal confirmed'])
                rules={row[2] for row in monitor.anomalies('Surface Test')}
                self.assertTrue({'SURFACE_SIGNALS_RECORDED','BIOLOGICAL_SIGNALS'}.issubset(rules))

    def test_geological_human_and_other_popup_switches_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.surface-split.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Split Surface','SystemAddress':92},
                    {'timestamp':'2','event':'SAASignalsFound','BodyName':'Split Surface A 1',
                     'SystemAddress':92,'Signals':[
                         {'Type':'$SAA_SignalType_Geological;','Type_Localised':'Geological','Count':2},
                         {'Type':'$SAA_SignalType_Human;','Type_Localised':'Human','Count':1},
                         {'Type':'$SAA_SignalType_Mystery;','Type_Localised':'Mystery','Count':1}]},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                options=(True,True,True,True,False,False,True,False,
                         False,False,False,False,True,True,False,True,False)
                found=monitor.poll(options)
                self.assertEqual({item[0] for item in found},{
                    'Geological surface signals confirmed','Human surface signal confirmed',
                    'Other surface signal confirmed'})
                self.assertEqual([item[0] for item in monitor.popup_findings],
                                 ['Human surface signal confirmed'])


class Version1190EarlyFSSSignalTests(unittest.TestCase):
    def test_fss_alerts_early_and_later_saa_confirmation_does_not_popup_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.early.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Early System','SystemAddress':501},
                    {'timestamp':'2','event':'FSSBodySignals','BodyName':'Early System A 2',
                     'BodyID':4,'SystemAddress':501,'Signals':[
                         {'Type':'$SAA_SignalType_Thargoid;','Type_Localised':'Thargoid','Count':1}]},
                    {'timestamp':'3','event':'SAASignalsFound','BodyName':'Early System A 2',
                     'BodyID':4,'SystemAddress':501,'Signals':[
                         {'Type':'$SAA_SignalType_Thargoid;','Type_Localised':'Thargoid','Count':1}]},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                found=monitor.poll()
                self.assertEqual([item[0] for item in found],[
                    'Possible Thargoid surface signal','Thargoid surface signal confirmed'])
                self.assertEqual([item[0] for item in monitor.popup_findings],
                                 ['Possible Thargoid surface signal'])
                rows=monitor.recent()
                self.assertEqual(len(rows),2)
                confirmation=next(row for row in rows if row[3]=='Thargoid surface signal confirmed')
                self.assertIn('matching FSS body-signal alert was already shown',confirmation[12])


class Version1191StratumTests(unittest.TestCase):
    def test_stratum_genus_is_a_lead_and_tectonicas_species_is_confirmed(self):
        saa={'event':'SAASignalsFound','BodyName':'Bio System A 1','Genuses':[
            {'Genus':'$Codex_Ent_Stratum_Genus_Name;','Genus_Localised':'Stratum'}]}
        lead=stratum_findings(saa)[0]
        self.assertEqual(lead[0],'BIO_STRATUM_LEAD')
        self.assertIn('possible Tectonicas',lead[1])
        self.assertIn('genus only',lead[2])
        organic={'event':'ScanOrganic','Body':'Bio System A 1','ScanType':'Log',
                 'Genus':'$Codex_Ent_Stratum_Genus_Name;','Genus_Localised':'Stratum',
                 'Species':'$Codex_Ent_Stratum_02_Name;',
                 'Species_Localised':'Stratum Tectonicas'}
        confirmed=stratum_findings(organic)[0]
        self.assertEqual(confirmed[0],'BIO_STRATUM_TECTONICAS')
        self.assertEqual(confirmed[1],'Stratum Tectonicas confirmed')
        self.assertEqual(alert_level(confirmed[0]),'Important')

    def test_stratum_preference_and_three_samples_only_alert_once(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            self.assertTrue(stratum_popup_preference(db_path))
            save_stratum_popup_preference(False,db_path)
            self.assertFalse(stratum_popup_preference(db_path))
            journal=folder/'Journal.stratum.log'; journal.write_text('')
            with Monitor(folder,db_path) as monitor:
                monitor.start_at_end()
                events=[{'timestamp':'1','event':'FSDJump','StarSystem':'Bio System','SystemAddress':601}]
                for index,scan_type in enumerate(('Log','Sample','Analyse'),2):
                    events.append({'timestamp':str(index),'event':'ScanOrganic','Body':'Bio System A 1',
                        'SystemAddress':601,'ScanType':scan_type,
                        'Genus_Localised':'Stratum','Species_Localised':'Stratum Tectonicas'})
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                found=monitor.poll((True,True,True,True,True,False,True,False,
                                    True,True,False,False,False))
                self.assertEqual([item[0] for item in found],['Stratum Tectonicas confirmed'])
                self.assertEqual(monitor.popup_findings,[])
                self.assertIn('Stratum popups are disabled',monitor.recent()[0][12])


class Version1210DiscoveryCasesAndWatchlistsTests(unittest.TestCase):
    def test_case_progression_before_leave_warning_and_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.cases.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                first=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Case System','SystemAddress':701},
                    {'timestamp':'2','event':'FSSBodySignals','BodyName':'Case System A 1','BodyID':3,
                     'SystemAddress':701,'Signals':[{'Type':'$SAA_SignalType_Biological;',
                                                    'Type_Localised':'Biological','Count':1}]},
                    {'timestamp':'3','event':'StartJump','JumpType':'Hyperspace','StarSystem':'Next System'},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in first))
                found=monitor.poll()
                self.assertTrue(any(item[0]=='Unfinished discoveries before departure' for item in found))
                case=monitor.active_cases('Case System')[0]
                self.assertEqual((case[3],case[4],case[5]),('Biological surface signals','Lead','Reported'))
                with journal.open('a') as output:
                    output.write(json.dumps({'timestamp':'4','event':'SAASignalsFound',
                        'BodyName':'Case System A 1','BodyID':3,'SystemAddress':701,
                        'Signals':[{'Type':'$SAA_SignalType_Biological;','Type_Localised':'Biological','Count':1}],
                        'Genuses':[{'Genus_Localised':'Stratum'}]})+'\n')
                    output.write(json.dumps({'timestamp':'5','event':'ScanOrganic','Body':'Case System A 1',
                        'SystemAddress':701,'ScanType':'Analyse','Genus_Localised':'Stratum',
                        'Species_Localised':'Stratum Tectonicas'})+'\n')
                monitor.poll()
                cases=monitor.db.execute("SELECT target_key,state,status FROM discovery_cases ORDER BY target_key").fetchall()
                self.assertIn(('bio:stratum','Completed','closed'),cases)
                self.assertIn(('surface:biological','Completed','closed'),cases)

    def test_before_leave_preference_and_commander_watchlist(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'; journal=folder/'Journal.watch.log'; journal.write_text('')
            self.assertTrue(before_leave_preference(db_path))
            save_before_leave_preference(False,db_path); self.assertFalse(before_leave_preference(db_path))
            with Monitor(folder,db_path) as monitor:
                monitor.add_watchlist('My rare beacon','Ancient Test Beacon',popup=False,priority=90)
                row=monitor.watchlists()[0]
                self.assertEqual((row[1],row[2],row[3],row[4],row[5]),
                                 ('My rare beacon','Ancient Test Beacon',1,0,90))
                monitor.start_at_end()
                journal.write_text(json.dumps({'timestamp':'1','event':'FSSSignalDiscovered',
                    'StarSystem':'Watch System','SignalName_Localised':'Ancient Test Beacon'})+'\n')
                found=monitor.poll()
                self.assertEqual(found[0][0],'Watchlist match: My rare beacon')
                self.assertEqual(monitor.popup_findings,[])
                self.assertEqual(monitor.recent()[0][10],'Important')
                monitor.toggle_watchlist(row[0],'enabled')
                self.assertFalse(monitor.watchlists()[0][3])


class Version1211PopupDiagnosticsTests(unittest.TestCase):
    def test_wayland_diagnostics_explain_monitor_control_and_report_support_data(self):
        with patch('discovery_watch.shutil.which',side_effect=lambda name:'/usr/bin/'+name):
            info=popup_diagnostics(None,'Mouse pointer monitor',True,15,True,True,
                                   {'XDG_SESSION_TYPE':'wayland','WAYLAND_DISPLAY':'wayland-0'},'Linux')
        self.assertEqual(info['notification_method'],'Native Wayland notification')
        self.assertFalse(info['monitor_setting_effective'])
        self.assertEqual(info['calculated_work_area'],'Desktop controlled')
        self.assertTrue(info['notify_send_available']); self.assertTrue(info['gdbus_available'])
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                report=monitor.diagnostic_report()
                self.assertIn('popup_diagnostics',report)
                self.assertNotIn('raw_json',json.dumps(report))


class Version1212HomeLayoutTests(unittest.TestCase):
    def test_home_investigations_and_alerts_use_resizable_side_by_side_layout(self):
        self.assertEqual(HOME_OVERVIEW_LOWER_LAYOUT,'side_by_side_resizable')


class Version1220SettingsNavigationTests(unittest.TestCase):
    def test_settings_pages_are_scrollable_and_keyboard_navigable(self):
        self.assertTrue(SETTINGS_SCROLLABLE)
        self.assertTrue(SETTINGS_KEYBOARD_NAVIGATION)
        self.assertTrue(callable(add_scrollable_notebook_page))
        self.assertEqual(SETTINGS_TAB_LABELS,
                         ('Basic alerts','Advanced alert rules','Data & diagnostics'))
        for method in ('_scroll_settings_wheel','_scroll_settings_key','_scroll_settings_end'):
            self.assertTrue(callable(getattr(App,method,None)))


class Version1230WindowsNotificationModeTests(unittest.TestCase):
    def test_windows_game_overlay_is_default_and_retired_custom_mode_migrates(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'db.sqlite3'
            self.assertEqual(WINDOWS_DEFAULT_NOTIFICATION_MODE,WINDOWS_NOTIFICATION_MODES[1])
            self.assertEqual(windows_notification_mode_preference(db_path),WINDOWS_NOTIFICATION_MODES[1])
            save_windows_notification_mode_preference(WINDOWS_NOTIFICATION_MODES[0],db_path)
            self.assertEqual(windows_notification_mode_preference(db_path),WINDOWS_NOTIFICATION_MODES[0])
            with closing(sqlite3.connect(db_path)) as db, db:
                db.execute("UPDATE preferences SET value='custom' WHERE key='windows_notification_mode'")
            self.assertEqual(windows_notification_mode_preference(db_path),WINDOWS_NOTIFICATION_MODES[1])
            with closing(sqlite3.connect(db_path)) as db, db:
                self.assertEqual(db.execute("SELECT value FROM preferences WHERE key='windows_notification_mode'").fetchone()[0],
                                 'overlay')
            with self.assertRaises(ValueError):
                save_windows_notification_mode_preference('invalid',db_path)

    def test_windows_notification_uses_hidden_encoded_powershell(self):
        completed=type('Completed',(),{'returncode':0,'stdout':'','stderr':''})()
        with patch('discovery_watch.platform.system',return_value='Windows'), \
             patch('discovery_watch.shutil.which',side_effect=lambda name:'C:/Windows/powershell.exe' if name=='powershell.exe' else None), \
             patch('discovery_watch.subprocess.run',return_value=completed) as run:
            self.assertTrue(send_windows_notification(
                [('Megaship detected','Sol','detail')],
                [{'name':'Test Megaship','signal_type':'Megaship','event':'FSSSignalDiscovered'}],15))
        command=run.call_args.args[0]
        self.assertIn('-WindowStyle',command); self.assertIn('Hidden',command)
        script=base64.b64decode(command[-1]).decode('utf-16le')
        self.assertIn('ToastNotificationManager',script)
        self.assertIn('Discovery Watch',script)

    def test_windows_notification_area_is_primary_and_cleanup_is_supported(self):
        class User32:
            def GetParent(self,_hwnd): return 22
            def LoadIconW(self,_instance,_icon): return 99
        class Shell32:
            def __init__(self): self.messages=[]
            def Shell_NotifyIconW(self,message,pointer):
                self.messages.append((message,pointer._obj.uID,pointer._obj.uFlags))
                return 1
        widget=type('Widget',(),{'winfo_id':lambda self:11})()
        shell=Shell32()
        with patch('discovery_watch.platform.system',return_value='Windows'):
            token=_send_windows_shell_notification(widget,
                [('Megaship detected','Sol','detail')],None,15,User32(),shell)
        self.assertEqual(token['method'],'Windows notification area')
        self.assertEqual([item[0] for item in shell.messages],[0,4,1])
        self.assertTrue(close_windows_notification(token,shell))
        self.assertEqual(shell.messages[-1][0],2)

    def test_windows_diagnostics_reports_selected_notification_mode(self):
        info=popup_diagnostics(system_name='Windows',windows_mode=WINDOWS_NOTIFICATION_MODES[0])
        self.assertEqual(info['notification_method'],WINDOWS_NOTIFICATION_MODES[0])

    def test_windows_overlay_launches_isolated_encoded_process(self):
        class User32:
            def GetParent(self,_hwnd): return 22
        calls=[]
        def popen(command,**kwargs):
            calls.append((command,kwargs)); return object()
        widget=type('Widget',(),{'winfo_id':lambda self:11})()
        with patch('discovery_watch.platform.system',return_value='Windows'):
            self.assertTrue(send_windows_overlay(widget,
                [('Installation detected','Sol','detail')],None,15,'Main monitor',User32(),popen))
        command,kwargs=calls[0]
        self.assertEqual(command[2],'--windows-overlay')
        payload=decode_windows_overlay_payload(command[3])
        self.assertEqual(payload['owner'],22)
        self.assertEqual(payload['monitor'],'primary')
        self.assertEqual(payload['position'],'Bottom right')
        self.assertEqual(payload['font_size'],'Normal')
        self.assertEqual(payload['layout'],'Standard')
        self.assertIn('Installation detected',payload['body'])
        self.assertIn('creationflags',kwargs)


class Version1250ReliabilityTests(unittest.TestCase):
    def test_realistic_popup_scenarios_have_compact_identity_metadata(self):
        self.assertEqual(POPUP_TEST_SCENARIOS,
                         ('Megaship discovery','Surface biology','Anomaly review'))
        for scenario in POPUP_TEST_SCENARIOS:
            findings,metadata=popup_test_scenario(scenario)
            self.assertEqual(len(findings),1); self.assertEqual(len(metadata),1)
            self.assertTrue(findings[0][0]); self.assertTrue(findings[0][1])
            self.assertTrue(metadata[0]['name']); self.assertTrue(metadata[0]['signal_type'])
            self.assertTrue(metadata[0]['event'])

    def test_notification_delivery_audit_records_launches_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'audit.sqlite3'
            findings=[('Megaship detected','Audit System','detail')]
            record_notification_delivery('Windows game overlay','launched',findings,'Popup test',db_path=db_path)
            record_notification_delivery('Native Windows notification','failed',findings,'Live journal',
                                         'Unavailable',db_path=db_path)
            summary=notification_delivery_summary(db_path)
            self.assertEqual((summary['total'],summary['launched'],summary['failed']),(2,1,1))
            self.assertEqual(summary['last_delivery']['result'],'failed')
            self.assertEqual(summary['last_delivery']['system_name'],'Audit System')
            self.assertNotIn('raw_json',json.dumps(summary))

    def test_builtin_reliability_check_covers_arrivals_duplicates_and_surface_signals(self):
        report=run_reliability_self_check()
        self.assertTrue(report['passed'],report)
        self.assertTrue(all(report['checks'].values()))
        self.assertGreaterEqual(report['duplicates_suppressed'],1)
        self.assertEqual(report['events'],10)

    def test_three_generic_notable_stellar_phenomena_all_reach_popup_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.phenomena.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.generic_notify_once(False)
                monitor.start_at_end()
                events=[{'timestamp':'1','event':'FSDJump','StarSystem':'Phenomena System','SystemAddress':771}]
                events.extend({'timestamp':str(index+1),'event':'FSSSignalDiscovered','SystemAddress':771,
                               'SignalType':'Generic','SignalName':f'$Fixed_Event_Life_Cloud_{index};',
                               'SignalName_Localised':'Notable Stellar Phenomena'}
                              for index in range(1,4))
                with journal.open('a') as output:
                    output.writelines(json.dumps(event)+'\n' for event in events)
                monitor.poll()
                phenomena=[row for row in monitor.recent(100) if row[3]=='Notable stellar phenomenon signal']
                popup_phenomena=[row for row in monitor.popup_findings
                                 if row[0]=='Notable stellar phenomenon signal']
                self.assertEqual(len(phenomena),3)
                self.assertEqual(len(popup_phenomena),3)
                self.assertTrue(all(row[2]=='Phenomena System' for row in phenomena))
                self.assertTrue(all('Popup eligible' in row[12] for row in phenomena))


class Version1252SimplifiedPopupAndHistoryTests(unittest.TestCase):
    def test_all_popup_categories_are_quantity_free_and_deduplicated(self):
        findings=[
            ('Notable stellar phenomenon signal','Simple System','FSSSignalDiscovered: Notable Stellar Phenomena'),
            ('Notable stellar phenomenon signal','Simple System','FSSSignalDiscovered: Notable Stellar Phenomena'),
            ('Megaship detected','Simple System','FSSSignalDiscovered: signalType=Megaship'),
            ('Megaship detected','Simple System','FSSSignalDiscovered: signalType=Megaship'),
            ('Possible Thargoid surface signals','Simple System','FSSBodySignals: Count=3'),
            ('Possible Guardian surface signal','Simple System','FSSBodySignals: Count=1'),
            ('Anomaly review: Simple System A 1','Simple System',
             'Rules: VALUABLE_WORLD (55), TERRAFORMABLE (45). Simple System A 1: Earthlike body'),
            ('Anomaly review: Simple System A 2','Simple System',
             'Rules: VALUABLE_WORLD (55). Simple System A 2: Water world'),
        ]
        metadata=[popup_identity({},title) for title,_,_ in findings]
        simplified,identities=simplify_popup_content(findings,metadata)
        labels=[row[0] for row in simplified]
        self.assertEqual(labels,['Notable Stellar Phenomena','Megaship','Thargoid signals',
                                 'Guardian signals','Earth-like world','Terraformable world','Water world'])
        self.assertEqual(len(labels),len(set(labels)))
        self.assertTrue(all(row[2]=='Check Discovery History for more information.' for row in simplified))
        self.assertTrue(all(item['compact_summary'] for item in identities))
        title,body=native_notification_payload(simplified,identities)
        self.assertEqual(title,'Discovery Watch - discoveries detected')
        self.assertIn('System: Simple System',body)
        self.assertIn('Notable Stellar Phenomena',body)
        self.assertNotIn('discovery updates',title.casefold())
        self.assertNotIn('Count=',body)

    def test_clear_discovery_history_preserves_other_data(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            with Monitor(folder,db_path) as monitor:
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,timestamp,detail,raw_json)
                    VALUES(?,?,?,?,?,?,?,?)''',('Journal.test.log',1,'MEGASHIP','Megaship detected',
                    'Preserved System','1','detail','{}'))
                monitor.db.execute('''INSERT INTO anomalies
                    (event_key,rule,score,system_name,body_name,explanation,evidence_field,raw_json)
                    VALUES(?,?,?,?,?,?,?,?)''',('event-1','HIGH_GRAVITY',70,'Preserved System','A 1',
                    'evidence','SurfaceGravity','{}'))
                monitor.db.execute('''INSERT INTO exploration_events
                    (fingerprint,journal_file,line_no,event_type,raw_json,event_key)
                    VALUES(?,?,?,?,?,?)''',('fact-1','Journal.test.log',2,'Scan','{}','fact-event-1'))
                monitor.db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('test_preserved','1')")
                monitor.db.execute('''INSERT INTO notification_deliveries
                    (attempted_at,operating_system,method,result,source,finding_count)
                    VALUES('1','Windows','Windows game overlay','launched','Popup test',1)''')
                monitor.db.execute('''INSERT INTO structure_identity_links
                    (rule,system_name,alias_a,alias_b) VALUES(?,?,?,?)''',
                    ('MEGASHIP','Preserved System','$internal;','readable name'))
                monitor.db.commit()
                self.assertEqual(clear_discovery_history(connection=monitor.db),1)
                self.assertEqual(monitor.db.execute('SELECT COUNT(*) FROM alerts').fetchone()[0],0)
                self.assertEqual(monitor.db.execute(
                    'SELECT COUNT(*) FROM structure_identity_links').fetchone()[0],0)
                self.assertEqual(monitor.db.execute('SELECT COUNT(*) FROM anomalies').fetchone()[0],1)
                self.assertEqual(monitor.db.execute('SELECT COUNT(*) FROM exploration_events').fetchone()[0],1)
                self.assertEqual(monitor.db.execute("SELECT value FROM preferences WHERE key='test_preserved'").fetchone()[0],'1')
                self.assertEqual(monitor.db.execute('SELECT COUNT(*) FROM notification_deliveries').fetchone()[0],1)


class Version1260UnifiedDiscoveryIntelligenceTests(unittest.TestCase):
    def test_finding_type_categories_cover_unified_history(self):
        self.assertEqual(FINDING_TYPE_CHOICES[0],'All findings')
        self.assertEqual(finding_type('MEGASHIP'),'Signals and POIs')
        self.assertEqual(finding_type('SURFACE_THARGOID'),'Surface signals')
        self.assertEqual(finding_type('BIO_STRATUM_TECTONICAS'),'Biological discoveries')
        self.assertEqual(finding_type('BEFORE_LEAVING'),'Exploration reminders')
        self.assertEqual(finding_type('ANOMALY_ALERT',detail='Rules: HIGH_GRAVITY (70)'),'Anomalies')
        self.assertEqual(finding_type('ANOMALY_ALERT',detail='Rules: VALUABLE_WORLD (55)'),'Notable worlds')
        self.assertEqual(finding_type('ANOMALY_ALERT',detail='Rules: TERRAFORMABLE (45)'),'Notable worlds')

    def test_anomaly_history_is_saved_when_popup_is_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            journal=folder/'Journal.unified.log'; journal.write_text('')
            with Monitor(folder,db_path) as monitor:
                monitor.start_at_end()
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'Location','StarSystem':'Unified System','SystemAddress':126})+'\n')
                    output.write(json.dumps({'event':'Scan','SystemAddress':126,'BodyName':'Unified System A 1',
                                             'PlanetClass':'Water world','TerraformState':'Terraformable'})+'\n')
                findings=monitor.poll((True,True,True,True,True,False))
                self.assertEqual(len(findings),1)
                self.assertEqual(monitor.popup_findings,[])
                row=monitor.recent()[0]
                self.assertEqual(row[13],'ANOMALY_ALERT')
                self.assertIn('VALUABLE_WORLD',row[4])
                self.assertIn('TERRAFORMABLE',row[4])
                self.assertIn('anomaly popups are disabled',row[12])

    def test_existing_anomalies_migrate_once_and_preserve_review_state(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            event={'event':'Scan','timestamp':'2026-09-26T12:00:00Z','SystemAddress':126,
                   'BodyName':'Legacy System A 1','SurfaceGravity':30.0}
            raw=json.dumps(event,sort_keys=True)
            with Monitor(folder,db_path) as monitor:
                monitor.db.execute('''INSERT INTO exploration_events
                    (fingerprint,journal_file,line_no,timestamp,system_name,system_address,event_type,
                     body_name,fact_type,raw_json,event_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    ('legacy-key','Journal.legacy.log',42,event['timestamp'],'Legacy System','126','Scan',
                     event['BodyName'],'scan',raw,'legacy-key'))
                monitor.db.execute('''INSERT INTO anomalies
                    (event_key,rule,score,system_name,body_name,timestamp,explanation,evidence_field,raw_json,status)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''',('legacy-key','HIGH_GRAVITY',70,'Legacy System',
                    event['BodyName'],event['timestamp'],'Legacy high gravity','SurfaceGravity',raw,'reviewed'))
                monitor.db.execute("DELETE FROM preferences WHERE key='unified_anomaly_history_version'")
                monitor.db.commit()
            with Monitor(folder,db_path) as monitor:
                rows=[row for row in monitor.recent() if row[13]=='ANOMALY_ALERT']
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0][6],'Journal.legacy.log')
                self.assertEqual(rows[0][7],42)
                self.assertEqual(rows[0][8],'acknowledged')
                self.assertEqual(rows[0][11],'Anomaly migration')
                self.assertEqual(len(monitor.anomalies()),1)
            with Monitor(folder,db_path) as monitor:
                self.assertEqual(len([row for row in monitor.recent() if row[13]=='ANOMALY_ALERT']),1)


class Version1270ArchitectureTests(unittest.TestCase):
    def test_public_compatibility_api_uses_internal_modules(self):
        self.assertEqual(classify.__module__,'discovery_watch_core.detection')
        self.assertEqual(detection_preferences.__module__,'discovery_watch_core.preferences')
        self.assertEqual(fetch_edsm_system.__module__,'discovery_watch_core.community')
        self.assertEqual(simplify_popup_content.__module__,'discovery_watch_core.presentation')

    def test_internal_modules_import_without_starting_the_interface(self):
        for name in ('config','detection','preferences','community','presentation'):
            module=__import__(f'discovery_watch_core.{name}',fromlist=[name])
            self.assertTrue(module.__name__.startswith('discovery_watch_core.'))

    def test_stateful_monitor_and_interface_remain_compatible(self):
        self.assertEqual(Monitor.__module__,'discovery_watch')
        self.assertEqual(App.__module__,'discovery_watch')
        self.assertEqual(AlertPopup.__module__,'discovery_watch')


class Version1271SignalIdentityPopupTests(unittest.TestCase):
    def test_all_explicit_signal_types_show_type_and_name(self):
        cases=[
            ({'event':'FSSSignalDiscovered','SignalName':'Generation Ship Artemis',
              'SignalType':'Megaship'},'Megaship — Generation Ship Artemis'),
            ({'event':'FSSSignalDiscovered','SignalName_Localised':'Military Installation',
              'SignalType':'Installation'},'Installation — Military Installation'),
            ({'event':'FSSSignalDiscovered','SignalName_Localised':'Unregistered Comms Beacon',
              'SignalType':'Generic'},'Generic — Unregistered Comms Beacon'),
            ({'event':'FSSSignalDiscovered','SignalName_Localised':'Ancient Battlefield',
              'SignalType':'TouristBeacon'},'TouristBeacon — Ancient Battlefield'),
            ({'event':'FSSSignalDiscovered','SignalName_Localised':'Titan Cocijo',
              'SignalType':'Titan'},'Titan — Titan Cocijo'),
            ({'event':'FSSSignalDiscovered','SignalName_Localised':'Threat 5',
              'USSType_Localised':'Nonhuman signal source'},
             'Nonhuman signal source — Threat 5'),
            ({'event':'FSSSignalDiscovered','SignalName_Localised':'Listening Post Alpha',
              'Type_Localised':'Listening Post'},'Listening Post — Listening Post Alpha'),
        ]
        findings=[('Discovery detected','Identity System','full evidence') for _event,_label in cases]
        metadata=[popup_identity(event,'Discovery detected') for event,_label in cases]
        simplified,identities=simplify_popup_content(findings,metadata)
        self.assertEqual([row[0] for row in simplified],[label for _event,label in cases])
        self.assertTrue(all(item['compact_summary'] for item in identities))

    def test_signal_identity_prefers_localised_names_and_deduplicates_exact_pairs(self):
        events=[
            {'event':'FSSSignalDiscovered','SignalType':'Megaship',
             'SignalName':'Generation Ship Artemis'},
            {'event':'FSSSignalDiscovered','SignalType':'Megaship',
             'SignalName':'Generation Ship Artemis'},
            {'event':'FSSSignalDiscovered','SignalType':'Megaship',
             'SignalName':'$Internal_Name;','SignalName_Localised':'DSSA Hope'},
            {'event':'FSSSignalDiscovered','signalType':'Megaship'},
        ]
        findings=[('Megaship detected','Identity System','full evidence') for _event in events]
        simplified,_metadata=simplify_popup_content(
            findings,[popup_identity(event,'Megaship detected') for event in events])
        self.assertEqual([row[0] for row in simplified],[
            'Megaship — Generation Ship Artemis','Megaship — DSSA Hope','Megaship'])

    def test_non_signal_findings_keep_categories_and_delivery_text_matches(self):
        signal={'event':'FSSSignalDiscovered','SignalType':'Megaship',
                'SignalName':'Generation Ship Artemis'}
        world={'event':'Scan','BodyName':'Identity System A 3','PlanetClass':'Water world'}
        findings=[
            ('Megaship detected','Identity System','signalType=Megaship'),
            ('Anomaly review: Identity System A 3','Identity System',
             'Rules: VALUABLE_WORLD (55). Identity System A 3: Water world'),
        ]
        simplified,metadata=simplify_popup_content(
            findings,[popup_identity(signal,findings[0][0]),popup_identity(world,findings[1][0])])
        self.assertEqual([row[0] for row in simplified],
                         ['Megaship — Generation Ship Artemis',
                          'Water world — Identity System A 3'])
        title,body=native_notification_payload(simplified,metadata)
        self.assertEqual(title,'Discovery Watch - discoveries detected')
        self.assertIn('Megaship — Generation Ship Artemis',body)
        self.assertIn('Water world',body)
        self.assertNotIn('signalType=',body)

    def test_live_journal_megaship_identity_reaches_compact_popup(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.identity.log'; journal.write_text('')
            event={'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1271,
                   'SignalName':'Generation Ship Artemis','SignalType':'Megaship'}
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.observe_signal_type(event,'Identity System')
                monitor.db.commit()
                monitor.set_signal_policy('megaship','alert',85,True)
                monitor.start_at_end()
                with journal.open('a') as output:
                    output.write(json.dumps({'timestamp':'1','event':'FSDJump',
                                             'StarSystem':'Identity System',
                                             'SystemAddress':1271})+'\n')
                    output.write(json.dumps(event)+'\n')
                monitor.poll()
                self.assertEqual(monitor.popup_findings[0][0],'Megaship detected')
                simplified,_metadata=simplify_popup_content(
                    monitor.popup_findings,monitor.popup_metadata)
                self.assertEqual(simplified,[('Megaship — Generation Ship Artemis',
                    'Identity System','Check Discovery History for more information.')])


class Version1272CompactJournalEvidenceTests(unittest.TestCase):
    def test_signal_evidence_uses_event_name_type_order(self):
        event={'timestamp':'2026-09-26T18:53:23Z','event':'FSSSignalDiscovered',
               'SystemAddress':9466510583217,'SignalName':'Generation Ship Artemis',
               'SignalType':'Megaship'}
        summary=journal_evidence_summary(event)
        self.assertEqual(summary,
                         'FSSSignalDiscovered — Generation Ship Artemis — Megaship')
        self.assertNotIn('timestamp',summary)
        self.assertNotIn('SystemAddress',summary)
        self.assertNotIn('{',summary)

    def test_evidence_summary_prefers_localised_values_and_omits_missing_parts(self):
        self.assertEqual(journal_evidence_summary({
            'event':'FSSSignalDiscovered','SignalName':'$Internal_Name;',
            'SignalName_Localised':'Localised Contact','SignalType':'Generic'}),
            'FSSSignalDiscovered — Localised Contact — Generic')
        self.assertEqual(journal_evidence_summary({'event':'Scan'}),'Scan')
        self.assertEqual(journal_evidence_summary({}),'Unknown journal event')
        self.assertEqual(journal_evidence_summary(None),'Unknown journal event')

    def test_compact_view_preserves_raw_evidence_and_exposes_raw_view(self):
        self.assertTrue(callable(getattr(App,'show_raw_journal_data',None)))
        event={'timestamp':'2026-09-26T18:53:23Z','event':'FSSSignalDiscovered',
               'SystemAddress':9466510583217,'SignalName':'Generation Ship Artemis',
               'SignalType':'Megaship'}
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.evidence.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                with journal.open('a') as output:
                    output.write(json.dumps({'timestamp':'1','event':'FSDJump',
                        'StarSystem':'Evidence System','SystemAddress':9466510583217})+'\n')
                    output.write(json.dumps(event)+'\n')
                monitor.poll()
                stored=next(row for row in monitor.recent() if row[13]=='MEGASHIP')
                self.assertEqual(json.loads(stored[5]),event)
                self.assertEqual(journal_evidence_summary(json.loads(stored[5])),
                    'FSSSignalDiscovered — Generation Ship Artemis — Megaship')


class Version1273ArrivalMegashipDeduplicationTests(unittest.TestCase):
    @staticmethod
    def seed_megaship(monitor,name='Generation Ship Artemis'):
        event={'event':'FSSSignalDiscovered','SignalName':name,'SignalType':'Megaship'}
        monitor.db.execute('''INSERT INTO alerts
            (journal_file,line_no,rule,title,system_name,detail,raw_json)
            VALUES(?,?,?,?,?,?,?)''',('old.log',1,'MEGASHIP','Megaship detected',
            'Arrival System','stored evidence',json.dumps(event)))
        monitor.db.commit()

    def test_arrival_recall_suppresses_same_live_popup_but_saves_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.arrival.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                self.seed_megaship(monitor); monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Arrival System',
                     'SystemAddress':1273},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1273,
                     'SignalName':'Generation Ship Artemis','SignalType':'Megaship'},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                monitor.poll()
                self.assertEqual(len(monitor.popup_findings),1)
                self.assertTrue(monitor.popup_findings[0][0].startswith('Known POIs on arrival'))
                live=[row for row in monitor.recent() if row[6].endswith('Journal.arrival.log')
                      and row[13]=='MEGASHIP']
                self.assertEqual(len(live),1)
                self.assertIn('already announced by Known POIs on arrival',live[0][12])


class Version1300UnifiedDetectionPolicyTests(unittest.TestCase):
    def test_finding_policy_separates_record_case_and_popup_decisions(self):
        mining=finding_policy('SURFACE_MINING')
        thargoid=finding_policy('SURFACE_THARGOID')
        megaship=finding_policy('MEGASHIP')
        self.assertEqual((mining.record,mining.creates_investigation,mining.popup_control,
                          mining.attention),(True,False,'Planetary Mining Locations','Informational'))
        self.assertTrue(thargoid.creates_investigation)
        self.assertEqual(thargoid.popup_control,'Thargoid surface signals')
        self.assertFalse(megaship.creates_investigation)
        explanation=policy_explanation('SURFACE_MINING')
        self.assertIn('Record: Yes',explanation)
        self.assertIn('Investigation: Not created',explanation)

    def test_master_popup_switch_is_delivery_only(self):
        findings=[('Megaship detected','Test','detail')]
        self.assertFalse(popup_delivery_allowed(False,findings))
        self.assertTrue(popup_delivery_allowed(True,findings))
        self.assertFalse(popup_delivery_allowed(True,[]))
        self.assertTrue(finding_policy('MEGASHIP').record)

    def test_settings_matrix_and_behaviour_check_cover_shared_invariants(self):
        self.assertGreaterEqual(len(SETTINGS_BEHAVIOUR),20)
        self.assertTrue(all(validate_policy_registry().values()))
        report=run_settings_behaviour_check()
        self.assertTrue(report['passed'],report)
        self.assertEqual(report['controls_documented'],len(SETTINGS_BEHAVIOUR))

    def test_schema_migration_is_versioned_and_runs_once(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            with Monitor(folder,db_path) as monitor:
                self.assertEqual(monitor.schema_version(),SCHEMA_VERSION)
                self.assertEqual(monitor.db.execute(
                    'SELECT COUNT(*) FROM schema_migrations').fetchone()[0],SCHEMA_VERSION)
                report=monitor.diagnostic_report()
                self.assertEqual(report['database']['schema_version'],SCHEMA_VERSION)
                self.assertEqual(report['database']['expected_schema_version'],SCHEMA_VERSION)
            with Monitor(folder,db_path) as monitor:
                self.assertEqual(monitor.db.execute(
                    'SELECT COUNT(*) FROM schema_migrations').fetchone()[0],SCHEMA_VERSION)

    def test_unified_policy_module_is_independent_of_interface(self):
        import discovery_watch_core.intelligence as intelligence
        self.assertFalse(hasattr(intelligence,'tk'))
        self.assertEqual(finding_policy.__module__,'discovery_watch_core.intelligence')


class Version1301ContactReconciliationTests(unittest.TestCase):
    def test_experimental_contact_setting_defaults_off_and_preserves_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertEqual(detection_preferences(db_path),(True,True,False))
            save_detection_preferences(True,True,True,db_path)
            self.assertEqual(detection_preferences(db_path),(True,True,True))

    def test_unique_contacts_repeated_honks_and_later_resolution_share_one_record(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.contacts.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end(); monitor.contact_reconcile_delay=0
                events=[
                    {'timestamp':'2026-09-28T12:00:00Z','event':'FSDJump',
                     'StarSystem':'Contact System','SystemAddress':77},
                    {'timestamp':'2026-09-28T12:00:01Z','event':'FSSSignalDiscovered',
                     'SystemAddress':77,'SignalName':'Known Contact A','SignalType':'Megaship'},
                    {'timestamp':'2026-09-28T12:00:01Z','event':'FSSSignalDiscovered',
                     'SystemAddress':77,'SignalName':'Known Contact A','SignalType':'Megaship'},
                    {'timestamp':'2026-09-28T12:00:02Z','event':'FSSDiscoveryScan',
                     'SystemAddress':77,'NonBodyCount':2},
                    {'timestamp':'2026-09-28T12:00:03Z','event':'FSSDiscoveryScan',
                     'SystemAddress':77,'NonBodyCount':2},
                ]
                with journal.open('a') as output:
                    output.writelines(json.dumps(event)+'\n' for event in events)
                findings=monitor.poll((True,True,True,True,True))
                self.assertEqual(sum(row[13]=='UNRESOLVED_NON_BODY_SIGNALS'
                                     for row in monitor.recent()),1)
                self.assertEqual(sum(item[0].startswith('System contacts need review')
                                     for item in monitor.popup_findings),1)
                self.assertTrue(any('remaining=1' in item[2] for item in findings))

                with journal.open('a') as output:
                    output.write(json.dumps({
                        'timestamp':'2026-09-28T12:00:04Z','event':'FSSSignalDiscovered',
                        'SystemAddress':77,'SignalName':'Known Contact B','SignalType':'Installation'})+'\n')
                self.assertTrue(monitor.poll((True,True,True,True,True)))  # installation finding only
                contact=next(row for row in monitor.recent() if row[13]=='UNRESOLVED_NON_BODY_SIGNALS')
                self.assertTrue(contact[3].startswith('System contacts resolved'))
                self.assertIn('remaining=0',contact[4])
                self.assertEqual(monitor.popup_findings[0][0],'Installation detected')
                state=monitor.db.execute('''SELECT lifecycle_state,reported_count,identified_count,
                    remaining_count,popup_sent FROM contact_reconciliations''').fetchone()
                self.assertEqual(state,('resolved',2,2,0,1))

    def test_departure_marks_delayed_observation_incomplete_without_popup(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.departure.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end(); monitor.contact_reconcile_delay=999
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'FSDJump','StarSystem':'First','SystemAddress':1})+'\n')
                    output.write(json.dumps({'event':'FSSDiscoveryScan','SystemAddress':1,
                                             'NonBodyCount':2})+'\n')
                self.assertEqual(monitor.poll((True,True,True,True,True)),[])
                with journal.open('a') as output:
                    output.write(json.dumps({'event':'FSDJump','StarSystem':'Second','SystemAddress':2})+'\n')
                findings=monitor.poll((True,True,True,True,True))
                self.assertTrue(any(item[0].startswith('System contacts incomplete') for item in findings))
                self.assertFalse(monitor.popup_findings)
                row=next(row for row in monitor.recent() if row[13]=='UNRESOLVED_NON_BODY_SIGNALS')
                self.assertIn('state=Incomplete',row[4])


class Version1302ResponsiveHomeTests(unittest.TestCase):
    def test_home_overview_is_scrollable_and_keyboard_navigable(self):
        import inspect
        self.assertTrue(HOME_OVERVIEW_SCROLLABLE)
        self.assertTrue(HOME_OVERVIEW_KEYBOARD_NAVIGATION)
        self.assertTrue(callable(add_scrollable_notebook_page))
        source=inspect.getsource(App.__init__)
        self.assertIn("add_scrollable_notebook_page(home_tabs,'Overview'",source)
        self.assertIn('self.home_overview_canvas',source)
        for method in ('_scroll_settings_wheel','_scroll_settings_key','_scroll_settings_end'):
            self.assertTrue(callable(getattr(App,method,None)))

    def test_startup_geometry_fits_laptop_and_preserves_large_display_target(self):
        self.assertEqual(initial_window_geometry(2560,1440),'1280x860')
        self.assertEqual(initial_window_geometry(1366,768),'1280x658')
        self.assertEqual(initial_window_geometry(1093,614),'1013x520')


class Version1302WindowsPortableTests(unittest.TestCase):
    def test_overlay_child_command_supports_source_and_frozen_executables(self):
        source=windows_overlay_command('payload',executable='python.exe',
                                       script_path='discovery_watch.py',frozen=False)
        frozen=windows_overlay_command('payload',executable='DiscoveryWatch.exe',frozen=True)
        self.assertEqual(source,['python.exe','discovery_watch.py','--windows-overlay','payload'])
        self.assertEqual(frozen,['DiscoveryWatch.exe','--windows-overlay','payload'])

    def test_one_time_windows_build_definition_is_complete(self):
        root=Path(__file__).parent
        packaging=root/'packaging'/'windows'
        required=('DiscoveryWatch.spec','version_info.txt',
                  'build_windows_portable.bat','WINDOWS_PORTABLE_TESTING.md')
        self.assertTrue(all((packaging/name).is_file() for name in required))
        self.assertTrue((root/'BUILD_WINDOWS_PORTABLE.bat').is_file())
        spec=(packaging/'DiscoveryWatch.spec').read_text(encoding='utf-8')
        batch=(packaging/'build_windows_portable.bat').read_text(encoding='utf-8')
        self.assertIn("name='DiscoveryWatch'",spec)
        self.assertIn('console=False',spec)
        self.assertIn('pyinstaller==6.22.3',batch)
        self.assertIn('python -W error::ResourceWarning -m unittest -q',batch)
        self.assertIn('Compress-Archive',batch)


class Version1291MegashipIdentityBridgeTests(unittest.TestCase):
    @staticmethod
    def seed_internal_only_megaship(monitor,system='Bridge System'):
        event={'event':'FSSSignalDiscovered','SignalName':'$MULTIPLAYER_SCENARIO42;',
               'SignalType':'Megaship'}
        monitor.db.execute('''INSERT INTO alerts
            (journal_file,line_no,rule,title,system_name,detail,raw_json)
            VALUES(?,?,?,?,?,?,?)''',('old.log',1,'MEGASHIP','Megaship detected',system,
                                     'cached internal identity',json.dumps(event)))
        monitor.db.commit()

    def test_internal_arrival_identity_and_localised_fss_name_popup_once(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.bridge.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                self.seed_internal_only_megaship(monitor); monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Bridge System',
                     'SystemAddress':1291},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1291,
                     'SignalName_Localised':'Generation Ship Artemis','SignalType':'Megaship'},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                found=monitor.poll()
                self.assertEqual([item[0] for item in monitor.popup_findings],
                                 ['Known POIs on arrival - 1 recorded'])
                self.assertTrue(any(item[0]=='Megaship detected' for item in found))
                live=monitor.db.execute("SELECT popup_decision FROM alerts WHERE journal_file=?",
                                        (str(journal),)).fetchone()
                self.assertIn('already announced by Known POIs on arrival',live[0])
                self.assertEqual(monitor.db.execute(
                    'SELECT COUNT(*) FROM structure_identity_links').fetchone()[0],1)
                self.assertEqual(monitor.known_pois('Bridge System')[0][2],
                                 'Generation Ship Artemis')

    def test_learned_identity_link_survives_a_return_visit(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.return-bridge.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                self.seed_internal_only_megaship(monitor); monitor.start_at_end()
                first=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Bridge System','SystemAddress':1291},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1291,
                     'SignalName_Localised':'Generation Ship Artemis','SignalType':'Megaship'},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in first)); monitor.poll()
                with journal.open('a') as output:
                    for event in (
                        {'timestamp':'3','event':'FSDJump','StarSystem':'Away','SystemAddress':1292},
                        {'timestamp':'4','event':'FSDJump','StarSystem':'Bridge System','SystemAddress':1291},
                        {'timestamp':'5','event':'FSSSignalDiscovered','SystemAddress':1291,
                         'SignalName_Localised':'Generation Ship Artemis','SignalType':'Megaship'},
                    ):
                        output.write(json.dumps(event)+'\n')
                monitor.poll()
                self.assertEqual([item[0] for item in monitor.popup_findings],
                                 ['Known POIs on arrival - 1 recorded'])
                self.assertEqual(len(monitor.known_pois('Bridge System')),1)

    def test_identity_fallback_does_not_hide_a_second_named_megaship(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.two-ships.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                self.seed_internal_only_megaship(monitor); monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Bridge System','SystemAddress':1291},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1291,
                     'SignalName_Localised':'Generation Ship Artemis','SignalType':'Megaship'},
                    {'timestamp':'3','event':'FSSSignalDiscovered','SystemAddress':1291,
                     'SignalName_Localised':'DSSA Argon Dream','SignalType':'Megaship'},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events)); monitor.poll()
                self.assertEqual(len(monitor.popup_findings),2)
                self.assertEqual(monitor.popup_findings[1][0],'Megaship detected')
                self.assertEqual(monitor.popup_metadata[1]['name'],'DSSA Argon Dream')


class Version1290InterfaceUnificationTests(unittest.TestCase):
    def test_main_interface_and_popup_share_one_palette(self):
        self.assertEqual(THEME_VERSION,'1.0')
        self.assertEqual(AlertPopup.BG,THEME['surface'])
        self.assertEqual(AlertPopup.PANEL,THEME['panel'])
        self.assertEqual(AlertPopup.ORANGE,THEME['orange'])
        self.assertEqual(AlertPopup.CYAN,THEME['cyan'])
        self.assertEqual(AlertPopup.TEXT,THEME['text'])
        self.assertTrue({'Accent.TButton','Danger.TButton','Treeview','TNotebook.Tab',
                         'Card.TLabelframe'}.issubset(set(THEMED_STYLES)))

    def test_theme_applies_portable_ttk_styles_without_a_display(self):
        class FakeRoot:
            def __init__(self): self.config={}; self.options={}
            def configure(self,**values): self.config.update(values)
            def option_add(self,pattern,value): self.options[pattern]=value
        class FakeStyle:
            def __init__(self): self.used=None; self.configured={}; self.mapped={}
            def theme_names(self): return ('default','clam')
            def theme_use(self,name): self.used=name
            def configure(self,name,**values): self.configured[name]=values
            def map(self,name,**values): self.mapped[name]=values
        root=FakeRoot(); style=FakeStyle()
        self.assertIs(apply_app_theme(root,style),style)
        self.assertEqual(style.used,'clam')
        self.assertEqual(root.config['background'],THEME['background'])
        self.assertEqual(root.options['*Text.background'],THEME['surface'])
        self.assertEqual(style.configured['Treeview']['background'],THEME['surface'])
        self.assertEqual(style.configured['Accent.TButton']['background'],THEME['orange'])
        self.assertEqual(style.mapped['TNotebook.Tab']['foreground'][0][1],THEME['orange'])


class Version1281MegashipAliasDeduplicationTests(unittest.TestCase):
    def test_internal_and_localised_name_variants_share_one_popup_identity(self):
        variants=(
            ({'event':'FSSSignalDiscovered','SignalName':'$MULTIPLAYER_SCENARIO14_TITLE;',
              'SignalType':'Megaship'},
             {'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1281,
              'SignalName':'$MULTIPLAYER_SCENARIO14_TITLE;',
              'SignalName_Localised':'Generation Ship Artemis','SignalType':'Megaship'}),
            ({'event':'FSSSignalDiscovered','SignalName':'$MULTIPLAYER_SCENARIO14_TITLE;',
              'SignalName_Localised':'Generation Ship Artemis','SignalType':'Megaship'},
             {'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1281,
              'SignalName':'$MULTIPLAYER_SCENARIO14_TITLE;','SignalType':'Megaship'}),
        )
        for cached,live_event in variants:
            with self.subTest(cached_localised=bool(cached.get('SignalName_Localised'))):
                with tempfile.TemporaryDirectory() as directory:
                    folder=Path(directory); journal=folder/'Journal.alias.log'; journal.write_text('')
                    with Monitor(folder,folder/'db.sqlite3') as monitor:
                        monitor.db.execute('''INSERT INTO alerts
                            (journal_file,line_no,rule,title,system_name,detail,raw_json)
                            VALUES(?,?,?,?,?,?,?)''',('old.log',1,'MEGASHIP','Megaship detected',
                            'Alias System','cached',json.dumps(cached)))
                        monitor.db.commit(); monitor.start_at_end()
                        events=[{'timestamp':'1','event':'FSDJump','StarSystem':'Alias System',
                                 'SystemAddress':1281},live_event]
                        journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                        monitor.poll()
                        self.assertEqual([item[0] for item in monitor.popup_findings],
                                         ['Known POIs on arrival - 1 recorded'])
                        live=[row for row in monitor.recent() if row[6].endswith('Journal.alias.log')
                              and row[13]=='MEGASHIP']
                        self.assertEqual(len(live),1)
                        self.assertIn('already announced by Known POIs on arrival',live[0][12])
                        pois=monitor.known_pois('Alias System')
                        self.assertEqual(len(pois),1)
                        self.assertEqual(pois[0][2],'Generation Ship Artemis')

    def test_different_internal_and_localised_names_remain_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.separate.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                cached={'event':'FSSSignalDiscovered','SignalName':'$GENERATION_SHIP_ARTEMIS;',
                        'SignalName_Localised':'Generation Ship Artemis','SignalType':'Megaship'}
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,detail,raw_json)
                    VALUES(?,?,?,?,?,?,?)''',('old.log',1,'MEGASHIP','Megaship detected',
                    'Separate System','cached',json.dumps(cached)))
                monitor.db.commit(); monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Separate System','SystemAddress':1282},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1282,
                     'SignalName':'$DSSA_ARGON_DREAM;','SignalName_Localised':'DSSA Argon Dream',
                     'SignalType':'Megaship'},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                monitor.poll()
                self.assertEqual(len(monitor.popup_findings),2)
                self.assertEqual(len(monitor.known_pois('Separate System')),2)


class Version1280SystemVisitIntelligenceTests(unittest.TestCase):
    seed_megaship=staticmethod(Version1273ArrivalMegashipDeduplicationTests.seed_megaship)

    def test_surface_evidence_progresses_from_fss_to_completed_organic_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.visit.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Intelligence System',
                     'SystemAddress':1280},
                    {'timestamp':'2','event':'FSSBodySignals','SystemAddress':1280,
                     'BodyName':'Intelligence System A 1','BodyID':4,
                     'Signals':[{'Type':'$SAA_SignalType_Biological;',
                                 'Type_Localised':'Biological','Count':2}]},
                    {'timestamp':'3','event':'SAASignalsFound','SystemAddress':1280,
                     'BodyName':'Intelligence System A 1','BodyID':4,
                     'Signals':[{'Type':'$SAA_SignalType_Biological;',
                                 'Type_Localised':'Biological','Count':2}],
                     'Genuses':[{'Genus':'$Codex_Ent_Stratum_Genus_Name;',
                                 'Genus_Localised':'Stratum'}]},
                    {'timestamp':'4','event':'ScanOrganic','SystemAddress':1280,
                     'Body':'Intelligence System A 1','BodyID':4,'ScanType':'Analyse',
                     'Genus_Localised':'Stratum','Species_Localised':'Stratum Tectonicas'},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                monitor.poll()
                rows={row[3]:row for row in monitor.current_visit_cases()}
                biological=rows['Biological surface signals']
                self.assertEqual((biological[4],biological[7],biological[8]),
                                 ('Completed',3,'ScanOrganic'))
                self.assertEqual(rows['Stratum Tectonicas'][4],'Completed')
                summary=monitor.current_visit_intelligence()
                self.assertEqual((summary['cases'],summary['completed'],summary['evidence']),(2,2,5))

    def test_new_arrival_starts_a_clean_visit_view_without_losing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.reset.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                first=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'First System','SystemAddress':1},
                    {'timestamp':'2','event':'FSSBodySignals','SystemAddress':1,'BodyName':'First A 1',
                     'Signals':[{'Type_Localised':'Guardian','Count':1}]},
                    {'timestamp':'3','event':'FSDJump','StarSystem':'Second System','SystemAddress':2},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in first))
                monitor.poll()
                self.assertEqual(monitor.current_visit_cases(),[])
                self.assertEqual(monitor.current_visit_intelligence()['cases'],0)
                self.assertEqual(monitor.db.execute(
                    "SELECT COUNT(*) FROM discovery_cases WHERE system_name='First System'").fetchone()[0],1)
                with journal.open('a') as output:
                    output.write(json.dumps({'timestamp':'4','event':'FSSBodySignals',
                        'SystemAddress':2,'BodyName':'Second A 2',
                        'Signals':[{'Type_Localised':'Thargoid','Count':1}]})+'\n')
                monitor.poll()
                current=monitor.current_visit_cases()
                self.assertEqual((len(current),current[0][2],current[0][4],current[0][7]),
                                 (1,'Second A 2','Lead',1))

    def test_duplicate_evidence_does_not_inflate_visit_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.duplicate.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                signal={'timestamp':'2','event':'FSSBodySignals','SystemAddress':1280,
                        'BodyName':'Duplicate A 1','Signals':[{'Type_Localised':'Biological','Count':1}]}
                events=[{'timestamp':'1','event':'FSDJump','StarSystem':'Duplicate',
                         'SystemAddress':1280},signal,dict(signal)]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                monitor.poll()
                self.assertEqual(monitor.current_visit_intelligence()['evidence'],1)
                self.assertEqual(monitor.current_visit_cases()[0][7],1)

    def test_ancient_probe_is_a_first_class_poi_and_recalled_on_return(self):
        event={'timestamp':'2','event':'CodexEntry','SystemAddress':1280,
               'Name':'$Ancient_Probe_Name;','Name_Localised':'Ancient Probe'}
        finding=classify(event)[0]
        self.assertEqual((finding[0],finding[1]),('ANCIENT_PROBE','Ancient Probe detected'))
        self.assertEqual(alert_level('ANCIENT_PROBE'),'Important')
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.probe.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Probe System','SystemAddress':1280},
                    event,
                    {'timestamp':'3','event':'FSDJump','StarSystem':'Away','SystemAddress':1281},
                    {'timestamp':'4','event':'FSDJump','StarSystem':'Probe System','SystemAddress':1280},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                found=monitor.poll()
                self.assertTrue(any(item[0]=='Ancient Probe detected' for item in found))
                self.assertTrue(any(item[0].startswith('Known POIs on arrival')
                                    and 'Ancient Probe' in item[2]
                                    for item in monitor.popup_findings))

    def test_differently_named_megaship_still_receives_live_popup(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.different.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                self.seed_megaship(monitor); monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Arrival System',
                     'SystemAddress':1273},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1273,
                     'SignalName_Localised':'DSSA Hope','SignalType':'Megaship'},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in events))
                monitor.poll()
                self.assertEqual(len(monitor.popup_findings),2)
                self.assertTrue(any(item.get('name')=='DSSA Hope'
                                    for item in monitor.popup_metadata))

    def test_disabled_recall_and_return_visits_reset_popup_state(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.return.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                self.seed_megaship(monitor); monitor.start_at_end()
                first=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Arrival System',
                     'SystemAddress':1273},
                    {'timestamp':'2','event':'FSSSignalDiscovered','SystemAddress':1273,
                     'SignalName':'Generation Ship Artemis','SignalType':'Megaship'},
                ]
                journal.write_text(''.join(json.dumps(event)+'\n' for event in first))
                monitor.poll((True,True,True,True,True,False,False))
                self.assertEqual([row[0] for row in monitor.popup_findings],['Megaship detected'])
                with journal.open('a') as output:
                    for event in (
                        {'timestamp':'3','event':'FSDJump','StarSystem':'Away System',
                         'SystemAddress':1274},
                        {'timestamp':'4','event':'FSDJump','StarSystem':'Arrival System',
                         'SystemAddress':1273},
                        {'timestamp':'5','event':'FSSSignalDiscovered','SystemAddress':1273,
                         'SignalName':'Generation Ship Artemis','SignalType':'Megaship'},
                    ):
                        output.write(json.dumps(event)+'\n')
                monitor.poll()
                self.assertEqual(len(monitor.popup_findings),1)
                self.assertTrue(monitor.popup_findings[0][0].startswith('Known POIs on arrival'))

    def test_exploration_criteria_preferences_cover_screenshot_checks(self):
        self.assertEqual(len(EXPLORATION_CRITERIA),23)
        self.assertIn('SHEPHERD_MOON',EXPLORATION_CRITERIA)
        self.assertIn('GREEN_GAS_GIANT',EXPLORATION_CRITERIA)
        self.assertNotIn('LANDABLE_ATMOSPHERE',EXPLORATION_CRITERIA)
        self.assertEqual(EXPLORATION_CRITERIA['GREEN_GAS_GIANT'],
                         'Experimental: Green Gas Giant')
        self.assertEqual(EXPLORATION_CRITERIA['LANDABLE_RING'],'Landable Ring')
        self.assertIn('ALL_SURFACE_MATERIALS',EXPLORATION_CRITERIA)
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'criteria.sqlite3'
            values=exploration_criteria_preferences(db_path)
            self.assertTrue(all(values.values()))
            values['WIDE_RING']=False
            save_exploration_criteria_preferences(values,db_path)
            self.assertFalse(exploration_criteria_preferences(db_path)['WIDE_RING'])

    def test_body_exploration_criteria_use_established_thresholds(self):
        event={
            'event':'Scan','BodyID':4,'BodyName':'Criteria A 4','Landable':True,
            'TerraformState':'Terraformable','Atmosphere':'thin carbon dioxide atmosphere',
            'PlanetClass':'Water world','SurfaceGravity':31.0,'Radius':19000000,
            'RotationPeriod':7200,'TidalLock':False,'OrbitalPeriod':14400,
            'Eccentricity':0.95,'WasMapped':False,
            'Rings':[{'Name':'Criteria A 4 A Ring','InnerRad':20000000,'OuterRad':130000000}],
            'Materials':[{'Name':name,'Percent':1.0} for name in
                         ('Carbon','Germanium','Arsenic','Niobium','Yttrium')],
        }
        rules={item[0] for item in detect_anomalies(event,[event])}
        expected={'LANDABLE_TERRAFORMABLE','LANDABLE_HIGH_G',
                  'LANDABLE_LARGE','LANDABLE_RING','WIDE_RING','FAST_ROTATION',
                  'FAST_ORBIT','HIGH_ECCENTRICITY','GOOD_FSD_INJECTION','HIGH_VALUE_BODY'}
        self.assertTrue(expected <= rules)
        self.assertNotIn('LANDABLE_ATMOSPHERE',rules)

    def test_relationship_criteria_correlate_parent_and_binary_scans(self):
        parent={'event':'Scan','BodyID':2,'BodyName':'Relations A 2','Radius':10000000,
                'Rings':[{'Name':'Relations A 2 A Ring','InnerRad':20000000,
                          'OuterRad':26000000}]}
        moon={'event':'Scan','BodyID':3,'BodyName':'Relations A 2 a','Radius':500000,
              'SemiMajorAxis':25500000,'Parents':[{'Planet':2},{'Planet':1}],
              'PlanetClass':'Rocky body'}
        moon_rules={item[0] for item in detect_anomalies(moon,[parent,moon])}
        self.assertTrue({'CLOSE_ORBIT','SHEPHERD_MOON','CLOSE_RING_PROXIMITY',
                         'NESTED_MOON'} <= moon_rules)
        first={'event':'Scan','BodyID':7,'BodyName':'Binary A','Radius':10000000,
               'SemiMajorAxis':10000000,'Eccentricity':0.1,'Parents':[{'Null':6}]}
        second={'event':'Scan','BodyID':8,'BodyName':'Binary B','Radius':10000000,
                'SemiMajorAxis':10000000,'Eccentricity':0.1,'Parents':[{'Null':6}]}
        binary_rules={item[0] for item in detect_anomalies(second,[first,second])}
        self.assertIn('COLLIDING_BINARY',binary_rules)

    def test_system_material_codex_and_diverse_life_criteria(self):
        materials=list(EXPLORATION_CRITERIA)  # keep this test independent of ordering side effects
        self.assertEqual(len(materials),23)
        from discovery_watch_core.exploration_criteria import ALL_SURFACE_MATERIALS
        first={'event':'Scan','BodyID':1,'BodyName':'Materials A 1','Landable':True,
               'Materials':[{'Name':name} for name in ALL_SURFACE_MATERIALS[:13]]}
        second={'event':'Scan','BodyID':2,'BodyName':'Materials A 2','Landable':True,
                'Materials':[{'Name':name} for name in ALL_SURFACE_MATERIALS[13:]]}
        rules={item[0] for item in detect_anomalies(second,[first,second])}
        self.assertTrue({'ALL_FSD_MATERIALS','ALL_SURFACE_MATERIALS'} <= rules)
        codex=detect_anomalies({'event':'CodexEntry','BodyName':'Materials A 2',
                                'Name_Localised':'Aleoida Arcus'})
        self.assertIn('CODEX_DISCOVERY',{item[0] for item in codex})
        signals=detect_anomalies({'event':'FSSBodySignals','BodyName':'Materials A 3',
                                  'Signals':[{'Type_Localised':'Biological','Count':8}]})
        self.assertIn('DIVERSE_LIFE',{item[0] for item in signals})

    def test_green_gas_giant_codex_and_conservative_temperature_candidate(self):
        codex={'event':'CodexEntry','System':'GGG Codex System',
               'Name':'$Codex_Ent_Green_Sudarsky_Class_II_Name;',
               'Name_Localised':'Green gas giant'}
        codex_findings=detect_anomalies(codex)
        confirmed=[item for item in codex_findings if item[0]=='GREEN_GAS_GIANT']
        self.assertEqual(len(confirmed),1)
        self.assertEqual(confirmed[0][1],98)
        self.assertIn('confirmed Green Gas Giant',confirmed[0][2])

        internal_only=dict(codex)
        internal_only.pop('Name_Localised')
        self.assertIn('GREEN_GAS_GIANT',
                      {item[0] for item in detect_anomalies(internal_only)})

        candidate={'event':'Scan','BodyID':4,'BodyName':'GGG Lead 4',
                   'PlanetClass':'Sudarsky class IV gas giant',
                   'SurfaceTemperature':1149.999878}
        candidate_findings=detect_anomalies(candidate,[candidate])
        lead=[item for item in candidate_findings if item[0]=='GREEN_GAS_GIANT']
        self.assertEqual(len(lead),1)
        self.assertEqual(lead[0][1],90)
        self.assertIn('verify visually',lead[0][2])

        ordinary=dict(candidate,BodyName='Ordinary IV',SurfaceTemperature=1200.0)
        self.assertNotIn('GREEN_GAS_GIANT',
                         {item[0] for item in detect_anomalies(ordinary,[ordinary])})
        self.assertNotIn('GREEN_GAS_GIANT',
                         {item[0] for item in detect_anomalies(candidate,[candidate],set())})

    def test_green_gas_giant_popup_wording_and_history_category(self):
        confirmed=('Anomaly review: GGG 2','GGG System',
                   'Rules: GREEN_GAS_GIANT (98). GGG 2: confirmed Green Gas Giant from Codex')
        candidate=('Anomaly review: GGG 4','GGG System',
                   'Rules: GREEN_GAS_GIANT (90). GGG 4: possible Green Gas Giant; verify visually')
        self.assertIn('Green Gas Giant',popup_category_labels(confirmed))
        self.assertIn('Green Gas Giant',popup_category_labels(candidate))
        simplified,_metadata=simplify_popup_content([confirmed,candidate])
        self.assertEqual(simplified,[('Green Gas Giant','GGG System',
                                      'Check Discovery History for more information.')])
        self.assertEqual(finding_type('ANOMALY_ALERT',detail=candidate[2]),'Notable worlds')

    def test_live_green_gas_giant_codex_creates_history_and_popup(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'green.sqlite3'
            journal=folder/'Journal.green.log'; journal.write_text('')
            with Monitor(folder,db_path) as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'Location','StarSystem':'Green Test',
                     'SystemAddress':3311},
                    {'timestamp':'2','event':'CodexEntry','System':'Green Test',
                     'SystemAddress':3311,
                     'Name':'$Codex_Ent_Green_Sudarsky_Class_II_Name;',
                     'Name_Localised':'Green gas giant','IsNewEntry':True},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                monitor.poll((True,True,True,True,False,True))
                row=monitor.db.execute("SELECT detail FROM alerts WHERE rule='ANOMALY_ALERT' "
                                       "AND system_name='Green Test'").fetchone()
                self.assertIsNotNone(row)
                self.assertIn('GREEN_GAS_GIANT',row[0])
                self.assertEqual(len(monitor.popup_findings),1)
                compact,_metadata=simplify_popup_content(monitor.popup_findings,
                                                          monitor.popup_metadata)
                self.assertEqual(compact[0][0],'Green Gas Giant')

    def test_live_monitor_records_criteria_once_and_honours_disabled_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db_path=folder/'db.sqlite3'
            values=exploration_criteria_preferences(db_path)
            values['WIDE_RING']=False
            save_exploration_criteria_preferences(values,db_path)
            journal=folder/'Journal.criteria.log'; journal.write_text('')
            with Monitor(folder,db_path) as monitor:
                monitor.start_at_end()
                scan={'timestamp':'2','event':'Scan','SystemAddress':3100,'BodyID':1,
                      'BodyName':'Live Criteria A 1','PlanetClass':'Icy body','Radius':200000,
                      'Rings':[{'Name':'Live Criteria A 1 A Ring','InnerRad':400000,
                                'OuterRad':1800000}]}
                events=[{'timestamp':'1','event':'FSDJump','StarSystem':'Live Criteria',
                         'SystemAddress':3100},scan,dict(scan,timestamp='3')]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                monitor.poll((True,True,True,True,False,True))
                rules={row[0] for row in monitor.db.execute(
                    'SELECT rule FROM anomalies WHERE system_name=?',('Live Criteria',))}
                self.assertNotIn('WIDE_RING',rules)
                self.assertEqual(monitor.db.execute(
                    "SELECT COUNT(*) FROM anomalies WHERE rule='SMALL_OBJECT'").fetchone()[0],1)


class Version1314FieldFeedbackTests(unittest.TestCase):
    def test_high_gravity_requires_landable_true(self):
        base={'event':'Scan','BodyName':'Gravity Test 1','SurfaceGravity':30.0}
        self.assertNotIn('HIGH_GRAVITY',{item[0] for item in detect_anomalies(base)})
        self.assertNotIn('HIGH_GRAVITY',{item[0] for item in detect_anomalies(
            dict(base,Landable=False))})
        landable=detect_anomalies(dict(base,Landable=True))
        high=next(item for item in landable if item[0]=='HIGH_GRAVITY')
        self.assertIn('landable',high[2])

    def test_water_life_green_gas_giant_marker_is_narrow_and_optional(self):
        supplied={'event':'Scan','BodyID':27,'BodyName':'Pyroifoea SS-Y b15-0 11',
                  'PlanetClass':'Gas giant with water based life',
                  'SurfaceTemperature':176.666656}
        finding=next(item for item in detect_anomalies(supplied,[supplied])
                     if item[0]=='GREEN_GAS_GIANT')
        self.assertEqual(finding[1],90)
        self.assertIn('verify visually',finding[2])
        self.assertNotIn('GREEN_GAS_GIANT',{item[0] for item in detect_anomalies(
            dict(supplied,PlanetClass='Sudarsky class III gas giant'),[supplied])})
        warm=dict(supplied,SurfaceTemperature=177.0)
        self.assertNotIn('GREEN_GAS_GIANT',{item[0] for item in detect_anomalies(warm,[warm])})
        self.assertNotIn('GREEN_GAS_GIANT',{item[0] for item in detect_anomalies(
            supplied,[supplied],set())})

    def test_green_gas_giant_bulk_density_is_calculated_from_journal_units(self):
        supplied={'MassEM':570.863342,'Radius':76344032.0}
        self.assertAlmostEqual(gas_giant_bulk_density(supplied),1829.164,places=3)
        self.assertIsNone(gas_giant_bulk_density({'MassEM':570.0}))
        self.assertIsNone(gas_giant_bulk_density({'MassEM':0,'Radius':76000000}))

    def test_green_gas_giant_candidates_record_density_support(self):
        supplied={'event':'Scan','BodyID':27,'BodyName':'Pyroifoea SS-Y b15-0 11',
                  'PlanetClass':'Gas giant with water based life',
                  'SurfaceTemperature':176.666656,'MassEM':570.863342,
                  'Radius':76344032.0}
        finding=next(item for item in detect_anomalies(supplied,[supplied])
                     if item[0]=='GREEN_GAS_GIANT')
        self.assertIn('1829.2 kg/m³',finding[2])
        self.assertEqual(finding[3],
                         'PlanetClass,SurfaceTemperature,MassEM,Radius')

    def test_green_gas_giant_density_signatures_are_class_specific_and_narrow(self):
        class_i={'event':'Scan','BodyID':2,'BodyName':'M17 Sector CF-Y c1-23 2',
                 'PlanetClass':'Sudarsky class I gas giant',
                 'SurfaceTemperature':133.998352,'MassEM':220.3668,
                 'Radius':66636000.0}
        class_i_finding=next(item for item in detect_anomalies(class_i,[class_i])
                             if item[0]=='GREEN_GAS_GIANT')
        self.assertEqual(class_i_finding[1],92)
        self.assertIn('experimental Class I cloud-layer signature',class_i_finding[2])

        water={'event':'Scan','BodyID':1,'BodyName':'Cyoilz JM-N b26-0 1',
               'PlanetClass':'Gas giant with water based life',
               'SurfaceTemperature':242.000015,'MassEM':1084.2090,
               'Radius':77259000.0}
        water_finding=next(item for item in detect_anomalies(water,[water])
                           if item[0]=='GREEN_GAS_GIANT')
        self.assertEqual(water_finding[1],92)
        self.assertIn('experimental water-life cloud-layer signature',water_finding[2])

        wrong_class=dict(class_i,PlanetClass='Sudarsky class II gas giant')
        wrong_density=dict(class_i,MassEM=300.0)
        self.assertNotIn('GREEN_GAS_GIANT',{item[0] for item in detect_anomalies(
            wrong_class,[wrong_class])})
        self.assertNotIn('GREEN_GAS_GIANT',{item[0] for item in detect_anomalies(
            wrong_density,[wrong_density])})

    def test_arrival_discovery_preference_defaults_off_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'db.sqlite3'
            self.assertFalse(arrival_discovery_status_preference(db_path))
            save_arrival_discovery_status_preference(True,db_path)
            self.assertTrue(arrival_discovery_status_preference(db_path))

    def test_possible_undiscovered_arrival_notifies_once_when_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.discovery.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Fresh System','SystemAddress':7001},
                    {'timestamp':'2','event':'Scan','StarSystem':'Fresh System','SystemAddress':7001,
                     'BodyName':'Fresh System','BodyID':0,'StarType':'G','DistanceFromArrivalLS':0.0,
                     'WasDiscovered':False},
                    {'timestamp':'3','event':'Scan','StarSystem':'Fresh System','SystemAddress':7001,
                     'BodyName':'Fresh System','BodyID':0,'StarType':'G','DistanceFromArrivalLS':0.0,
                     'WasDiscovered':False},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                options=(True,True,True,True,False,False,True,False,
                         True,True,False,False,True,True,False,False,True)
                found=monitor.poll(options)
                statuses=[item for item in found if item[0]=='Possible undiscovered system']
                self.assertEqual(len(statuses),1)
                self.assertEqual([item[0] for item in monitor.popup_findings],
                                 ['Possible undiscovered system'])
                row=monitor.db.execute(
                    "SELECT detail FROM alerts WHERE rule='SYSTEM_DISCOVERY_STATUS'").fetchone()
                self.assertIn('not proof that every body is undiscovered',row[0])

    def test_discovered_arrival_waits_for_primary_star_and_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.discovery-known.log'; journal.write_text('')
            with Monitor(folder,folder/'db.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'1','event':'FSDJump','StarSystem':'Known System','SystemAddress':7002},
                    {'timestamp':'2','event':'Scan','StarSystem':'Known System','SystemAddress':7002,
                     'BodyName':'Known System 2','BodyID':2,'PlanetClass':'Icy body',
                     'WasDiscovered':False},
                    {'timestamp':'3','event':'Scan','StarSystem':'Known System','SystemAddress':7002,
                     'BodyName':'Known System','BodyID':0,'StarType':'K','DistanceFromArrivalLS':0.0,
                     'WasDiscovered':True},
                    {'timestamp':'4','event':'Scan','StarSystem':'Known System','SystemAddress':7002,
                     'BodyName':'Known System','BodyID':0,'StarType':'K','DistanceFromArrivalLS':0.0,
                     'WasDiscovered':False},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events))
                enabled=(True,True,True,True,False,False,True,False,
                         True,True,False,False,True,True,False,False,True)
                found=monitor.poll(enabled)
                self.assertNotIn('Arrival star previously discovered',[item[0] for item in found])
                self.assertNotIn('Possible undiscovered system',[item[0] for item in found])
                self.assertEqual(monitor.popup_findings,[])
                self.assertNotIn('SYSTEM_DISCOVERY_STATUS',
                                 {row[13] for row in monitor.recent()})

            second=folder/'Journal.discovery-disabled.log'; second.write_text('')
            with Monitor(folder,folder/'disabled.sqlite3') as monitor:
                monitor.start_at_end()
                second.write_text(''.join(json.dumps(item)+'\n' for item in events))
                self.assertNotIn('SYSTEM_DISCOVERY_STATUS',
                    {row[13] for row in monitor.recent()} if monitor.poll() else set())


class Version1315NotificationRefinementsTests(unittest.TestCase):
    def test_possible_discovery_popup_preserves_explanatory_wording(self):
        finding=('Possible undiscovered system','Fresh System',
                 'Scan: Arrival star reports WasDiscovered=false. This is a possible '
                 'first-discovery opportunity, not proof that every body is undiscovered.')
        simplified,metadata=simplify_popup_content([finding],[{
            'name':'Fresh System','signal_type':'SYSTEM_DISCOVERY_STATUS','event':'Scan'}])
        self.assertEqual(simplified,[finding])
        self.assertTrue(metadata[0]['show_detail'])
        _title,body=native_notification_payload(simplified,metadata)
        self.assertIn('WasDiscovered=false',body)
        self.assertIn('not proof that every body is undiscovered',body)

    def test_windows_overlay_queue_launches_one_alert_at_a_time(self):
        class Value:
            def __init__(self,value): self.value=value
            def get(self): return self.value
        class Status:
            def __init__(self): self.messages=[]
            def set(self,value): self.messages.append(value)
        app=App.__new__(App)
        app.windows_overlay_queue=deque()
        app.windows_overlay_active=False
        app.windows_overlay_timer=None
        app.popup_sound=Value(False)
        app.status=Status()
        app._audit_popup_delivery=lambda *args,**kwargs: None
        scheduled=[]
        app.after=lambda delay,callback: scheduled.append((delay,callback)) or len(scheduled)
        first=[('Megaship','Queue System','detail')]
        second=[('Installation','Queue System','detail')]
        with patch('discovery_watch.send_windows_overlay',return_value=True) as send:
            self.assertTrue(app._queue_windows_overlay(first,[],5,'Main monitor','Live journal'))
            self.assertTrue(app._queue_windows_overlay(second,[],5,'Main monitor','Live journal'))
            self.assertEqual(send.call_count,1)
            self.assertEqual(len(app.windows_overlay_queue),1)
            self.assertEqual(scheduled[0][0],5350)
            scheduled[0][1]()
            self.assertEqual(send.call_count,2)
            self.assertEqual(len(app.windows_overlay_queue),0)
            self.assertTrue(app.windows_overlay_active)


class Version1317StartupPerformanceTests(unittest.TestCase):
    def test_hidden_startup_views_load_once_when_selected(self):
        class Notebook:
            def __init__(self,index): self.selected=index
            def select(self): return self.selected
            def index(self,_selected): return self.selected
        class Status:
            def set(self,_value): pass
        app=App.__new__(App)
        app._startup_views_loaded=True
        app._lazy_views_loaded=set()
        app.startup_timings={'views':{}}
        app.tabs=Notebook(2)
        app.explorer_tabs=Notebook(1)
        app.settings_tabs=Notebook(0)
        app.rule_views=Notebook(0)
        app.journal_error=Status()
        calls=[]
        app.refresh_historical=lambda: calls.append('journal_search')
        app.refresh_signal_catalog=lambda: calls.append('signal_catalogue')
        app.refresh_generic_signals=lambda: calls.append('generic_rules')
        app.refresh_watchlists=lambda: calls.append('watchlists')
        app._load_selected_lazy_view()
        app._load_selected_lazy_view()
        self.assertEqual(calls,['journal_search'])
        self.assertIn('journal_search',app.startup_timings['views'])

    def test_read_only_view_monitor_does_not_create_live_session(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); database=folder/'startup.sqlite3'
            with Monitor(folder,database,create_session=False) as monitor:
                self.assertIsNone(monitor.session_id)
                self.assertEqual(monitor.db.execute(
                    'SELECT COUNT(*) FROM live_sessions').fetchone()[0],0)
                self.assertEqual(monitor.schema_version(),SCHEMA_VERSION)

    def test_legacy_alert_maintenance_is_a_one_time_schema_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); database=folder/'migration.sqlite3'
            with Monitor(folder,database) as monitor:
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,detail,raw_json,level)
                    VALUES('test.log',1,'MEGASHIP','Megaship','detail','{}','Custom')''')
                monitor.db.commit()
                self.assertEqual(monitor.schema_version(),SCHEMA_VERSION)
            with Monitor(folder,database,create_session=False) as monitor:
                level=monitor.db.execute(
                    "SELECT level FROM alerts WHERE rule='MEGASHIP'").fetchone()[0]
                self.assertEqual(level,'Custom')
                self.assertEqual(monitor.db.execute(
                    'SELECT COUNT(*) FROM schema_migrations').fetchone()[0],SCHEMA_VERSION)


class Version1318DatabasePerformanceTests(unittest.TestCase):
    def test_system_address_lookup_uses_dedicated_index(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); database=folder/'indexed.sqlite3'
            with Monitor(folder,database,create_session=False) as monitor:
                indexes={row[1] for row in monitor.db.execute(
                    "PRAGMA index_list('exploration_events')")}
                self.assertIn('exploration_address_idx',indexes)
                plan=' '.join(str(value) for row in monitor.db.execute(
                    '''EXPLAIN QUERY PLAN SELECT system_name FROM exploration_events
                       WHERE system_address=? AND system_name IS NOT NULL
                       ORDER BY rowid DESC LIMIT 1''',('42',)) for value in row)
                self.assertIn('exploration_address_idx',plan)

    def test_alert_integrity_repairs_only_new_alert_ids_after_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); database=folder/'incremental.sqlite3'
            with Monitor(folder,database) as monitor:
                event={'event':'FSDJump','StarSystem':'Indexed System','SystemAddress':42}
                monitor._store_exploration(event,'journal.log',1,'Indexed System',42)
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,detail,raw_json)
                    VALUES('old.log',1,'MEGASHIP','Old','Wrong','detail',?)''',
                    (json.dumps(event),))
                monitor.db.commit()
            with Monitor(folder,database,create_session=False) as monitor:
                first_max=int(monitor.db.execute(
                    "SELECT value FROM maintenance_state WHERE key='system_repair_alert_id'").fetchone()[0])
                self.assertEqual(monitor.recent()[0][2],'Indexed System')
                second=dict(event,event='FSSSignalDiscovered')
                cursor=monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,detail,raw_json)
                    VALUES('new.log',2,'MEGASHIP','New','Wrong Again','detail',?)''',
                    (json.dumps(second),))
                second_id=cursor.lastrowid
                monitor.db.commit()
            with Monitor(folder,database,create_session=False) as monitor:
                self.assertGreater(second_id,first_max)
                row=monitor.db.execute('SELECT system_name FROM alerts WHERE id=?',
                                       (second_id,)).fetchone()
                self.assertEqual(row[0],'Indexed System')

    def test_migration_removes_only_short_closed_empty_legacy_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); database=folder/'sessions.sqlite3'
            with Monitor(folder,database) as monitor:
                monitor.db.executemany('''INSERT INTO live_sessions(session_id,started_at,ended_at)
                    VALUES(?,?,?)''',(
                    ('short-empty','2026-01-01T00:00:00','2026-01-01T00:00:02'),
                    ('long-empty','2026-01-01T00:00:00','2026-01-01T00:01:00'),
                    ('open-empty','2026-01-01T00:00:00',None),
                ))
                monitor.db.execute('DELETE FROM schema_migrations WHERE version=4')
                monitor.db.commit()
            with Monitor(folder,database,create_session=False) as monitor:
                sessions={row[0] for row in monitor.db.execute(
                    'SELECT session_id FROM live_sessions')}
                self.assertNotIn('short-empty',sessions)
                self.assertIn('long-empty',sessions)
                self.assertIn('open-empty',sessions)


class Version1319DiscoveryHistoryClarityTests(unittest.TestCase):
    def test_anomaly_table_summary_removes_rule_codes_scores_and_body_repetition(self):
        detail=('Rules: HIGH_VALUE_BODY (70), LANDABLE_TERRAFORMABLE (65). '
                'Synuefai A 5: high-value body (Water world); '
                'Synuefai A 5: landable and Terraformable')
        event={'event':'Scan','BodyName':'Synuefai A 5','PlanetClass':'Water world',
               'TerraformState':'Terraformable'}
        summary=discovery_history_detail_summary(
            'Anomaly review: Synuefai A 5',detail,json.dumps(event),'ANOMALY_ALERT')
        self.assertEqual(summary,'Water world • Terraformable world')
        self.assertNotIn('HIGH_VALUE_BODY',summary)
        self.assertNotIn('(70)',summary)

    def test_green_gas_giant_summary_keeps_useful_measurements(self):
        detail=('Rules: GREEN_GAS_GIANT (90). Test 4: possible Green Gas Giant; '
                'Gas giant with water based life at 176.667 K; calculated bulk density '
                '1829.2 kg/m³; verify visually')
        event={'event':'Scan','BodyName':'Test 4',
               'PlanetClass':'Gas giant with water based life'}
        summary=discovery_history_detail_summary(
            'Anomaly review: Test 4',detail,json.dumps(event),'ANOMALY_ALERT')
        self.assertEqual(summary,
                         'Experimental candidate • Green Gas Giant • 176.667 K • 1829.2 kg/m³')

    def test_signal_and_surface_summaries_use_compact_source_wording(self):
        megaship={'event':'FSSSignalDiscovered','SignalName':'Generation Ship Artemis',
                  'SignalType':'Megaship'}
        self.assertEqual(discovery_history_detail_summary(
            'Megaship — Generation Ship Artemis','long technical detail',
            json.dumps(megaship),'MEGASHIP'),'Detected by FSSSignalDiscovered')
        surface={'event':'SAASignalsFound','BodyName':'Test A 2'}
        self.assertEqual(discovery_history_detail_summary(
            'Human surface signals','long technical detail',json.dumps(surface),'SURFACE_HUMAN'),
            'Human surface signal • SAASignalsFound')

    def test_possible_discovery_summary_keeps_the_actionable_meaning(self):
        event={'event':'Scan','WasDiscovered':False}
        self.assertEqual(discovery_history_detail_summary(
            'Possible undiscovered system','full caution',json.dumps(event),
            'SYSTEM_DISCOVERY_STATUS'),
            'Arrival star not previously discovered • Possible first-discovery opportunity')


class Version13110ArrivalHistoryNoiseTests(unittest.TestCase):
    def test_migration_removes_true_status_alert_only_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); database=folder/'arrival-cleanup.sqlite3'
            true_event={'timestamp':'1','event':'Scan','BodyName':'Known Star',
                        'SystemAddress':8001,'WasDiscovered':True}
            false_event={'timestamp':'2','event':'Scan','BodyName':'Fresh Star',
                         'SystemAddress':8002,'WasDiscovered':False}
            with Monitor(folder,database) as monitor:
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,detail,raw_json)
                    VALUES('known.log',1,'SYSTEM_DISCOVERY_STATUS',
                           'Arrival star previously discovered','Known System',
                           'Scan: arrival star reports WasDiscovered=true.',?)''',
                    (json.dumps(true_event),))
                monitor.db.execute('''INSERT INTO alerts
                    (journal_file,line_no,rule,title,system_name,detail,raw_json)
                    VALUES('fresh.log',2,'SYSTEM_DISCOVERY_STATUS',
                           'Possible undiscovered system','Fresh System',
                           'Scan: arrival star reports WasDiscovered=false.',?)''',
                    (json.dumps(false_event),))
                monitor._store_historical(true_event,'known.log',1,'Known System')
                monitor.db.execute('DELETE FROM schema_migrations WHERE version=5')
                monitor.db.commit()
            with Monitor(folder,database,create_session=False) as monitor:
                titles={row[0] for row in monitor.db.execute(
                    "SELECT title FROM alerts WHERE rule='SYSTEM_DISCOVERY_STATUS'")}
                self.assertNotIn('Arrival star previously discovered',titles)
                self.assertIn('Possible undiscovered system',titles)
                self.assertEqual(monitor.db.execute(
                    "SELECT COUNT(*) FROM historical_events WHERE event_type='Scan'").fetchone()[0],1)
                self.assertEqual(monitor.schema_version(),SCHEMA_VERSION)


class Version1320ContextAwarePopupTests(unittest.TestCase):
    def test_high_gravity_popup_names_body_and_shows_gravity(self):
        event={'event':'Scan','BodyName':'Achenar 3','Landable':True,
               'SurfaceGravity':6.73*9.80665}
        finding=('Anomaly review: Achenar 3','Achenar',
                 'Rules: HIGH_GRAVITY (70). Achenar 3: landable high gravity')
        compact,metadata=simplify_popup_content(
            [finding],[popup_identity(event,finding[0],'ANOMALY_ALERT')])
        self.assertEqual(compact[0][0],'High-gravity world — Achenar 3')
        self.assertEqual(metadata[0]['key_fact'],'Gravity: 6.73 g')
        _title,body=native_notification_payload(compact,metadata)
        self.assertIn('High-gravity world — Achenar 3',body)
        self.assertIn('Gravity: 6.73 g',body)

    def test_fast_rotation_and_orbit_use_readable_durations(self):
        event={'event':'Scan','BodyName':'Rapid A 1','RotationPeriod':9000,
               'OrbitalPeriod':7200}
        finding=('Anomaly review: Rapid A 1','Rapid',
                 'Rules: FAST_ROTATION (60), FAST_ORBIT (60).')
        compact,metadata=simplify_popup_content(
            [finding],[popup_identity(event,finding[0],'ANOMALY_ALERT')])
        self.assertEqual([row[0] for row in compact],[
            'Fast-rotating body — Rapid A 1','Fast-orbiting body — Rapid A 1'])
        self.assertEqual([item['key_fact'] for item in metadata],
                         ['Rotation period: 2h 30m','Orbital period: 2h'])

    def test_green_gas_giant_popup_keeps_two_decision_measurements(self):
        event={'event':'Scan','BodyName':'Pyroifoea 11',
               'PlanetClass':'Gas giant with water based life',
               'SurfaceTemperature':176.666656,'MassEM':570.863342,
               'Radius':76344032.0}
        finding=('Anomaly review: Pyroifoea 11','Pyroifoea',
                 'Rules: GREEN_GAS_GIANT (90). possible Green Gas Giant')
        compact,metadata=simplify_popup_content(
            [finding],[popup_identity(event,finding[0],'ANOMALY_ALERT')])
        self.assertEqual(compact[0][0],'Green Gas Giant — Pyroifoea 11')
        self.assertIn('Temperature: 176.7 K',metadata[0]['key_fact'])
        self.assertIn('Density: 1,829 kg/m³',metadata[0]['key_fact'])

    def test_named_signal_format_is_unchanged_and_has_no_measurement_clutter(self):
        event={'event':'FSSSignalDiscovered','SignalType':'Megaship',
               'SignalName':'Generation Ship Artemis'}
        finding=('Megaship detected','Test System','full evidence')
        compact,metadata=simplify_popup_content(
            [finding],[popup_identity(event,finding[0],'MEGASHIP')])
        self.assertEqual(compact[0][0],'Megaship — Generation Ship Artemis')
        self.assertEqual(metadata[0]['key_fact'],'')


class Version1321PreArrivalSignalReliabilityTests(unittest.TestCase):
    def test_station_megaship_before_fsdjump_uses_arrival_system_and_megaship_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.2026-10-10T105848.01.log'
            journal.write_text('',encoding='utf-8')
            with Monitor(folder,folder/'hip74116.sqlite3') as monitor:
                monitor.start_at_end()
                events=[
                    {'timestamp':'2026-10-10T10:42:00Z','event':'Location',
                     'StarSystem':'Previous System','SystemAddress':111},
                    {'timestamp':'2026-10-10T10:43:09Z','event':'FSSSignalDiscovered',
                     'SystemAddress':800768182659,'SignalName':'Zero Squared',
                     'SignalType':'StationMegaShip','IsStation':True},
                    {'timestamp':'2026-10-10T10:43:09Z','event':'FSDJump',
                     'StarSystem':'HIP 74116','SystemAddress':800768182659,
                     'Body':'HIP 74116 A','BodyID':3,'BodyType':'Star'},
                ]
                journal.write_text(''.join(json.dumps(item)+'\n' for item in events),
                                   encoding='utf-8')
                monitor.poll()
                row=monitor.db.execute('''SELECT system_name,line_no,raw_json,popup_decision
                    FROM alerts WHERE rule='MEGASHIP' AND title='Megaship detected' ''').fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0],'HIP 74116')
                self.assertEqual(row[1],2)
                self.assertEqual(json.loads(row[2])['SignalType'],'StationMegaShip')
                self.assertIn('Popup eligible',row[3])
                self.assertIn(('Megaship detected','HIP 74116',
                               'FSSSignalDiscovered: signalType=StationMegaShip (direct journal classification)'),
                              monitor.popup_findings)
                compact,_metadata=simplify_popup_content(monitor.popup_findings,
                                                          monitor.popup_metadata)
                self.assertIn(('Megaship — Zero Squared','HIP 74116',
                               'Check Discovery History for more information.'),compact)
                self.assertIsNone(monitor.db.execute(
                    "SELECT 1 FROM signal_catalog WHERE signal_key='stationmegaship'").fetchone())

    def test_prearrival_signal_survives_separate_poll_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); journal=folder/'Journal.split.log'
            journal.write_text('',encoding='utf-8')
            with Monitor(folder,folder/'split.sqlite3') as monitor:
                monitor.start_at_end()
                with journal.open('a',encoding='utf-8') as output:
                    output.write(json.dumps({'timestamp':'1','event':'Location',
                        'StarSystem':'Departure','SystemAddress':1})+'\n')
                monitor.poll()
                with journal.open('a',encoding='utf-8') as output:
                    output.write(json.dumps({'timestamp':'2','event':'FSSSignalDiscovered',
                        'SystemAddress':800768182659,'SignalName':'Zero Squared',
                        'SignalType':'StationMegaShip'})+'\n')
                monitor.poll()
                self.assertEqual(monitor.db.execute(
                    "SELECT COUNT(*) FROM alerts WHERE rule='MEGASHIP'").fetchone()[0],0)
                with journal.open('a',encoding='utf-8') as output:
                    output.write(json.dumps({'timestamp':'2','event':'FSDJump',
                        'StarSystem':'HIP 74116','SystemAddress':800768182659})+'\n')
                monitor.poll()
                row=monitor.db.execute(
                    "SELECT system_name,line_no FROM alerts WHERE rule='MEGASHIP'").fetchone()
                self.assertEqual(row,('HIP 74116',2))
                self.assertFalse(monitor.deferred_prearrival)

    def test_station_megaship_is_canonicalised_without_losing_raw_classification(self):
        event={'event':'FSSSignalDiscovered','SignalType':'StationMegaShip',
               'SignalName':'Zero Squared'}
        self.assertEqual(Monitor.signal_type(event),('Megaship','megaship'))
        identity=popup_identity(event,'Megaship detected','MEGASHIP')
        self.assertEqual(identity['signal_type'],'Megaship')
        self.assertEqual(popup_category_labels(
            ('Megaship detected','HIP 74116','StationMegaShip'),identity),['Megaship'])


class Version1322ApplicationIconTests(unittest.TestCase):
    def test_dw_icon_assets_exist_and_have_expected_formats(self):
        png_icon,ico_icon=application_icon_paths()
        self.assertTrue(png_icon.is_file())
        self.assertTrue(ico_icon.is_file())
        self.assertEqual(png_icon.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
        self.assertEqual(ico_icon.read_bytes()[:4],b'\x00\x00\x01\x00')
        self.assertEqual(bundled_resource('assets','icons','discovery-watch.png'),png_icon)


class Version1330PublicBetaFoundationTests(unittest.TestCase):
    def test_popup_appearance_defaults_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertEqual(popup_appearance_preferences(db_path),('Bottom right','Normal'))
            save_popup_appearance_preferences('Top left','Large',db_path)
            self.assertEqual(popup_appearance_preferences(db_path),('Top left','Large'))
            with self.assertRaises(ValueError):
                save_popup_appearance_preferences('Somewhere','Large',db_path)

    def test_all_popup_position_presets_remain_inside_work_area(self):
        area=(100,50,1700,950)
        positions={choice:popup_position(area,600,300,'Linux',choice)
                   for choice in POPUP_POSITION_CHOICES}
        self.assertEqual(positions['Top left'],(132,110))
        self.assertEqual(positions['Bottom right'],(1068,618))
        self.assertEqual(positions['Centre'],(600,350))
        for x,y in positions.values():
            self.assertGreaterEqual(x,area[0]); self.assertGreaterEqual(y,area[1])
            self.assertLessEqual(x+600,area[2]); self.assertLessEqual(y+300,area[3])

    def test_popup_size_choices_are_stable(self):
        self.assertEqual(POPUP_FONT_CHOICES,('Small','Normal','Large'))


class Version1331WindowsPopupLayoutTests(unittest.TestCase):
    def test_windows_layout_preference_defaults_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertEqual(windows_popup_layout_preference(db_path),'Standard')
            save_windows_popup_layout_preference('Fit content',db_path)
            self.assertEqual(windows_popup_layout_preference(db_path),'Fit content')
            with self.assertRaises(ValueError):
                save_windows_popup_layout_preference('Tiny',db_path)

    def test_fit_content_and_compact_reduce_short_windows_overlay(self):
        title='Discovery Watch'
        body='Megaship - Generation Ship Artemis'
        standard=windows_overlay_dimensions(title,body,'Normal','Standard')
        compact=windows_overlay_dimensions(title,body,'Normal','Compact')
        fitted=windows_overlay_dimensions(title,body,'Normal','Fit content')
        self.assertLess(compact[0],standard[0])
        self.assertLess(compact[1],standard[1])
        self.assertLess(fitted[0],standard[0])
        self.assertLess(fitted[1],standard[1])

    def test_windows_layout_choices_and_bounds(self):
        self.assertEqual(WINDOWS_POPUP_LAYOUT_CHOICES,('Compact','Standard','Fit content'))
        width,height=windows_overlay_dimensions('Title','\n'.join(['Long line '*20]*20),
                                                'Large','Fit content')
        self.assertLessEqual(width,620)
        self.assertLessEqual(height,420)


class Version1332WindowsPopupCascadeTests(unittest.TestCase):
    def test_windows_popup_flow_defaults_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path=Path(directory)/'preferences.sqlite3'
            self.assertEqual(windows_popup_flow_preference(db_path),'Sequential queue')
            save_windows_popup_flow_preference('Cascaded stack',db_path)
            self.assertEqual(windows_popup_flow_preference(db_path),'Cascaded stack')
            with self.assertRaises(ValueError):
                save_windows_popup_flow_preference('Overlap everything',db_path)

    def test_cascade_cells_do_not_overlap_on_common_display(self):
        area=(0,0,1920,1080); size=(600,250)
        bottom=[windows_cascade_position(area,size,'Bottom right',slot) for slot in range(3)]
        top=[windows_cascade_position(area,size,'Top left',slot) for slot in range(3)]
        self.assertGreater(bottom[0][1],bottom[1][1])
        self.assertGreater(bottom[1][1],bottom[2][1])
        self.assertLessEqual(bottom[1][1]+bottom[1][3],bottom[0][1])
        self.assertLess(top[0][1],top[1][1])
        self.assertLessEqual(top[0][1]+top[0][3],top[1][1])

    def test_cascade_shows_three_and_queues_the_fourth(self):
        class Value:
            def __init__(self,value): self.value=value
            def get(self): return self.value
        class Status:
            def set(self,_value): pass
        app=App.__new__(App)
        app.windows_overlay_queue=deque(); app.windows_overlay_slots={}
        app.windows_overlay_active=False; app.windows_overlay_timer=None
        app.windows_popup_flow=Value('Cascaded stack')
        app.popup_sound=Value(False); app.status=Status()
        app._audit_popup_delivery=lambda *args,**kwargs: None
        scheduled=[]
        app.after=lambda delay,callback: scheduled.append((delay,callback)) or len(scheduled)
        with patch('discovery_watch.send_windows_overlay',return_value=True) as send:
            for index in range(4):
                self.assertTrue(app._queue_windows_overlay(
                    [(f'Finding {index}','Stack System','detail')],[],5,'Main monitor','Live journal'))
            self.assertEqual(send.call_count,3)
            self.assertEqual(len(app.windows_overlay_slots),3)
            self.assertEqual(len(app.windows_overlay_queue),1)
            self.assertEqual([call.kwargs['stack_slot'] for call in send.call_args_list],[0,1,2])
            scheduled[0][1]()
            self.assertEqual(send.call_count,4)
            self.assertEqual(send.call_args.kwargs['stack_slot'],0)
            self.assertEqual(len(app.windows_overlay_queue),0)

    def test_windows_popup_flow_choices_are_stable(self):
        self.assertEqual(WINDOWS_POPUP_FLOW_CHOICES,('Sequential queue','Cascaded stack'))


class Version1333WindowsPopupWrappingTests(unittest.TestCase):
    def test_compact_and_fit_content_allow_for_wrapped_details(self):
        short='Megaship - Artemis'
        long=('Possible discovery - this explanatory detail is deliberately long enough to wrap '
              'onto several rendered lines in the native Windows overlay without explicit newlines. ')*2
        for layout in ('Compact','Fit content'):
            short_size=windows_overlay_dimensions('Discovery Watch',short,'Normal',layout)
            long_size=windows_overlay_dimensions('Discovery Watch',long,'Normal',layout)
            self.assertGreater(long_size[1],short_size[1])
            self.assertLessEqual(long_size[1],420)

    def test_cascade_position_never_shrinks_overlay_content_height(self):
        positioned=windows_cascade_position((0,0,1366,768),(500,300),'Bottom right',1)
        self.assertEqual(positioned[2:],(500,300))
