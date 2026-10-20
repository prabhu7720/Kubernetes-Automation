-- POST-DEPLOYMENT CHECKS - release 1.0 (mariadb)
-- Read-only queries. Compare each result with the expected value.

-- ---- step 1: CREATE_TABLE inventory_item
-- inventory_item created | expected: 1
SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_item' AND TABLE_TYPE = 'BASE TABLE';
-- Column definitions as designed | expected: 5 rows
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, column_default FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'inventory_item' AND column_name IN ('item_id', 'sku', 'qty', 'price', 'updated_at');

-- ---- step 2: MODIFY_COLUMN inventory_item
-- New definition applied | expected: as designed
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, column_default FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'inventory_item' AND column_name IN ('sku');

-- ---- step 3: ADD_COLUMN inventory_item
-- inventory_item.warehouse_id added | expected: 1
SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'inventory_item' AND column_name = 'warehouse_id';
-- New column definition | expected: as designed
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, column_default FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'inventory_item' AND column_name IN ('warehouse_id');

-- ---- step 4: CREATE_INDEX idx_inventory_wh
-- Index idx_inventory_wh created | expected: 1
SELECT COUNT(DISTINCT INDEX_NAME) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND INDEX_NAME = 'idx_inventory_wh' AND TABLE_NAME = 'inventory_item';

-- ---- step 5: CREATE_PROCEDURE sp_restock
-- PROCEDURE sp_restock present | expected: 1
SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_NAME = 'sp_restock';

-- ---- step 6: INSERT inventory_item
-- Row inserted | expected: 1
SELECT COUNT(*) FROM inventory_item WHERE sku = 'SKU-001' AND qty = 10 AND price = 9.99;
-- Total row count | expected: pre-count +/- expected delta
SELECT COUNT(*) FROM inventory_item;

-- [release] Liquibase history | expected: release changeSets EXECUTED
SELECT ID, AUTHOR, FILENAME, DATEEXECUTED, EXECTYPE FROM DATABASECHANGELOG ORDER BY ORDEREXECUTED DESC;

