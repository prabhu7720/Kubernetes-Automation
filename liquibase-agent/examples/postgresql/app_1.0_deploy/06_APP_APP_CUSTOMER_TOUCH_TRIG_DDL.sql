--liquibase formatted sql

--changeset agent:006 splitStatements:false
--comment: Create Trigger - trg_customer_touch

CREATE TRIGGER trg_customer_touch BEFORE INSERT ON app.customer
    FOR EACH ROW EXECUTE FUNCTION app.fn_touch_created()

--rollback DROP TRIGGER trg_customer_touch ON app.customer
--rollback /
