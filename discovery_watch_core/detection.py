"""Pure journal classification and exploration-intelligence rules.

These functions are deliberately independent of Tkinter and persistent state so
they can be tested and reused without starting the desktop application.
"""

from .intelligence import finding_policy
from .exploration_criteria import detect_exploration_criteria


RAW_MATERIAL_GRADES={
    'carbon':1,'iron':1,'nickel':1,'phosphorus':1,'sulphur':1,
    'chromium':2,'germanium':2,'manganese':2,'vanadium':2,'zinc':2,'zirconium':2,
    'arsenic':3,'cadmium':3,'mercury':3,'molybdenum':3,'niobium':3,'tin':3,'tungsten':3,
    'antimony':4,'polonium':4,'ruthenium':4,'selenium':4,'tellurium':4,'technetium':4,'yttrium':4,
}


def alert_level(rule, priority=None):
    """Return a stable, human-facing attention level for a discovery alert."""
    policy=finding_policy(rule)
    if policy.attention!='Review':
        return policy.attention
    if priority is not None:
        if int(priority)>=75: return 'Important'
        if int(priority)<40: return 'Informational'
    return policy.attention


def finding_type(rule, title='', detail=''):
    """Return the Discovery History category used by the unified findings filter."""
    return finding_policy(rule,title,detail).category


def classify(event, megaships=True, installations=True, phenomena=True, unusual=True):
    kind = event.get('event')
    signal = ' '.join(str(event.get(k) or '') for k in ('SignalName_Localised', 'SignalName', 'Name_Localised', 'Name', 'StationName', 'StationType'))
    lower = signal.casefold()
    results = []
    signal_type = str(event.get('signalType') or event.get('SignalType') or '')
    signal_type_lower = signal_type.casefold()
    probe_fields=' '.join(str(event.get(key) or '') for key in (
        'SignalName_Localised','SignalName','Name_Localised','Name','Type_Localised','Type',
        'Category_Localised','Category','SubCategory_Localised','SubCategory'))
    probe_normalized=''.join(character for character in probe_fields.casefold()
                             if character.isalnum())
    # Fleet carriers can contain megaship-like display text, but are not discovery leads.
    if signal_type_lower.replace(' ', '') == 'fleetcarrier':
        return results
    if unusual and 'ancientprobe' in probe_normalized:
        display=(event.get('SignalName_Localised') or event.get('Name_Localised') or
                 event.get('Type_Localised') or event.get('SignalName') or
                 event.get('Name') or event.get('Type') or 'Ancient Probe')
        results.append(('ANCIENT_PROBE','Ancient Probe detected',
                        f'{kind}: {display} (direct journal name/type match)'))
    if (unusual and signal_type_lower.strip() == 'generic' and
            ('unregistered comms beacon' in lower or
             'unregistered communications beacon' in lower)):
        results.append(('COMMS_BEACON', 'Unregistered Comms Beacon detected',
                        f'{kind}: SignalName={signal.strip()}; signalType={signal_type} '
                        '(combined journal field match)'))
    if installations and signal_type_lower.strip() == 'installation':
        results.append(('INSTALLATION', 'Installation detected',
                        f'{kind}: signalType={signal_type} (direct journal classification)'))
    if megaships and ('megaship' in signal_type_lower or 'mega ship' in signal_type_lower):
        results.append(('MEGASHIP', 'Megaship detected',
                        f'{kind}: signalType={signal_type} (direct journal classification)'))
    structure_found=any(rule in ('MEGASHIP','INSTALLATION') for rule,_,_ in results)
    if not structure_found and kind in ('FSSSignalDiscovered', 'Location', 'Docked', 'ApproachSettlement', 'SupercruiseExit'):
        if megaships and ('megaship' in lower or 'mega ship' in lower):
            results.append(('MEGASHIP', 'Megaship reference', f'{kind}: {signal.strip()} (journal name match; verify in game)'))
        elif installations and 'installation' in lower and kind == 'FSSSignalDiscovered':
            results.append(('INSTALLATION', 'Installation signal', f'{kind}: {signal.strip()} (journal name match; verify in game)'))
    if phenomena and kind == 'FSSSignalDiscovered' and any(s in lower for s in ('notable stellar phenomena', 'notable stellar phenomenon', 'stellar phenomena')):
        results.append(('STELLAR_PHENOMENON', 'Notable stellar phenomenon signal', f'{kind}: {signal.strip()}'))
    if phenomena and kind == 'CodexEntry':
        category = ' '.join(str(event.get(k) or '') for k in ('Category', 'Category_Localised', 'SubCategory', 'SubCategory_Localised')).casefold()
        if 'stellar phenomena' in category or 'stellar phenomenon' in category:
            results.append(('CODEX_PHENOMENON', 'Stellar phenomenon Codex entry', f'CodexEntry: {signal.strip() or category}'))
    if unusual and kind == 'FSSSignalDiscovered' and ('unidentified' in lower or 'unknown' in lower):
        results.append(('UNIDENTIFIED_SIGNAL', 'Unidentified signal name', f'{kind}: {signal.strip()} (name alone does not establish rarity)'))
    return results


def discovery_facts(event):
    """Only classify journal-reported facts; never infer first-discovery awards."""
    kind = event.get('event')
    if kind == 'Scan' and event.get('BodyName'):
        return 'scan', event['BodyName']
    if kind == 'SAAScanComplete' and event.get('BodyName'):
        return 'mapping', event['BodyName']
    if kind == 'ScanOrganic' and event.get('Body'):
        return 'organic_' + str(event.get('ScanType', 'unknown')).lower(), str(event['Body'])
    return None


def is_planetary_mining_signal(item):
    """Return whether one signal object explicitly names a mining location."""
    if not isinstance(item,dict):
        return False
    for key in ('Type_Localised','SignalName_Localised','Name_Localised',
                'Type','SignalName','Name'):
        compact=''.join(character for character in str(item.get(key) or '').casefold()
                        if character.isalnum())
        if compact in ('planetarymininglocation','saasignaltypeplanetarymininglocation'):
            return True
    return False


def surface_signal_observations(event):
    """Return normalised, positive planetary surface-signal observations."""
    if event.get('event') not in ('FSSBodySignals','SAASignalsFound'):
        return []
    body=str(event.get('BodyName') or event.get('Body') or 'Unnamed body')
    if ' ring' in body.casefold():
        return []
    observations=[]
    for item in event.get('Signals') or []:
        if not isinstance(item,dict):
            continue
        count=item.get('Count',0)
        if isinstance(count,bool) or not isinstance(count,(int,float)) or count<=0:
            continue
        internal=str(item.get('Type') or '').strip()
        localised=str(item.get('Type_Localised') or '').strip()
        display=localised or internal or 'Unlabelled'
        match=(internal+' '+localised).casefold()
        if is_planetary_mining_signal(item):
            category='mining'
        elif 'thargoid' in match:
            category='thargoid'
        elif 'guardian' in match:
            category='guardian'
        elif 'biological' in match:
            category='biological'
        elif 'geological' in match:
            category='geological'
        elif 'human' in match:
            category='human'
        else:
            category='other'
        observations.append({'category':category,'display':display,'count':int(count),
                             'internal':internal,'localised':localised,'body':body})
    return observations


def surface_signal_findings(event):
    """Create clear user-facing findings from individual surface categories."""
    grouped={}
    for item in surface_signal_observations(event):
        key=(item['category'],item['display'])
        grouped[key]=grouped.get(key,0)+item['count']
    findings=[]
    labels={'thargoid':'Thargoid','guardian':'Guardian','biological':'Biological',
            'geological':'Geological','human':'Human','other':'Other','mining':'Planetary Mining Location'}
    for (category,display),count in grouped.items():
        label=labels[category]
        rule='SURFACE_'+category.upper()
        plural='s' if count!=1 else ''
        if category=='mining':
            title=f'Planetary Mining Location{plural} ' + (
                'reported' if event.get('event')=='FSSBodySignals' else 'confirmed')
            stage=('FSS body-signal report.' if event.get('event')=='FSSBodySignals' else
                   'Detailed Surface Scanner confirmation.')
        elif event.get('event')=='FSSBodySignals':
            title=f'Possible {label} surface signal{plural}'
            stage='Early FSS body-signal report; map the body for detailed confirmation.'
        else:
            title=f'{label} surface signal{plural} confirmed'
            stage='Detailed Surface Scanner confirmation.'
        body=str(event.get('BodyName') or event.get('Body') or 'Unnamed body')
        detail=(f"{event.get('event')}: Body={body}; Signal type={display}; Count={count}. "
                f'{stage} Recorded from the journal Signals list.')
        findings.append((rule,title,detail,category,display,count))
    return findings


def stratum_findings(event):
    """Return evidence-based Stratum leads and confirmed Tectonicas findings."""
    kind=event.get('event')
    body=str(event.get('BodyName') or event.get('Body') or 'Unnamed body')
    if kind=='SAASignalsFound':
        for item in event.get('Genuses') or []:
            if not isinstance(item,dict):
                continue
            genus=str(item.get('Genus_Localised') or item.get('Genus') or '').strip()
            if 'stratum' in genus.casefold():
                return [('BIO_STRATUM_LEAD','Stratum genus detected - possible Tectonicas',
                         f'SAASignalsFound: Body={body}; Genus={genus}. '
                         'The journal confirms Stratum genus only; identify the organism on foot to confirm its species.')]
    if kind=='ScanOrganic':
        genus=str(event.get('Genus_Localised') or event.get('Genus') or '').strip()
        species=str(event.get('Species_Localised') or event.get('Species') or '').strip()
        internal_species=str(event.get('Species') or '').casefold()
        tectonicas=('tectonicas' in species.casefold() or
                    'codex_ent_stratum_02_name' in internal_species)
        if 'stratum' in genus.casefold() and tectonicas:
            scan_type=str(event.get('ScanType') or 'Unknown')
            return [('BIO_STRATUM_TECTONICAS','Stratum Tectonicas confirmed',
                     f'ScanOrganic: Body={body}; Species={species}; Scan progress={scan_type}. '
                     'Confirmed directly from the journal species field.')]
    return []


def _matching_body_scan(event,system_scans):
    """Return the latest scan for the signal body's stable ID, then its name."""
    body_id=event.get('BodyID')
    body_name=str(event.get('BodyName') or event.get('Body') or '').casefold()
    matches=[]
    for scan in system_scans or ():
        if not isinstance(scan,dict):
            continue
        if body_id is not None and scan.get('BodyID')==body_id:
            matches.append(scan)
        elif body_id is None and body_name and str(scan.get('BodyName') or '').casefold()==body_name:
            matches.append(scan)
    return matches[-1] if matches else None


def _material_opportunities(scan,minimum_grade=3,limit=5):
    """Return the most valuable journal-reported raw materials on one body."""
    ranked=[]
    for item in (scan or {}).get('Materials') or []:
        if not isinstance(item,dict):
            continue
        internal=str(item.get('Name') or '').strip()
        display=str(item.get('Name_Localised') or internal.replace('_',' ').title()).strip()
        grade=RAW_MATERIAL_GRADES.get(internal.casefold())
        percent=item.get('Percent')
        if not display or grade is None or grade<minimum_grade:
            continue
        ranked.append((grade,float(percent) if isinstance(percent,(int,float)) else None,display))
    ranked.sort(key=lambda value:(-value[0],-(value[1] if value[1] is not None else -1),value[2].casefold()))
    return ranked[:limit]


def biological_material_findings(event,system_scans=()):
    """Identify confirmed Brain Trees or cautious biology/material opportunities."""
    if event.get('event') not in ('FSSBodySignals','SAASignalsFound'):
        return []
    observations=surface_signal_observations(event)
    if not any(item['category']=='biological' for item in observations):
        return []
    body=str(event.get('BodyName') or event.get('Body') or 'Unnamed body')
    genera=[]
    for item in event.get('Genuses') or []:
        if isinstance(item,dict):
            genera.append(str(item.get('Genus_Localised') or item.get('Genus') or '').strip())
    confirmed=any('braintree' in ''.join(character for character in genus.casefold()
                                         if character.isalnum()) for genus in genera)
    scan=_matching_body_scan(event,system_scans)
    materials=_material_opportunities(scan)
    if materials:
        material_text=', '.join(
            f'{name} (G{grade}' + (f', {percent:.2f}%' if percent is not None else '') + ')'
            for grade,percent,name in materials)
    else:
        material_text='No Grade 3 or Grade 4 composition data is currently recorded for this body'
    if confirmed:
        genus=next((value for value in genera if 'braintree' in ''.join(
            character for character in value.casefold() if character.isalnum())), 'Brain Tree')
        return [('BIO_BRAIN_TREE_CONFIRMED','Brain Trees confirmed',
                 f'SAASignalsFound: Body={body}; Genus={genus}. '
                 f'Potential raw engineering materials from the body scan: {material_text}. '
                 'Surface investigation recommended.')]
    if not materials:
        return []
    return [('BIO_MATERIAL_CANDIDATE','Biological material opportunity',
             f'{event.get("event")}: Body={body}; Biological signals detected. '
             f'Potential raw engineering materials from the body scan: {material_text}. '
             'This is a material-bearing biological lead, not confirmation of Brain Trees.')]


def detect_anomalies(event, system_scans=(), enabled_criteria=None):
    """Conservative, explainable observations; scores indicate review priority, not rarity."""
    results = []
    kind = event.get('event')
    if kind == 'Scan':
        body = event.get('BodyName', 'Unnamed body')
        gravity = event.get('SurfaceGravity')
        if event.get('Landable') is True and isinstance(gravity, (int, float)):
            earth_g = gravity / 9.80665
            if earth_g >= 2.5:
                results.append(('HIGH_GRAVITY', 70,
                                f'{body}: landable with {earth_g:.2f} g',
                                'Landable,SurfaceGravity'))
        planet_class = str(event.get('PlanetClass') or '')
        terraform = str(event.get('TerraformState') or '')
        if planet_class in ('Earthlike body', 'Water world', 'Ammonia world'):
            results.append(('VALUABLE_WORLD', 55, f'{body}: {planet_class}', 'PlanetClass'))
        if terraform and terraform.casefold() != 'not terraformable':
            results.append(('TERRAFORMABLE', 45, f'{body}: {terraform}', 'TerraformState'))
        star_type = str(event.get('StarType') or '')
        if star_type in ('N','H','SupermassiveBlackHole','D','DA','DAB','DAO','DAZ','DAV','DB','DBZ','DBV','DO','DOV','DQ','DC','DCV','DX'):
            results.append(('COMPACT_STAR', 60, f'{body}: stellar type {star_type}', 'StarType'))
    if kind in ('FSSBodySignals', 'SAASignalsFound'):
        body = str(event.get('BodyName') or 'Unnamed body')
        signals = event.get('Signals')
        if isinstance(signals, list):
            counts = []
            signal_summary = []
            biological = geological = 0
            for item in signals:
                if not isinstance(item, dict):
                    continue
                count = item.get('Count', 0)
                if isinstance(count, bool) or not isinstance(count, (int, float)) or count <= 0:
                    continue
                count = int(count)
                if is_planetary_mining_signal(item):
                    continue
                counts.append(count)
                internal_type=str(item.get('Type') or '')
                localised_type=str(item.get('Type_Localised') or '')
                signal_type = internal_type + ' ' + localised_type
                display_type=localised_type or internal_type or 'Unlabelled'
                signal_summary.append(f'{display_type}={count}')
                if 'biological' in signal_type.casefold():
                    biological += count
                elif 'geological' in signal_type.casefold():
                    geological += count
            total = sum(counts)
            # Ring hotspot counts are not planetary surface signals.
            if total and ' ring' not in body.casefold():
                results.append(('SURFACE_SIGNALS_RECORDED', 55,
                                f'{body}: {total} recorded surface signal(s) ({kind}); ' +
                                ', '.join(signal_summary), 'Signals'))
                if total >= 8:
                    results.append(('SIGNAL_RICH_BODY', min(85, 45 + total),
                                    f'{body}: {total} recorded surface signals ({kind})', 'Signals'))
                if biological:
                    results.append(('BIOLOGICAL_SIGNALS', 70,
                                    f'{body}: {biological} biological signal(s) ({kind}); investigate if useful', 'Signals'))
                if geological:
                    results.append(('GEOLOGICAL_SIGNALS', 45,
                                    f'{body}: {geological} geological signal(s) ({kind})', 'Signals'))
    results.extend(detect_exploration_criteria(
        event, system_scans=system_scans, enabled=enabled_criteria))
    # Several established Discovery Watch rules intentionally overlap newer,
    # more specific criteria.  Keep one record per rule while avoiding an
    # accidental duplicate if a future rule implementation shares a name.
    unique=[]; seen=set()
    for item in results:
        if item[0] not in seen:
            unique.append(item); seen.add(item[0])
    return unique
