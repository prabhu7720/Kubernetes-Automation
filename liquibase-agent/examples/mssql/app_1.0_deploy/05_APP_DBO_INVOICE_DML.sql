--liquibase formatted sql

--changeset agent:005-bkp
-- =====================================================
-- Backup of data affected by this change (used by rollback)
-- =====================================================
SELECT * INTO dbo.INVOICE_BKP6 FROM dbo.Invoice WHERE Amount < 0;
--rollback DROP TABLE dbo.INVOICE_BKP6;

--changeset agent:005
--comment: Update - Invoice

UPDATE dbo.Invoice SET Amount = 0 WHERE Amount < 0;

COMMIT;

-- =====================================================
-- Rollback notes:
-- Pre-update values restored from INVOICE_BKP6 by primary key.
-- =====================================================
--rollback MERGE INTO dbo.Invoice t USING dbo.INVOICE_BKP6 b ON (t.InvoiceId = b.InvoiceId) WHEN MATCHED THEN UPDATE SET t.Amount = b.Amount;
