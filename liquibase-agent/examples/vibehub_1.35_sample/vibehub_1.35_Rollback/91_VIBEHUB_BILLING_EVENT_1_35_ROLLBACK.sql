--liquibase formatted sql

--changeset SOL_DATA:RB.SOL_SERVICES.1.35.1.0.1-pre

Insert Into LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER (CHANGESET_ID,SCHEMA_NAME,SCRIPT_NAME,RELEASE_NUMBER,OBJECT_TYPE,OBJECT_NAME,SQL_LOCATION,ACTION,STATUS,COUNT_BEFORE_CHANGE,COUNT_AFTER_CHANGE,ROLLBACK_FLAG) VALUES ('RB.SOL_SERVICES.1.35.1.0.1','BILLING_EVENT','91_VIBEHUB_BILLING_EVENT_1_35_ROLLBACK.sql','SOL_SERVICES 1.35','Multiple','Release 1.35 rollback','/opt/scripts/','Rollback','PENDING',(select count (*) from DBA_OBJECTS where OWNER = 'BILLING_EVENT'),0,1);
COMMIT;
--rollback DELETE FROM LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER WHERE CHANGESET_ID = 'RB.SOL_SERVICES.1.35.1.0.1';

--changeset SOL_DATA:RB.SOL_SERVICES.1.35.1.0.1
--comment: Rollback of release 1.35 (reverse order of deploy scripts)

-- =====================================================
-- 1) Reverse 05_VIBEHUB_BILLING_EVENT_CANCEL_REASON_BEFORE_TRIG_DDL.sql (SOL_SERVICES.1.35.1.0.5)
-- =====================================================
DROP TRIGGER BILLING_EVENT.TRG_CANCEL_REASON_BEFORE;

-- =====================================================
-- 2) Reverse 04_VIBEHUB_BILLING_EVENT_CANCEL_REASON_DML.sql (SOL_SERVICES.1.35.1.0.4)
-- Superseded: object(s) CANCEL_REASON are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 3) Reverse 03_VIBEHUB_BILLING_EVENT_CANCEL_REASON_DDL.sql (SOL_SERVICES.1.35.1.0.3)
-- =====================================================
DROP TABLE BILLING_EVENT.CANCEL_REASON CASCADE CONSTRAINTS;
DROP SEQUENCE BILLING_EVENT.SEQ_CANCEL_REASON_ID;

-- =====================================================
-- 4) Reverse 02_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_INDEXES_DDL.sql (SOL_SERVICES.1.35.1.0.2)
-- =====================================================
DROP INDEX BILLING_EVENT.IDX_SHADOW_ORDER_TTL2;

-- =====================================================
-- 5) Reverse 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_ADD_COLUMNS_ALTER_DDL.sql (SOL_SERVICES.1.35.1.0.1)
-- =====================================================
ALTER TABLE BILLING_EVENT.SHADOW_ORDER DROP COLUMN CANCEL_REASON;

-- Forward-only rollback script: to undo it, re-run the release deploy scripts.
--rollback SELECT 1 FROM DUAL;

--changeset SOL_DATA:RB.SOL_SERVICES.1.35.1.0.1-post

UPDATE LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER SET COUNT_AFTER_CHANGE = (select count (*) from DBA_OBJECTS where OWNER = 'BILLING_EVENT'), STATUS = 'COMPLETED' WHERE CHANGESET_ID = 'RB.SOL_SERVICES.1.35.1.0.1';
COMMIT;
--rollback UPDATE LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER SET STATUS = 'ROLLED_BACK', ROLLBACK_FLAG = 1 WHERE CHANGESET_ID = 'RB.SOL_SERVICES.1.35.1.0.1';
