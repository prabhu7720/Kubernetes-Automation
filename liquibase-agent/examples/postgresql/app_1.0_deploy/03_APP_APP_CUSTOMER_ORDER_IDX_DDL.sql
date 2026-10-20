--liquibase formatted sql

--changeset agent:003 runInTransaction:false
--comment: Create Index - idx_customer_order_created

CREATE INDEX CONCURRENTLY idx_customer_order_created ON app.customer_order (created_at DESC);

--rollback DROP INDEX app.idx_customer_order_created;
