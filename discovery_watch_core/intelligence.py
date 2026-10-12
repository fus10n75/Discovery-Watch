"""Shared finding policy and Settings behaviour definitions.

The journal parser establishes facts.  This module establishes what Discovery
Watch does with those facts so recording, investigation and popup decisions do
not drift apart in separate parts of the application.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class FindingPolicy:
    category: str
    record: bool
    creates_investigation: bool
    popup_control: str
    attention: str
    rationale: str


_EXACT_POLICIES={
    'MEGASHIP':FindingPolicy('Signals and POIs',True,False,'Megaships','Important',
        'A named structure is useful system intelligence, but is not unfinished exploration work.'),
    'INSTALLATION':FindingPolicy('Signals and POIs',True,False,'Installations','Important',
        'A named structure is useful system intelligence, but is not unfinished exploration work.'),
    'ANCIENT_PROBE':FindingPolicy('Signals and POIs',True,False,'Unknown or unidentified names','Important',
        'A recognised point of interest is retained without creating a body investigation.'),
    'STELLAR_PHENOMENON':FindingPolicy('Signals and POIs',True,False,'Stellar phenomena','Review',
        'The journal explicitly names a stellar phenomenon worth reviewing.'),
    'CODEX_PHENOMENON':FindingPolicy('Signals and POIs',True,False,'Stellar phenomena','Review',
        'A Codex phenomenon is a confirmed record rather than unfinished body work.'),
    'SIGNAL_TYPE_TITAN':FindingPolicy('Signals and POIs',True,False,'Titans','Important',
        'The journal explicitly classifies this high-priority signal as a Titan.'),
    'SIGNAL_TYPE_TOURISTBEACON':FindingPolicy('Signals and POIs',True,False,'Tourist beacons','Informational',
        'A known tourist beacon is useful local context rather than an investigation.'),
    'UNIDENTIFIED_SIGNAL':FindingPolicy('Exploration reminders',True,False,
        'Unknown or unidentified names','Informational',
        'The name is a prompt to review, not proof that the contact is unusual.'),
    'UNRESOLVED_NON_BODY_SIGNALS':FindingPolicy('Exploration reminders',True,False,
        'Unidentified system contacts','Informational',
        'The FSS count indicates unresolved contacts without identifying their nature.'),
    'SYSTEM_DISCOVERY_STATUS':FindingPolicy('Exploration reminders',True,False,
        'Arrival discovery status','Informational',
        'Only WasDiscovered=false is retained as a cautious possible first-discovery opportunity.'),
    'ANOMALY_ALERT':FindingPolicy('Anomalies',True,True,'Notable worlds and anomalies','Review',
        'Evidence-backed anomaly rules create a reviewable investigation lead.'),
    'SURFACE_MINING':FindingPolicy('Surface signals',True,False,
        'Planetary Mining Locations','Informational',
        'This is a known utility location, so it is recorded without becoming an investigation.'),
    'SURFACE_THARGOID':FindingPolicy('Surface signals',True,True,'Thargoid surface signals','Important',
        'Thargoid surface evidence is retained as an investigation target.'),
    'SURFACE_GUARDIAN':FindingPolicy('Surface signals',True,True,'Guardian surface signals','Important',
        'Guardian surface evidence is retained as an investigation target.'),
    'SURFACE_BIOLOGICAL':FindingPolicy('Biological discoveries',True,True,'Biological surface signals','Review',
        'Biological evidence can progress through mapping and organic sampling.'),
    'SURFACE_GEOLOGICAL':FindingPolicy('Surface signals',True,True,'Geological surface signals','Review',
        'Geological evidence is reviewable body intelligence.'),
    'SURFACE_HUMAN':FindingPolicy('Surface signals',True,True,'Human surface signals','Review',
        'Human surface evidence is retained for review.'),
    'SURFACE_OTHER':FindingPolicy('Surface signals',True,True,'Other surface signals','Review',
        'An unclassified surface contact remains a lead until its evidence is understood.'),
    'BIO_STRATUM_LEAD':FindingPolicy('Biological discoveries',True,True,'Stratum discoveries','Important',
        'A reported Stratum genus is a lead that can be confirmed through organic sampling.'),
    'BIO_STRATUM_TECTONICAS':FindingPolicy('Biological discoveries',True,True,'Stratum discoveries','Important',
        'The journal explicitly confirms the sought-after species.'),
    'BEFORE_LEAVING':FindingPolicy('Exploration reminders',True,False,'Before-departure warning','Review',
        'This reminder summarises existing unfinished investigations; it does not create another one.'),
    'NONHUMAN_USS':FindingPolicy('Signals and POIs',True,False,'Nonhuman signal sources','Important',
        'The journal explicitly classifies the USS as nonhuman.'),
    'LISTENING_POST':FindingPolicy('Signals and POIs',True,False,'Listening posts','Important',
        'A recognised navigation contact is recorded as a point of interest.'),
    'COMMS_BEACON':FindingPolicy('Signals and POIs',True,False,'Generic signal rule','Important',
        'The Generic type and signal name jointly identify the beacon.'),
}

_DEFAULT_POLICY=FindingPolicy('Signals and POIs',True,False,'Matching rule','Review',
    'The matching journal rule records this evidence; no investigation lifecycle is implied.')


def finding_policy(rule,title='',detail=''):
    """Return the single operational policy for a finding rule."""
    rule=str(rule or '')
    if rule in _EXACT_POLICIES:
        policy=_EXACT_POLICIES[rule]
        if rule=='ANOMALY_ALERT':
            evidence=(str(title or '')+' '+str(detail or '')).casefold()
            if ('valuable_world' in evidence or 'terraformable' in evidence or
                    'high_value_body' in evidence or 'green_gas_giant' in evidence):
                return replace(policy,category='Notable worlds')
        return policy
    if rule.startswith('WATCHLIST_'):
        return FindingPolicy('Signals and POIs',True,False,'Commander Watchlist','Review',
            'A commander-defined phrase matched the journal evidence.')
    if rule.startswith('SIGNAL_TYPE_'):
        return FindingPolicy('Signals and POIs',True,False,'Signal-type rule','Review',
            'The signal catalogue controls whether this broad journal type alerts or records silently.')
    if rule.startswith('GENERIC_'):
        return FindingPolicy('Signals and POIs',True,False,'Generic signal rule','Review',
            'The reviewed Generic-name rule controls this finding independently of the broad type.')
    if rule.startswith('SURFACE_'):
        return FindingPolicy('Surface signals',True,True,'Other surface signals','Review',
            'An unrecognised surface category is retained as a reviewable lead.')
    return _DEFAULT_POLICY


SETTINGS_BEHAVIOUR=(
    ('Megaships','Megaship findings','Recorded','No investigation','Controls this popup'),
    ('Installations','Installation findings','Recorded','No investigation','Controls this popup'),
    ('Titans / Tourist beacons / USS / Listening posts','Signal catalogue','Policy controlled','No investigation','Per-type popup'),
    ('Unidentified system contacts','Experimental per-visit FSS reconciliation','When enabled','No investigation','Opt-in; one reminder per visit'),
    ('Stellar phenomena','Phenomenon findings','Recorded','No investigation','Controls finding'),
    ('Unknown or unidentified names','Unknown-name findings','Recorded','No investigation','Controls finding'),
    ('Notable worlds and anomalies','Anomaly findings','Always recorded','Creates review lead','Controls popup only'),
    ('Built-in exploration criteria','23 journal-based astronomical checks','Enabled individually',
     'Creates review lead','Uses anomaly popup control'),
    ('Planetary Mining Locations','Known mining locations','Always recorded','Never creates lead','Controls popup only'),
    ('Before-departure warning','Existing unfinished cases','Reminder recorded','No new lead','Controls reminder'),
    ('Show popup notifications','All eligible findings','Unaffected','Unaffected','Master delivery switch'),
    ('Known POIs on arrival','Cached local POIs','No replayed evidence','No investigation','Controls arrival reminder'),
    ('Arrival discovery status','Arrival-star Scan WasDiscovered value','When enabled','No investigation','Opt-in; once per FSD visit'),
    ('Thargoid surface signals','Thargoid evidence','Always recorded','Creates investigation','Controls popup only'),
    ('Guardian surface signals','Guardian evidence','Always recorded','Creates investigation','Controls popup only'),
    ('Biological surface signals','Biological evidence','Always recorded','Creates investigation','Controls popup only'),
    ('Geological surface signals','Geological evidence','Always recorded','Creates investigation','Controls popup only'),
    ('Human surface signals','Human evidence','Always recorded','Creates investigation','Controls popup only'),
    ('Other surface signals','Unknown surface evidence','Always recorded','Creates investigation','Controls popup only'),
    ('Stratum discoveries','Stratum evidence','Always recorded','Creates investigation','Controls popup only'),
    ('Notify once for new Generic names','Unreviewed Generic names','Catalogue retained','No investigation','Controls review prompt'),
    ('Start monitoring automatically','Application startup','Unaffected','Unaffected','Starts monitor only'),
    ('Enable EDSM Community Intelligence','Optional community lookup','Local evidence unaffected','Possible leads labelled','Controls online lookup'),
    ('Close popups / keep above / sound / monitor','Popup presentation','Unaffected','Unaffected','Presentation only'),
)


def policy_explanation(rule,title='',detail=''):
    policy=finding_policy(rule,title,detail)
    return (f'Record: {"Yes" if policy.record else "No"}\n'
            f'Investigation: {"Created or progressed" if policy.creates_investigation else "Not created"}\n'
            f'Popup control: {policy.popup_control}\n'
            f'Policy reason: {policy.rationale}')


def popup_delivery_allowed(master_enabled,findings):
    """Apply the master switch only at delivery time; recording is unaffected."""
    return bool(master_enabled and findings)


def validate_policy_registry():
    """Return deterministic checks for the invariants Settings promises."""
    checks={
        'planetary_mining_records_without_investigation':(
            finding_policy('SURFACE_MINING').record and
            not finding_policy('SURFACE_MINING').creates_investigation),
        'planetary_mining_has_independent_popup_control':(
            finding_policy('SURFACE_MINING').popup_control=='Planetary Mining Locations'),
        'important_surface_categories_create_investigations':all(
            finding_policy(rule).creates_investigation
            for rule in ('SURFACE_THARGOID','SURFACE_GUARDIAN','SURFACE_BIOLOGICAL')),
        'structures_do_not_create_unfinished_work':all(
            not finding_policy(rule).creates_investigation for rule in ('MEGASHIP','INSTALLATION')),
        'master_popup_switch_does_not_change_record_policy':(
            finding_policy('MEGASHIP').record and not popup_delivery_allowed(False,[('x','y','z')])),
        'settings_controls_have_unique_names':(
            len({row[0] for row in SETTINGS_BEHAVIOUR})==len(SETTINGS_BEHAVIOUR)),
        'settings_controls_document_their_effects':all(all(str(value).strip() for value in row)
                                                       for row in SETTINGS_BEHAVIOUR),
    }
    return checks
