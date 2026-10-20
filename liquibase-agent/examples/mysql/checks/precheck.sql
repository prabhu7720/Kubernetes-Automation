-- PRE-DEPLOYMENT CHECKS - release 1.0 (mysql)
-- Read-only queries. Compare each result with the expected value.

-- [release] No stale Liquibase lock | expected: LOCKED = 0/false
SELECT * FROM DATABASECHANGELOGLOCK;

-- ---- step 1: CREATE_TABLE inventory_item
-- inventory_item must not exist yet | expected: 0
SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_item' AND TABLE_TYPE = 'BASE TABLE';

-- ---- step 2: MODIFY_COLUMN inventory_item
-- Current definition (rollback reference) | expected: record value
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, column_default FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'inventory_item' AND column_name IN ('sku');
-- NULLs would block NOT NULL on sku | expected: 0
SELECT COUNT(*) FROM inventory_item WHERE sku IS NULL;
-- Longest existing value fits new size | expected: <= new length of VARCHAR(30)
SELECT MAX(LENGTH(sku)) FROM inventory_item;
-- Dependent objects that will be invalidated | expected: review
SELECT TABLE_NAME FROM information_schema.VIEWS WHERE TABLE_SCHEMA = DATABASE() AND VIEW_DEFINITION LIKE '%inventory_item%';

-- ---- step 3: ADD_COLUMN inventory_item
-- inventory_item.warehouse_id must not exist yet | expected: 0
SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'inventory_item' AND column_name = 'warehouse_id';

-- ---- step 4: CREATE_INDEX idx_inventory_wh
-- Index idx_inventory_wh must not exist | expected: 0
SELECT COUNT(DISTINCT INDEX_NAME) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND INDEX_NAME = 'idx_inventory_wh' AND TABLE_NAME = 'inventory_item';
-- Table inventory_item exists | expected: 1
SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_item' AND TABLE_TYPE = 'BASE TABLE';

-- ---- step 5: CREATE_PROCEDURE sp_restock
-- PROCEDURE must not exist | expected: 0
SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_NAME = 'sp_restock';

-- ---- step 6: INSERT inventory_item
-- Rows affected by INSERT | expected: record value (expected volume)
SELECT COUNT(*) FROM inventory_item;
-- Row not already present (idempotency) | expected: 0
SELECT COUNT(*) FROM inventory_item WHERE sku = 'SKU-001' AND qty = 10 AND price = 9.99;

