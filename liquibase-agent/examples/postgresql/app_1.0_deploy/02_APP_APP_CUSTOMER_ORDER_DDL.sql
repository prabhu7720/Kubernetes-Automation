--liquibase formatted sql

--changeset agent:002
--comment: Create Table - customer_order

CREATE TABLE app.customer_order (
    order_id     BIGSERIAL PRIMARY KEY,
    customer_id  BIGINT NOT NULL REFERENCES app.customer (customer_id) ON DELETE CASCADE,
    amount       NUMERIC(12,2) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

--rollback DROP TABLE app.customer_order;
