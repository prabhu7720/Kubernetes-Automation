-- MariaDB 10.6 release
CREATE TABLE `inventory_item` (
  `item_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `sku` VARCHAR(40) NOT NULL,
  `qty` INT NOT NULL DEFAULT 0,
  `price` DECIMAL(10,2) NOT NULL,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`item_id`),
  UNIQUE KEY `uk_inventory_sku` (`sku`),
  KEY `idx_inventory_qty` (`qty`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Stock items';

ALTER TABLE inventory_item MODIFY COLUMN sku VARCHAR(30) NOT NULL;
ALTER TABLE inventory_item ADD COLUMN warehouse_id INT NULL AFTER sku;
CREATE INDEX idx_inventory_wh ON inventory_item (warehouse_id);

DELIMITER $$
CREATE PROCEDURE sp_restock(IN p_item INT, IN p_qty INT)
BEGIN
  IF p_qty > 0 THEN
    UPDATE inventory_item SET qty = qty + p_qty WHERE item_id = p_item;
  END IF;
END$$
DELIMITER ;

INSERT INTO inventory_item (sku, qty, price) VALUES ('SKU-001', 10, 9.99);
