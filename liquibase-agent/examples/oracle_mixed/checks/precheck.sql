-- PRE-DEPLOYMENT CHECKS - release 1.0 (oracle)
-- Read-only queries. Compare each result with the expected value.

-- [release] Invalid objects BEFORE deploy in HR | expected: baseline (record)
SELECT OBJECT_TYPE, OBJECT_NAME, STATUS FROM ALL_OBJECTS WHERE OWNER = 'HR' AND STATUS <> 'VALID' ORDER BY OBJECT_TYPE, OBJECT_NAME;

-- [release] No stale Liquibase lock | expected: LOCKED = 0/false
SELECT * FROM DATABASECHANGELOGLOCK;

-- ---- step 1: CREATE_SEQUENCE HR.SEQ_DEPARTMENT_ID
-- Sequence must not exist | expected: 0
SELECT COUNT(*) FROM ALL_SEQUENCES WHERE SEQUENCE_OWNER = 'HR' AND SEQUENCE_NAME = 'SEQ_DEPARTMENT_ID';

-- ---- step 2: CREATE_TABLE HR.DEPARTMENT
-- HR.DEPARTMENT must not exist yet | expected: 0
SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = 'HR' AND TABLE_NAME = 'DEPARTMENT';

-- ---- step 3: ADD_COLUMN HR.EMPLOYEE
-- EMPLOYEE.DEPARTMENT_ID must not exist yet | expected: 0
SELECT COUNT(*) FROM ALL_TAB_COLUMNS WHERE OWNER = 'HR' AND TABLE_NAME = 'EMPLOYEE' AND COLUMN_NAME = 'DEPARTMENT_ID';
-- EMPLOYEE.HIRE_STATUS must not exist yet | expected: 0
SELECT COUNT(*) FROM ALL_TAB_COLUMNS WHERE OWNER = 'HR' AND TABLE_NAME = 'EMPLOYEE' AND COLUMN_NAME = 'HIRE_STATUS';
-- NOT NULL add needs empty table or default | expected: 0 (or DEFAULT supplied)
SELECT COUNT(*) FROM HR.EMPLOYEE;

-- ---- step 4: MODIFY_COLUMN HR.EMPLOYEE
-- Current definition (rollback reference) | expected: record value
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT FROM ALL_TAB_COLUMNS WHERE OWNER = 'HR' AND TABLE_NAME = 'EMPLOYEE' AND COLUMN_NAME IN ('EMPLOYEE_NAME');
-- Longest existing value fits new size | expected: <= new length of VARCHAR2(50)
SELECT MAX(LENGTH(EMPLOYEE_NAME)) FROM HR.EMPLOYEE;
-- Dependent objects that will be invalidated | expected: review
SELECT OWNER, NAME, TYPE FROM ALL_DEPENDENCIES WHERE REFERENCED_OWNER = 'HR' AND REFERENCED_NAME = 'EMPLOYEE' ORDER BY TYPE, NAME;

-- ---- step 5: ADD_CONSTRAINT HR.FK_EMPLOYEE_DEPARTMENT
-- Constraint name FK_EMPLOYEE_DEPARTMENT free | expected: 0
SELECT COUNT(*) FROM ALL_CONSTRAINTS WHERE OWNER = 'HR' AND CONSTRAINT_NAME = 'FK_EMPLOYEE_DEPARTMENT';
-- No orphan child rows | expected: 0
SELECT COUNT(*) FROM HR.EMPLOYEE c WHERE c.DEPARTMENT_ID IS NOT NULL AND NOT EXISTS (SELECT 1 FROM HR.DEPARTMENT p WHERE p.DEPARTMENT_ID = c.DEPARTMENT_ID);
-- FK index advisory
-- No index found on EMPLOYEE (DEPARTMENT_ID) - consider indexing the FK column(s)

-- ---- step 6: CREATE_INDEX HR.IDX_EMPLOYEE_NAME
-- Index IDX_EMPLOYEE_NAME must not exist | expected: 0
SELECT COUNT(*) FROM ALL_INDEXES WHERE OWNER = 'HR' AND INDEX_NAME = 'IDX_EMPLOYEE_NAME';
-- Table EMPLOYEE exists | expected: 1
SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = 'HR' AND TABLE_NAME = 'EMPLOYEE';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM HR.EMPLOYEE;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'HR' AND o.OBJECT_NAME = 'EMPLOYEE';

-- ---- step 7: CREATE_VIEW HR.EMPLOYEE_DEPT_VW
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM ALL_OBJECTS WHERE OWNER = 'HR' AND OBJECT_NAME = 'EMPLOYEE_DEPT_VW' AND OBJECT_TYPE = 'VIEW';
-- Capture current source for rollback (if it exists) | expected: save output
SELECT DBMS_METADATA.GET_DDL('VIEW', 'EMPLOYEE_DEPT_VW', 'HR') FROM DUAL;

-- ---- step 8: CREATE_PROCEDURE HR.PRC_ASSIGN_DEPARTMENT
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM ALL_OBJECTS WHERE OWNER = 'HR' AND OBJECT_NAME = 'PRC_ASSIGN_DEPARTMENT' AND OBJECT_TYPE = 'PROCEDURE';
-- Capture current source for rollback (if it exists) | expected: save output
SELECT DBMS_METADATA.GET_DDL('PROCEDURE', 'PRC_ASSIGN_DEPARTMENT', 'HR') FROM DUAL;

-- ---- step 9: INSERT HR.DEPARTMENT
-- Rows affected by INSERT | expected: record value (expected volume)
SELECT COUNT(*) FROM HR.DEPARTMENT;
-- Row not already present (idempotency) | expected: 0
SELECT COUNT(*) FROM HR.DEPARTMENT WHERE DEPARTMENT_ID = 1 AND DEPT_CODE = 'IT' AND DEPT_NAME = 'Information Technology';

-- ---- step 10: UPDATE HR.EMPLOYEE
-- Rows affected by UPDATE | expected: record value (expected volume)
SELECT COUNT(*) FROM HR.EMPLOYEE WHERE DEPARTMENT_ID IS NULL;

