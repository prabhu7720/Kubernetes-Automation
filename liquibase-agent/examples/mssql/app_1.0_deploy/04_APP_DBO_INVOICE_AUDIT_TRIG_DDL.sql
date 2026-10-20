--liquibase formatted sql

--changeset agent:004 splitStatements:false
--comment: Create Trigger - trg_Invoice_Audit

CREATE TRIGGER dbo.trg_Invoice_Audit ON dbo.Invoice AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO dbo.InvoiceAudit (InvoiceId, ChangedAt) SELECT InvoiceId, GETDATE() FROM inserted;
END

--rollback DROP TRIGGER dbo.trg_Invoice_Audit
--rollback /
