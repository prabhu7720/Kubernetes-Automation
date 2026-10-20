--liquibase formatted sql

--changeset agent:003
--comment: Create Index - idx_inventory_wh

CREATE INDEX idx_inventory_wh ON inventory_item (warehouse_id);

--rollback DROP INDEX idx_inventory_wh ON inventory_item;
