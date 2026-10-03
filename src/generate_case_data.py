from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import random
import uuid

import pandas as pd
from faker import Faker

SEED = 20260929
N_ORDERS = 100_000
ITEMS_PER_ORDER = 2
N_PRODUCTS = 5_000

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "bronze"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")

CATEGORIES = ["home", "electronics", "kitchen", "sports", "beauty", "books", "fashion"]
ORDER_STATUSES = ["delivered", "shipped", "processing", "canceled"]
STATUS_WEIGHTS = [0.82, 0.08, 0.07, 0.03]
PAYMENT_TYPES = ["credit_card", "debit_card", "boleto", "pix", "voucher"]


def generate_products() -> pd.DataFrame:
    product_ids = [str(uuid.uuid4()) for _ in range(N_PRODUCTS)]
    rows = []
    for product_id in product_ids:
        category = random.choice(CATEGORIES)
        rows.append(
            {
                "product_id": product_id,
                "product_category_name_raw": f"  {category.title()}  ",
                "title_raw": f"{fake.catch_phrase()} {fake.word().title()}",
                "description_raw": fake.paragraph(nb_sentences=8),
            }
        )
    return pd.DataFrame(rows)


def generate_orders_and_items(product_ids: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    orders = []
    order_items = []
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2026, 8, 31)

    for _ in range(N_ORDERS):
        order_id = str(uuid.uuid4())
        customer_id = str(uuid.uuid4())
        purchase_time = fake.date_time_between(start_date=start_date, end_date=end_date)
        status = random.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        delivered_time = (
            purchase_time + timedelta(days=random.randint(1, 20))
            if status == "delivered"
            else None
        )

        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "order_status": status,
                "order_purchase_timestamp": purchase_time,
                "order_delivered_customer_date": delivered_time,
            }
        )

        for item_id in range(1, ITEMS_PER_ORDER + 1):
            item_price = round(random.uniform(5, 1500), 2)
            freight = round(random.uniform(0, 120), 2)
            order_items.append(
                {
                    "order_id": order_id,
                    "order_item_id": item_id,
                    "product_id": random.choice(product_ids),
                    "price": item_price,
                    "freight_value": freight,
                }
            )

    return pd.DataFrame(orders), pd.DataFrame(order_items)


def generate_customers(order_rows: list[dict]) -> pd.DataFrame:
    rows = []
    for order in order_rows:
        customer_id = order["customer_id"]
        rows.append(
            {
                "customer_id": customer_id,
                "customer_state": fake.state_abbr(),
                "customer_city": fake.city(),
                "customer_segment": random.choice(["new", "returning", "vip"]),
                "customer_channel": random.choice(["web", "mobile", "marketplace", "store"]),
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["customer_id"]).reset_index(drop=True)


def generate_payments(order_rows: list[dict], order_items_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grouped = order_items_df.groupby("order_id")["price"].sum().to_dict()
    for order in order_rows:
        order_id = order["order_id"]
        payment_type = random.choice(PAYMENT_TYPES)
        value = round(grouped.get(order_id, 0.0) + random.uniform(0, 100), 2)
        rows.append(
            {
                "payment_id": str(uuid.uuid4()),
                "order_id": order_id,
                "payment_type": payment_type,
                "payment_value": value,
                "payment_status": random.choice(["approved", "pending", "refused"]),
            }
        )
    return pd.DataFrame(rows)


def generate_reviews(order_rows: list[dict]) -> pd.DataFrame:
    rows = []
    for order in order_rows:
        if random.random() < 0.4:
            rows.append(
                {
                    "order_id": order["order_id"],
                    "customer_id": order["customer_id"],
                    "review_score": random.randint(1, 5),
                    "review_text": fake.paragraph(nb_sentences=3),
                    "review_created_at": fake.date_time_between(start_date=datetime(2025, 1, 1), end_date=datetime(2026, 8, 31)),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    product_df = generate_products()
    orders_df, order_items_df = generate_orders_and_items(product_df["product_id"].tolist())
    customers_df = generate_customers(orders_df.to_dict(orient="records"))
    payments_df = generate_payments(orders_df.to_dict(orient="records"), order_items_df)
    reviews_df = generate_reviews(orders_df.to_dict(orient="records"))

    datasets = {
        "tb_orders.csv": orders_df,
        "tb_order_items.csv": order_items_df,
        "tb_products_unstructured.csv": product_df,
        "tb_customers.csv": customers_df,
        "tb_payments.csv": payments_df,
        "tb_reviews.csv": reviews_df,
    }

    for filename, dataframe in datasets.items():
        dataframe.to_csv(OUTPUT_DIR / filename, index=False, encoding="utf-8")
        print(f"{filename}: {len(dataframe):,} registros")

    assert len(orders_df) == N_ORDERS
    assert len(order_items_df) == N_ORDERS * ITEMS_PER_ORDER
    assert len(product_df) == N_PRODUCTS
    assert len(customers_df) <= N_ORDERS
    assert len(payments_df) == N_ORDERS
    assert orders_df["order_id"].is_unique
    assert order_items_df.columns.tolist() == ["order_id", "order_item_id", "product_id", "price", "freight_value"]
    assert product_df.columns.tolist() == ["product_id", "product_category_name_raw", "title_raw", "description_raw"]

    print(f"\nTotal de registros: {sum(len(df) for df in datasets.values()):,}")
    print("Base sintética do case e bônus gerada com sucesso.")


if __name__ == "__main__":
    main()
