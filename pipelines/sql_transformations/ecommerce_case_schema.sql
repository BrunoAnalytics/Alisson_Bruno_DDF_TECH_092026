CREATE TABLE IF NOT EXISTS tb_orders_transacional_raw (
    order_id VARCHAR(36),
    customer_id VARCHAR(36),
    order_status VARCHAR(50),
    order_purchase_timestamp TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    data_ingestao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_order_items_raw (
    order_id VARCHAR(36),
    order_item_id INTEGER,
    product_id VARCHAR(36),
    price NUMERIC(18,2),
    freight_value NUMERIC(18,2),
    data_ingestao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_products_unstructured_raw (
    product_id VARCHAR(36),
    product_category_name_raw VARCHAR(255),
    title_raw TEXT,
    description_raw TEXT,
    data_ingestao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_customers_raw (
    customer_id VARCHAR(36),
    customer_state VARCHAR(100),
    customer_city VARCHAR(150),
    customer_segment VARCHAR(50),
    customer_channel VARCHAR(50),
    data_ingestao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_payments_raw (
    payment_id VARCHAR(36),
    order_id VARCHAR(36),
    payment_type VARCHAR(50),
    payment_value NUMERIC(18,2),
    payment_status VARCHAR(50),
    data_ingestao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_reviews_raw (
    order_id VARCHAR(36),
    customer_id VARCHAR(36),
    review_score INTEGER,
    review_text TEXT,
    review_created_at TIMESTAMP,
    data_ingestao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE VIEW vw_orders_clean AS
SELECT
    CAST(TRIM(order_id) AS VARCHAR(36)) AS order_id,
    CAST(TRIM(customer_id) AS VARCHAR(36)) AS customer_id,
    LOWER(TRIM(order_status)) AS order_status,
    CAST(order_purchase_timestamp AS TIMESTAMP) AS order_purchase_timestamp,
    CAST(order_delivered_customer_date AS TIMESTAMP) AS order_delivered_customer_date,
    CURRENT_TIMESTAMP AS data_ingestao
FROM tb_orders_transacional_raw;

CREATE OR REPLACE VIEW vw_order_items_clean AS
SELECT
    CAST(TRIM(order_id) AS VARCHAR(36)) AS order_id,
    CAST(order_item_id AS INTEGER) AS order_item_id,
    CAST(TRIM(product_id) AS VARCHAR(36)) AS product_id,
    CAST(price AS NUMERIC(18,2)) AS price,
    CAST(freight_value AS NUMERIC(18,2)) AS freight_value,
    CURRENT_TIMESTAMP AS data_ingestao
FROM tb_order_items_raw;

CREATE OR REPLACE VIEW vw_products_unstructured_clean AS
SELECT
    CAST(TRIM(product_id) AS VARCHAR(36)) AS product_id,
    TRIM(product_category_name_raw) AS product_category_name_raw,
    TRIM(title_raw) AS title_raw,
    TRIM(description_raw) AS description_raw,
    CURRENT_TIMESTAMP AS data_ingestao
FROM tb_products_unstructured_raw;
