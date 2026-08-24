#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="${OPENAUT_ROOT:-$(cd "$HERE/.." && pwd)}"
deploy="$root/deploy/platform-poc1"
compose=(docker compose --project-directory "$deploy")
psql_cmd=("${compose[@]}" exec --no-TTY timescaledb psql -v ON_ERROR_STOP=1 -U postgres -d openaut)

"${psql_cmd[@]}" <<'SQL'
INSERT INTO system.sites(site, name) VALUES ('poc-lab', 'POC lab') ON CONFLICT (site) DO NOTHING;
DELETE FROM system.audit_events WHERE target_id IN ('poc2-draft', 'poc2-invalid-scope', 'poc2-self-approve', 'poc2-approved');
DELETE FROM system.approvals WHERE case_id IN ('poc2-draft', 'poc2-invalid-scope', 'poc2-self-approve', 'poc2-approved');
DELETE FROM system.cases WHERE case_id IN ('poc2-draft', 'poc2-invalid-scope', 'poc2-self-approve', 'poc2-approved');
DROP ROLE IF EXISTS poc2_advisor_test, poc2_approver_test, poc2_engineer_test, poc2_dual_test;
CREATE ROLE poc2_advisor_test NOLOGIN IN ROLE advisor_app;
CREATE ROLE poc2_approver_test NOLOGIN IN ROLE approver_app;
CREATE ROLE poc2_engineer_test NOLOGIN IN ROLE engineer_app;
CREATE ROLE poc2_dual_test NOLOGIN IN ROLE advisor_app, approver_app;

SET SESSION AUTHORIZATION poc2_advisor_test;
INSERT INTO system.cases(case_id, site, title, summary)
VALUES ('poc2-draft', 'poc-lab', 'Draft must fail', 'POC2 negative gate');
INSERT INTO system.cases(case_id, site, title, summary)
VALUES ('poc2-invalid-scope', 'poc-lab', 'Invalid scope must fail', 'POC2 scope gate');
INSERT INTO system.cases(case_id, site, title, summary)
VALUES ('poc2-approved', 'poc-lab', 'Approved test', 'POC2 positive gate');
SELECT system.request_case_approval('poc2-invalid-scope');
SELECT system.request_case_approval('poc2-approved');
RESET SESSION AUTHORIZATION;

SET SESSION AUTHORIZATION poc2_dual_test;
INSERT INTO system.cases(case_id, site, title, summary)
VALUES ('poc2-self-approve', 'poc-lab', 'Self approval must fail', 'POC2 separation-of-duties gate');
SELECT system.request_case_approval('poc2-self-approve');
RESET SESSION AUTHORIZATION;
SQL

if "${psql_cmd[@]}" -c "SET SESSION AUTHORIZATION poc2_advisor_test; INSERT INTO system.cases(case_id,site,created_by,title,summary) VALUES('spoofed','poc-lab','spoofed','x','x')" >/dev/null 2>&1; then
  echo "FAIL — Advisor spoofed created_by." >&2
  exit 1
fi

if "${psql_cmd[@]}" -c "SET SESSION AUTHORIZATION poc2_engineer_test; SELECT system.engineer_start_case('poc2-draft')" >/dev/null 2>&1; then
  echo "FAIL — Engineer started an unapproved case." >&2
  exit 1
fi

if "${psql_cmd[@]}" -c "SET SESSION AUTHORIZATION poc2_approver_test; SELECT system.approve_case('poc2-invalid-scope','approval-invalid','{\"action\":\"forge-pr-only\",\"field_write\":false,\"deploy\":true}'::jsonb,'invalid')" >/dev/null 2>&1; then
  echo "FAIL — approver granted an expanded POC2 scope." >&2
  exit 1
fi

if "${psql_cmd[@]}" -c "SET SESSION AUTHORIZATION poc2_dual_test; SELECT system.approve_case('poc2-self-approve','approval-self','{\"action\":\"forge-pr-only\",\"field_write\":false}'::jsonb,'self')" >/dev/null 2>&1; then
  echo "FAIL — case creator approved its own case." >&2
  exit 1
fi

"${psql_cmd[@]}" <<'SQL'
SET SESSION AUTHORIZATION poc2_approver_test;
SELECT system.approve_case('poc2-approved', 'approval-poc2-approved', '{"action":"forge-pr-only","field_write":false}'::jsonb, 'POC2 test');
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION poc2_engineer_test;
SELECT system.engineer_start_case('poc2-approved');
SELECT case_id, status, approval_scope FROM system.engineer_approved_cases WHERE case_id = 'poc2-approved';
RESET SESSION AUTHORIZATION;
SQL

result="$("${psql_cmd[@]}" -Atc "SELECT c.status || ':' || count(a.audit_id) || ':' || count(DISTINCT a.actor) FROM system.cases c JOIN system.audit_events a ON a.target_id=c.case_id WHERE c.case_id='poc2-approved' GROUP BY c.status")"
[ "$result" = "in_progress:3:3" ]

"${psql_cmd[@]}" <<'SQL'
DROP ROLE poc2_advisor_test, poc2_approver_test, poc2_engineer_test, poc2_dual_test;
SQL

echo "POC2_DB_OK unapproved_case=denied invalid_scope=denied self_approval=denied spoofed_actor=denied approved_case=$result"
