from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
BRONZE = ROOT / "data" / "bronze"
SILVER = ROOT / "data" / "silver"
DATABASE_PATH = ROOT / "data" / "gold" / "ecommerce_star.duckdb"


def load_sources() -> tuple[pd.DataFrame, ...]:
    orders = pd.read_csv(
        BRONZE / "tb_orders.csv",
        parse_dates=["order_purchase_timestamp", "order_delivered_customer_date"],
    )
    items = pd.read_csv(BRONZE / "tb_order_items.csv")
    products = pd.read_csv(BRONZE / "tb_products_unstructured.csv")
    customers = pd.read_csv(SILVER / "tb_customers_aligned_synthetic.csv")
    reviews = pd.read_csv(
        SILVER / "tb_reviews_aligned_synthetic.csv",
        parse_dates=["review_created_at"],
    )
    product_feature_sample = pd.read_csv(SILVER / "tb_products_enriched_sample.csv")

    if not orders["order_id"].is_unique:
        raise ValueError("orders.order_id não é único.")
    if not items["order_id"].isin(orders["order_id"]).all():
        raise ValueError("Há itens com order_id sem correspondência nos pedidos.")
    if not items["product_id"].isin(products["product_id"]).all():
        raise ValueError("Há itens com product_id sem correspondência nos produtos.")
    if not customers["customer_id"].isin(orders["customer_id"]).all():
        raise ValueError("Há clientes alinhados sem correspondência nos pedidos.")
    if not reviews["order_id"].isin(orders["order_id"]).all():
        raise ValueError("Há avaliações alinhadas sem correspondência nos pedidos.")
    if not product_feature_sample["product_id"].is_unique:
        raise ValueError("product_id precisa ser único na amostra de features.")
    if not product_feature_sample["source_type"].eq("synthetic_demo_text").all():
        raise ValueError("A tabela de demonstração deve identificar sua origem sintética.")
    parsed_features = product_feature_sample["key_features_json"].map(json.loads)
    if not parsed_features.map(lambda value: isinstance(value, dict)).all():
        raise ValueError("key_features_json deve conter objetos JSON.")

    items["price"] = pd.to_numeric(items["price"], errors="raise")
    items["freight_value"] = pd.to_numeric(items["freight_value"], errors="raise")
    products["product_category_name_raw"] = products[
        "product_category_name_raw"
    ].fillna("Sem categoria").str.strip()
    products["title_raw"] = products["title_raw"].fillna("").str.strip()
    products["description_raw"] = products["description_raw"].fillna("").str.strip()
    customers["geography_key"] = customers["customer_state"] + "|" + customers["customer_city"]
    return orders, items, products, customers, reviews, product_feature_sample


def build_time_dimension(*date_series: pd.Series) -> pd.DataFrame:
    all_dates = pd.concat([pd.to_datetime(series, errors="coerce") for series in date_series])
    all_dates = all_dates.dropna().dt.normalize()
    calendar = pd.DataFrame(
        {"calendar_date": pd.date_range(all_dates.min(), all_dates.max(), freq="D")}
    )
    calendar["date_key"] = calendar["calendar_date"].dt.strftime("%Y%m%d").astype(int)
    calendar["year"] = calendar["calendar_date"].dt.year
    calendar["quarter"] = calendar["calendar_date"].dt.quarter
    calendar["month"] = calendar["calendar_date"].dt.month
    calendar["month_name"] = calendar["calendar_date"].dt.strftime("%B")
    calendar["day"] = calendar["calendar_date"].dt.day
    calendar["day_of_week"] = calendar["calendar_date"].dt.dayofweek + 1
    calendar["is_weekend"] = calendar["calendar_date"].dt.dayofweek >= 5
    return calendar


def build_model() -> None:
    orders, items, products, customers, reviews, product_feature_sample = load_sources()
    time_dimension = build_time_dimension(
        orders["order_purchase_timestamp"],
        orders["order_delivered_customer_date"],
        reviews["review_created_at"],
    )
    geography_dimension = customers[
        ["geography_key", "customer_state", "customer_city", "source_type"]
    ].drop_duplicates().reset_index(drop=True)
    customer_dimension = customers[
        ["customer_id", "geography_key", "source_type"]
    ].drop_duplicates("customer_id").rename(columns={"customer_id": "customer_key"})
    product_dimension = products[
        ["product_id", "product_category_name_raw", "title_raw", "description_raw"]
    ].rename(
        columns={
            "product_id": "product_key",
            "product_category_name_raw": "category_name",
            "title_raw": "product_title",
            "description_raw": "product_description",
        }
    )
    status_dimension = pd.DataFrame(
        {
            "status_key": sorted(orders["order_status"].dropna().unique()),
        }
    )
    status_dimension["status_description"] = status_dimension["status_key"].map(
        {
            "delivered": "Pedido entregue",
            "shipped": "Pedido enviado",
            "processing": "Pedido em processamento",
            "canceled": "Pedido cancelado",
        }
    )

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(DATABASE_PATH))
    try:
        for name, dataframe in {
            "_orders": orders,
            "_items": items,
            "_reviews": reviews,
            "_product_feature_sample": product_feature_sample,
            "_time_dimension": time_dimension,
            "_geography_dimension": geography_dimension,
            "_customer_dimension": customer_dimension,
            "_product_dimension": product_dimension,
            "_status_dimension": status_dimension,
        }.items():
            connection.register(name, dataframe)

        connection.execute("CREATE OR REPLACE TABLE dim_tempo AS SELECT * FROM _time_dimension")
        connection.execute("CREATE OR REPLACE TABLE dim_geolocalizacao AS SELECT * FROM _geography_dimension")
        connection.execute("CREATE OR REPLACE TABLE dim_cliente AS SELECT * FROM _customer_dimension")
        connection.execute("CREATE OR REPLACE TABLE dim_produto AS SELECT * FROM _product_dimension")
        connection.execute("CREATE OR REPLACE TABLE dim_status_pedido AS SELECT * FROM _status_dimension")
        connection.execute(
            """
            CREATE OR REPLACE TABLE tb_products_enriched_sample AS
            SELECT
                product_id,
                title_raw,
                description_raw,
                category_extracted,
                material_extracted,
                CAST(key_features_json AS JSON) AS key_features_json,
                source_type,
                extraction_method
            FROM _product_feature_sample
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE TABLE fato_pedidos AS
            WITH item_totals AS (
                SELECT
                    order_id,
                    COUNT(*)::INTEGER AS item_count,
                    SUM(price)::DECIMAL(18, 2) AS items_revenue,
                    SUM(freight_value)::DECIMAL(18, 2) AS freight_total
                FROM _items
                GROUP BY order_id
            )
            SELECT
                orders.order_id AS order_key,
                orders.customer_id AS customer_key,
                CAST(STRFTIME(orders.order_purchase_timestamp, '%Y%m%d') AS INTEGER) AS purchase_date_key,
                CASE
                    WHEN orders.order_delivered_customer_date IS NULL THEN NULL
                    ELSE CAST(STRFTIME(orders.order_delivered_customer_date, '%Y%m%d') AS INTEGER)
                END AS delivery_date_key,
                orders.order_status AS status_key,
                COALESCE(item_totals.item_count, 0) AS item_count,
                COALESCE(item_totals.items_revenue, 0)::DECIMAL(18, 2) AS items_revenue,
                COALESCE(item_totals.freight_total, 0)::DECIMAL(18, 2) AS freight_total
            FROM _orders AS orders
            LEFT JOIN item_totals USING (order_id)
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE TABLE fato_itens_pedido AS
            SELECT
                items.order_id AS order_key,
                items.order_item_id AS item_key,
                items.product_id AS product_key,
                orders.customer_id AS customer_key,
                CAST(STRFTIME(orders.order_purchase_timestamp, '%Y%m%d') AS INTEGER) AS purchase_date_key,
                orders.order_status AS status_key,
                items.price::DECIMAL(18, 2) AS item_price,
                items.freight_value::DECIMAL(18, 2) AS freight_value
            FROM _items AS items
            JOIN _orders AS orders USING (order_id)
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE TABLE fato_avaliacoes AS
            SELECT
                reviews.review_id AS review_key,
                reviews.order_id AS order_key,
                reviews.customer_id AS customer_key,
                CAST(STRFTIME(reviews.review_created_at, '%Y%m%d') AS INTEGER) AS review_date_key,
                reviews.review_score::INTEGER AS review_score,
                reviews.review_text,
                reviews.source_type
            FROM _reviews AS reviews
            JOIN _orders AS orders USING (order_id)
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW vw_analitico_pedidos AS
            SELECT
                fact.order_key AS order_id,
                calendar.calendar_date::TIMESTAMP AS purchase_date,
                fact.status_key AS order_status,
                status.status_description AS order_status_description,
                customer.customer_key AS customer_id,
                geography.customer_state,
                geography.customer_city,
                geography.source_type AS geography_source,
                fact.item_count,
                fact.items_revenue,
                fact.freight_total,
                fact.items_revenue + fact.freight_total AS order_total
            FROM fato_pedidos AS fact
            JOIN dim_tempo AS calendar ON calendar.date_key = fact.purchase_date_key
            JOIN dim_status_pedido AS status ON status.status_key = fact.status_key
            JOIN dim_cliente AS customer ON customer.customer_key = fact.customer_key
            JOIN dim_geolocalizacao AS geography ON geography.geography_key = customer.geography_key
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW vw_analitico_pedidos_itens AS
            SELECT
                item.order_key AS order_id,
                item.item_key AS order_item_id,
                calendar.calendar_date::TIMESTAMP AS purchase_date,
                item.status_key AS order_status,
                status.status_description AS order_status_description,
                customer.customer_key AS customer_id,
                geography.customer_state,
                geography.customer_city,
                product.product_key AS product_id,
                product.category_name,
                product.product_title,
                item.item_price,
                item.freight_value
            FROM fato_itens_pedido AS item
            JOIN dim_tempo AS calendar ON calendar.date_key = item.purchase_date_key
            JOIN dim_status_pedido AS status ON status.status_key = item.status_key
            JOIN dim_cliente AS customer ON customer.customer_key = item.customer_key
            JOIN dim_geolocalizacao AS geography ON geography.geography_key = customer.geography_key
            JOIN dim_produto AS product ON product.product_key = item.product_key
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW vw_analitico_avaliacoes AS
            SELECT
                review.review_key AS review_id,
                review.order_key AS order_id,
                calendar.calendar_date AS review_date,
                customer.customer_key AS customer_id,
                geography.customer_state,
                geography.customer_city,
                review.review_score,
                review.review_text,
                review.source_type
            FROM fato_avaliacoes AS review
            JOIN dim_tempo AS calendar ON calendar.date_key = review.review_date_key
            JOIN dim_cliente AS customer ON customer.customer_key = review.customer_key
            JOIN dim_geolocalizacao AS geography ON geography.geography_key = customer.geography_key
            """
        )

        expected_counts = {
            "fato_pedidos": len(orders),
            "fato_itens_pedido": len(items),
            "fato_avaliacoes": len(reviews),
            "tb_products_enriched_sample": len(product_feature_sample),
            "vw_analitico_pedidos": len(orders),
            "vw_analitico_pedidos_itens": len(items),
            "vw_analitico_avaliacoes": len(reviews),
        }
        for relation, expected_count in expected_counts.items():
            actual_count = connection.execute(f"SELECT COUNT(*) FROM {relation}").fetchone()[0]
            if actual_count != expected_count:
                raise AssertionError(f"{relation}: esperado {expected_count}, encontrado {actual_count}.")
            print(f"{relation}: {actual_count:,} linhas")
    finally:
        connection.close()

    print(f"DuckDB salvo em: {DATABASE_PATH.relative_to(ROOT)}")
    print("Geografia é sintética e ilustrativa; não contém coordenadas IBGE.")


if __name__ == "__main__":
    build_model()