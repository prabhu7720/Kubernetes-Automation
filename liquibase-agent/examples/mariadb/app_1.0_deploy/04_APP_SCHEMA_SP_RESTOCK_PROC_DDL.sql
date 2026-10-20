--liquibase formatted sql

--changeset agent:004 splitStatements:false
--comment: Create Procedure - sp_restock

CREATE PROCEDURE sp_restock(IN p_item INT, IN p_qty INT)
BEGIN
  IF p_qty > 0 THEN
    UPDATE inventory_item SET qty = qty + p_qty WHERE item_id = p_item;
  END IF;
END

--rollback DROP PROCEDURE sp_restock
--rollback /
