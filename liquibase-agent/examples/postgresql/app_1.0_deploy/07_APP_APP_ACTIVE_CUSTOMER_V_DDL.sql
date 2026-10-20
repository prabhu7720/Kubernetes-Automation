--liquibase formatted sql

--changeset agent:007
--comment: Create View - active_customer_v

CREATE OR REPLACE VIEW app.active_customer_v AS
SELECT customer_id, email, full_name FROM app.customer WHERE status = 'active';

-- =====================================================
-- Rollback notes:
-- CREATE OR REPLACE app.active_customer_v without --baseline: the agent cannot know whether a previous version exists, so it will not generate a DROP that could delete a live object.
-- =====================================================
-- ROLLBACK-MANUAL: restore the previous definition of app.active_customer_v (definition captured by the pre-check) or DROP VIEW app.active_customer_v if the object is new
