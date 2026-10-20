-- PRE-DEPLOYMENT CHECKS - release 1.0 (oracle)
-- Read-only queries. Compare each result with the expected value.

-- [release] Invalid objects BEFORE deploy in None | expected: baseline (record)
SELECT OBJECT_TYPE, OBJECT_NAME, STATUS FROM ALL_OBJECTS WHERE OWNER = SYS_CONTEXT('USERENV','CURRENT_SCHEMA') AND STATUS <> 'VALID' ORDER BY OBJECT_TYPE, OBJECT_NAME;

-- [release] No stale Liquibase lock | expected: LOCKED = 0/false
SELECT * FROM DATABASECHANGELOGLOCK;

-- ---- step 1: CREATE_TABLE employee
-- employee must not exist yet | expected: 0
SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = SYS_CONTEXT('USERENV','CURRENT_SCHEMA') AND TABLE_NAME = 'EMPLOYEE';

