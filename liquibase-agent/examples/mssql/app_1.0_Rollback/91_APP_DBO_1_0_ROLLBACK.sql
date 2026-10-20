--liquibase formatted sql

--changeset agent:RB.001
--comment: Rollback of release 1.0 (reverse order of deploy scripts)

-- =====================================================
-- 1) Reverse 05_APP_DBO_INVOICE_DML.sql (005)
-- Superseded: object(s) Invoice are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 2) Reverse 04_APP_DBO_INVOICE_AUDIT_TRIG_DDL.sql (004)
-- =====================================================
DROP TRIGGER dbo.trg_Invoice_Audit;

-- =====================================================
-- 3) Reverse 03_APP_DBO_USP_GETINVOICES_PROC_DDL.sql (003)
-- NOTE: CREATE OR REPLACE dbo.usp_GetInvoices without --baseline: the agent cannot know whether a previous version exists, so it will not generate a DROP that could delete a live object.
-- =====================================================
-- ROLLBACK-MANUAL: restore the previous definition of dbo.usp_GetInvoices (definition captured by the pre-check) or DROP PROCEDURE dbo.usp_GetInvoices if the object is new

-- =====================================================
-- 4) Reverse 02_APP_DBO_INVOICE_ADD_COLUMNS_ALTER_DDL.sql (002)
-- Superseded: object(s) Invoice are created in this release and dropped later in this script.
-- =====================================================

-- =====================================================
-- 5) Reverse 01_APP_DBO_INVOICE_DDL.sql (001)
-- =====================================================
DROP TABLE dbo.Invoice;

-- Forward-only rollback script: to undo it, re-run the release deploy scripts.
--rollback SELECT 1;
