--liquibase formatted sql

--changeset agent:RB.001
--comment: Rollback of release 1.0 (reverse order of deploy scripts)

-- =====================================================
-- 1) Reverse 05_APP_SCHEMA_INVENTORY_ITEM_DML.sql (005)
-- Superseded: object(s) inventory_item are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 2) Reverse 04_APP_SCHEMA_SP_RESTOCK_PROC_DDL.sql (004)
-- =====================================================
DROP PROCEDURE sp_restock;

-- =====================================================
-- 3) Reverse 03_APP_SCHEMA_INVENTORY_ITEM_IDX_DDL.sql (003)
-- Superseded: object(s) idx_inventory_wh are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 4) Reverse 02_APP_SCHEMA_INVENTORY_ITEM_ALTER_DDL.sql (002)
-- Superseded: object(s) inventory_item are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 5) Reverse 01_APP_SCHEMA_INVENTORY_ITEM_DDL.sql (001)
-- =====================================================
DROP TABLE inventory_item;

-- Forward-only rollback script: to undo it, re-run the release deploy scripts.
--rollback SELECT 1;
