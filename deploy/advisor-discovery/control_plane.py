"""Owner-controlled registrar, OUTSIDE the Engineer sandbox. Never expose this as an Engineer tool."""
import argparse
import json
from pathlib import Path
import re

from integration import validate_contract


def validate_request(value, artifact):
    if not isinstance(value, dict) or set(value) != {'case_id', 'integration'}:
        raise ValueError('invalid_proposal_envelope')
    if not isinstance(value['case_id'], str) or not 1 <= len(value['case_id']) <= 200:
        raise ValueError('invalid_case')
    return value['case_id'], validate_contract(value['integration'], artifact)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True, help='Proposal accepted through the owner-controlled artifact handoff')
    parser.add_argument('--artifact', type=Path, required=True, help='Independently approved release artifact, not an arbitrary Engineer-supplied path')
    parser.add_argument('--engineer', required=True, help='Authenticated Engineer principal from trusted owner job context, never from the proposal')
    parser.add_argument('--service', required=True, help='Owner-provisioned registrar libpq service; credentials stay outside Engineer')
    args = parser.parse_args()
    case, contract = validate_request(json.loads(args.request.read_text(encoding='utf-8')), args.artifact.read_bytes())
    if not args.engineer.strip() or not re.fullmatch(r'[a-zA-Z0-9_-]{1,63}', args.service):
        raise ValueError('trusted_context_required')
    import psycopg
    from psycopg.types.json import Jsonb
    with psycopg.connect(service=args.service, connect_timeout=5) as db:
        db.execute('SELECT system.register_advisor_integration(%s::text,%s::text,%s::jsonb)',
                   (case, args.engineer, Jsonb(contract)))
    print(json.dumps({'case_id': case, 'equipment_id': contract['equipment_id'], 'registered': True,
                      'acceptance': 'Verify scoped reads, synthetic receipt and completed model reply before closing the case.'}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('REGISTRATION_FAILED: raw database output and credentials withheld.') from None
