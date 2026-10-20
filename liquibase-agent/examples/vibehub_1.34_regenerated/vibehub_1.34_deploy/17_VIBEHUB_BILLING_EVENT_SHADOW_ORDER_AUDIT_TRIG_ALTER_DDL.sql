--liquibase formatted sql

--changeset SOL_DATA:SOL_SERVICES.1.34.1.0.17-pre

Insert Into LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER (CHANGESET_ID,SCHEMA_NAME,SCRIPT_NAME,RELEASE_NUMBER,OBJECT_TYPE,OBJECT_NAME,SQL_LOCATION,ACTION,STATUS,COUNT_BEFORE_CHANGE,COUNT_AFTER_CHANGE,ROLLBACK_FLAG) VALUES ('SOL_SERVICES.1.34.1.0.17','BILLING_EVENT','17_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql','SOL_SERVICES 1.34','TRIGGER','TRG_SHADOW_ORDER_AUDIT','/opt/scripts/','Create or Replace Trigger','PENDING',(select count (*) from DBA_TRIGGERS where OWNER = 'BILLING_EVENT'),0,0);

COMMIT;
--rollback DELETE FROM LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER WHERE CHANGESET_ID = 'SOL_SERVICES.1.34.1.0.17';

--changeset SOL_DATA:SOL_SERVICES.1.34.1.0.17 endDelimiter:"/"
--comment: Create Trigger - TRG_SHADOW_ORDER_AUDIT

-- =====================================================
-- Recreate TRG_SHADOW_ORDER_AUDIT without STATUS, which was dropped
-- from SHADOW_ORDER (script 10) and SHADOW_ORDER_AUDIT (script 11).
-- =====================================================
CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
AFTER INSERT OR UPDATE OR DELETE ON BILLING_EVENT.SHADOW_ORDER
FOR EACH ROW
DECLARE
    v_action VARCHAR2(10);
    v_transaction_id VARCHAR2(100);
BEGIN
    IF INSERTING THEN
        v_action := 'INSERT';
    ELSIF UPDATING THEN
        v_action := 'UPDATE';
    ELSIF DELETING THEN
        v_action := 'DELETE';
    END IF;

    v_transaction_id := SYS_GUID();

    INSERT INTO BILLING_EVENT.SHADOW_ORDER_AUDIT (
        AUDIT_ID,
        AUDIT_TIMESTAMP,
        AUDIT_ACTION,
        AUDIT_TRANSACTION_ID,
        SHADOW_ORDER_ID,
        CUSTOMER_ORDER_ID,
        ACCOUNT_ID,
        ACCOUNT_NUMBER,
        SITE_ID,
        ORDER_TYPE,
        TTL_EXPIRES_AT,
        CREATED_DT,
        CREATED_BY,
        UPDATED_DT,
        UPDATED_BY
    ) VALUES (
        BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID.NEXTVAL,
        SYSTIMESTAMP,
        v_action,
        v_transaction_id,
        COALESCE(:NEW.SHADOW_ORDER_ID, :OLD.SHADOW_ORDER_ID),
        COALESCE(:NEW.CUSTOMER_ORDER_ID, :OLD.CUSTOMER_ORDER_ID),
        COALESCE(:NEW.ACCOUNT_ID, :OLD.ACCOUNT_ID),
        COALESCE(:NEW.ACCOUNT_NUMBER, :OLD.ACCOUNT_NUMBER),
        COALESCE(:NEW.SITE_ID, :OLD.SITE_ID),
        COALESCE(:NEW.ORDER_TYPE, :OLD.ORDER_TYPE),
        COALESCE(:NEW.TTL_EXPIRES_AT, :OLD.TTL_EXPIRES_AT),
        COALESCE(:NEW.CREATED_DT, :OLD.CREATED_DT),
        COALESCE(:NEW.CREATED_BY, :OLD.CREATED_BY),
        COALESCE(:NEW.UPDATED_DT, :OLD.UPDATED_DT),
        COALESCE(:NEW.UPDATED_BY, :OLD.UPDATED_BY)
    );
END;

-- =====================================================
-- Rollback notes:
-- Restores the previous definition of BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT captured from baseline/earlier step.
-- =====================================================
--rollback CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
--rollback AFTER INSERT OR UPDATE OR DELETE ON BILLING_EVENT.SHADOW_ORDER
--rollback FOR EACH ROW
--rollback DECLARE
--rollback     v_action VARCHAR2(10);
--rollback     v_transaction_id VARCHAR2(100);
--rollback BEGIN
--rollback     IF INSERTING THEN
--rollback         v_action := 'INSERT';
--rollback     ELSIF UPDATING THEN
--rollback         v_action := 'UPDATE';
--rollback     ELSIF DELETING THEN
--rollback         v_action := 'DELETE';
--rollback     END IF;
--rollback 
--rollback     v_transaction_id := SYS_GUID();
--rollback 
--rollback     INSERT INTO BILLING_EVENT.SHADOW_ORDER_AUDIT (
--rollback         AUDIT_ID,
--rollback         AUDIT_TIMESTAMP,
--rollback         AUDIT_ACTION,
--rollback         AUDIT_TRANSACTION_ID,
--rollback         SHADOW_ORDER_ID,
--rollback         CUSTOMER_ORDER_ID,
--rollback         ACCOUNT_ID,
--rollback         ACCOUNT_NUMBER,
--rollback         SITE_ID,
--rollback         ORDER_TYPE,
--rollback         STATUS,
--rollback         TTL_EXPIRES_AT,
--rollback         CREATED_DT,
--rollback         CREATED_BY,
--rollback         UPDATED_DT,
--rollback         UPDATED_BY
--rollback     ) VALUES (
--rollback         BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID.NEXTVAL,
--rollback         SYSTIMESTAMP,
--rollback         v_action,
--rollback         v_transaction_id,
--rollback         COALESCE(:NEW.SHADOW_ORDER_ID, :OLD.SHADOW_ORDER_ID),
--rollback         COALESCE(:NEW.CUSTOMER_ORDER_ID, :OLD.CUSTOMER_ORDER_ID),
--rollback         COALESCE(:NEW.ACCOUNT_ID, :OLD.ACCOUNT_ID),
--rollback         COALESCE(:NEW.ACCOUNT_NUMBER, :OLD.ACCOUNT_NUMBER),
--rollback         COALESCE(:NEW.SITE_ID, :OLD.SITE_ID),
--rollback         COALESCE(:NEW.ORDER_TYPE, :OLD.ORDER_TYPE),
--rollback         COALESCE(:NEW.STATUS, :OLD.STATUS),
--rollback         COALESCE(:NEW.TTL_EXPIRES_AT, :OLD.TTL_EXPIRES_AT),
--rollback         COALESCE(:NEW.CREATED_DT, :OLD.CREATED_DT),
--rollback         COALESCE(:NEW.CREATED_BY, :OLD.CREATED_BY),
--rollback         COALESCE(:NEW.UPDATED_DT, :OLD.UPDATED_DT),
--rollback         COALESCE(:NEW.UPDATED_BY, :OLD.UPDATED_BY)
--rollback     );
--rollback END;
--rollback /

--changeset SOL_DATA:SOL_SERVICES.1.34.1.0.17-post

UPDATE LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER SET COUNT_AFTER_CHANGE = (select count (*) from DBA_TRIGGERS where OWNER = 'BILLING_EVENT'), STATUS = 'COMPLETED' WHERE CHANGESET_ID = 'SOL_SERVICES.1.34.1.0.17';
COMMIT;
--rollback UPDATE LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER SET STATUS = 'ROLLED_BACK', ROLLBACK_FLAG = 1 WHERE CHANGESET_ID = 'SOL_SERVICES.1.34.1.0.17';
