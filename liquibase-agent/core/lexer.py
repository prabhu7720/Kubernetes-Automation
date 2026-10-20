"""Small, dependency-free SQL lexer used by the parsers.

Produces tokens with source offsets so callers can slice the original text
(keeps original formatting of types, defaults and expressions intact).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

WORD, QIDENT, STRING, NUMBER, SYMBOL = "WORD", "QIDENT", "STRING", "NUMBER", "SYMBOL"

_word_re = re.compile(r"[A-Za-z_\$#@][A-Za-z0-9_\$#@]*")
_num_re = re.compile(r"\d+(\.\d+)?([eE][+-]?\d+)?")


@dataclass
class Token:
    type: str
    value: str
    start: int
    end: int

    @property
    def upper(self) -> str:
        return self.value.upper() if self.type == WORD else self.value

    def is_word(self, *words: str) -> bool:
        return self.type == WORD and self.value.upper() in words

    def is_sym(self, *syms: str) -> bool:
        return self.type == SYMBOL and self.value in syms


def strip_comments(sql: str, mysql_hash: bool = False) -> str:
    """Replace comments by spaces (keeps offsets/line numbers stable)."""
    out = list(sql)
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'" and j + 1 < n and sql[j + 1] == "'":
                    j += 2
                    continue
                if sql[j] == "'":
                    break
                j += 1
            i = j + 1
            continue
        if c == '"':
            j = sql.find('"', i + 1)
            i = n if j < 0 else j + 1
            continue
        if c == "$":
            m = re.match(r"\$([A-Za-z_]*)\$", sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                i = n if j < 0 else j + len(tag)
                continue
        if sql.startswith("--", i) or (mysql_hash and c == "#"):
            j = sql.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


def tokenize(sql: str) -> List[Token]:
    """Tokenize SQL that has already had comments stripped."""
    toks: List[Token] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c.isspace():
            i += 1
            continue
        # Oracle alternative quoting q'[...]'
        if c in "qQnN" and i + 2 < n and sql[i + 1] == "'" and c in "qQ":
            opener = sql[i + 2]
            closer = {"[": "]", "(": ")", "{": "}", "<": ">"}.get(opener, opener)
            j = sql.find(closer + "'", i + 3)
            j = n - 2 if j < 0 else j
            toks.append(Token(STRING, sql[i:j + 2], i, j + 2))
            i = j + 2
            continue
        if c in "nNeE" and i + 1 < n and sql[i + 1] == "'":
            i += 1  # N'...' / E'...' prefix, fall through to string handling
            c = "'"
            start = i - 1
        else:
            start = i
        if c == "'":
            j = i + 1
            while j < n:
                if sql[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if sql[j] == "'" and j + 1 < n and sql[j + 1] == "'":
                    j += 2
                    continue
                if sql[j] == "'":
                    break
                j += 1
            toks.append(Token(STRING, sql[start:j + 1], start, j + 1))
            i = j + 1
            continue
        if c in '"`':
            j = sql.find(c, i + 1)
            j = n - 1 if j < 0 else j
            toks.append(Token(QIDENT, sql[i + 1:j], i, j + 1))
            i = j + 1
            continue
        if c == "[":
            j = sql.find("]", i + 1)
            if j > 0 and re.fullmatch(r"[^\[\]\n]+", sql[i + 1:j] or "x"):
                toks.append(Token(QIDENT, sql[i + 1:j], i, j + 1))
                i = j + 1
                continue
        if c == "$":
            m = re.match(r"\$([A-Za-z_]*)\$", sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                j = n if j < 0 else j + len(tag)
                toks.append(Token(STRING, sql[i:j], i, j))
                i = j
                continue
        m = _num_re.match(sql, i)
        if m and (c.isdigit()):
            toks.append(Token(NUMBER, m.group(0), i, m.end()))
            i = m.end()
            continue
        m = _word_re.match(sql, i)
        if m:
            toks.append(Token(WORD, m.group(0), i, m.end()))
            i = m.end()
            continue
        two = sql[i:i + 2]
        if two in ("<=", ">=", "<>", "!=", "||", ":=", "::", "=>", ".."):
            toks.append(Token(SYMBOL, two, i, i + 2))
            i += 2
            continue
        toks.append(Token(SYMBOL, c, i, i + 1))
        i += 1
    return toks


def match_paren(toks: List[Token], idx: int) -> int:
    """Given index of '(' token, return index of matching ')'."""
    depth = 0
    for j in range(idx, len(toks)):
        if toks[j].is_sym("("):
            depth += 1
        elif toks[j].is_sym(")"):
            depth -= 1
            if depth == 0:
                return j
    return len(toks) - 1


def split_top(toks: List[Token], sep: str = ",") -> List[List[Token]]:
    """Split a token list on a separator symbol at paren depth 0."""
    parts, cur, depth = [], [], 0
    for t in toks:
        if t.is_sym("("):
            depth += 1
        elif t.is_sym(")"):
            depth -= 1
        if depth == 0 and t.is_sym(sep):
            parts.append(cur)
            cur = []
            continue
        cur.append(t)
    if cur:
        parts.append(cur)
    return parts


def text_of(sql: str, toks: List[Token]) -> str:
    if not toks:
        return ""
    return sql[toks[0].start:toks[-1].end].strip()


def ident(t: Token) -> str:
    return t.value


def read_qualified(toks: List[Token], i: int) -> Tuple[Optional[str], Optional[str], int, bool]:
    """Read [db.][schema.]name starting at i. Returns (schema, name, next_index, quoted)."""
    parts, quoted = [], False
    while i < len(toks) and toks[i].type in (WORD, QIDENT):
        parts.append(toks[i].value)
        quoted = quoted or toks[i].type == QIDENT
        if i + 1 < len(toks) and toks[i + 1].is_sym("."):
            i += 2
            continue
        i += 1
        break
    if not parts:
        return None, None, i, False
    # strip trailing @dblink (oracle) handled by caller
    if len(parts) == 1:
        return None, parts[0], i, quoted
    return parts[-2], parts[-1], i, quoted


def words_upper(toks: List[Token]) -> List[str]:
    return [t.value.upper() if t.type == WORD else t.value for t in toks]
