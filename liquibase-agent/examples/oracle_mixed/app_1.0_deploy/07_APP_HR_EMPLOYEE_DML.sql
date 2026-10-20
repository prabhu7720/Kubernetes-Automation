--liquibase formatted sql

--changeset agent:007-bkp
-- =====================================================
-- Backup of data affected by this change (used by rollback)
-- =====================================================
CREATE TABLE HR.EMPLOYEE_BKP10 AS SELECT * FROM HR.EMPLOYEE WHERE DEPARTMENT_ID IS NULL;
--rollback DROP TABLE HR.EMPLOYEE_BKP10;

--changeset agent:007
--comment: Update - EMPLOYEE

UPDATE HR.EMPLOYEE SET DEPARTMENT_ID = 1 WHERE DEPARTMENT_ID IS NULL;

COMMIT;

-- =====================================================
-- Rollback notes:
-- Pre-update values restored from EMPLOYEE_BKP10 by primary key.
-- =====================================================
--rollback MERGE INTO HR.EMPLOYEE t USING HR.EMPLOYEE_BKP10 b ON (t.EMPLOYEE_ID = b.EMPLOYEE_ID) WHEN MATCHED THEN UPDATE SET t.DEPARTMENT_ID = b.DEPARTMENT_ID;
