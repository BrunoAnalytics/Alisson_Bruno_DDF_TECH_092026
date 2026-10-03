from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BRONZE = ROOT / "data" / "bronze"

EXPECTED = {
    "tb_orders.csv": {
        "min_rows": 100_000,
        "columns": [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_delivered_customer_date",
        ],
    },
    "tb_order_items.csv": {
        "min_rows": 200_000,
        "columns": [
            "order_id",
            "order_item_id",
            "product_id",
            "price",
            "freight_value",
        ],
    },
    "tb_products_unstructured.csv": {
        "min_rows": 5_000,
        "columns": [
            "product_id",
            "product_category_name_raw",
            "title_raw",
            "description_raw",
        ],
    },
}


def validate_file(file_name: str) -> None:
    path = BRONZE / file_name
    if not path.exists():
        raise FileNotFoundError(f"Arquivo ausente: {path}")

    df = pd.read_csv(path)
    cfg = EXPECTED[file_name]

    if len(df) < cfg["min_rows"]:
        raise ValueError(
            f"{file_name}: esperava pelo menos {cfg['min_rows']} linhas, "
            f"mas encontrou {len(df)}."
        )

    actual_cols = list(df.columns)
    for expected in cfg["columns"]:
        if expected not in actual_cols:
            raise ValueError(
                f"{file_name}: coluna ausente '{expected}'. Colunas encontradas: {actual_cols}"
            )

    print(f"{file_name}: OK | linhas={len(df)} | colunas={actual_cols}")


def main() -> None:
    if not BRONZE.exists():
        raise FileNotFoundError(f"Diretório de dados não encontrado: {BRONZE}")

    for file_name in EXPECTED:
        validate_file(file_name)

    print("\nValidação concluída com sucesso para a base gerada localmente.")


if __name__ == "__main__":
    main()
