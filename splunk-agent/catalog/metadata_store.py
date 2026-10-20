"""SQLite-backed metadata catalog.

Discovery replaces each table atomically (per collector) so stale objects never
linger.  The catalog can be exported/imported as JSON, which enables a fully
air-gapped workflow: run discovery on a jump host, copy the JSON, generate content
anywhere.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Iterable, Iterator

from catalog.models import (DataModelInfo, DatasetInfo, EntityInfo, FieldInfo, IndexInfo, KnowledgeObject,
                            to_dict)
from core.exceptions import CatalogError

log = logging.getLogger(__name__)
SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS indexes (name TEXT PRIMARY KEY, datatype TEXT, event_count INTEGER, size_mb REAL,
    earliest TEXT, latest TEXT, disabled INTEGER);
CREATE TABLE IF NOT EXISTS datasets (idx TEXT, sourcetype TEXT, event_count INTEGER, last_seen REAL,
    PRIMARY KEY (idx, sourcetype));
CREATE TABLE IF NOT EXISTS fields (idx TEXT, sourcetype TEXT, name TEXT, coverage REAL, distinct_count INTEGER,
    sample_values TEXT, is_numeric INTEGER, kind TEXT, PRIMARY KEY (idx, sourcetype, name));
CREATE INDEX IF NOT EXISTS ix_fields_name ON fields (name);
CREATE TABLE IF NOT EXISTS datamodels (name TEXT PRIMARY KEY, app TEXT, accelerated INTEGER, objects TEXT);
CREATE TABLE IF NOT EXISTS knowledge_objects (kind TEXT, name TEXT, app TEXT, owner TEXT, attributes TEXT,
    PRIMARY KEY (kind, name, app));
CREATE TABLE IF NOT EXISTS entities (kind TEXT, name TEXT, event_count INTEGER, last_seen REAL,
    PRIMARY KEY (kind, name));
"""


class MetadataStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        try:
            if self.path != ":memory:":
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            self._conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
                               (str(SCHEMA_VERSION),))
            self._conn.commit()
        except sqlite3.Error as exc:
            raise CatalogError(f"Cannot open catalog {self.path}: {exc}") from exc

    # ------------------------------------------------------------- plumbing
    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise CatalogError(f"Catalog write failed: {exc}") from exc

    def _rows(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            try:
                return self._conn.execute(sql, tuple(params)).fetchall()
            except sqlite3.Error as exc:
                raise CatalogError(f"Catalog read failed: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "MetadataStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ----------------------------------------------------------------- meta
    def set_meta(self, key: str, value: Any) -> None:
        with self._tx() as c:
            c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, json.dumps(value)))

    def get_meta(self, key: str, default: Any = None) -> Any:
        rows = self._rows("SELECT value FROM meta WHERE key = ?", (key,))
        if not rows:
            return default
        try:
            return json.loads(rows[0]["value"])
        except (TypeError, ValueError):
            return rows[0]["value"]

    # -------------------------------------------------------------- writers
    def replace_indexes(self, items: Iterable[IndexInfo]) -> int:
        items = list(items)
        with self._tx() as c:
            c.execute("DELETE FROM indexes")
            c.executemany("INSERT OR REPLACE INTO indexes VALUES (?,?,?,?,?,?,?)",
                          [(i.name, i.datatype, i.event_count, i.size_mb, i.earliest, i.latest, int(i.disabled))
                           for i in items])
        return len(items)

    def replace_datasets(self, items: Iterable[DatasetInfo]) -> int:
        items = list(items)
        with self._tx() as c:
            c.execute("DELETE FROM datasets")
            c.executemany("INSERT OR REPLACE INTO datasets VALUES (?,?,?,?)",
                          [(d.index, d.sourcetype, d.event_count, d.last_seen) for d in items])
        return len(items)

    def replace_fields(self, items: Iterable[FieldInfo], *, scope: tuple[str, str] | None = None) -> int:
        items = list(items)
        with self._tx() as c:
            if scope:
                c.execute("DELETE FROM fields WHERE idx = ? AND sourcetype = ?", scope)
            else:
                c.execute("DELETE FROM fields")
            c.executemany("INSERT OR REPLACE INTO fields VALUES (?,?,?,?,?,?,?,?)",
                          [(f.index, f.sourcetype, f.name, f.coverage, f.distinct_count,
                            json.dumps(list(f.sample_values)), int(f.is_numeric), f.kind) for f in items])
        return len(items)

    def replace_datamodels(self, items: Iterable[DataModelInfo]) -> int:
        items = list(items)
        with self._tx() as c:
            c.execute("DELETE FROM datamodels")
            c.executemany("INSERT OR REPLACE INTO datamodels VALUES (?,?,?,?)",
                          [(d.name, d.app, int(d.accelerated), json.dumps(list(d.objects))) for d in items])
        return len(items)

    def replace_knowledge_objects(self, kinds: Iterable[str], items: Iterable[KnowledgeObject]) -> int:
        items = list(items)
        kinds = list(kinds)
        with self._tx() as c:
            c.executemany("DELETE FROM knowledge_objects WHERE kind = ?", [(k,) for k in kinds])
            c.executemany("INSERT OR REPLACE INTO knowledge_objects VALUES (?,?,?,?,?)",
                          [(k.kind, k.name, k.app or "", k.owner, json.dumps(k.attributes, default=str))
                           for k in items])
        return len(items)

    def replace_entities(self, kind: str, items: Iterable[EntityInfo]) -> int:
        items = list(items)
        with self._tx() as c:
            c.execute("DELETE FROM entities WHERE kind = ?", (kind,))
            c.executemany("INSERT OR REPLACE INTO entities VALUES (?,?,?,?)",
                          [(e.kind, e.name, e.event_count, e.last_seen) for e in items])
        return len(items)

    # -------------------------------------------------------------- readers
    def indexes(self) -> list[IndexInfo]:
        return [IndexInfo(r["name"], r["datatype"], r["event_count"] or 0, r["size_mb"] or 0.0, r["earliest"],
                          r["latest"], bool(r["disabled"])) for r in self._rows("SELECT * FROM indexes ORDER BY name")]

    def index(self, name: str) -> IndexInfo | None:
        return next((i for i in self.indexes() if i.name == name), None)

    def metric_indexes(self) -> list[IndexInfo]:
        return [i for i in self.indexes() if i.datatype == "metric" and not i.disabled]

    def datasets(self, index: str | None = None) -> list[DatasetInfo]:
        sql, params = "SELECT * FROM datasets", ()
        if index:
            sql, params = sql + " WHERE idx = ?", (index,)
        return [DatasetInfo(r["idx"], r["sourcetype"], r["event_count"] or 0, r["last_seen"])
                for r in self._rows(sql + " ORDER BY event_count DESC, idx, sourcetype", params)]

    @staticmethod
    def _field(r: sqlite3.Row) -> FieldInfo:
        return FieldInfo(r["idx"], r["sourcetype"], r["name"], r["coverage"] or 0.0, r["distinct_count"] or 0,
                         tuple(json.loads(r["sample_values"] or "[]")), bool(r["is_numeric"]), r["kind"] or "field")

    def fields(self, index: str, sourcetype: str) -> dict[str, FieldInfo]:
        """Fields for a dataset; *sourcetype* may contain wildcards (``kube:container:*``)."""
        rows = self._rows("SELECT * FROM fields WHERE idx = ?", (index,))
        out: dict[str, FieldInfo] = {}
        for r in rows:
            if r["sourcetype"] == sourcetype or fnmatchcase(r["sourcetype"].lower(), sourcetype.lower()):
                f = self._field(r)
                prev = out.get(f.name)
                if prev is None or f.coverage > prev.coverage:
                    out[f.name] = f
        return out

    def all_fields(self) -> list[FieldInfo]:
        return [self._field(r) for r in self._rows("SELECT * FROM fields ORDER BY idx, sourcetype, name")]

    def datamodels(self) -> list[DataModelInfo]:
        return [DataModelInfo(r["name"], r["app"], bool(r["accelerated"]), tuple(json.loads(r["objects"] or "[]")))
                for r in self._rows("SELECT * FROM datamodels ORDER BY name")]

    def datamodel(self, name: str) -> DataModelInfo | None:
        return next((d for d in self.datamodels() if d.name.lower() == name.lower()), None)

    def knowledge_objects(self, kind: str | Iterable[str] | None = None) -> list[KnowledgeObject]:
        rows = self._rows("SELECT * FROM knowledge_objects ORDER BY kind, name")
        kinds = {kind} if isinstance(kind, str) else set(kind) if kind else None
        return [KnowledgeObject(r["kind"], r["name"], r["app"] or None, r["owner"], json.loads(r["attributes"] or "{}"))
                for r in rows if kinds is None or r["kind"] in kinds]

    def entities(self, kind: str) -> list[EntityInfo]:
        return [EntityInfo(r["kind"], r["name"], r["event_count"] or 0, r["last_seen"])
                for r in self._rows("SELECT * FROM entities WHERE kind = ? ORDER BY event_count DESC", (kind,))]

    # ------------------------------------------------------------ summaries
    def is_empty(self) -> bool:
        return not self._rows("SELECT 1 FROM indexes LIMIT 1") and not self._rows("SELECT 1 FROM datasets LIMIT 1")

    def summary(self) -> dict[str, Any]:
        def count(sql: str, params: tuple = ()) -> int:
            return int(self._rows(sql, params)[0][0])
        kos = {r["kind"]: r["n"] for r in self._rows("SELECT kind, COUNT(*) AS n FROM knowledge_objects GROUP BY kind")}
        return {
            "indexes": count("SELECT COUNT(*) FROM indexes"),
            "datasets": count("SELECT COUNT(*) FROM datasets"),
            "fields": count("SELECT COUNT(*) FROM fields"),
            "datamodels": count("SELECT COUNT(*) FROM datamodels"),
            "hosts": count("SELECT COUNT(*) FROM entities WHERE kind = 'host'"),
            "sources": count("SELECT COUNT(*) FROM entities WHERE kind = 'source'"),
            "knowledge_objects": kos,
            "last_discovery": self.get_meta("last_discovery"),
            "server": self.get_meta("server_info"),
        }

    # ------------------------------------------------------- import/export
    def to_dict(self) -> dict[str, Any]:
        meta = {r["key"]: r["value"] for r in self._rows("SELECT * FROM meta")}
        return {
            "schema_version": SCHEMA_VERSION,
            "exported_at": time.time(),
            "meta": meta,
            "indexes": [to_dict(i) for i in self.indexes()],
            "datasets": [to_dict(d) for d in self.datasets()],
            "fields": [to_dict(f) for f in self.all_fields()],
            "datamodels": [to_dict(d) for d in self.datamodels()],
            "knowledge_objects": [to_dict(k) for k in self.knowledge_objects()],
            "entities": [to_dict(e) for e in self.entities("host") + self.entities("source")],
        }

    def export_json(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(p)
        return p

    def load_dict(self, data: dict[str, Any]) -> None:
        if int(data.get("schema_version", 0)) > SCHEMA_VERSION:
            raise CatalogError(f"Catalog schema {data.get('schema_version')} is newer than supported {SCHEMA_VERSION}")
        try:
            self.replace_indexes(IndexInfo(**i) for i in data.get("indexes", []))
            self.replace_datasets(DatasetInfo(**d) for d in data.get("datasets", []))
            self.replace_fields(FieldInfo(**{**f, "sample_values": tuple(f.get("sample_values", ()))})
                                for f in data.get("fields", []))
            self.replace_datamodels(DataModelInfo(**{**d, "objects": tuple(d.get("objects", ()))})
                                    for d in data.get("datamodels", []))
            kos = [KnowledgeObject(**k) for k in data.get("knowledge_objects", [])]
            self.replace_knowledge_objects({k.kind for k in kos} | {"report", "alert", "saved_search", "dashboard",
                                                                    "kvstore", "lookup_definition", "lookup_file"}, kos)
            ents = [EntityInfo(**e) for e in data.get("entities", [])]
            for kind in ("host", "source"):
                self.replace_entities(kind, [e for e in ents if e.kind == kind])
        except TypeError as exc:
            raise CatalogError(f"Malformed catalog document: {exc}") from exc
        for key, value in (data.get("meta") or {}).items():
            if key != "schema_version":
                with self._tx() as c:
                    c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))

    def import_json(self, path: str | Path) -> None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CatalogError(f"Cannot read catalog JSON {path}: {exc}") from exc
        self.load_dict(data)
        log.info("Imported catalog from %s", path)
