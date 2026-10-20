--liquibase formatted sql

--changeset agent:002
--comment: Add Column - Invoice

ALTER TABLE dbo.Invoice ADD Notes NVARCHAR(MAX) NULL;

--rollback ALTER TABLE dbo.Invoice DROP COLUMN Notes;
