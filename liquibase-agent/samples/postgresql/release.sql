CREATE TABLE app.customer (
    customer_id   BIGSERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL,
    full_name     TEXT,
    status        VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uk_customer_email UNIQUE (email),
    CONSTRAINT chk_customer_status CHECK (status IN ('active', 'blocked'))
);

CREATE TABLE app.customer_order (
    order_id     BIGSERIAL PRIMARY KEY,
    customer_id  BIGINT NOT NULL REFERENCES app.customer (customer_id) ON DELETE CASCADE,
    amount       NUMERIC(12,2) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX CONCURRENTLY idx_customer_order_created ON app.customer_order (created_at DESC);

ALTER TABLE app.customer ADD COLUMN phone VARCHAR(30), ADD COLUMN loyalty_points INTEGER NOT NULL DEFAULT 0;
ALTER TABLE app.customer ALTER COLUMN full_name SET NOT NULL;

CREATE OR REPLACE FUNCTION app.fn_touch_created() RETURNS TRIGGER AS $$
BEGIN
    NEW.created_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customer_touch BEFORE INSERT ON app.customer
    FOR EACH ROW EXECUTE FUNCTION app.fn_touch_created();

CREATE OR REPLACE VIEW app.active_customer_v AS
SELECT customer_id, email, full_name FROM app.customer WHERE status = 'active';

DELETE FROM app.customer WHERE status = 'blocked';
