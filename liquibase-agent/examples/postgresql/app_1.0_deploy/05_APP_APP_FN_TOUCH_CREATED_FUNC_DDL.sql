--liquibase formatted sql

--changeset agent:005 splitStatements:false
--comment: Create Function - fn_touch_created

CREATE OR REPLACE FUNCTION app.fn_touch_created() RETURNS TRIGGER AS $$
BEGIN
    NEW.created_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql

-- =====================================================
-- Rollback notes:
-- CREATE OR REPLACE app.fn_touch_created without --baseline: the agent cannot know whether a previous version exists, so it will not generate a DROP that could delete a live object.
-- =====================================================
-- ROLLBACK-MANUAL: restore the previous definition of app.fn_touch_created (definition captured by the pre-check) or DROP FUNCTION app.fn_touch_created if the object is new
