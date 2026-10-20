"""Explains an SPL pipeline in plain English, one sentence per stage (rule based)."""

from __future__ import annotations

import re
from typing import Callable

from core.spl import command_of, split_pipes

_BY_SPLIT = re.compile(r"\bby\b", re.IGNORECASE)


def _split_by(args: str) -> tuple[str, str]:
    parts = _BY_SPLIT.split(args, maxsplit=1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


def _aggs(text: str) -> str:
    funcs = re.findall(r"([a-z0-9_]+)\(([^)]*)\)(?:\s+as\s+(\w+))?", text, re.IGNORECASE)
    if not funcs:
        names = re.findall(r"\b(count|dc|sum|avg|max|min)\b", text, re.IGNORECASE)
        return ", ".join(names) or text
    out = []
    for fn, arg, alias in funcs:
        label = f"{fn}({arg})" if arg else fn
        out.append(f"{label} as {alias}" if alias else label)
    if re.match(r"^\s*count\b(?!\()", text, re.IGNORECASE):
        out.insert(0, "count")
    return ", ".join(out)


def _stats(name: str) -> Callable[[str], str]:
    def explain(args: str) -> str:
        head, by = _split_by(args)
        text = f"`{name}` computes {_aggs(head)}"
        return text + (f" grouped by {by}." if by else " across all matching events.")
    return explain


def _timechart(args: str) -> str:
    span = re.search(r"span=(\S+)", args)
    head, by = _split_by(re.sub(r"\b(span|limit|useother)=\S+", "", args))
    text = f"`timechart` buckets results over time ({'span ' + span.group(1) if span else 'auto span'}) computing {_aggs(head)}"
    return text + (f", one series per {by}." if by else ".")


def _tstats(args: str) -> str:
    dm = re.search(r"datamodel=(\S+)", args)
    head, by = _split_by(args)
    src = f"the accelerated '{dm.group(1)}' data model" if dm else "indexed fields (tsidx)"
    return f"`tstats` reads {src} - much faster than raw events - computing {_aggs(head.split('FROM')[0].split('WHERE')[0])}" + (f" by {by}." if by else ".")


def _mstats(args: str) -> str:
    head, by = _split_by(args)
    return f"`mstats` queries the metrics store computing {_aggs(head.split('WHERE')[0])}" + (f" by {by}." if by else ".")


_COMMANDS: dict[str, Callable[[str], str]] = {
    "stats": _stats("stats"),
    "eventstats": lambda a: f"`eventstats` adds aggregate values ({_aggs(_split_by(a)[0])}) to each event without collapsing them.",
    "streamstats": lambda a: f"`streamstats` computes running aggregates ({_aggs(_split_by(a)[0])}).",
    "chart": _stats("chart"),
    "timechart": _timechart,
    "tstats": _tstats,
    "mstats": _mstats,
    "mcatalog": lambda a: "`mcatalog` lists metric names/dimensions in the metrics catalog.",
    "where": lambda a: f"`where` keeps only rows where {a}.",
    "search": lambda a: f"`search` filters results to {a}.",
    "sort": lambda a: f"`sort` orders results by {a.replace('- ', 'descending ').replace('-', 'descending ')}.",
    "head": lambda a: f"`head` keeps the first {a or 10} rows.",
    "tail": lambda a: f"`tail` keeps the last {a or 10} rows.",
    "table": lambda a: f"`table` shows the columns {a}.",
    "fields": lambda a: f"`fields` restricts output to {a}.",
    "eval": lambda a: f"`eval` derives fields: {a}.",
    "rex": lambda a: "`rex` extracts new fields with a regular expression.",
    "bin": lambda a: f"`bin` buckets _time ({a}).",
    "bucket": lambda a: f"`bucket` buckets _time ({a}).",
    "dedup": lambda a: f"`dedup` removes duplicate {a}.",
    "top": lambda a: f"`top` returns the most common values of {a}.",
    "rare": lambda a: f"`rare` returns the least common values of {a}.",
    "rename": lambda a: f"`rename` renames {a}.",
    "convert": lambda a: f"`convert` formats {a} as human-readable time.",
    "fillnull": lambda a: "`fillnull` replaces null values.",
    "lookup": lambda a: f"`lookup` enriches results from lookup {a.split()[0] if a else ''}.",
    "inputlookup": lambda a: f"`inputlookup` reads lookup {a}.",
    "iplocation": lambda a: f"`iplocation` adds geo-location for {a}.",
    "join": lambda a: "`join` combines with a subsearch (expensive).",
    "transaction": lambda a: "`transaction` groups related events (expensive).",
}


def _explain_base(stage: str) -> str:
    indexes = re.findall(r"index\s*=\s*(\"[^\"]+\"|\S+)", stage)
    sourcetypes = re.findall(r"sourcetype\s*=\s*(\"[^\"]+\"|\S+)", stage)
    rest = re.sub(r"(index|sourcetype|earliest|latest)\s*=\s*(\"[^\"]+\"|\S+)", "", stage)
    prev = None
    while prev != rest:
        prev = rest
        rest = re.sub(r"\(\s*(?:OR\s*)*\)", " ", rest)
    rest = re.sub(r"^\s*(?:OR\s+)+", "", rest).strip()
    rest = re.sub(r"\s+", " ", rest)
    text = f"Retrieves events from index {', '.join(i.strip(chr(34)).rstrip(')') for i in indexes) or 'default'}"
    if sourcetypes:
        text += f" (sourcetype {', '.join(s.strip(chr(34)).rstrip(')') for s in sourcetypes)})"
    times = re.findall(r"(earliest|latest)\s*=\s*(\S+)", stage)
    if times:
        text += " for " + " to ".join(v for _, v in times)
    return text + (f" matching: {rest}." if rest else ".")


def explain(spl: str) -> list[str]:
    stages = split_pipes(spl)
    leading_pipe = spl.lstrip().startswith("|")
    if leading_pipe:
        stages = stages[1:]
    steps: list[str] = []
    for i, stage in enumerate(stages):
        s = " ".join(stage.split())
        if not s:
            continue
        if i == 0 and not leading_pipe:
            steps.append(_explain_base(s))
            continue
        cmd = command_of(s)
        args = s[len(cmd):].strip()
        fn = _COMMANDS.get(cmd)
        steps.append(fn(args) if fn else f"`{cmd}` {args}".strip() + ".")
    return steps
