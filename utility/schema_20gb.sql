-- DROP OLD TABLES
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS shipments CASCADE;
DROP TABLE IF EXISTS inventory CASCADE;

-- USERS
DO $$
BEGIN
   IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mcpuser') THEN
      CREATE ROLE mcpuser LOGIN PASSWORD 'mcppassword';
   END IF;
END$$;

GRANT CONNECT ON DATABASE mcp_demo TO mcpuser;



-- BASE TABLES
CREATE TABLE customers (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE,
  country TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE categories (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE products (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  price NUMERIC(10,2),
  category_id INT REFERENCES categories(id)
);



-- ORDERS (PARTITIONED)
CREATE TABLE orders (
  id BIGSERIAL NOT NULL,
  customer_id BIGINT NOT NULL REFERENCES customers(id),
  order_date TIMESTAMP NOT NULL,
  status TEXT,
  total_amount NUMERIC(12,2),
  PRIMARY KEY (id, order_date)
) PARTITION BY RANGE (order_date);



-- ORDER ITEMS (PARTITIONED)
CREATE TABLE order_items (
  id BIGSERIAL,
  order_id BIGINT NOT NULL,
  order_date TIMESTAMP NOT NULL,
  product_id BIGINT NOT NULL REFERENCES products(id),
  quantity INT,
  price NUMERIC(10,2),
  PRIMARY KEY (id, order_date)
) PARTITION BY RANGE (order_date);



-- PAYMENTS  (NO order_date, NO FK)
CREATE TABLE payments (
  id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL,
  paid_at TIMESTAMP,
  amount NUMERIC(12,2),
  method TEXT
);



-- SHIPMENTS (NO FK, NO order_date)
CREATE TABLE shipments (
  id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL,
  shipped_at TIMESTAMP,
  carrier TEXT,
  tracking_number TEXT
);



-- INVENTORY
CREATE TABLE inventory (
  id BIGSERIAL PRIMARY KEY,
  product_id BIGINT NOT NULL REFERENCES products(id),
  warehouse TEXT,
  quantity INT,
  updated_at TIMESTAMP DEFAULT now()
);



-- INDEXES
CREATE INDEX idx_customers_country ON customers(country);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_payments_order ON payments(order_id);
CREATE INDEX idx_shipments_order ON shipments(order_id);
CREATE INDEX idx_inventory_product ON inventory(product_id);



-- GRANTS
GRANT USAGE ON SCHEMA public TO mcpuser;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcpuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcpuser;