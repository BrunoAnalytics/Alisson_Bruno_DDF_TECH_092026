from pathlib import Path
import json

import pandas as pd
import plotly.express as px

ROOT = Path(__file__).resolve().parent.parent
BRONZE = ROOT / "data" / "bronze"
DASHBOARD_DIR = ROOT / "data" / "dashboard"
CATALOG_PATH = ROOT / "data" / "catalog" / "catalog_index.json"
CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

TABLE_METADATA = {
    "tb_orders.csv": {
        "description": "Pedidos sintéticos do e-commerce; um registro por pedido.",
        "tags": ["ecommerce", "orders", "transactional", "synthetic"],
        "quality_rules": ["order_id único", "customer_id preenchido", "order_status no domínio esperado"],
    },
    "tb_order_items.csv": {
        "description": "Itens sintéticos associados aos pedidos; um registro por linha de pedido.",
        "tags": ["ecommerce", "order-items", "transactional", "synthetic"],
        "quality_rules": ["order_id existente em tb_orders", "product_id existente em tb_products_unstructured", "price e freight_value não negativos"],
    },
    "tb_products_unstructured.csv": {
        "description": "Produtos sintéticos com categoria, título e descrição textual livre.",
        "tags": ["ecommerce", "products", "text", "synthetic"],
        "quality_rules": ["product_id único", "título e descrição não vazios"],
    },
    "tb_customers.csv": {
        "description": "Perfis sintéticos de clientes, região e canal de compra.",
        "tags": ["ecommerce", "customers", "synthetic"],
        "quality_rules": ["customer_id único", "relacionamento com tb_orders a validar"],
    },
    "tb_payments.csv": {
        "description": "Pagamentos sintéticos associados a pedidos.",
        "tags": ["ecommerce", "payments", "synthetic"],
        "quality_rules": ["payment_id único", "order_id existente em tb_orders a validar", "payment_value não negativo"],
    },
    "tb_reviews.csv": {
        "description": "Avaliações sintéticas com nota e comentário textual.",
        "tags": ["ecommerce", "reviews", "text", "synthetic"],
        "quality_rules": ["review_score entre 1 e 5", "order_id existente em tb_orders a validar", "review_text não vazio"],
    },
}

COLUMN_DESCRIPTIONS = {
    "order_id": "Identificador do pedido.",
    "customer_id": "Identificador sintético do cliente associado ao pedido.",
    "order_status": "Status operacional do pedido.",
    "order_purchase_timestamp": "Data e hora em que o pedido foi realizado.",
    "order_delivered_customer_date": "Data e hora da entrega; pode ficar vazia para pedidos não entregues.",
    "order_item_id": "Sequência do item dentro do pedido.",
    "product_id": "Identificador do produto associado ao item.",
    "price": "Preço do item, em reais no cenário sintético.",
    "freight_value": "Valor de frete do item, em reais no cenário sintético.",
    "product_category_name_raw": "Categoria original do produto, mantida como texto bruto.",
    "title_raw": "Título textual original do produto.",
    "description_raw": "Descrição textual original do produto.",
    "customer_state": "Sigla de estado sintética do cliente.",
    "customer_city": "Cidade sintética do cliente.",
    "customer_segment": "Segmento sintético atribuído ao cliente.",
    "customer_channel": "Canal sintético de compra do cliente.",
    "payment_id": "Identificador do pagamento.",
    "payment_type": "Tipo de pagamento sintético.",
    "payment_value": "Valor sintético associado ao pagamento.",
    "payment_status": "Status sintético do pagamento.",
    "review_score": "Nota sintética da avaliação, de 1 a 5.",
    "review_text": "Comentário textual sintético da avaliação.",
    "review_created_at": "Data e hora sintéticas de criação da avaliação.",
}


def build_catalog() -> dict:
    catalog = {
        "project": "Dadosfera E-commerce Case",
        "bronze_tables": [],
        "zones": {
            "bronze": "dados brutos ingeridos",
            "silver": "dados tratados e validados",
            "gold": "dados prontos para consumo analítico"
        }
    }

    for file_name in sorted(BRONZE.glob("*.csv")):
        df = pd.read_csv(file_name)
        metadata = TABLE_METADATA.get(file_name.name, {})
        catalog["bronze_tables"].append({
            "name": file_name.name,
            "rows": int(len(df)),
            "columns": list(df.columns),
            "column_metadata": [
                {
                    "name": column,
                    "type": str(df[column].dtype),
                    "description": COLUMN_DESCRIPTIONS.get(column, "Descrição pendente."),
                }
                for column in df.columns
            ],
            "description": metadata.get("description", "Descrição pendente."),
            "tags": metadata.get("tags", ["ecommerce", "synthetic"]),
            "zone": "bronze",
            "classification": "synthetic_non_personal",
            "owner": "case-ecommerce",
            "quality_rules": metadata.get("quality_rules", []),
        })

    return catalog


def save_catalog() -> None:
    catalog = build_catalog()
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Catalog salvo em: {CATALOG_PATH}")


def build_dashboard_summary() -> None:
    orders = pd.read_csv(BRONZE / "tb_orders.csv")
    items = pd.read_csv(BRONZE / "tb_order_items.csv")

    summary = {
        "total_orders": int(len(orders)),
        "total_items": int(len(items)),
        "status_counts": orders["order_status"].value_counts().to_dict(),
        "avg_item_value": round(items["price"].mean(), 2),
        "avg_freight": round(items["freight_value"].mean(), 2),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    status_df = orders["order_status"].value_counts().reset_index()
    status_df.columns = ["status", "quantidade"]

    fig = px.bar(
        status_df,
        x="status",
        y="quantidade",
        title="Distribuição de status dos pedidos",
        labels={"status": "Status", "quantidade": "Quantidade"},
        color="status",
    )
    fig.write_html(str(ROOT / "data" / "dashboard" / "status_orders_dashboard.html"))
    print("Dashboard HTML salvo em: data/dashboard/status_orders_dashboard.html")


def main() -> None:
    save_catalog()
    build_dashboard_summary()


if __name__ == "__main__":
    main()
