"""Engineer-side, offline delivery proposal. No database/network credentials or connections."""
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
    parser.add_argument('action', choices=['validate', 'prepare'])
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--case')
    parser.add_argument('--output', type=Path, help='New proposal file in the permitted Engineer work directory')
    args = parser.parse_args()
    contract = validate_contract(json.loads(args.contract.read_text(encoding='utf-8')), args.artifact.read_bytes())
    if args.action == 'prepare':
        if not args.case or not args.output:
            raise ValueError('case_and_output_required')
        # The proposal is data, not approval or executable code. Actor identity is
        # deliberately absent: the owner controller obtains it from its trusted job context.
        with args.output.open('x', encoding='utf-8') as output:
            json.dump({'case_id': args.case, 'integration': contract}, output, sort_keys=True, indent=2)
            output.write('\n')
    print(json.dumps({'equipment_id': contract['equipment_id'], 'action': args.action, 'ok': True,
                      'acceptance': 'Owner-mediated registration and end-to-end acceptance are still required.'}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('PROPOSAL_FAILED: inspect the contract and approved work-directory inputs.') from None
