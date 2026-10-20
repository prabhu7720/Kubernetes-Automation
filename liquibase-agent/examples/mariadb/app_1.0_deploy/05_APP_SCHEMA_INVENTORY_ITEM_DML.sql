--liquibase formatted sql

--changeset agent:005
--comment: Insert - inventory_item

INSERT INTO inventory_item (sku, qty, price) VALUES ('SKU-001', 10, 9.99);

COMMIT;

--rollback DELETE FROM inventory_item WHERE sku = 'SKU-001' AND qty = 10 AND price = 9.99;
