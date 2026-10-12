"""Offline exploration criteria derived from Elite Dangerous journal evidence.

The criteria are intentionally pure and deterministic.  A caller may provide
the most recent Scan event for each body in the current system so relationship
and system-material checks can be evaluated without network access.
"""

from collections import OrderedDict
from math import pi


PREMIUM_FSD_MATERIALS = (
    'Carbon', 'Germanium', 'Arsenic', 'Niobium', 'Yttrium', 'Polonium',
)

ALL_SURFACE_MATERIALS = (
    'Antimony', 'Arsenic', 'Cadmium', 'Carbon', 'Chromium', 'Germanium',
    'Iron', 'Manganese', 'Mercury', 'Molybdenum', 'Nickel', 'Niobium',
    'Phosphorus', 'Polonium', 'Ruthenium', 'Selenium', 'Sulphur',
    'Technetium', 'Tellurium', 'Tin', 'Tungsten', 'Vanadium', 'Yttrium',
    'Zinc', 'Zirconium',
)

EARTH_MASS_KG = 5.9722e24

# Ordered for a predictable two-column Settings layout and stable diagnostics.
EXPLORATION_CRITERIA = OrderedDict((
    ('LANDABLE_TERRAFORMABLE', 'Landable & Terraformable'),
    ('LANDABLE_HIGH_G', 'Landable High-g'),
    ('LANDABLE_LARGE', 'Landable Large'),
    ('CLOSE_ORBIT', 'Close Orbit'),
    ('SHEPHERD_MOON', 'Shepherd Moon'),
    ('WIDE_RING', 'Wide Ring'),
    ('CLOSE_BINARY', 'Close Binary'),
    ('COLLIDING_BINARY', 'Colliding Binary'),
    ('CLOSE_RING_PROXIMITY', 'Close Ring Proximity'),
    ('CODEX_DISCOVERY', 'Codex Discoveries'),
    ('GREEN_GAS_GIANT', 'Experimental: Green Gas Giant'),
    ('UNCOMMON_SECONDARY_STAR', 'Uncommon Secondary Star'),
    ('LANDABLE_RING', 'Landable Ring'),
    ('NESTED_MOON', 'Nested Moon'),
    ('SMALL_OBJECT', 'Small Object'),
    ('FAST_ROTATION', 'Fast Rotation'),
    ('FAST_ORBIT', 'Fast Orbit'),
    ('HIGH_ECCENTRICITY', 'High Eccentricity'),
    ('DIVERSE_LIFE', 'Diverse Life'),
    ('GOOD_FSD_INJECTION', 'Good FSD Injection'),
    ('ALL_FSD_MATERIALS', 'All FSD Mats In System'),
    ('ALL_SURFACE_MATERIALS', 'All Surface Mats In System'),
    ('HIGH_VALUE_BODY', 'High-Value Body'),
))


def _number(value, default=0.0):
    if isinstance(value, bool):
        return default
    return float(value) if isinstance(value, (int, float)) else default


def _parent(event, index=0):
    parents = event.get('Parents') or []
    if index >= len(parents) or not isinstance(parents[index], dict):
        return None, None
    item = parents[index]
    for kind in ('Planet', 'Star', 'Null'):
        if item.get(kind) is not None:
            return kind, item.get(kind)
    return None, None


def _rings(event):
    return [ring for ring in event.get('Rings') or []
            if isinstance(ring, dict) and 'belt' not in str(ring.get('Name') or '').casefold()]


def _material_names(event):
    names = set()
    for item in event.get('Materials') or []:
        if isinstance(item, dict):
            name = str(item.get('Name') or '').strip()
            if name:
                names.add(name.casefold())
    return names


def _enabled(enabled, rule):
    return enabled is None or rule in enabled


def _finding(rule, score, body, description, field):
    return rule, score, f'{body}: {description}', field


def _green_gas_giant_codex(event):
    """Return whether a Codex event explicitly identifies a Green Gas Giant."""
    text = ' '.join(str(event.get(key) or '') for key in (
        'Name', 'Name_Localised', 'SubCategory', 'SubCategory_Localised',
        'NearestDestination', 'NearestDestination_Localised',
    )).casefold()
    compact = ''.join(character for character in text if character.isalnum())
    return ('green gas giant' in text or 'greengasgiant' in compact or
            'codexentgreensudarsky' in compact or
            'codexentgreengasgiant' in compact)


def _green_gas_giant_temperature_candidate(event):
    """Return whether a scan matches a conservative known GGG temperature lead.

    Elite's journal does not expose the rendered planet colour.  The only
    temperature marker treated as sufficiently specific here is the documented
    Class IV value around 1150 K.  This remains a candidate until the commander
    verifies the body in the FSS or system map.
    """
    planet_class = str(event.get('PlanetClass') or '').casefold()
    temperature = _number(event.get('SurfaceTemperature'), -1.0)
    return ('sudarsky class iv gas giant' in planet_class and
            abs(temperature - 1150.0) <= 0.01)


def _green_gas_giant_water_life_candidate(event):
    """Recognise the supplied water-life GGG temperature marker narrowly."""
    planet_class = str(event.get('PlanetClass') or '').strip().casefold()
    temperature = _number(event.get('SurfaceTemperature'), -1.0)
    return (planet_class == 'gas giant with water based life' and
            abs(temperature - 176.666656) <= 0.02)


def gas_giant_bulk_density(event):
    """Return journal-derived bulk density in kg/m^3, or ``None``.

    Elite reports planetary mass in Earth masses and radius in metres.  The
    calculated value is supporting evidence for experimental GGG leads; it is
    not proof that the rendered body is green.
    """
    mass_earth = _number(event.get('MassEM'), -1.0)
    radius_m = _number(event.get('Radius'), -1.0)
    if mass_earth <= 0 or radius_m <= 0:
        return None
    return mass_earth * EARTH_MASS_KG / ((4.0 / 3.0) * pi * radius_m ** 3)


def _green_gas_giant_density_candidate(event):
    """Return a narrow community-observed temperature/density signature.

    These signatures reproduce two visually confirmed finds attributed to the
    cloud-layer density method.  They intentionally do not extrapolate a
    universal range from two examples.
    """
    planet_class = str(event.get('PlanetClass') or '').strip().casefold()
    temperature = _number(event.get('SurfaceTemperature'), -1.0)
    density = gas_giant_bulk_density(event)
    if density is None:
        return None
    signatures = (
        ('sudarsky class i gas giant', 133.998352, 1061.9, 'Class I'),
        ('gas giant with water based life', 242.000015, 3352.0, 'water-life'),
    )
    for expected_class, expected_temperature, expected_density, label in signatures:
        if (planet_class == expected_class and
                abs(temperature - expected_temperature) <= 0.02 and
                abs(density - expected_density) <= 2.0):
            return label, density
    return None


def detect_exploration_criteria(event, system_scans=(), enabled=None):
    """Return ``(rule, score, explanation, evidence_field)`` observations.

    ``system_scans`` should contain the latest Scan event for each known body.
    Results describe journal-supported facts or geometry leads; they never claim
    a first discovery or guarantee that every body in the system was scanned.
    """
    kind = event.get('event')
    body = str(event.get('BodyName') or event.get('Body') or kind or 'Journal event')
    results = []

    if kind == 'CodexEntry' and _enabled(enabled, 'CODEX_DISCOVERY'):
        name = str(event.get('Name_Localised') or event.get('Name') or
                   event.get('NearestDestination_Localised') or 'Codex entry')
        results.append(_finding('CODEX_DISCOVERY', 65, body,
                                f'Codex discovery: {name}', 'Name'))

    if (kind == 'CodexEntry' and _enabled(enabled, 'GREEN_GAS_GIANT') and
            _green_gas_giant_codex(event)):
        name = str(event.get('Name_Localised') or event.get('Name') or
                   'Green gas giant')
        results.append(_finding('GREEN_GAS_GIANT', 98, body,
                                f'confirmed Green Gas Giant from Codex ({name})',
                                'Name,Name_Localised'))

    if kind in ('FSSBodySignals', 'SAASignalsFound') and _enabled(enabled, 'DIVERSE_LIFE'):
        biological = 0
        for item in event.get('Signals') or []:
            if not isinstance(item, dict):
                continue
            identity = (str(item.get('Type') or '') + ' ' +
                        str(item.get('Type_Localised') or '')).casefold()
            if 'biological' in identity:
                biological += int(_number(item.get('Count'), 0))
        if biological > 7:
            results.append(_finding('DIVERSE_LIFE', 75, body,
                                    f'{biological} biological signals reported', 'Signals'))

    if kind != 'Scan':
        return results

    scans = {}
    for scan in system_scans or ():
        if not isinstance(scan, dict) or scan.get('event') != 'Scan':
            continue
        body_id = scan.get('BodyID')
        if body_id is not None:
            scans[body_id] = scan
    if event.get('BodyID') is not None:
        scans[event.get('BodyID')] = event

    landable = event.get('Landable') is True
    terraform = str(event.get('TerraformState') or '').strip()
    radius = _number(event.get('Radius'))
    gravity = _number(event.get('SurfaceGravity'))
    semimajor = _number(event.get('SemiMajorAxis'))
    eccentricity = _number(event.get('Eccentricity'))
    planet_class = str(event.get('PlanetClass') or '')
    star_type = str(event.get('StarType') or '')
    rings = _rings(event)
    is_ring = ' ring' in body.casefold()

    density = gas_giant_bulk_density(event)
    density_evidence = (f'; calculated bulk density {density:.1f} kg/m³'
                        if density is not None else '')

    if (_enabled(enabled, 'GREEN_GAS_GIANT') and
            _green_gas_giant_temperature_candidate(event)):
        temperature = _number(event.get('SurfaceTemperature'))
        results.append(_finding('GREEN_GAS_GIANT', 90, body,
                                f'possible Green Gas Giant; {planet_class} at '
                                f'{temperature:.3f} K matches the known Class IV temperature marker'
                                f'{density_evidence}; '
                                'verify visually in the FSS or system map',
                                'PlanetClass,SurfaceTemperature,MassEM,Radius'))

    if (_enabled(enabled, 'GREEN_GAS_GIANT') and
            _green_gas_giant_water_life_candidate(event)):
        temperature = _number(event.get('SurfaceTemperature'))
        results.append(_finding('GREEN_GAS_GIANT', 90, body,
                                f'possible Green Gas Giant; {planet_class} at '
                                f'{temperature:.3f} K matches the supplied water-life temperature marker'
                                f'{density_evidence}; '
                                'verify visually in the FSS or system map',
                                'PlanetClass,SurfaceTemperature,MassEM,Radius'))

    density_match = _green_gas_giant_density_candidate(event)
    if (_enabled(enabled, 'GREEN_GAS_GIANT') and density_match and
            not any(item[0] == 'GREEN_GAS_GIANT' for item in results)):
        label, matched_density = density_match
        temperature = _number(event.get('SurfaceTemperature'))
        results.append(_finding(
            'GREEN_GAS_GIANT', 92, body,
            f'possible Green Gas Giant; {planet_class} at {temperature:.3f} K '
            f'and calculated bulk density {matched_density:.1f} kg/m³ matches '
            f'the experimental {label} cloud-layer signature; verify visually '
            'in the FSS or system map',
            'PlanetClass,SurfaceTemperature,MassEM,Radius'))

    if (landable and terraform and terraform.casefold() != 'not terraformable' and
            _enabled(enabled, 'LANDABLE_TERRAFORMABLE')):
        results.append(_finding('LANDABLE_TERRAFORMABLE', 65, body,
                                f'landable and {terraform}', 'Landable,TerraformState'))
    if landable and gravity > 29.4 and _enabled(enabled, 'LANDABLE_HIGH_G'):
        results.append(_finding('LANDABLE_HIGH_G', 75, body,
                                f'landable with {gravity / 9.80665:.2f} g surface gravity',
                                'Landable,SurfaceGravity'))
    if landable and radius > 18000000 and _enabled(enabled, 'LANDABLE_LARGE'):
        results.append(_finding('LANDABLE_LARGE', 60, body,
                                f'landable body radius {radius / 1000:,.0f} km', 'Landable,Radius'))
    if landable and rings and _enabled(enabled, 'LANDABLE_RING'):
        results.append(_finding('LANDABLE_RING', 60, body,
                                'landable body with a ring system', 'Landable,Rings'))

    high_value_classes = ('Earthlike body', 'Ammonia world', 'Water world')
    if (_enabled(enabled, 'HIGH_VALUE_BODY') and
            (planet_class in high_value_classes or
             (terraform and terraform.casefold() != 'not terraformable'))):
        mapping = 'already mapped' if event.get('WasMapped') else 'not previously mapped in this journal evidence'
        results.append(_finding('HIGH_VALUE_BODY', 70, body,
                                f'high-value body ({planet_class or terraform}; {mapping})',
                                'PlanetClass,TerraformState,WasMapped'))

    if _enabled(enabled, 'WIDE_RING') and radius > 0:
        for ring in rings:
            width = _number(ring.get('OuterRad')) - _number(ring.get('InnerRad'))
            if width > radius * 5:
                name = str(ring.get('Name') or 'Ring')
                results.append(_finding('WIDE_RING', 60, body,
                                        f'{name} width {width / 1000:,.0f} km exceeds five body radii',
                                        'Rings'))
                break

    parent_type, parent_id = _parent(event)
    parent = scans.get(parent_id)
    if parent and parent_type in ('Planet', 'Star') and semimajor > 0:
        parent_radius = _number(parent.get('Radius'))
        if (_enabled(enabled, 'CLOSE_ORBIT') and not is_ring and parent_radius > 0 and
                semimajor < parent_radius * 3):
            results.append(_finding('CLOSE_ORBIT', 70, body,
                                    f'orbit {semimajor / 1000:,.0f} km; parent radius {parent_radius / 1000:,.0f} km',
                                    'Parents,SemiMajorAxis'))
        parent_rings = _rings(parent)
        if (_enabled(enabled, 'SHEPHERD_MOON') and not is_ring and parent_rings and
                semimajor < max(_number(ring.get('OuterRad')) for ring in parent_rings)):
            results.append(_finding('SHEPHERD_MOON', 75, body,
                                    'orbit lies inside the parent ring system',
                                    'Parents,SemiMajorAxis,Rings'))
        if _enabled(enabled, 'CLOSE_RING_PROXIMITY') and parent_rings and radius > 0:
            separation = min(min(abs(semimajor - _number(ring.get('InnerRad'))),
                                 abs(semimajor - _number(ring.get('OuterRad')))) - radius
                             for ring in parent_rings)
            if separation < radius * 10:
                results.append(_finding('CLOSE_RING_PROXIMITY', 65, body,
                                        f'body is {separation / 1000:,.0f} km from a parent ring edge',
                                        'Parents,SemiMajorAxis,Radius,Rings'))

    if parent_type == 'Null' and parent_id is not None and semimajor > 0 and radius / semimajor > 0.4:
        partners = []
        for candidate in scans.values():
            if candidate.get('BodyID') == event.get('BodyID'):
                continue
            candidate_type, candidate_parent = _parent(candidate)
            candidate_axis = _number(candidate.get('SemiMajorAxis'))
            candidate_radius = _number(candidate.get('Radius'))
            if (candidate_type == 'Null' and candidate_parent == parent_id and
                    candidate_axis > 0 and candidate_radius / candidate_axis > 0.4):
                partners.append(candidate)
        if len(partners) == 1:
            partner = partners[0]
            partner_name = str(partner.get('BodyName') or 'binary partner')
            partner_radius = _number(partner.get('Radius'))
            partner_axis = _number(partner.get('SemiMajorAxis'))
            closest = (partner_axis * (1 - _number(partner.get('Eccentricity'))) +
                       semimajor * (1 - eccentricity))
            if (_enabled(enabled, 'COLLIDING_BINARY') and
                    partner_radius + radius >= closest):
                results.append(_finding('COLLIDING_BINARY', 90, body,
                                        f'calculated orbital ranges overlap {partner_name}',
                                        'Parents,SemiMajorAxis,Eccentricity,Radius'))
            elif _enabled(enabled, 'CLOSE_BINARY'):
                results.append(_finding('CLOSE_BINARY', 75, body,
                                        f'close binary pairing with {partner_name}',
                                        'Parents,SemiMajorAxis,Radius'))

    second_parent_type, _ = _parent(event, 1)
    if (_enabled(enabled, 'NESTED_MOON') and not is_ring and
            parent_type == 'Planet' and second_parent_type == 'Planet'):
        results.append(_finding('NESTED_MOON', 75, body,
                                'moon orbiting another moon', 'Parents'))
    if (_enabled(enabled, 'SMALL_OBJECT') and not star_type and planet_class and
            planet_class.casefold() != 'barycentre' and radius and radius < 300000):
        results.append(_finding('SMALL_OBJECT', 55, body,
                                f'body radius {radius / 1000:,.0f} km', 'Radius'))
    rotation = abs(_number(event.get('RotationPeriod')))
    if (_enabled(enabled, 'FAST_ROTATION') and not star_type and not is_ring and
            rotation and rotation < 28800 and event.get('TidalLock') is not True):
        results.append(_finding('FAST_ROTATION', 60, body,
                                f'non-locked rotation period {rotation / 3600:.1f} hours',
                                'RotationPeriod,TidalLock'))
    orbit = abs(_number(event.get('OrbitalPeriod')))
    if _enabled(enabled, 'FAST_ORBIT') and not is_ring and orbit and orbit < 28800:
        results.append(_finding('FAST_ORBIT', 60, body,
                                f'orbital period {orbit / 3600:.1f} hours', 'OrbitalPeriod'))
    if _enabled(enabled, 'HIGH_ECCENTRICITY') and eccentricity > 0.9:
        results.append(_finding('HIGH_ECCENTRICITY', 70, body,
                                f'orbital eccentricity {eccentricity:.4f}', 'Eccentricity'))

    materials = _material_names(event)
    premium = {name.casefold() for name in PREMIUM_FSD_MATERIALS}
    matched = premium & materials
    if landable and _enabled(enabled, 'GOOD_FSD_INJECTION') and len(matched) == 5:
        missing = next(name for name in PREMIUM_FSD_MATERIALS if name.casefold() not in matched)
        results.append(_finding('GOOD_FSD_INJECTION', 65, body,
                                f'five of six premium FSD materials; missing {missing}', 'Materials'))

    system_materials = set()
    for scan in scans.values():
        system_materials.update(_material_names(scan))
    if _enabled(enabled, 'ALL_FSD_MATERIALS') and premium <= system_materials:
        results.append(_finding('ALL_FSD_MATERIALS', 80, body,
                                'all six premium FSD injection materials recorded in this system',
                                'Materials'))
    surface = {name.casefold() for name in ALL_SURFACE_MATERIALS}
    if _enabled(enabled, 'ALL_SURFACE_MATERIALS') and surface <= system_materials:
        results.append(_finding('ALL_SURFACE_MATERIALS', 85, body,
                                'all standard surface materials recorded in this system',
                                'Materials'))

    if (_enabled(enabled, 'UNCOMMON_SECONDARY_STAR') and event.get('BodyID', 0) > 0 and
            star_type and _number(event.get('DistanceFromArrivalLS')) > 10 and
            star_type.upper() not in {'O', 'B', 'A', 'F', 'G', 'K', 'M', 'L', 'T', 'Y', 'TTS'}):
        results.append(_finding('UNCOMMON_SECONDARY_STAR', 70, body,
                                f'uncommon secondary stellar type {star_type} at '
                                f'{_number(event.get("DistanceFromArrivalLS")):,.0f} ls',
                                'BodyID,StarType,DistanceFromArrivalLS'))

    return results
