--liquibase formatted sql

--changeset agent:RB.001
--comment: Rollback of release 1.0 (reverse order of deploy scripts)

-- =====================================================
-- 1) Reverse 07_APP_HR_EMPLOYEE_DML.sql (007)
-- NOTE: Pre-update values restored from EMPLOYEE_BKP10 by primary key.
-- =====================================================
MERGE INTO HR.EMPLOYEE t USING HR.EMPLOYEE_BKP10 b ON (t.EMPLOYEE_ID = b.EMPLOYEE_ID) WHEN MATCHED THEN UPDATE SET t.DEPARTMENT_ID = b.DEPARTMENT_ID;

-- =====================================================
-- 2) Reverse 06_APP_HR_DEPARTMENT_DML.sql (006)
-- Superseded: object(s) DEPARTMENT are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 3) Reverse 05_APP_HR_PRC_ASSIGN_DEPARTMENT_PROC_DDL.sql (005)
-- =====================================================
DROP PROCEDURE HR.PRC_ASSIGN_DEPARTMENT;

-- =====================================================
-- 4) Reverse 04_APP_HR_EMPLOYEE_DEPT_VW_DDL.sql (004)
-- =====================================================
DROP VIEW HR.EMPLOYEE_DEPT_VW;

-- =====================================================
-- 5) Reverse 03_APP_HR_EMPLOYEE_IDX_DDL.sql (003)
-- =====================================================
DROP INDEX HR.IDX_EMPLOYEE_NAME;

-- =====================================================
-- 6) Reverse 02_APP_HR_EMPLOYEE_ALTER_DDL.sql (002)
-- =====================================================
ALTER TABLE HR.EMPLOYEE DROP CONSTRAINT FK_EMPLOYEE_DEPARTMENT;
ALTER TABLE HR.EMPLOYEE MODIFY (EMPLOYEE_NAME VARCHAR2(100));
ALTER TABLE HR.EMPLOYEE DROP (DEPARTMENT_ID, HIRE_STATUS);

-- =====================================================
-- 7) Reverse 01_APP_HR_DEPARTMENT_DDL.sql (001)
-- =====================================================
DROP TABLE HR.DEPARTMENT CASCADE CONSTRAINTS;
DROP SEQUENCE HR.SEQ_DEPARTMENT_ID;

-- Forward-only rollback script: to undo it, re-run the release deploy scripts.
--rollback SELECT 1 FROM DUAL;
