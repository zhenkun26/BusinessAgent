"""Print a BLOCKED browser acceptance plan or validate sanitized operator observations.

No network, browser, environment access or file writes. Supplied observations are reports,
never independent acceptance evidence; full review must use the retained source artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from reference_idp.server import strict_json

CASES = {
    'S01': 'Browser login, callback, one-use handoff, /me and repeat identity mapping',
    'S02': 'Concurrent first login and two subjects sharing one display username',
    'S03': 'First-login salesperson/default department; remote privilege claims ignored',
    'S04': 'Disabled local mapping denied; existing local role/department preserved',
    'S05': 'Bad signature, unknown kid and malformed token denied before provisioning',
    'S06': 'Wrong issuer/audience and multi-audience without matching azp denied',
    'S07': 'Wrong nonce, missing subject and oversized subject denied',
    'S08': 'Expired token, future iat, expired authorization request/code/state denied',
    'S09': 'Wrong/missing cookie/state, callback replay and concurrent callbacks denied',
    'S10': 'Wrong client/redirect/PKCE, code replay and concurrent redemption denied',
    'S11': 'Key publication overlap, active switch and old key retirement verified',
    'S12': 'IdP/TLS/JWKS outage fails closed; local password login remains secure',
    'S13': 'Two API processes share Redis state; restart and Redis failure fail closed',
    'S14': 'IdP disk restart preserves spent codes, pending state, key selection and identity',
    'S15': 'No tokens/codes/secrets in URLs after handoff, logs or exported evidence',
    'S16': 'Operator separation, invalid framing, isolated images/TLS/CA and retained evidence',
}


def plan() -> dict[str, Any]:
    return {'schema': 'controlled-sso-evidence-v1', 'status': 'BLOCKED',
            'evidence_type': 'plan_only', 'formal_uat': False, 'release_evidence': False,
            'release_allowed': False,
            'cases': [{'id': key, 'requirement': value, 'status': 'BLOCKED'}
                      for key, value in CASES.items()]}


def observations(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {'candidate_commit', 'app_digest', 'idp_digest', 'store_id',
                      'store_identity_hash', 'cases'}:
        raise ValueError
    for key, pattern in {'candidate_commit': r'[0-9a-f]{40}',
                         'app_digest': r'sha256:[0-9a-f]{64}',
                         'idp_digest': r'sha256:[0-9a-f]{64}',
                         'store_identity_hash': r'[0-9a-f]{64}'}.items():
        if not isinstance(value[key], str) or not re.fullmatch(pattern, value[key]):
            raise ValueError
    store = UUID(value['store_id'])
    if str(store) != value['store_id'] or store.version != 4:
        raise ValueError
    rows = value['cases']
    if not isinstance(rows, list) or len(rows) != len(CASES):
        raise ValueError
    seen: set[str] = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id', 'reported_status', 'artifact_sha256'}
                or row['id'] not in CASES or row['id'] in seen
                or row['reported_status'] not in {'PASS', 'FAIL', 'BLOCKED'}
                or not isinstance(row['artifact_sha256'], list)
                or len(row['artifact_sha256']) > 50
                or any(not isinstance(h, str) or not re.fullmatch(r'[0-9a-f]{64}', h)
                       for h in row['artifact_sha256'])
                or row['reported_status'] != 'BLOCKED' and not row['artifact_sha256']):
            raise ValueError
        seen.add(row['id'])
    result = plan()
    result['evidence_type'] = 'operator_report_unverified'
    result['observations'] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations', type=Path)
    args = parser.parse_args()
    try:
        if args.observations:
            with args.observations.open('rb') as source:
                raw = source.read(65537)
            if len(raw) > 65536:
                raise ValueError
            result = observations(strict_json(raw))
        else:
            result = plan()
        print(json.dumps(result, indent=2))
        return 2  # A valid plan/report never certifies runtime acceptance.
    except (OSError, ValueError, TypeError, KeyError):
        print('{"status":"FAIL","error":"INVALID_SSO_OBSERVATIONS"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
