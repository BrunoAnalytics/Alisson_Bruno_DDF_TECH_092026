SELECT
CAST(TRIM(order_id) AS VARCHAR(36)) AS order_id,
CAST(TRIM(customer_id) AS VARCHAR(36)) AS customer_id,
LOWER(TRIM(order_status)) AS order_status,
CAST(order_purchase_timestamp AS TIMESTAMP) AS order_purchase_timestamp,
CAST(order_delivered_customer_date AS TIMESTAMP) AS order_delivered_customer_date,
CURRENT_TIMESTAMP AS data_ingestao
FROM tb_orders_transacional_raw;