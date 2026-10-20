--liquibase formatted sql

--changeset agent:002
--comment: Modify Column, Add Column - inventory_item

ALTER TABLE inventory_item MODIFY COLUMN sku VARCHAR(30) NOT NULL;

ALTER TABLE inventory_item ADD COLUMN warehouse_id INT NULL AFTER sku;

--rollback ALTER TABLE inventory_item DROP COLUMN warehouse_id;
--rollback ALTER TABLE inventory_item MODIFY COLUMN sku VARCHAR(40) NOT NULL;
