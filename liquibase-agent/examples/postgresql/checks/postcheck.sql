-- POST-DEPLOYMENT CHECKS - release 1.0 (postgresql)
-- Read-only queries. Compare each result with the expected value.

-- ---- step 1: CREATE_TABLE app.customer
-- app.customer created | expected: 1
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'app' AND table_name = 'customer';
-- Column definitions as designed | expected: 5 rows
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'customer' AND column_name IN ('customer_id', 'email', 'full_name', 'status', 'created_at');

-- ---- step 2: CREATE_TABLE app.customer_order
-- app.customer_order created | expected: 1
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'app' AND table_name = 'customer_order';
-- Column definitions as designed | expected: 4 rows
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'customer_order' AND column_name IN ('order_id', 'customer_id', 'amount', 'created_at');

-- ---- step 3: CREATE_INDEX app.idx_customer_order_created
-- Index idx_customer_order_created created | expected: 1
SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'app' AND indexname = 'idx_customer_order_created';

-- ---- step 4: ADD_COLUMN app.customer
-- customer.phone added | expected: 1
SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'customer' AND column_name = 'phone';
-- customer.loyalty_points added | expected: 1
SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'customer' AND column_name = 'loyalty_points';
-- No NULLs in loyalty_points | expected: 0
SELECT COUNT(*) FROM app.customer WHERE loyalty_points IS NULL;
-- New column definition | expected: as designed
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'customer' AND column_name IN ('phone', 'loyalty_points');

-- ---- step 5: MODIFY_COLUMN app.customer
-- New definition applied | expected: as designed
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'customer' AND column_name IN ('full_name');

-- ---- step 6: CREATE_FUNCTION app.fn_touch_created
-- FUNCTION fn_touch_created present | expected: 1
SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema = 'app' AND routine_name = 'fn_touch_created';

-- ---- step 7: CREATE_TRIGGER app.trg_customer_touch
-- TRIGGER trg_customer_touch present | expected: 1
SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema = 'app' AND trigger_name = 'trg_customer_touch';

-- ---- step 8: CREATE_VIEW app.active_customer_v
-- VIEW active_customer_v present | expected: 1
SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'app' AND table_name = 'active_customer_v';
-- View is queryable | expected: executes
SELECT COUNT(*) FROM app.active_customer_v WHERE 1 = 0;

-- ---- step 9: DELETE app.customer
-- Rows removed | expected: 0
SELECT COUNT(*) FROM app.customer WHERE status = 'blocked';
-- Total row count | expected: pre-count +/- expected delta
SELECT COUNT(*) FROM app.customer;

-- [release] Invalid objects in app | expected: 0 rows (or same as before deploy)
SELECT indexrelid::regclass AS invalid_index FROM pg_index WHERE NOT indisvalid;

-- [release] Liquibase history | expected: release changeSets EXECUTED
SELECT ID, AUTHOR, FILENAME, DATEEXECUTED, EXECTYPE FROM DATABASECHANGELOG ORDER BY ORDEREXECUTED DESC;

