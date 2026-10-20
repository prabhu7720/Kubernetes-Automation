-- POST-DEPLOYMENT CHECKS - release 1.0 (mssql)
-- Read-only queries. Compare each result with the expected value.

-- ---- step 1: CREATE_TABLE dbo.Invoice
-- dbo.Invoice created | expected: 1
SELECT CASE WHEN OBJECT_ID('dbo.Invoice', 'U') IS NULL THEN 0 ELSE 1 END;
-- Column definitions as designed | expected: 4 rows
SELECT c.name, ty.name AS data_type, c.max_length, c.precision, c.scale, c.is_nullable FROM sys.columns c JOIN sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('dbo.Invoice') AND c.name IN ('InvoiceId', 'CustomerId', 'Amount', 'CreatedAt');

-- ---- step 2: CREATE_INDEX dbo.IX_Invoice_Customer
-- Index IX_Invoice_Customer created | expected: 1
SELECT COUNT(*) FROM sys.indexes WHERE name = 'IX_Invoice_Customer' AND object_id = OBJECT_ID('dbo.Invoice');

-- ---- step 3: ADD_COLUMN dbo.Invoice
-- Invoice.Notes added | expected: 1
SELECT CASE WHEN COL_LENGTH('dbo.Invoice', 'Notes') IS NULL THEN 0 ELSE 1 END;
-- New column definition | expected: as designed
SELECT c.name, ty.name AS data_type, c.max_length, c.precision, c.scale, c.is_nullable FROM sys.columns c JOIN sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('dbo.Invoice') AND c.name IN ('Notes');

-- ---- step 4: CREATE_PROCEDURE dbo.usp_GetInvoices
-- PROCEDURE usp_GetInvoices present | expected: 1
SELECT CASE WHEN OBJECT_ID('dbo.usp_GetInvoices', 'P') IS NULL THEN 0 ELSE 1 END;

-- ---- step 5: CREATE_TRIGGER dbo.trg_Invoice_Audit
-- TRIGGER trg_Invoice_Audit present | expected: 1
SELECT CASE WHEN OBJECT_ID('dbo.trg_Invoice_Audit', 'TR') IS NULL THEN 0 ELSE 1 END;

-- ---- step 6: UPDATE dbo.Invoice
-- Rows still matching predicate | expected: same as pre-check
SELECT COUNT(*) FROM dbo.Invoice WHERE Amount < 0;
-- Total row count | expected: pre-count +/- expected delta
SELECT COUNT(*) FROM dbo.Invoice;

-- [release] Liquibase history | expected: release changeSets EXECUTED
SELECT ID, AUTHOR, FILENAME, DATEEXECUTED, EXECTYPE FROM DATABASECHANGELOG ORDER BY ORDEREXECUTED DESC;

