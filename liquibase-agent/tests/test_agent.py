"""Offline unit tests - run:  python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from core import models as M  # noqa: E402
from core.config import load_profile  # noqa: E402
from core.engine import LiquibaseAgent  # noqa: E402
from parsers.sql_parser import split_statements, detect_dialect  # noqa: E402
from parsers.ddl_parser import DDLParser  # noqa: E402
from parsers import liquibase_parser as LP  # noqa: E402
from validators import liquibase_validator  # noqa: E402

EMPLOYEE = """CREATE TABLE employee (
    employee_id NUMBER PRIMARY KEY,
    employee_name VARCHAR2(100),
    created_date DATE
);"""


def run(sql, profile="default", **kw):
    p = load_profile(profile)
    p["tag_before_release"] = kw.pop("tag", False)
    p["preconditions"] = kw.pop("pre", False)
    p["xml_changelog_dbms_precondition"] = False
    for k, v in kw.pop("overrides", {}).items():
        p[k] = v
    a = LiquibaseAgent(p, **kw)
    return a.run([], inline_sql=sql)


class SplitterTests(unittest.TestCase):
    def test_oracle_plsql_without_slash(self):
        sql = "CREATE OR REPLACE TRIGGER t BEFORE INSERT ON x FOR EACH ROW\nBEGIN\n IF INSERTING THEN :NEW.a := 1; END IF;\nEND;\nCREATE TABLE y (a NUMBER);"
        st = split_statements(sql, "oracle")
        self.assertEqual(len(st), 2)
        self.assertTrue(st[0].sql.rstrip().endswith("END;"))

    def test_oracle_slash_and_package(self):
        sql = "CREATE OR REPLACE PACKAGE p AS\n PROCEDURE a;\nEND p;\n/\nCREATE OR REPLACE PACKAGE BODY p AS\n PROCEDURE a IS BEGIN NULL; END a;\nEND p;\n/\n"
        self.assertEqual(len(split_statements(sql, "oracle")), 2)

    def test_mysql_delimiter(self):
        sql = "DELIMITER $$\nCREATE PROCEDURE p() BEGIN SELECT 1; SELECT 2; END$$\nDELIMITER ;\nSELECT 3;"
        st = split_statements(sql, "mysql")
        self.assertEqual(len(st), 2)
        self.assertIn("SELECT 2", st[0].sql)

    def test_mssql_go(self):
        sql = "CREATE PROCEDURE dbo.p AS\nBEGIN\n SELECT 1;\n SELECT 2;\nEND\nGO\nSELECT 3\nGO"
        self.assertEqual(len(split_statements(sql, "mssql")), 2)

    def test_pg_dollar_quotes(self):
        sql = "CREATE FUNCTION f() RETURNS trigger AS $$ BEGIN NEW.a := 1; RETURN NEW; END; $$ LANGUAGE plpgsql;\nSELECT 1;"
        self.assertEqual(len(split_statements(sql, "postgresql")), 2)

    def test_liquibase_meta_lines_are_boundaries(self):
        sql = "--liquibase formatted sql\n--changeset a:1\nCREATE TABLE a (x NUMBER);\n--rollback DROP TABLE a;\n"
        st = split_statements(sql, "oracle")
        self.assertEqual(len(st), 1)

    def test_detect(self):
        self.assertEqual(detect_dialect("CREATE TABLE a (b VARCHAR2(10)) TABLESPACE X")[0], "oracle")
        self.assertEqual(detect_dialect("CREATE TABLE a (id BIGSERIAL, j JSONB)")[0], "postgresql")
        self.assertEqual(detect_dialect("CREATE TABLE `a` (id INT AUTO_INCREMENT) ENGINE=InnoDB")[0], "mysql")
        self.assertEqual(detect_dialect("CREATE TABLE dbo.a (id INT IDENTITY(1,1))\nGO")[0], "mssql")


class ParserTests(unittest.TestCase):
    def parse(self, sql, d="oracle"):
        p = DDLParser(d)
        return [o for st in split_statements(sql, d) for o in p.parse(st)]

    def test_create_table_constraints(self):
        op = self.parse("CREATE TABLE s.t (a NUMBER NOT NULL, b VARCHAR2(10) DEFAULT 'x', c NUMBER REFERENCES s.p (id) ON DELETE CASCADE,"
                        " CONSTRAINT pk_t PRIMARY KEY (a), CONSTRAINT uk_t UNIQUE (b, c), CONSTRAINT chk_t CHECK (a > 0)) TABLESPACE ts NOLOGGING")[0]
        self.assertEqual(op.kind, M.CREATE_TABLE)
        self.assertEqual(op.schema, "s")
        cons = {c.ctype for c in op.details["constraints"]}
        self.assertEqual(cons, {"PRIMARY KEY", "UNIQUE", "FOREIGN KEY", "CHECK"})
        self.assertEqual(op.details["tablespace"], "ts")
        self.assertTrue(op.details["nologging"])
        self.assertEqual(op.details["columns"][1].default, "'x'")

    def test_alter_split(self):
        ops = self.parse("ALTER TABLE app.t ADD COLUMN a INT, ADD COLUMN b INT, DROP COLUMN c", "postgresql")
        self.assertEqual([o.kind for o in ops], [M.ADD_COLUMN, M.DROP_COLUMN])
        self.assertEqual(len(ops[0].details["columns"]), 2)

    def test_oracle_modify_null(self):
        op = self.parse('ALTER TABLE "S"."T" MODIFY "C" NULL')[0]
        self.assertEqual(op.kind, M.MODIFY_COLUMN)
        self.assertTrue(op.details["columns"][0].nullable)

    def test_trigger_events(self):
        op = self.parse("CREATE TRIGGER dbo.tr ON dbo.x AFTER UPDATE AS BEGIN INSERT INTO a SELECT 1 FROM inserted; END", "mssql")[0]
        self.assertEqual(op.details["events"], ["UPDATE"])


class GenerationTests(unittest.TestCase):
    def test_employee_example_xml(self):
        res = run(EMPLOYEE, dialect="oracle")
        root = ET.fromstring(res.xml)
        ns = {"l": "http://www.liquibase.org/xml/ns/dbchangelog"}
        cs = root.findall("l:changeSet", ns)
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0].get("id"), "001")
        self.assertEqual(cs[0].get("author"), "agent")
        ct = cs[0].find("l:createTable", ns)
        self.assertEqual(ct.get("tableName"), "employee")
        cols = ct.findall("l:column", ns)
        self.assertEqual([(c.get("name"), c.get("type")) for c in cols],
                         [("employee_id", "NUMBER"), ("employee_name", "VARCHAR2(100)"), ("created_date", "DATE")])
        self.assertEqual(cols[0].find("l:constraints", ns).get("primaryKey"), "true")
        rb = cs[0].find("l:rollback/l:dropTable", ns)
        self.assertEqual(rb.get("tableName"), "employee")

    def test_drop_column_rollback_with_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            b = os.path.join(d, "b.sql")
            open(b, "w").write("CREATE TABLE s.t (id NUMBER NOT NULL, c VARCHAR2(20) DEFAULT 'A' NOT NULL, "
                               "CONSTRAINT pk_t PRIMARY KEY (id), CONSTRAINT chk_c CHECK (c IN ('A','B')));\n"
                               "CREATE INDEX s.idx_c ON s.t (c);")
            p = load_profile("default")
            a = LiquibaseAgent(p, dialect="oracle")
            a.add_baseline([b])
            res = a.run([], inline_sql="ALTER TABLE s.t DROP COLUMN c CASCADE CONSTRAINTS;")
            rb = res.results[0].rollback
            self.assertTrue(rb.complete)
            joined = "\n".join(rb.sql)
            self.assertIn("ADD (c VARCHAR2(20) DEFAULT 'A' NOT NULL)", joined)
            self.assertIn("CHK_C", joined.upper())
            self.assertIn("CREATE INDEX s.idx_c", joined)
            self.assertTrue(rb.pre_sql and "SELECT id, c FROM s.t" in rb.pre_sql[0])

    def test_replace_without_baseline_is_manual(self):
        res = run("CREATE OR REPLACE VIEW v_x AS SELECT 1 a FROM dual;", dialect="oracle")
        self.assertFalse(res.results[0].rollback.complete)

    def test_ddl_dml_split(self):
        res = run("ALTER TABLE t ADD c NUMBER;\nUPDATE t SET c = 1;\nCOMMIT;", dialect="oracle")
        types = [u.unit_type for u in res.units_sql]
        self.assertEqual(types, ["ALTER", "DML"])

    def test_house_style(self):
        sql = ("CREATE SEQUENCE BILLING_EVENT.SEQ_X_ID START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;\n"
               "CREATE TABLE BILLING_EVENT.X (X_ID NUMBER NOT NULL, CREATED_DT TIMESTAMP, CREATED_BY VARCHAR2(30), "
               "UPDATED_DT TIMESTAMP, UPDATED_BY VARCHAR2(30), CONSTRAINT PK_X PRIMARY KEY (X_ID)) TABLESPACE \"BILLING_EVENT_DATA\";\n"
               "CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_X_BEFORE BEFORE INSERT ON BILLING_EVENT.X FOR EACH ROW\nBEGIN\n"
               "  :NEW.CREATED_DT := SYSTIMESTAMP;\nEND;\n")
        res = run(sql, profile="sol_services", release="1.35")
        files = sorted(res.sql_files)
        self.assertTrue(any(f.endswith("01_VIBEHUB_BILLING_EVENT_X_DDL.sql") for f in files), files)
        first = [t for f, t in res.sql_files.items() if f.endswith("01_VIBEHUB_BILLING_EVENT_X_DDL.sql")][0]
        self.assertIn("--changeset SOL_DATA:SOL_SERVICES.1.35.1.0.1-pre", first)
        self.assertIn("LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER", first)
        self.assertIn('GRANT SELECT ON "BILLING_EVENT"."X" TO "BILLING_EVENT_READ_ROLE"', first)  # auto grant
        trig = [t for f, t in res.sql_files.items() if "TRIG" in f][0]
        self.assertIn('--changeset SOL_DATA:SOL_SERVICES.1.35.1.0.2 endDelimiter:"/"', trig)
        self.assertTrue(any("ROLLBACK" in f for f in files))

    def test_invalid_window(self):
        sql = ("CREATE TABLE a (id NUMBER, st VARCHAR2(1));\n"
               "CREATE OR REPLACE TRIGGER trg_a BEFORE INSERT ON a FOR EACH ROW\nBEGIN\n :NEW.st := 'A';\nEND;\n"
               "ALTER TABLE a DROP COLUMN st;\n")
        res = run(sql, dialect="oracle")
        self.assertIn("DEPENDENT_INVALIDATED", {f.code for f in res.findings})


class ValidatorTests(unittest.TestCase):
    def test_plsql_split_detected(self):
        cf = LP.parse_formatted_sql("x.sql", "--liquibase formatted sql\n--changeset a:1\nCREATE OR REPLACE TRIGGER t "
                                             "BEFORE INSERT ON x FOR EACH ROW\nBEGIN\n NULL;\nEND;\n")
        codes = {f.code for f in liquibase_validator.validate([cf], load_profile("default"))}
        self.assertIn("LB_PLSQL_SPLIT", codes)

    def test_duplicate_ids(self):
        cf = LP.parse_formatted_sql("x.sql", "--liquibase formatted sql\n--changeset a:1\nSELECT 1;\n--changeset a:1\nSELECT 2;\n")
        codes = {f.code for f in liquibase_validator.validate([cf], load_profile("default"))}
        self.assertIn("LB_DUPLICATE", codes)

    def test_generated_xml_is_valid(self):
        res = run("CREATE TABLE t (a NUMBER PRIMARY KEY);\nCREATE INDEX idx_t_a2 ON t (a);\nDROP TABLE old_t;", dialect="oracle")
        cf = LP.parse_xml("g.xml", res.xml)
        self.assertFalse(cf.errors)
        bad = [f for f in liquibase_validator.validate([cf], res.profile) if f.severity in ("HIGH", "CRITICAL")]
        self.assertFalse(bad, bad)


if __name__ == "__main__":
    unittest.main()
