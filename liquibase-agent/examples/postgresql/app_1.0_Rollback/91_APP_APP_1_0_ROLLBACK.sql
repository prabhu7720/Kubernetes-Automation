--liquibase formatted sql

--changeset agent:RB.001
--comment: Rollback of release 1.0 (reverse order of deploy scripts)

-- =====================================================
-- 1) Reverse 08_APP_APP_CUSTOMER_DML.sql (008)
-- Superseded: object(s) customer are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 2) Reverse 07_APP_APP_ACTIVE_CUSTOMER_V_DDL.sql (007)
-- NOTE: CREATE OR REPLACE app.active_customer_v without --baseline: the agent cannot know whether a previous version exists, so it will not generate a DROP that could delete a live object.
-- =====================================================
-- ROLLBACK-MANUAL: restore the previous definition of app.active_customer_v (definition captured by the pre-check) or DROP VIEW app.active_customer_v if the object is new

-- =====================================================
-- 3) Reverse 06_APP_APP_CUSTOMER_TOUCH_TRIG_DDL.sql (006)
-- =====================================================
DROP TRIGGER trg_customer_touch ON app.customer;

-- =====================================================
-- 4) Reverse 05_APP_APP_FN_TOUCH_CREATED_FUNC_DDL.sql (005)
-- NOTE: CREATE OR REPLACE app.fn_touch_created without --baseline: the agent cannot know whether a previous version exists, so it will not generate a DROP that could delete a live object.
-- =====================================================
-- ROLLBACK-MANUAL: restore the previous definition of app.fn_touch_created (definition captured by the pre-check) or DROP FUNCTION app.fn_touch_created if the object is new

-- =====================================================
-- 5) Reverse 04_APP_APP_CUSTOMER_ALTER_DDL.sql (004)
-- Superseded: object(s) customer are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 6) Reverse 03_APP_APP_CUSTOMER_ORDER_IDX_DDL.sql (003)
-- Superseded: object(s) idx_customer_order_created are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 7) Reverse 02_APP_APP_CUSTOMER_ORDER_DDL.sql (002)
-- =====================================================
DROP TABLE app.customer_order;

-- =====================================================
-- 8) Reverse 01_APP_APP_CUSTOMER_DDL.sql (001)
-- =====================================================
DROP TABLE app.customer;

-- Forward-only rollback script: to undo it, re-run the release deploy scripts.
--rollback SELECT 1;
