"""Deterministic text normalisation used by the intent parser and matcher.

No ML models: lower-casing, phrase canonicalisation, a light suffix stemmer and a
domain synonym table.  Rule keywords pass through the *same* pipeline, so matching
is consistent by construction.
"""

from __future__ import annotations

import re

_PHRASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p), r) for p, r in [
        (r"\bout[\s-]+of[\s-]+memory\b", " oomkill "),
        (r"\boom[\s-]?kill(?:ed|ing|s)?\b", " oomkill "),
        (r"\bcrash[\s-]?loop(?:[\s-]?back[\s-]?off)?s?\b", " crashloop "),
        (r"\bresponse[\s-]+times?\b", " latency "),
        (r"\bbrute[\s-]?forc(?:e|ing|ed)\b", " bruteforce "),
        (r"\bprivilege[sd]?[\s-]+escalations?\b|\bescalation[\s-]+of[\s-]+privileges?\b", " privesc "),
        (r"\b(?:log|sign)[\s-]?(?:in|on)s?\b", " login "),
        (r"\block(?:ed)?[\s-]?outs?\b", " lockout "),
        (r"\bpassword[\s-]+spray(?:ing|s)?\b", " passwordspray "),
        (r"\bport[\s-]?scan(?:s|ning|ner)?\b", " portscan "),
        (r"\bstatus[\s-]+codes?\b", " statuscode "),
        (r"\b(?:not|stopped|stop)[\s-]+(?:reporting|sending|forwarding)\b|\bno[\s-]+data\b", " notreporting "),
        (r"\bimage[\s-]?pull(?:[\s-]?back[\s-]?off)?s?\b|\berrimagepull\b", " imagepull "),
        (r"\bcardholder[\s-]+data(?:[\s-]+environment)?\b", " cde "),
        (r"\bhttp[\s-]?5xx\b", " 5xx "),
        (r"\bfailed[\s-]?scheduling\b", " failedscheduling "),
        (r"\bmulti[\s-]?factor\b", " mfa "),
    ]
]

SYNONYMS: dict[str, str] = {
    "k8s": "kubernetes", "kube": "kubernetes", "kubernetes": "kubernetes", "openshift": "kubernetes",
    "failure": "fail", "failed": "fail", "failing": "fail", "fails": "fail", "unsuccessful": "fail",
    "invalid": "fail", "errors": "error", "err": "error", "erroring": "error",
    "app": "application", "apps": "application", "applications": "application",
    "authentication": "auth", "authenticate": "auth", "authenticated": "auth", "authn": "auth",
    "logon": "login", "signin": "login",
    "denied": "deny", "denies": "deny", "blocked": "deny", "block": "deny", "dropped": "deny",
    "drop": "deny", "rejected": "deny",
    "slow": "latency", "slowness": "latency", "sluggish": "latency",
    "crashed": "crash", "crashing": "crash", "crashes": "crash",
    "spikes": "spike", "surge": "spike", "burst": "spike", "bursts": "spike",
    "oom": "oomkill", "oomkilled": "oomkill", "oomkilling": "oomkill", "crashloopbackoff": "crashloop",
    "server": "host", "servers": "host", "machine": "host", "hosts": "host", "vm": "host",
    "utilisation": "utilization", "usage": "utilization", "util": "utilization",
    "mem": "memory", "ram": "memory", "processor": "cpu",
    "administrator": "admin", "administrators": "admin", "admins": "admin",
    "ips": "ip", "virus": "malware", "viruses": "malware", "trojan": "malware", "ransomware": "malware",
    "throughput": "traffic", "deploy": "deployment", "deployments": "deployment",
    "rollout": "deployment", "rollouts": "deployment",
    "evicted": "eviction", "evict": "eviction", "evictions": "eviction",
    "pods": "pod", "containers": "container", "nodes": "node", "namespaces": "namespace",
    "entra": "azure", "aad": "azure",
}

STOPWORDS: frozenset[str] = frozenset("""
a an the show me all any for of in on at from to with by and or when what which list give create generate
build make display find get please i we want need my our is are be there that this these those it its into
about over per every each new can you could would should help let us view see look dashboard report alert
search saved query spl correlation runbook playbook notify notification trigger if than then up set setup
activity event log data splunk based using use whenever exceed above below more less greater threshold
named called titled last past hour minute day week month time across where how many much
""".split())

_PROTECTED_SUFFIX = ("ss", "us", "is", "os")


def stem(word: str) -> str:
    """Light, predictable suffix stripping + synonym canonicalisation."""
    if word in SYNONYMS:
        return SYNONYMS[word]
    w = word
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith(("ches", "shes", "sses", "xes", "zes")):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith(_PROTECTED_SUFFIX):
        w = w[:-1]
    if w in SYNONYMS:
        return SYNONYMS[w]
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed") and not w.endswith("eed"):
        w = w[:-2]
    return SYNONYMS.get(w, w)


def canonicalize_phrases(text: str) -> str:
    t = text.lower()
    for pattern, repl in _PHRASES:
        t = pattern.sub(repl, t)
    return t


def normalize(text: str, *, keep_stopwords: bool = False) -> list[str]:
    """Return canonical tokens for *text* (order preserved)."""
    out: list[str] = []
    for raw in re.findall(r"[a-z0-9]+", canonicalize_phrases(text)):
        if not keep_stopwords and raw in STOPWORDS:
            continue
        token = stem(raw)
        if not keep_stopwords and token in STOPWORDS:
            continue
        out.append(token)
    return out
