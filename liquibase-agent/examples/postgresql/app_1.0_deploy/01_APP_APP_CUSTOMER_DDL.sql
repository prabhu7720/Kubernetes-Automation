--liquibase formatted sql

--changeset agent:001
--comment: Create Table - customer

CREATE TABLE app.customer (
    customer_id   BIGSERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL,
    full_name     TEXT,
    status        VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uk_customer_email UNIQUE (email),
    CONSTRAINT chk_customer_status CHECK (status IN ('active', 'blocked'))
);

--rollback DROP TABLE app.customer;
