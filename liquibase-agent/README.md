# Offline Liquibase Automation Agent

A rule-based, template-driven agent that analyses SQL scripts and produces production-ready
Liquibase changelogs for **Oracle, PostgreSQL, MySQL, MariaDB and SQL Server**.

- **Fully offline.** Pure Python 3.8+ standard library. No pip installs, no network calls, no AI or LLM APIs.
  Scripts and metadata never leave the host.
- **Two output formats from one analysis run:**
  - **Liquibase XML** (`db.changelog-<release>.xml`): native change types, one logical change per changeSet,
    explicit `<rollback>`, preconditions and a `tagDatabase` before the release.
  - **House-style formatted SQL**, modelled on the `vibehub_1.34` package: `SOL_DATA:SOL_SERVICES.<rel>.1.0.N`
    ids, `LIQUIBASE_DB_CHANGE_TRACKER` `-pre`/`-post` changeSets, `endDelimiter:"/"` for PL/SQL, inline
    `--rollback`, and a consolidated `91_..._ROLLBACK.sql` in a `_Rollback` folder.
- **A report in the requested format:** Change Summary, Liquibase XML, Rollback, Risk Assessment, Deployment Notes,
  Validation Checklist, plus pre-check and post-check SQL.

---

## Quick start

```bash
# your own example (employee table) -> prints the full report
python agent.py analyze --sql "CREATE TABLE employee (employee_id NUMBER PRIMARY KEY, employee_name VARCHAR2(100), created_date DATE);" --print --no-files

# a release folder, house style, continuing ids from the existing changelogs
python agent.py analyze -i release_1.35/ --profile sol_services --release 1.35 \
       --baseline baseline/BILLING_EVENT.sql --changelog vibehub_1.34_deploy/ -o out/

# validate existing Liquibase files (XML or formatted SQL)
python agent.py validate -i vibehub_1.34_deploy/ vibehub_1.34_Rollback/ --profile sol_services -o out/

# CI gate: non-zero exit if HIGH or worse is found
python agent.py analyze -i release/ --profile sol_services --fail-on HIGH -o out/

python agent.py profiles          # list profiles
python -m unittest discover -s tests -v
```

On Windows use `py agent.py ...`. All paths may be files or directories.

### Output layout (`-o out/`)

```
out/
├── report.md                     # the 7 sections (summary, XML, rollback, risk, deploy notes, checklist, checks)
├── report.json                   # machine-readable (CI dashboards / gates)
├── changelog/db.changelog-SOL_SERVICES-1.35.xml
├── vibehub_1.35_deploy/          # house formatted SQL, one script per logical object
│   ├── 01_VIBEHUB_BILLING_EVENT_<OBJECT>_DDL.sql
│   ├── 02_VIBEHUB_BILLING_EVENT_<TRIGGER>_TRIG_DDL.sql
│   └── ...
├── vibehub_1.35_Rollback/91_VIBEHUB_BILLING_EVENT_1_35_ROLLBACK.sql
└── checks/precheck.sql, checks/postcheck.sql
```

---

## Inputs

| Input | How |
|---|---|
| SQL scripts / table definitions / index, view, trigger, procedure scripts | `-i file_or_dir ...`, `--sql "..."`, `--stdin` |
| Existing Liquibase XML / formatted SQL (to re-analyse or convert) | `-i` (detected automatically) |
| Existing Liquibase changelogs (duplicate ids, id continuation, already-deployed objects) | `--changelog` |
| Existing database DDL (exact rollbacks and conflict detection) | `--baseline` (export with `tools/export_baseline_*`) |

**Why `--baseline` matters.** Without the current DDL, the agent can't know a column's old definition, the old
source of a view or trigger, or a constraint's definition. In those cases it marks the rollback `ROLLBACK-MANUAL`,
and the validation checklist fails. It doesn't guess. When you supply a baseline, it generates exact rollbacks. On the
1.34 release it re-creates your hand-written 91 rollback: it restores the 1.33 `ACCOUNT_EVENT_VW` *before* it drops
`TO_ACCOUNT_ID`, re-adds `FK_ACCT_TRANSFER_FROM_ACCT` and resets `NOT NULL`.

## Supported operations

Create, alter or drop a table. Add, modify (type, nullability, default, rename) or drop a column. Add or drop a
constraint (PK, UK, FK, CHECK). Create or drop an index (unique, bitmap, function-based, `CONCURRENTLY`, `ONLINE`).
Create a view or replace a view (`FORCE`, `EDITIONABLE`, materialized). Create, alter or drop a sequence. Triggers,
procedures, functions, packages and package bodies (PL/SQL, PL/pgSQL, T-SQL, MySQL routines). Comments, grants and
revokes. Data migration (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `TRUNCATE`). Anonymous blocks. Rollback generation
for all of these.

## Script analysis pipeline

```
parse (sql_parser: dialect detection + statement splitting)
  -> classify (ddl_parser: statement -> operations; ALTERs with several actions are split)
  -> per operation, against an in-memory schema model (baseline + changelogs + earlier statements):
       syntax checks -> pre-apply analysis -> apply (conflicts, BEFORE image) -> risk analysis + impact text
       -> rollback generation -> pre/post check SQL
  -> release-level analysis (ordering, invalidation windows, FK indexes, naming, best practices)
  -> grouping into changeSets / scripts -> XML + formatted SQL generation from templates
  -> validation of the GENERATED output (Liquibase syntax, duplicates, rollback coverage, id sequence)
  -> report.md / report.json
```

### Examples of rules found on the vibehub 1.34 package

- **INVALID_WINDOW.** `TRG_SHADOW_ORDER_AUDIT` is invalid between script 10 (`DROP COLUMN STATUS`) and
  script 12 (its re-creation). DML on `SHADOW_ORDER` fails with ORA-04098 in that window.
- **LB_DDL_DML_MIX.** Script 07 mixes `ALTER` with `UPDATE` in one changeSet. The agent splits them into
  `_ALTER_DDL` + `_DML` and adds a `-bkp` backup changeSet so the UPDATE can be rolled back.
- **RB_MISSING.** None of the 1.34 changeSets have `--rollback`, so `liquibase rollback` can't undo them. The
  generated scripts have rollbacks on every changeSet, including the tracker `-pre`/`-post` changeSets.
- **IMPLICIT_DROPS.** `DROP COLUMN STATUS CASCADE CONSTRAINTS` silently drops `CHK_SHADOW_STATUS`,
  `IDX_SHADOW_ORDER_ACCT` and `IDX_SHADOW_ORDER_TTL`. The rollback re-creates them.
- **INDEX_LOCK.** The FK index script builds indexes on existing tables without `ONLINE`.
- **NOLOGGING.** Recovery and Data Guard impact. **SEQ_NOCACHE.** Contention at high insert rates.
  **IDENT_LONG.** `TRG_SHADOW_PRODUCT_ORDER_BEFORE` is 31 characters long and fails on databases older than 12.2.

## Validation

| Check | What is checked |
|---|---|
| SQL syntax | Balanced parentheses, quotes and BEGIN/END. Trailing or double commas. Reserved words. Dialect-foreign types (for example `VARCHAR2` on PostgreSQL). Identifier length. `GO` in Oracle. |
| Liquibase syntax | Well-formed XML. Header. id and author present. Known change types (Pro-only ones are flagged). PL/SQL without `splitStatements:false`/`endDelimiter`. A `/` inside a body when `endDelimiter:"/"` is used. |
| Duplicate changeSets | Same file (fatal) and across files. Duplicate CREATEs in the input. |
| Missing rollback | Generated output and supplied files. Notes whether Liquibase can auto-generate a rollback for each XML change type. |
| Naming conventions | Prefixes and suffixes from the profile (`PK_`, `FK_`, `UK_`, `CHK_`, `IDX_`, `SEQ_`, `TRG_`, `_VW`). Case. Unnamed constraints. Author format. |
| Existing object conflicts | Creating something that already exists. Altering or dropping something that is missing. Constraint name reuse. Index columns that are missing at that step. Triggers referencing columns that don't exist. |
| Best practices | One change per changeSet. DDL and DML separated. Sequential ids. Hard-coded schema, tablespace or db-link names. Environment-specific data. |

## Profiles (`config/`)

`config/default.json` is the base. `config/profiles/*.json` are deep-merged over it.

- `sol_services`: your house style (Oracle, `SOL_DATA`, tracker table, `VIBEHUB` file naming, auto read/write role
  grants, `_AUDIT` tables read-only, tablespace enforced, standard audit columns required).
- `oracle`, `postgresql`, `mysql`, `mariadb`, `mssql`: generic profiles.

Settings you'll most likely change: `author`, `project`, `app`, `release`, `default_schema`, `changeset_id_pattern`,
`file_name_pattern`, `tracker.*`, `grants.*`, `naming.*`, `preconditions`, `precondition_on_fail`, `dml_backup`,
`plsql_changeset_attrs`, `allow_grouped_ddl`, `assume_new_when_unknown`.

To onboard another team, copy `sol_services.json`, then change `project`, `app`, `author` and the tracker settings.

## Templates (`templates/`)

All emitted XML and SQL comes from editable `string.Template` files: `create_table.xml`, `alter_table.xml`,
`create_index.xml`, `procedure.xml`, `changelog.xml` and `formatted_sql.sql`. One file can hold several templates,
each separated by an `@template name` marker. You can change formatting without touching the code.

## Project structure

```
liquibase-agent/
├── agent.py                     # CLI (analyze / validate / profiles)
├── core/        models.py, lexer.py, schema.py (schema model + BEFORE images), engine.py, config.py
├── parsers/     sql_parser.py (dialects, splitting), ddl_parser.py (operations), liquibase_parser.py
├── analyzers/   table_analyzer.py, index_analyzer.py, procedure_analyzer.py, dml_analyzer.py, dependency_analyzer.py
├── generators/  liquibase_generator.py, rollback_generator.py, check_generator.py, grouping.py, naming.py,
│                report_generator.py, dialect.py, xml_util.py
├── validators/  syntax_validator.py, naming_validator.py, rollback_validator.py, liquibase_validator.py,
│                best_practice_validator.py
├── templates/   *.xml, formatted_sql.sql, loader.py
├── config/      default.json, profiles/*.json
├── tools/       export_baseline_{oracle.sql,postgresql.sh,mysql.sh,mssql.ps1}
├── samples/     per-dialect inputs + sample baseline
├── examples/    generated output (employee, vibehub 1.34 regenerated)
└── tests/       test_agent.py (python -m unittest)
```

## CI/CD integration (Jenkins / GitLab)

```groovy
stage('DB change review') {
  steps {
    sh 'python3 liquibase-agent/agent.py analyze -i db/release_${RELEASE} --profile sol_services --release ${RELEASE} ' +
       '--baseline db/baseline --changelog db/released -o build/lb --fail-on HIGH'
    archiveArtifacts 'build/lb/**'
  }
}
stage('Liquibase dry run') {
  steps { sh 'liquibase --changelog-file=build/lb/changelog/db.changelog-SOL_SERVICES-${RELEASE}.xml update-sql > build/lb/preview.sql' }
}
```

The exit code is `2` when the `--fail-on` threshold is reached, so the pipeline stops before deployment.
`report.json` holds the checklist and findings for dashboards.

## Deployment runbook (generated per release in report.md, summarised)

1. Run `checks/precheck.sql` and record the results, including invalid objects and `DATABASECHANGELOGLOCK`.
2. Run `liquibase validate`, then `liquibase update-sql`, and review the SQL.
3. Run `liquibase tag --tag=<PROJECT>_<REL>_PRE`, then `liquibase update` (or run the deploy scripts in order).
4. Run `checks/postcheck.sql`. Recompile the schema and refresh statistics on changed tables. Confirm the tracker
   rows show `COMPLETED`.
5. To roll back, use `liquibase rollback --tag=...` (inline rollbacks) or run the `_Rollback` script.

## Limits

- The parsing is rule-based, not a full SQL grammar. Anything it can't classify is emitted as `<sql>` with a
  manual-rollback marker and a MEDIUM `UNRECOGNISED` finding, so it is never dropped silently.
- XSD validation is structural, not schema-based, because that would need network access or a bundled XSD.
  Liquibase does the final validation offline with `liquibase validate`, using the XSD bundled in its jar.
- Without `--baseline`, rollbacks for `CREATE OR REPLACE` objects are deliberately left manual rather than turned
  into `DROP` statements that could delete a live object. Triggers on tables created in the same release are the
  exception. You can set `assume_new_when_unknown: true` to change this.
