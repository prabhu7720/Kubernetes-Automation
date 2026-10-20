--liquibase formatted sql

--changeset agent:001
--comment: Create Table - inventory_item

-- =====================================================
-- MariaDB 10.6 release
-- =====================================================
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

--rollback DROP TABLE inventory_item;
