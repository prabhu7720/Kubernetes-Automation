#!/usr/bin/env bash
# Schema-only export used as --baseline (stays on the host). Usage: ./export_baseline_postgresql.sh <db> <schema> <out.sql>
set -euo pipefail
pg_dump --schema-only --no-owner --no-privileges --schema="$2" -d "$1" -f "$3"
