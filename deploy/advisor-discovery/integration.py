"""Validate and register an Engineer delivery through an existing scoped libpq service."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def validate_contract(value, artifact):
    if not isinstance(value, dict) or set(value) != {'equipment_id','node','telemetry_system','alarm_metrics','alarm_watch','artifact_sha256'}:
        raise ValueError('invalid_contract_fields')
    for key in ('equipment_id','node','telemetry_system'):
        if not isinstance(value[key], str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,62}', value[key]):
            raise ValueError('invalid_identity')
    metrics = value['alarm_metrics']
    if type(value['alarm_watch']) is not bool or not isinstance(metrics, dict) or len(metrics) > 64 or (value['alarm_watch'] and not metrics):
        raise ValueError('invalid_alarm_contract')
    if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', k) or v not in ('boolean','integer','uint16') for k,v in metrics.items()):
        raise ValueError('invalid_profile')
    if value['artifact_sha256'] != hashlib.sha256(artifact).hexdigest():
        raise ValueError('artifact_hash_mismatch')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate', 'register'])
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--case')
    parser.add_argument('--service', help='Provisioned scoped Engineer libpq service name, not a DSN or password')
    args = parser.parse_args()
    contract = validate_contract(json.loads(args.contract.read_text(encoding='utf-8')), args.artifact.read_bytes())
    if args.action == 'register':
        if not args.case or not args.service or not re.fullmatch(r'[a-zA-Z0-9_-]{1,63}', args.service):
            raise ValueError('case_and_service_required')
        import psycopg
        from psycopg.types.json import Jsonb
        with psycopg.connect(service=args.service, connect_timeout=5) as db:
            db.execute('SELECT system.register_advisor_integration(%s::text,%s::jsonb)', (args.case, Jsonb(contract)))
    print(json.dumps({'equipment_id': contract['equipment_id'], 'action': args.action, 'ok': True,
                      'acceptance': 'Verify read path, synthetic receipt and completed model reply before closing the case.'}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('DELIVERY_FAILED: raw database output and credentials withheld.') from None
