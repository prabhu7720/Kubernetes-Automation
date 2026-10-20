-- Export the CURRENT definition of a schema as a baseline for the agent (--baseline).
-- Run with SQL*Plus / SQLcl inside your network; the output file never leaves your environment.
--   sqlplus -s user/pwd@db @tools/export_baseline_oracle.sql BILLING_EVENT baseline_BILLING_EVENT.sql
SET LONG 2000000 LONGCHUNKSIZE 2000000 PAGESIZE 0 LINESIZE 32767 TRIMSPOOL ON FEEDBACK OFF HEADING OFF VERIFY OFF
DEFINE OWNER = &1
SPOOL &2
BEGIN
  DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SQLTERMINATOR', TRUE);
  DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PRETTY', TRUE);
  DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SEGMENT_ATTRIBUTES', FALSE);
  DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'STORAGE', FALSE);
  DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'TABLESPACE', TRUE);
END;
/
SELECT DBMS_METADATA.GET_DDL(object_type, object_name, owner)
  FROM dba_objects
 WHERE owner = UPPER('&OWNER')
   AND object_type IN ('SEQUENCE','TABLE','VIEW','PROCEDURE','FUNCTION','PACKAGE','TRIGGER','TYPE')
   AND object_name NOT LIKE 'BIN$%'
   AND object_name NOT IN ('DATABASECHANGELOG','DATABASECHANGELOGLOCK')
 ORDER BY DECODE(object_type,'SEQUENCE',1,'TABLE',2,'VIEW',3,'TYPE',4,'PACKAGE',5,'FUNCTION',6,'PROCEDURE',7,'TRIGGER',8,9), object_name;
-- indexes that are not created by constraints
SELECT DBMS_METADATA.GET_DDL('INDEX', i.index_name, i.owner)
  FROM dba_indexes i
 WHERE i.owner = UPPER('&OWNER')
   AND NOT EXISTS (SELECT 1 FROM dba_constraints c WHERE c.owner = i.owner AND c.index_name = i.index_name)
   AND i.index_type NOT IN ('LOB');
SELECT DBMS_METADATA.GET_DEPENDENT_DDL('COMMENT', table_name, owner) FROM dba_tables t
 WHERE owner = UPPER('&OWNER') AND EXISTS (SELECT 1 FROM dba_col_comments c WHERE c.owner = t.owner AND c.table_name = t.table_name AND c.comments IS NOT NULL);
SPOOL OFF
