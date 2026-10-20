CREATE TABLE dbo.Invoice (
    InvoiceId   INT IDENTITY(1,1) NOT NULL,
    CustomerId  INT NOT NULL,
    Amount      DECIMAL(12,2) NOT NULL,
    CreatedAt   DATETIME2 NOT NULL CONSTRAINT DF_Invoice_CreatedAt DEFAULT GETDATE(),
    CONSTRAINT PK_Invoice PRIMARY KEY CLUSTERED (InvoiceId)
);
GO
CREATE NONCLUSTERED INDEX IX_Invoice_Customer ON dbo.Invoice (CustomerId);
GO
ALTER TABLE dbo.Invoice ADD Notes NVARCHAR(MAX) NULL;
GO
CREATE OR ALTER PROCEDURE dbo.usp_GetInvoices
    @CustomerId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT InvoiceId, Amount, CreatedAt FROM dbo.Invoice WHERE CustomerId = @CustomerId;
END
GO
CREATE TRIGGER dbo.trg_Invoice_Audit ON dbo.Invoice AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO dbo.InvoiceAudit (InvoiceId, ChangedAt) SELECT InvoiceId, GETDATE() FROM inserted;
END
GO
UPDATE dbo.Invoice SET Amount = 0 WHERE Amount < 0;
GO
