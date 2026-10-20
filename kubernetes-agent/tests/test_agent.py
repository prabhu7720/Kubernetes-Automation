"""Test-suite: unit tests for rules/engine + end-to-end runs against fake_kubectl.py.

Run:  python -m pytest -q tests/
"""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import agent  # noqa: E402
from config.settings import Settings  # noqa: E402
from core.context import PodContext  # noqa: E402
from core.models import Severity  # noqa: E402
from core.quantity import parse_cpu, parse_memory  # noqa: E402
from core.redact import Redactor  # noqa: E402
from core.rule_engine import RuleEngine, RuleLoader  # noqa: E402
from fixtures import scenario as S  # noqa: E402
from rules.scheduling import FailedSchedulingRule  # noqa: E402

FAKE = str(ROOT / "tests" / "fake_kubectl.py")


def ids(findings):
    return {f.rule_id for f in findings}


def pod_ctx(name, **kw):
    pod = next(p for p in S.PODS + S.KUBE_SYSTEM if p["metadata"]["name"] == name)
    events = [e for e in S.EVENTS if e["involvedObject"]["name"] == name]
    return PodContext(settings=Settings(), pod=pod, events=events, **kw)


@pytest.fixture(scope="module")
def engine():
    return RuleEngine(Settings())


# ---------------------------------------------------------------- unit
def test_quantities():
    assert parse_memory("512Mi") == 512 * 2 ** 20
    assert parse_memory("1G") == 10 ** 9
    assert parse_cpu("250m") == 250
    assert parse_cpu("2") == 2000


def test_redaction():
    r = Redactor()
    out = r.redact("password=hunter2 token: abc Authorization: Bearer eyJabc.def postgres://u:p@db:5432")
    assert "hunter2" not in out and "u:p@" not in out and "Bearer eyJ" not in out


def test_all_rules_discovered(engine):
    assert len(engine.rules) >= 30
    assert not engine.load_errors


def test_disabled_rule():
    eng = RuleEngine(Settings(disabled_rules=["K8S-OOM-001"]))
    assert "K8S-OOM-001" not in {r.id for r in eng.rules}


def test_external_rule_dir(tmp_path):
    (tmp_path / "my_rule.py").write_text(
        "from rules.base import Rule\nfrom core.models import Scope, Severity\n"
        "class AlwaysRule(Rule):\n    id='CUSTOM-001'\n    name='always'\n    scopes=(Scope.POD,)\n"
        "    def evaluate(self, ctx):\n        return [self.finding(ctx, title='t', root_cause='r', severity=Severity.LOW)]\n")
    eng = RuleEngine(Settings(extra_rule_dirs=[str(tmp_path)]))
    assert "CUSTOM-001" in {r.id for r in eng.rules}


def test_oom(engine):
    ctx = pod_ctx(f"{S.RS}-abcde", logs_previous={"app": S.LOGS[f"payments/{S.RS}-abcde/app"]["previous"]})
    findings = engine.evaluate(ctx)
    oom = next(f for f in findings if f.rule_id == "K8S-OOM-001")
    assert oom.confidence == 95 and oom.severity == Severity.HIGH
    assert any("Exit Code: 137" in e for e in oom.evidence)
    crash = next(f for f in findings if f.rule_id == "K8S-CRASH-001")
    assert crash.is_symptom


def test_crashloop_with_dependency_failures(engine):
    ctx = pod_ctx(f"{S.RS}-fghij", logs_previous={"app": S.LOGS[f"payments/{S.RS}-fghij/app"]["previous"]})
    got = ids(engine.evaluate(ctx))
    assert {"K8S-CRASH-001", "K8S-NET-001", "K8S-NET-002"} <= got


def test_config_error_and_missing_secret(engine):
    ctx = pod_ctx("orders-worker-6d9f7c-x1y2z", secret_names={"other"})
    got = ids(engine.evaluate(ctx))
    assert {"K8S-CFG-001", "K8S-CFG-003"} <= got


def test_image_pull(engine):
    f = [x for x in engine.evaluate(pod_ctx("frontend-5c8d-pq7rs")) if x.rule_id == "K8S-IMG-001"][0]
    assert "does not exist" in f.root_cause


def test_probes(engine):
    got = ids(engine.evaluate(pod_ctx("api-gw-7f6b-t8u9v")))
    assert {"K8S-PROBE-001", "K8S-PROBE-002"} <= got


def test_scheduling_parser():
    causes, _ = FailedSchedulingRule.parse(
        "0/3 nodes are available: 1 Insufficient memory, 2 node(s) had untolerated taint {dedicated: gpu}.")
    assert len(causes) == 2 and "memory" in causes[0] and "dedicated: gpu" in causes[1]


def test_node_not_ready(engine):
    ctx = pod_ctx("ledger-6c5d-zz1", node=S.NODES[2])
    assert "K8S-NODE-001" in ids(engine.evaluate(ctx))


def test_egress_guard_blocks_sockets():
    from core import egress_guard
    egress_guard.install()
    with pytest.raises(egress_guard.ExternalEgressBlocked):
        socket.create_connection(("example.com", 443), timeout=1)


# ---------------------------------------------------------------- end-to-end
def run(capsys, *argv):
    code = agent.run(list(argv) + ["--kubectl", FAKE, "--no-color"])
    return code, capsys.readouterr().out


def test_e2e_pod(capsys):
    code, out = run(capsys, "analyze", "pod", f"{S.RS}-abcde", "-n", "payments")
    assert code == 1
    assert "KUBERNETES ROOT CAUSE ANALYSIS REPORT" in out and "OOMKilled" in out and "95%" in out


def test_e2e_namespace_json(capsys):
    code, out = run(capsys, "analyze", "namespace", "payments", "-o", "json")
    data = json.loads(out)
    assert data["summary"]["severity"] == "High"
    flat = json.dumps(data)
    for rule in ("K8S-OOM-001", "K8S-IMG-001", "K8S-SCHED-001", "K8S-CFG-003", "K8S-PROBE-002", "K8S-DEPLOY-001"):
        assert rule in flat
    assert "SuperSecret123" not in flat


def test_e2e_cluster(capsys):
    code, out = run(capsys, "analyze", "cluster")
    assert "Node NotReady" in out and "kube-dns" in out


def test_e2e_not_found(capsys):
    code, _ = run(capsys, "analyze", "pod", "missing", "-n", "payments")
    assert code == 2


def test_e2e_healthy_threshold(capsys):
    code, _ = run(capsys, "analyze", "pod", f"{S.RS}-klmno", "-n", "payments", "--fail-on", "high")
    assert code == 0
