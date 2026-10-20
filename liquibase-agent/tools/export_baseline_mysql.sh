#!/usr/bin/env bash
# Schema-only export (MySQL / MariaDB) used as --baseline. Usage: ./export_baseline_mysql.sh <db> <out.sql>
set -euo pipefail
mysqldump --no-data --routines --triggers --skip-comments --single-transaction "$1" > "$2"
