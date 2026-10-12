"""Popup wording and compact notification presentation helpers."""

import json
import re

from .config import POPUP_TEST_SCENARIOS
from .detection import surface_signal_observations
from .exploration_criteria import gas_giant_bulk_density


def journal_evidence_summary(event):
    """Return a compact ``event — signal name — signal type`` evidence line."""
    if not isinstance(event,dict):
        return 'Unknown journal event'
    event_name=str(event.get('event') or '').strip()
    signal_name=str(event.get('SignalName_Localised') or event.get('SignalName') or
                    event.get('Name_Localised') or event.get('Name') or
                    event.get('StationName') or '').strip()
    signal_type=str(event.get('SignalType_Localised') or event.get('SignalType') or
                    event.get('signalType') or event.get('USSType_Localised') or
                    event.get('USSType') or event.get('Type_Localised') or
                    event.get('Type') or '').strip()
    parts=[]
    for value in (event_name,signal_name,signal_type):
        if value and value not in parts:
            parts.append(value)
    return ' — '.join(parts) if parts else 'Unknown journal event'


def discovery_history_detail_summary(title,detail,raw_json='',rule=''):
    """Return concise table text while leaving the stored explanation intact."""
    title=str(title or '').strip()
    detail=str(detail or '').strip()
    rule=str(rule or '').strip()
    try:
        event=json.loads(raw_json) if isinstance(raw_json,str) else dict(raw_json or {})
    except (TypeError,ValueError):
        event={}
    event_name=str(event.get('event') or '').strip()

    if rule=='SYSTEM_DISCOVERY_STATUS':
        if event.get('WasDiscovered') is False:
            return 'Arrival star not previously discovered • Possible first-discovery opportunity'
        if event.get('WasDiscovered') is True:
            return 'Arrival star previously discovered'

    if rule=='UNRESOLVED_NON_BODY_SIGNALS':
        return ('System contacts resolved' if 'resolved' in title.casefold() and
                'unresolved' not in title.casefold()
                else 'Unidentified contacts remain • Check navigation panel or FSS')

    if rule.startswith('SURFACE_'):
        labels={
            'SURFACE_THARGOID':'Thargoid surface signal',
            'SURFACE_GUARDIAN':'Guardian surface signal',
            'SURFACE_BIOLOGICAL':'Biological surface signal',
            'SURFACE_GEOLOGICAL':'Geological surface signal',
            'SURFACE_HUMAN':'Human surface signal',
            'SURFACE_MINING':'Planetary Mining Location',
            'SURFACE_OTHER':'Other surface signal',
        }
        summary=labels.get(rule,'Surface signal')
        return f'{summary} • {event_name}' if event_name else summary

    identity=popup_identity(event,title,rule)
    signal_label=popup_signal_label(identity)
    if signal_label:
        return f'Detected by {event_name}' if event_name else signal_label

    if rule=='ANOMALY_ALERT':
        labels=popup_category_labels((title,'',detail),identity)
        labels=[label for label in labels if label!='Discovery finding']
        if labels:
            summary=' • '.join(labels)
            if 'green gas giant' in summary.casefold():
                measurements=[]
                temperature=re.search(r'(-?\d+(?:\.\d+)?)\s*K\b',detail)
                density=re.search(r'(\d+(?:\.\d+)?)\s*kg/m³',detail)
                if temperature: measurements.append(temperature.group(1)+' K')
                if density: measurements.append(density.group(1)+' kg/m³')
                if measurements: summary+=' • '+' • '.join(measurements)
                if 'possible green gas giant' in detail.casefold():
                    summary='Experimental candidate • '+summary
            return summary

    if 'known pois on arrival' in title.casefold():
        return 'Previously recorded point of interest • Arrival reminder'
    if rule=='NONHUMAN_USS':
        return f'Nonhuman signal source • {event_name or "Journal evidence"}'
    if rule=='LISTENING_POST':
        return f'Listening Post • {event_name or "Journal evidence"}'

    # Remove diagnostic rule headers and common policy annotations from the
    # compact table only. The complete original string remains in row[4].
    cleaned=re.sub(r'^Rules:\s*.*?\.\s*','',detail,flags=re.IGNORECASE)
    cleaned=re.sub(r'\s*\((?:catalogue policy|journal [^)]+|priority)[^)]*\)','',cleaned,
                   flags=re.IGNORECASE)
    cleaned=cleaned.replace('; ',' • ').strip(' .')
    if not cleaned:
        cleaned=event_name or title or 'Journal evidence recorded'
    if len(cleaned)>150:
        cleaned=cleaned[:147].rstrip()+'…'
    return cleaned


def popup_test_scenario(name):
    """Return realistic compact popup content without requiring live journal data."""
    scenarios={
        'Megaship discovery':(
            [('Megaship detected','Test system','A named Megaship was reported by FSSSignalDiscovered.')],
            [{'name':'DSSA Test Vessel','signal_type':'Megaship','event':'FSSSignalDiscovered','source':'Popup test'}]),
        'Surface biology':(
            [('Possible Biological surface signals','Test system','FSSBodySignals reported biological activity on Test system A 2.')],
            [{'name':'Test system A 2','signal_type':'Biological','event':'FSSBodySignals','source':'Popup test'}]),
        'Anomaly review':(
            [('Anomaly review: Test system A 1','Test system','HIGH_GRAVITY and SIGNAL_RICH_BODIES merit review.')],
            [{'name':'Test system A 1','body_name':'Test system A 1',
              'signal_type':'HIGH_GRAVITY','event':'Scan','source':'Popup test',
              'measurements':{'gravity_g':3.42}}]),
    }
    return scenarios.get(name,scenarios[POPUP_TEST_SCENARIOS[0]])


def popup_category_labels(finding,identity=None):
    """Translate detailed findings into calm notification categories."""
    title,_,detail=finding
    identity=identity or {}
    text=' '.join((str(title),str(detail),str(identity.get('name') or ''),
                   str(identity.get('signal_type') or ''))).casefold()
    if 'known pois on arrival' in text or 'previously recorded poi' in text:
        return ['Known points of interest']
    if 'unfinished discoveries' in text:
        return ['Unfinished discoveries']
    if 'watchlist match' in text:
        return ['Commander watchlist match']
    labels=[]
    def add(label):
        if label not in labels: labels.append(label)
    if 'notable stellar phenomena' in text or 'notable stellar phenomenon' in text:
        add('Notable Stellar Phenomena')
    elif 'stellar phenomenon' in text: add('Stellar phenomenon')
    if 'stratum tectonicas' in text: add('Stratum Tectonicas')
    elif 'stratum' in text: add('Stratum biological signal')
    if 'earthlike body' in text or 'earth-like world' in text: add('Earth-like world')
    if 'water world' in text: add('Water world')
    if 'ammonia world' in text: add('Ammonia world')
    if 'terraformable' in text and 'not terraformable' not in text: add('Terraformable world')
    if 'high_gravity' in text or 'high-gravity' in text or 'high gravity' in text: add('High-gravity world')
    if 'compact_star' in text or 'compact star' in text: add('Compact stellar object')
    if 'landable_atmosphere' in text: add('Landable atmospheric world')
    if 'landable_large' in text: add('Large landable world')
    if 'landable_ring' in text: add('Ringed landable world')
    if 'close_orbit' in text: add('Close orbit')
    if 'shepherd_moon' in text: add('Shepherd moon')
    if 'wide_ring' in text: add('Wide ring')
    if 'colliding_binary' in text: add('Colliding binary')
    elif 'close_binary' in text: add('Close binary')
    if 'close_ring_proximity' in text: add('Close ring proximity')
    if 'codex_discovery' in text and 'green_gas_giant' not in text:
        add('Codex discovery')
    if 'uncommon_secondary_star' in text: add('Uncommon secondary star')
    if 'nested_moon' in text: add('Nested moon')
    if 'small_object' in text: add('Small object')
    if 'fast_rotation' in text: add('Fast-rotating body')
    if 'fast_orbit' in text: add('Fast-orbiting body')
    if 'high_eccentricity' in text: add('Highly eccentric orbit')
    if 'diverse_life' in text: add('Diverse biological signals')
    if 'good_fsd_injection' in text: add('Good FSD injection materials')
    if 'all_fsd_materials' in text: add('All FSD injection materials')
    if 'all_surface_materials' in text: add('All surface materials')
    if 'high_value_body' in text and not any(label in labels for label in (
            'Earth-like world','Water world','Ammonia world','Terraformable world')):
        add('High-value body')
    if ('confirmed green gas giant' in text or 'green_gas_giant' in text or
            'possible green gas giant' in text):
        # The popup is intentionally only a prompt. Confidence and supporting
        # measurements remain visible in Discovery History.
        add('Green Gas Giant')
    if 'signal_rich' in text or 'signal-rich' in text: add('Signal-rich body')
    if 'megaship' in text: add('Megaship')
    if 'installation' in text: add('Installation')
    if 'ancient probe' in text: add('Ancient Probe')
    if 'tourist beacon' in text or 'touristbeacon' in text: add('Tourist beacon')
    if 'titan' in text and 'tectonicas' not in text: add('Titan')
    if 'unregistered comms beacon' in text or 'unregistered communications beacon' in text:
        add('Unregistered Comms Beacon')
    if 'listening post' in text: add('Listening Post')
    if 'nonhuman signal' in text or 'nonhuman uss' in text: add('Nonhuman signal source')
    if 'thargoid' in text and 'nonhuman signal' not in text: add('Thargoid signals')
    if 'guardian' in text: add('Guardian signals')
    if 'biological' in text and 'stratum' not in text: add('Biological signals')
    if 'geological' in text: add('Geological signals')
    if 'planetary mining location' in text: add('Planetary Mining Location')
    if 'human surface' in text: add('Human surface signals')
    if 'other surface' in text: add('Other surface signals')
    if 'unresolved non-body' in text or 'unresolved system contact' in text:
        add('Unresolved system contacts')
    elif 'unidentified signal' in text: add('Unidentified system contact')
    if not labels:
        name=str(identity.get('name') or '').strip()
        candidate=name if name and name.casefold() not in ('discovery','unknown') else str(title).strip()
        for suffix in (' signal detected',' detected',' confirmed'):
            if candidate.casefold().endswith(suffix):
                candidate=candidate[:-len(suffix)].strip()
                break
        add(candidate or 'Discovery finding')
    return labels


def simplify_popup_content(findings,metadata=None):
    """Return concise, quantity-free popup lines with named signal identities."""
    rows=list(findings or []); identities=list(metadata or [])
    simplified=[]; simplified_metadata=[]; seen=set()
    for index,row in enumerate(rows):
        identity=identities[index] if index<len(identities) else popup_identity({},row[0])
        if str(row[0]).casefold()=='possible undiscovered system':
            key=(str(row[1] or '').casefold(),'possible undiscovered system')
            if key in seen:
                continue
            seen.add(key)
            simplified.append(row)
            simplified_metadata.append({
                'name':'Possible undiscovered system',
                'signal_type':'Arrival discovery status',
                'event':'Scan',
                'source':'Live journal',
                'compact_summary':False,
                'show_detail':True,
            })
            continue
        signal_label=popup_signal_label(identity)
        labels=[signal_label] if signal_label else popup_category_labels(row,identity)
        for label in labels:
            body_name=str(identity.get('body_name') or '').strip()
            display_label=(f'{label} — {body_name}' if body_name and not signal_label and
                           body_name.casefold() not in label.casefold() else label)
            key=(str(row[1] or '').casefold(),label.casefold(),body_name.casefold())
            if key in seen: continue
            seen.add(key)
            key_fact=popup_key_fact(label,identity)
            simplified.append((display_label,row[1],'Check Discovery History for more information.'))
            simplified_metadata.append({'name':display_label,
                'signal_type':identity.get('signal_type') or 'Discovery finding',
                'event':'Discovery History','source':'Condensed popup summary','compact_summary':True,
                'body_name':body_name,'key_fact':key_fact})
    return simplified,simplified_metadata


def _friendly_duration(seconds):
    """Format a journal duration compactly without implying false precision."""
    try: total=max(0,int(round(abs(float(seconds)))))
    except (TypeError,ValueError): return ''
    if total<60: return f'{total}s'
    hours,remainder=divmod(total,3600); minutes,_seconds=divmod(remainder,60)
    if hours:
        return f'{hours}h {minutes:02d}m' if minutes else f'{hours}h'
    return f'{minutes}m'


def popup_measurements(event):
    """Extract reusable, locally calculated measurements for compact alerts."""
    event=event or {}
    measurements={}
    def number(name):
        value=event.get(name)
        return float(value) if isinstance(value,(int,float)) else None
    gravity=number('SurfaceGravity')
    if gravity is not None: measurements['gravity_g']=gravity/9.80665
    rotation=number('RotationPeriod')
    if rotation: measurements['rotation_seconds']=abs(rotation)
    orbit=number('OrbitalPeriod')
    if orbit: measurements['orbit_seconds']=abs(orbit)
    eccentricity=number('Eccentricity')
    if eccentricity is not None: measurements['eccentricity']=eccentricity
    radius=number('Radius')
    if radius is not None: measurements['radius_km']=radius/1000
    semimajor=number('SemiMajorAxis')
    if semimajor is not None: measurements['orbit_km']=semimajor/1000
    temperature=number('SurfaceTemperature')
    if temperature is not None: measurements['temperature_k']=temperature
    density=gas_giant_bulk_density(event)
    if density is not None: measurements['density_kg_m3']=density
    widths=[]
    for ring in event.get('Rings') or []:
        if not isinstance(ring,dict): continue
        inner=ring.get('InnerRad'); outer=ring.get('OuterRad')
        if isinstance(inner,(int,float)) and isinstance(outer,(int,float)) and outer>inner:
            widths.append((outer-inner)/1000)
    if widths: measurements['ring_width_km']=max(widths)
    return measurements


def popup_key_fact(label,identity):
    """Return the single most useful measurement for a compact popup card."""
    values=dict((identity or {}).get('measurements') or {})
    text=str(label or '').casefold()
    if 'high-gravity' in text and values.get('gravity_g') is not None:
        return f"Gravity: {values['gravity_g']:.2f} g"
    if 'fast-rotating' in text and values.get('rotation_seconds'):
        return f"Rotation period: {_friendly_duration(values['rotation_seconds'])}"
    if 'fast-orbiting' in text and values.get('orbit_seconds'):
        return f"Orbital period: {_friendly_duration(values['orbit_seconds'])}"
    if 'highly eccentric' in text and values.get('eccentricity') is not None:
        return f"Eccentricity: {values['eccentricity']:.4f}"
    if 'large landable' in text and values.get('radius_km') is not None:
        return f"Radius: {values['radius_km']:,.0f} km"
    if 'wide ring' in text and values.get('ring_width_km') is not None:
        return f"Ring width: {values['ring_width_km']:,.0f} km"
    if 'close orbit' in text and values.get('orbit_km') is not None:
        return f"Orbital distance: {values['orbit_km']:,.0f} km"
    if 'green gas giant' in text:
        facts=[]
        if values.get('temperature_k') is not None:
            facts.append(f"Temperature: {values['temperature_k']:.1f} K")
        if values.get('density_kg_m3') is not None:
            facts.append(f"Density: {values['density_kg_m3']:,.0f} kg/m³")
        return ' · '.join(facts[:2])
    return ''


def popup_signal_label(identity):
    """Format an explicit journal signal as ``type — name`` without repetition."""
    identity=identity or {}
    event=str(identity.get('event') or '')
    signal_type=str(identity.get('signal_type') or '').strip()
    journal_signal=identity.get('journal_signal')
    if journal_signal is None:
        journal_signal=(event=='FSSSignalDiscovered' and
                        signal_type.casefold() not in ('','discovery','discovery finding'))
    if not journal_signal or not signal_type:
        return None
    if 'signal_name' in identity:
        signal_name=str(identity.get('signal_name') or '').strip()
    else:
        signal_name=str(identity.get('name') or '').strip()
    if (not signal_name or signal_name.casefold()==signal_type.casefold() or
            signal_name.casefold() in ('discovery','unknown','discovery update')):
        return signal_type
    return f'{signal_type} — {signal_name}'


def native_notification_payload(findings,metadata=None):
    metadata=list(metadata or [])
    compact=bool(findings and metadata and all(item.get('compact_summary') for item in metadata))
    if compact:
        systems=[]
        for _title,system,_detail in findings:
            if system and system not in systems: systems.append(system)
        system_line=('System: '+systems[0]) if len(systems)==1 else \
                    ('Systems: '+', '.join(systems) if systems else 'System: Unknown system')
        categories=[]
        for finding,item in zip(findings,metadata):
            categories.append(str(item.get('name') or finding[0]))
            if item.get('key_fact'): categories.append(str(item['key_fact']))
        body='\n'.join([system_line]+categories+['Check Discovery History for more information.'])
        return 'Discovery Watch - discoveries detected',body
    title='Discovery Watch - discovery update' if len(findings)==1 else \
          f'Discovery Watch - {len(findings)} discovery updates'
    lines=[]
    for index,(finding_title,system,_detail) in enumerate(findings):
        identity=metadata[index] if index<len(metadata) else popup_identity({},finding_title)
        lines.append(f"{popup_attention_label(finding_title)}: {identity.get('name') or finding_title}")
        lines.append(f"{identity.get('signal_type') or 'Discovery'} | {identity.get('event') or 'Unknown'} | {system or 'Unknown system'}")
        if identity.get('show_detail') and _detail:
            lines.append(str(_detail))
    return title,'\n'.join(lines)


def popup_attention_label(title):
    text=str(title or '').casefold()
    if any(term in text for term in ('megaship','installation','ancient probe','nonhuman','listening post','titan',
                                     'comms beacon','thargoid','guardian','stratum')):
        return 'IMPORTANT'
    if any(term in text for term in ('anomaly','unresolved','unidentified','unknown')):
        return 'REVIEW'
    return 'INFORMATION'


def popup_identity(event,title,rule=None,source='Live journal'):
    """Extract a compact, human-readable identity for an alert card."""
    event=event or {}
    surface=surface_signal_observations(event)
    if str(rule or '').startswith('SURFACE_'):
        # A journal event may contain several surface-signal categories. Keep
        # each popup card tied to its own finding so a suppressed mining entry
        # cannot leak into an eligible biological/geological/etc. popup.
        category=str(rule)[len('SURFACE_'):].casefold()
        surface=[item for item in surface if item.get('category')==category]
    surface_types=', '.join(dict.fromkeys(item['display'] for item in surface))
    organic_species=str(event.get('Species_Localised') or event.get('Species') or '').strip()
    genera=[str(item.get('Genus_Localised') or item.get('Genus') or '').strip()
            for item in event.get('Genuses') or [] if isinstance(item,dict)]
    genus_types=', '.join(value for value in genera if value)
    signal_name=(event.get('SignalName_Localised') or event.get('SignalName') or
                 event.get('Name_Localised') or event.get('Name') or
                 event.get('StationName') or '')
    name=(signal_name or
          event.get('USSType_Localised') or event.get('Type_Localised') or
          organic_species or genus_types or
          event.get('BodyName') or event.get('Body') or title or 'Discovery update')
    signal_type=(event.get('SignalType') or event.get('signalType') or
                 event.get('USSType_Localised') or event.get('USSType') or
                 event.get('Type_Localised') or organic_species or genus_types or
                 surface_types or rule or 'Discovery')
    if str(rule or '').upper()=='MEGASHIP' and 'megaship' in str(signal_type).casefold():
        signal_type='Megaship'
    journal_signal=bool(event.get('SignalType') or event.get('signalType') or
                        event.get('USSType_Localised') or event.get('USSType') or
                        (event.get('event')=='FSSSignalDiscovered' and
                         (event.get('Type_Localised') or event.get('Type'))))
    event_type=event.get('event') or source
    body_name=str(event.get('BodyName') or event.get('Body') or '').strip()
    return {'name':str(name),'signal_name':str(signal_name),'signal_type':str(signal_type),
            'journal_signal':journal_signal,'event':str(event_type),'source':str(source),
            'body_name':body_name,'measurements':popup_measurements(event)}
