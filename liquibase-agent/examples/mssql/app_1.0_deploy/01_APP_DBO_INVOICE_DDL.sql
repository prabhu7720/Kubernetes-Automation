--liquibase formatted sql

--changeset agent:001
--comment: Create Table, Create Index - Invoice, IX_Invoice_Customer

CREATE TABLE dbo.Invoice (
    InvoiceId   INT IDENTITY(1,1) NOT NULL,
    CustomerId  INT NOT NULL,
    Amount      DECIMAL(12,2) NOT NULL,
    CreatedAt   DATETIME2 NOT NULL CONSTRAINT DF_Invoice_CreatedAt DEFAULT GETDATE(),
    CONSTRAINT PK_Invoice PRIMARY KEY CLUSTERED (InvoiceId)
);

CREATE NONCLUSTERED INDEX IX_Invoice_Customer ON dbo.Invoice (CustomerId);

--rollback DROP TABLE dbo.Invoice;
