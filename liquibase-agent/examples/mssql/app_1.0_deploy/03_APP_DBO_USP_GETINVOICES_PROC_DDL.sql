--liquibase formatted sql

--changeset agent:003 splitStatements:false
--comment: Create Procedure - usp_GetInvoices

CREATE OR ALTER PROCEDURE dbo.usp_GetInvoices
    @CustomerId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT InvoiceId, Amount, CreatedAt FROM dbo.Invoice WHERE CustomerId = @CustomerId;
END

-- =====================================================
-- Rollback notes:
-- CREATE OR REPLACE dbo.usp_GetInvoices without --baseline: the agent cannot know whether a previous version exists, so it will not generate a DROP that could delete a live object.
-- =====================================================
-- ROLLBACK-MANUAL: restore the previous definition of dbo.usp_GetInvoices (definition captured by the pre-check) or DROP PROCEDURE dbo.usp_GetInvoices if the object is new
