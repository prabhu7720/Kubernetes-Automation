# Offline Splunk Automation Agent

Turns plain-English requests into production-ready Splunk content: **SPL searches, scheduled
reports, alerts, Dashboard Studio dashboards, ES correlation searches and operational runbooks.**

It runs **fully offline**. There are no LLM or cloud AI calls. All "reasoning" is deterministic and local:
regex/lexicon intent parsing, weighted keyword matching against rule packs, and catalog-driven
datasource/field resolution over metadata pulled from *your* Splunk through the REST API / Python SDK.

```
"Create alert when HTTP 500 errors exceed 100 per hour"
        │
        ▼  IntentParser   → artifact=alert, threshold > 100, window 1h, status=[500]
        ▼  UseCaseMatcher → http_status_errors (application rule pack)
        ▼  Resolver       → index=web sourcetype=access_combined, status_code→status (from catalog)
        ▼  Generators     → SPL + report + alert (+ runbook) + dashboard components
        ▼  Publisher      → saved/searches (dry-run by default)
```

## Project layout

```
splunk-agent/
├── agent.py                    # SplunkAgent orchestrator + CLI
├── core/                       # framework (no Splunk dependency)
│   ├── config.py               # layered YAML + env config, validation
│   ├── logging_setup.py        # console/rotating file, JSON logs, secret redaction
│   ├── models.py               # UseCase, AlertSpec, DashboardBlueprint, enums
│   ├── nlp.py / intent.py      # normaliser + rule-based intent parser
│   ├── matcher.py              # use-case / blueprint scoring
│   ├── template.py             # strict {{placeholder}} renderer
│   ├── spl.py                  # quoting, pipe splitter, offline SPL linter
│   ├── spl_explainer.py        # plain-English explanation per pipeline stage
│   ├── visualization.py        # viz recommendation from result shape
│   ├── schedule.py             # window → cron / dispatch window
│   ├── plugins.py              # auto-discovery of plugin modules/dirs
│   ├── splunk_client.py        # splunk-sdk wrapper: token auth, TLS, retries
│   └── response.py             # AgentResponse → Markdown / JSON / files
├── discovery/                  # collector plugins → catalog
│   ├── indexes.py  sourcetypes.py  hosts.py  fields.py  datamodels.py  knowledge_objects.py
│   └── engine.py               # ordered, fault-isolated execution
├── catalog/
│   ├── metadata_store.py       # SQLite catalog (+ JSON import/export for air-gap)
│   ├── resolver.py             # logical datasource/field → real index/sourcetype/field
│   ├── enrichment.py           # inject lookups only if they exist
│   └── sample_catalog.json     # demo environment
├── generators/                 # artifact plugins
│   ├── search_generator.py  report_generator.py  alert_generator.py
│   ├── dashboard_generator.py  correlation_generator.py  runbook_generator.py
├── rules/                      # rule-pack plugins (*.py or *.yaml)
│   ├── security_rules.py  kubernetes_rules.py  infra_rules.py  app_rules.py
│   ├── aws_rules.py  azure_rules.py  compliance_rules.py  nginx_rules.yaml
├── publishers/splunk_publisher.py   # idempotent REST upserts
├── templates/{reports,alerts,dashboards,runbooks}/   # editable text templates
├── config/settings.yaml  datasources.yaml  field_aliases.yaml
├── scripts/build_sample_catalog.py
└── tests/                      # 71 unit/integration tests (unittest, pytest-compatible)
```

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # air-gapped: pip install --no-index --find-links wheels/ -r requirements.txt

# Try it with no Splunk at all (synthetic catalog)
python agent.py catalog import catalog/sample_catalog.json
python agent.py ask "Show failed login activity"
python agent.py ask "Generate dashboard for Kubernetes health" --out out/k8s

# Against your Splunk
export SPLUNK_HOST=splunk-mgmt.internal SPLUNK_TOKEN=<token> SPLUNK_CA_BUNDLE=/etc/ssl/certs/ca.pem
python agent.py discover                         # or --collectors indexes,sourcetypes,fields
python agent.py ask "Create alert when HTTP 500 errors exceed 100 per hour" --dry-run
python agent.py ask "Create alert when HTTP 500 errors exceed 100 per hour" --deploy   # needs publish.enabled: true
```

Other commands: `capabilities`, `interactive`, `catalog summary|datasets|fields <idx> <st>|export|import`,
`validate "<spl>" [--remote]`, `ask ... --format json`.

Exit codes: `0` ok, `1` generic/invalid SPL, `2` config or unmatched request, `3` Splunk connectivity/auth, `4` partial discovery.

## Output per request

Every `ask` returns the six required sections, plus the primary artifact:

1. **Generated SPL**: ad-hoc (inline time), saved-search form, and an accelerated `tstats` variant when the CIM data model is accelerated
2. **Explanation**: use case, datasource resolution + field mapping, and one sentence per pipeline stage
3. **Visualization recommendation**: rule-pack intent vs. result-shape analysis, with alternatives
4. **Dashboard component suggestions**: KPI, main panel, trend, and related use cases
5. **Alert recommendations**: threshold, severity, cron, dispatch window, throttling, actions, `savedsearches.conf`
6. **Report definition**: title, business description, schedule, time range, viz, `savedsearches.conf`

Plus, depending on the request: Dashboard Studio JSON and the deployable `<dashboard version="2">` XML, an ES
correlation search with notable and risk actions and MITRE annotations, or a Markdown runbook.
`--out DIR` writes everything to files (`search.spl`, `*.conf`, `dashboard_*.json/xml`, `runbook_*.md`, `response.json`).

## How the "intelligence" works (all local)

| Stage | Technique |
|---|---|
| Intent | Phrase canonicalisation (`crash loop back off` → `crashloop`), synonym table, light stemmer, regex extractors for time range, threshold/comparator, window, status codes, top-N, group-by, `field=value` / "for user bob" filters, severity, schedule, title |
| Matching | Σ `len(keyword)^1.5 + 0.5` for fully matched keywords (×1.25 when contiguous) + name overlap + domain bonus; *exclusive* packs (AWS, Azure, PCI, NGINX) need an explicit mention |
| Resolution | Each (index, sourcetype) in the catalog is scored on profile patterns + coverage of the fields the template needs. Wildcard sourcetype families collapse (`kube:container:*`). Canonical fields map through `field_aliases.yaml`. When datasets disagree it adds `eval user=coalesce(user,'actor.alternateId')` |
| Enrichment | `{{enrich.threat_intel}}` becomes a `lookup` only if a matching lookup exists in the catalog |
| Reuse | Warns when an existing report or alert has a similar name or the same SPL |
| Safety | Offline linter (balance, empty stages, unresolved tokens, `delete`/`script`/`outputlookup`, `join`/`transaction`, `index=*`); optional server-side `search/parser` validation |

## Extending (plugin architecture)

**Drop a file in, get a capability.** No registration code is needed.

*Python rule pack* (`rules/gcp_rules.py`):

```python
from core.models import AlertSpec, Severity
from rules.base import RulePack

class GcpRules(RulePack):
    domain = "gcp"
    exclusive = True                       # only when "gcp" is mentioned
    domain_keywords = ("gcp", "google cloud")
    datasources = {"gcp_audit": {"index_patterns": ["gcp*"], "sourcetype_patterns": ["google:gcp:pubsub:audit*"],
                                 "default_index": "gcp"}}

    def use_cases(self):
        return [self.uc("gcp_iam_changes", "GCP IAM Changes", description="SetIamPolicy calls",
                        datasource="gcp_audit", keywords=("gcp iam change", "setiampolicy"),
                        filter='protoPayload.methodName="SetIamPolicy"',
                        pipeline="| stats count BY protoPayload.authenticationInfo.principalEmail",
                        alert=AlertSpec(threshold=0, severity=Severity.HIGH, window="15m"))]
```

*Declarative YAML pack*: see `rules/nginx_rules.yaml`.
*New artifact type*: subclass `generators.base.ArtifactGenerator` (set `name`, implement `applies` and `generate`).
*New metadata*: subclass `discovery.base.Collector` (set `name` and `priority`, implement `run`).
External directories go in `plugins.rule_dirs | generator_dirs | collector_dirs`. Set `plugins.strict: true` in CI so
broken plugins fail the build. Otherwise they are logged and skipped.

Template placeholders: `{{base}} {{index}} {{time}} {{f.<field>}} {{q.<field>}} {{m.<metric>}} {{p.<param>}}
{{groupby}} {{span}} {{limit}} {{threshold}} {{comparator}} {{extra_filter}} {{enrich.<name>}}`.
Unknown placeholders are errors. Nothing is silently left in the SPL.

Tune without code in `config/settings.yaml`:

```yaml
use_case_overrides:
  brute_force: {alert: {threshold: 30, severity: critical}}
  pci_failed_access: {params: {cde_scope: 'dest_category="pci"'}}
```

Pin a datasource when auto-selection is not what you want (`config/datasources.yaml`):

```yaml
datasources:
  web: {pinned_indexes: [edge_web], pinned_sourcetypes: ["nginx:plus:kv"]}
```

## Splunk permissions (service account role)

* Discovery: `search`, REST read on `data/indexes`, `saved/searches`, `data/ui/views`, `datamodel/model`,
  `storage/collections/config`, `data/transforms/lookups`, `data/lookup-table-files`, and `srchIndexesAllowed` covering the indexes to profile
* Publishing: `schedule_search`, write access on the target app (`publish.app`), plus ES `edit_correlationsearches` for correlation searches

## Deployment notes

* **Air-gapped:** run `discover` on a host that can reach the management port (8089), then `catalog export` → copy → `catalog import` anywhere. Generation never needs connectivity.
* **GitOps:** use `--out` and commit the `*.conf` / dashboard XML into a Splunk app repo, then deploy with your CI (`splunk-appinspect`, deployer/SHC bundle push) instead of `--deploy`.
* **Container:** see `Dockerfile` (offline wheel install, non-root user).
* Publishing is **dry-run by default**, and `--deploy` additionally requires `publish.enabled: true`. Existing objects are skipped unless `publish.overwrite: true`.

## Tests

```bash
python -m pytest -q            # or: python -m unittest discover -s tests -t .
```

The tests cover intent parsing, matching for all sample requests, resolver selection, normalisation and metric mapping, SPL lint/explain/viz,
every use case rendering lint-clean on an empty catalog, alerts, reports, correlation searches, Dashboard Studio structural
integrity (data source refs, layout, inputs, XML/CDATA), discovery with a fake client (including fault isolation), catalog round-trip,
Python, YAML and generator plugins (including broken-plugin handling), the publisher create/update/skip paths, and config validation.

## Known limitations

* Metric units (e.g. `container.cpu.utilization`) differ between OTel collector versions, so check the thresholds in `kubernetes_rules.py`.
* Windows use cases assume CIM-style field extractions from the Splunk Add-on for Windows (`user`, `dest`, `EventCode`).
* Dashboard Studio visualization `options` are kept minimal for cross-version compatibility. Style them in the Studio editor after import.
