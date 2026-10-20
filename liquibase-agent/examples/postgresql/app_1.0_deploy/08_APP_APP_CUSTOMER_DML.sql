--liquibase formatted sql

--changeset agent:008-bkp
-- =====================================================
-- Backup of data affected by this change (used by rollback)
-- =====================================================
CREATE TABLE app.CUSTOMER_BKP9 AS SELECT * FROM app.customer WHERE status = 'blocked';
--rollback DROP TABLE app.CUSTOMER_BKP9;

--changeset agent:008
--comment: Delete - customer

DELETE FROM app.customer WHERE status = 'blocked';

COMMIT;

-- =====================================================
-- Rollback notes:
-- Deleted rows restored from CUSTOMER_BKP9.
-- =====================================================
--rollback INSERT INTO app.customer SELECT * FROM app.CUSTOMER_BKP9;
