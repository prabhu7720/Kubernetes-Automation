-- PRE-DEPLOYMENT CHECKS - release 1.0 (postgresql)
-- Read-only queries. Compare each result with the expected value.

-- [release] Invalid objects BEFORE deploy in app | expected: baseline (record)
SELECT indexrelid::regclass AS invalid_index FROM pg_index WHERE NOT indisvalid;

-- [release] No stale Liquibase lock | expected: LOCKED = 0/false
SELECT * FROM DATABASECHANGELOGLOCK;

-- ---- step 1: CREATE_TABLE app.customer
-- app.customer must not exist yet | expected: 0
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'app' AND table_name = 'customer';

-- ---- step 2: CREATE_TABLE app.customer_order
-- app.customer_order must not exist yet | expected: 0
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'app' AND table_name = 'customer_order';
-- FK parent customer exists | expected: 1
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'app' AND table_name = 'customer';

-- ---- step 3: CREATE_INDEX app.idx_customer_order_created
-- Index idx_customer_order_created must not exist | expected: 0
SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'app' AND indexname = 'idx_customer_order_created';
-- Table customer_order exists | expected: 1
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'app' AND table_name = 'customer_order';

-- ---- step 4: ADD_COLUMN app.customer
-- customer.phone must not exist yet | expected: 0
SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'customer' AND column_name = 'phone';
-- customer.loyalty_points must not exist yet | expected: 0
SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'customer' AND column_name = 'loyalty_points';
-- NOT NULL add needs empty table or default | expected: 0 (or DEFAULT supplied)
SELECT COUNT(*) FROM app.customer;

-- ---- step 5: MODIFY_COLUMN app.customer
-- Current definition (rollback reference) | expected: record value
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'customer' AND column_name IN ('full_name');
-- NULLs would block NOT NULL on full_name | expected: 0
SELECT COUNT(*) FROM app.customer WHERE full_name IS NULL;
-- Dependent objects that will be invalidated | expected: review
SELECT DISTINCT dependent_view.relname AS dependent FROM pg_depend JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid JOIN pg_class dependent_view ON pg_rewrite.ev_class = dependent_view.oid JOIN pg_class src ON pg_depend.refobjid = src.oid WHERE src.relname = 'customer';

-- ---- step 6: CREATE_FUNCTION app.fn_touch_created
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema = 'app' AND routine_name = 'fn_touch_created';

-- ---- step 7: CREATE_TRIGGER app.trg_customer_touch
-- TRIGGER must not exist | expected: 0
SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema = 'app' AND trigger_name = 'trg_customer_touch';
-- Trigger table customer exists | expected: 1
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'app' AND table_name = 'customer';

-- ---- step 8: CREATE_VIEW app.active_customer_v
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'app' AND table_name = 'active_customer_v';

-- ---- step 9: DELETE app.customer
-- Rows affected by DELETE | expected: record value (expected volume)
SELECT COUNT(*) FROM app.customer WHERE status = 'blocked';

