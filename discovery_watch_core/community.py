"""Optional EDSM community-data lookup and lead scoring."""

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .config import APP_VERSION, EDSM_BODIES_URL, EDSM_SYSTEM_URL


def _read_json_url(url, opener=urllib.request.urlopen, timeout=10):
    request=urllib.request.Request(url,headers={'User-Agent':f'Discovery-Watch/{APP_VERSION}'})
    with opener(request,timeout=timeout) as response:
        payload=response.read()
    value=json.loads(payload.decode('utf-8'))
    if not isinstance(value,dict):
        raise ValueError('EDSM returned an unexpected response')
    return value


def fetch_edsm_system(system, opener=urllib.request.urlopen, timeout=10):
    """Fetch public EDSM catalogue context. No commander API key is required."""
    system=str(system or '').strip()
    if not system:
        raise ValueError('A system name is required for EDSM lookup')
    query=urllib.parse.urlencode({'systemName':system})
    info_query=urllib.parse.urlencode({'systemName':system,'showId':1,'showCoordinates':1,
                                      'showPermit':1,'showInformation':1,'showPrimaryStar':1})
    errors=[]; info={}; bodies={}
    try: info=_read_json_url(EDSM_SYSTEM_URL+'?'+info_query,opener,timeout)
    except (OSError,ValueError,urllib.error.URLError) as exc: errors.append(f'system: {exc}')
    try: bodies=_read_json_url(EDSM_BODIES_URL+'?'+query,opener,timeout)
    except (OSError,ValueError,urllib.error.URLError) as exc: errors.append(f'bodies: {exc}')
    if not info and not bodies:
        raise OSError('; '.join(errors) or 'EDSM lookup failed')
    found=bool(info.get('name') or bodies.get('name') or bodies.get('id'))
    return {'status':'ok' if found else 'not_found','system':system,'system_info':info,
            'body_data':bodies,'partial_errors':errors,
            'fetched_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}


def edsm_system_url(system):
    return 'https://www.edsm.net/en/system?' + urllib.parse.urlencode({'systemName':str(system or '')})


def score_edsm_leads(payload, local_body_names=()):
    """Conservative comparisons and configurations; every result is only a possible lead."""
    body_data=payload.get('body_data') or {}
    bodies=body_data.get('bodies') if isinstance(body_data.get('bodies'),list) else []
    expected=body_data.get('bodyCount')
    expected=int(expected) if isinstance(expected,(int,float)) and not isinstance(expected,bool) else None
    leads=[]
    if expected is not None and expected>len(bodies):
        leads.append((65,'Incomplete EDSM body catalogue',
                      f'EDSM reports {expected} bodies but provides details for {len(bodies)}.'))
    edsm_names={' '.join(str(body.get('name') or '').casefold().split()) for body in bodies}
    local_names={' '.join(str(name or '').casefold().split()) for name in local_body_names if str(name or '').strip()}
    missing_local=sorted(name for name in local_names if name not in edsm_names)
    if missing_local:
        leads.append((70,'Local bodies absent from EDSM',
                      f'{len(missing_local)} locally recorded body name(s) are not in the returned EDSM body list.'))
    star_types=[str(body.get('subType') or '') for body in bodies if str(body.get('type') or '').casefold()=='star']
    unusual=[kind for kind in star_types if any(term in kind.casefold() for term in
              ('black hole','neutron','wolf-rayet','carbon star'))]
    if unusual:
        leads.append((70,'Unusual stellar type recorded',', '.join(sorted(set(unusual)))))
    if len(star_types)>=3:
        leads.append((40,'Complex multi-star configuration',
                      f'EDSM lists {len(star_types)} stellar bodies in this system.'))
    notable=[]
    for body in bodies:
        subtype=str(body.get('subType') or '')
        if any(term in subtype.casefold() for term in ('earth-like','ammonia world','water world')):
            notable.append(subtype)
    if notable:
        leads.append((55,'Potentially valuable or notable worlds',
                      f'EDSM lists {len(notable)}: '+', '.join(sorted(set(notable)))))
    return sorted(leads,key=lambda item:(-item[0],item[1]))
