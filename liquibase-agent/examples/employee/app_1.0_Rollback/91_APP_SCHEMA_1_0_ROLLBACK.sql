--liquibase formatted sql

--changeset agent:RB.001
--comment: Rollback of release 1.0 (reverse order of deploy scripts)

-- =====================================================
-- 1) Reverse 01_APP_SCHEMA_EMPLOYEE_DDL.sql (001)
-- =====================================================
DROP TABLE employee CASCADE CONSTRAINTS;

-- Forward-only rollback script: to undo it, re-run the release deploy scripts.
--rollback SELECT 1 FROM DUAL;
