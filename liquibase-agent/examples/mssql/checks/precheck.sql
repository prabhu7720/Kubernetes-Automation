-- PRE-DEPLOYMENT CHECKS - release 1.0 (mssql)
-- Read-only queries. Compare each result with the expected value.

-- [release] No stale Liquibase lock | expected: LOCKED = 0/false
SELECT * FROM DATABASECHANGELOGLOCK;

-- ---- step 1: CREATE_TABLE dbo.Invoice
-- dbo.Invoice must not exist yet | expected: 0
SELECT CASE WHEN OBJECT_ID('dbo.Invoice', 'U') IS NULL THEN 0 ELSE 1 END;

-- ---- step 2: CREATE_INDEX dbo.IX_Invoice_Customer
-- Index IX_Invoice_Customer must not exist | expected: 0
SELECT COUNT(*) FROM sys.indexes WHERE name = 'IX_Invoice_Customer' AND object_id = OBJECT_ID('dbo.Invoice');
-- Table Invoice exists | expected: 1
SELECT CASE WHEN OBJECT_ID('dbo.Invoice', 'U') IS NULL THEN 0 ELSE 1 END;

-- ---- step 3: ADD_COLUMN dbo.Invoice
-- Invoice.Notes must not exist yet | expected: 0
SELECT CASE WHEN COL_LENGTH('dbo.Invoice', 'Notes') IS NULL THEN 0 ELSE 1 END;

-- ---- step 4: CREATE_PROCEDURE dbo.usp_GetInvoices
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT CASE WHEN OBJECT_ID('dbo.usp_GetInvoices', 'P') IS NULL THEN 0 ELSE 1 END;

-- ---- step 5: CREATE_TRIGGER dbo.trg_Invoice_Audit
-- TRIGGER must not exist | expected: 0
SELECT CASE WHEN OBJECT_ID('dbo.trg_Invoice_Audit', 'TR') IS NULL THEN 0 ELSE 1 END;
-- Trigger table Invoice exists | expected: 1
SELECT CASE WHEN OBJECT_ID('dbo.Invoice', 'U') IS NULL THEN 0 ELSE 1 END;

-- ---- step 6: UPDATE dbo.Invoice
-- Rows affected by UPDATE | expected: record value (expected volume)
SELECT COUNT(*) FROM dbo.Invoice WHERE Amount < 0;

