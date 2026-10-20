--liquibase formatted sql

--changeset agent:004
--comment: Add Column, Modify Column - customer

ALTER TABLE app.customer ADD COLUMN phone VARCHAR(30), ADD COLUMN loyalty_points INTEGER NOT NULL DEFAULT 0;

ALTER TABLE app.customer ALTER COLUMN full_name SET NOT NULL;

--rollback ALTER TABLE app.customer ALTER COLUMN full_name DROP NOT NULL;
--rollback ALTER TABLE app.customer DROP COLUMN phone, DROP COLUMN loyalty_points;
