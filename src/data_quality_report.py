from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
BRONZE = ROOT / "data" / "bronze"
SILVER = ROOT / "data" / "silver"
QUALITY_DIR = ROOT / "data" / "quality"
REPORT_PATH = QUALITY_DIR / "data_quality_report.json"
LOG_PATH = QUALITY_DIR / "log_execucao.csv"

CORE_FILES = {
    "orders": BRONZE / "tb_orders.csv",
    "items": BRONZE / "tb_order_items.csv",
    "products": BRONZE / "tb_products_unstructured.csv",
}
OPTIONAL_FILES = {
    "customers": BRONZE / "tb_customers.csv",
    "payments": BRONZE / "tb_payments.csv",
    "reviews": BRONZE / "tb_reviews.csv",
}
ALIGNED_SYNTHETIC_FILES = {
    "customers_aligned": SILVER / "tb_customers_aligned_synthetic.csv",
    "reviews_aligned": SILVER / "tb_reviews_aligned_synthetic.csv",
}
OLIST_REVIEW_FILES = {
    "reviews_olist_sample": SILVER / "tb_reviews_aligned_real.csv",
}
VALID_STATUSES = {"delivered", "shipped", "processing", "canceled"}


def add_check(
    checks: list[dict],
    failed_rows: dict[str, set[int]],
    table: str,
    rule: str,
    failed_mask: pd.Series,
    expectation: str,
    severity: str = "error",
) -> None:
    failed_indexes = set(failed_mask[failed_mask].index.tolist())
    failed_rows.setdefault(table, set()).update(failed_indexes)
    checks.append(
        {
            "table": table,
            "rule": rule,
            "severity": severity,
            "status": "PASS" if not failed_indexes else "FAIL",
            "failed_rows": len(failed_indexes),
            "expectation": expectation,
        }
    )


def add_foreign_key_check(
    checks: list[dict],
    failed_rows: dict[str, set[int]],
    source_table: str,
    source: pd.DataFrame,
    source_column: str,
    target: pd.DataFrame,
    target_column: str,
    target_table: str,
    severity: str = "error",
) -> None:
    target_values = set(target[target_column].dropna())
    failed_mask = source[source_column].isna() | ~source[source_column].isin(target_values)
    add_check(
        checks,
        failed_rows,
        source_table,
        f"{source_column}_references_{target_table}.{target_column}",
        failed_mask,
        f"Todos os valores de {source_column} existem em {target_table}.{target_column}.",
        severity,
    )


def table_summary(dataframe: pd.DataFrame) -> dict:
    total_rows = len(dataframe)
    missing_counts = dataframe.isna().sum().astype(int).to_dict()
    missing_percentages = {
        column: round(count / total_rows * 100, 2) if total_rows else 0
        for column, count in missing_counts.items()
    }
    return {
        "rows": total_rows,
        "columns": list(dataframe.columns),
        "missing_counts": missing_counts,
        "missing_percentages": missing_percentages,
    }


def load_tables() -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    tables: dict[str, pd.DataFrame] = {}
    missing_core_files = []
    for name, path in CORE_FILES.items():
        if not path.exists():
            missing_core_files.append(path.name)
        else:
            tables[name] = pd.read_csv(path)

    if missing_core_files:
        raise FileNotFoundError("Arquivos principais ausentes: " + ", ".join(missing_core_files))

    optional_missing = {}
    for name, path in OPTIONAL_FILES.items():
        if path.exists():
            tables[name] = pd.read_csv(path)
        else:
            optional_missing[name] = f"Arquivo opcional ausente: {path.name}"
    for name, path in ALIGNED_SYNTHETIC_FILES.items():
        if path.exists():
            tables[name] = pd.read_csv(path)
        else:
            optional_missing[name] = f"Extensão sintética ainda não gerada: {path.name}"
    for name, path in OLIST_REVIEW_FILES.items():
        if path.exists():
            tables[name] = pd.read_csv(path)
        else:
            optional_missing[name] = f"Amostra Olist anotada ausente: {path.name}"
    return tables, optional_missing


def run_quality_checks(tables: dict[str, pd.DataFrame]) -> tuple[list[dict], dict[str, set[int]]]:
    checks: list[dict] = []
    failed_rows: dict[str, set[int]] = {}
    orders = tables["orders"]
    items = tables["items"]
    products = tables["products"]

    add_check(
        checks, failed_rows, "orders", "order_id_not_null", orders["order_id"].isna(),
        "order_id não nulo.",
    )
    add_check(
        checks, failed_rows, "orders", "order_id_unique", orders["order_id"].duplicated(keep=False),
        "order_id único.",
    )
    add_check(
        checks, failed_rows, "orders", "customer_id_not_null", orders["customer_id"].isna(),
        "customer_id não nulo.",
    )
    add_check(
        checks,
        failed_rows,
        "orders",
        "purchase_timestamp_not_null",
        pd.to_datetime(orders["order_purchase_timestamp"], errors="coerce").isna(),
        "Data de compra válida e preenchida.",
    )

    invalid_status = ~orders["order_status"].fillna("").str.strip().str.lower().isin(VALID_STATUSES)
    add_check(
        checks, failed_rows, "orders", "status_in_allowed_domain", invalid_status,
        f"Status em {sorted(VALID_STATUSES)}.",
    )
    delivered_without_date = orders["order_status"].eq("delivered") & orders[
        "order_delivered_customer_date"
    ].isna()
    add_check(
        checks, failed_rows, "orders", "delivered_date_required_for_delivered_orders",
        delivered_without_date, "Pedidos delivered possuem data de entrega.",
    )

    add_check(
        checks, failed_rows, "items", "order_id_not_null", items["order_id"].isna(),
        "order_id não nulo.",
    )
    add_foreign_key_check(
        checks, failed_rows, "items", items, "order_id", orders, "order_id", "orders"
    )
    add_foreign_key_check(
        checks, failed_rows, "items", items, "product_id", products, "product_id", "products"
    )
    for column in ("price", "freight_value"):
        numeric_values = pd.to_numeric(items[column], errors="coerce")
        invalid_values = numeric_values.isna() | numeric_values.lt(0)
        add_check(
            checks, failed_rows, "items", f"{column}_numeric_and_nonnegative", invalid_values,
            f"{column} numérico e maior ou igual a zero.",
        )

    add_check(
        checks, failed_rows, "products", "product_id_unique", products["product_id"].duplicated(keep=False),
        "product_id único.",
    )
    for column in ("product_category_name_raw", "title_raw", "description_raw"):
        empty_values = products[column].fillna("").str.strip().eq("")
        add_check(
            checks, failed_rows, "products", f"{column}_not_empty", empty_values,
            f"{column} preenchido.",
        )

    if "customers" in tables:
        customers = tables["customers"]
        add_check(
            checks, failed_rows, "customers", "customer_id_unique",
            customers["customer_id"].duplicated(keep=False), "customer_id único.", "warning",
        )
        add_foreign_key_check(
            checks, failed_rows, "customers", customers, "customer_id", orders, "customer_id",
            "orders", "warning",
        )

    if "payments" in tables:
        payments = tables["payments"]
        add_foreign_key_check(
            checks, failed_rows, "payments", payments, "order_id", orders, "order_id",
            "orders", "warning",
        )

    if "reviews" in tables:
        reviews = tables["reviews"]
        add_foreign_key_check(
            checks, failed_rows, "reviews", reviews, "order_id", orders, "order_id",
            "orders", "warning",
        )
        add_foreign_key_check(
            checks, failed_rows, "reviews", reviews, "customer_id", orders, "customer_id",
            "orders", "warning",
        )
        score = pd.to_numeric(reviews["review_score"], errors="coerce")
        add_check(
            checks, failed_rows, "reviews", "review_score_between_1_and_5",
            score.isna() | ~score.between(1, 5), "review_score entre 1 e 5.", "warning",
        )
        add_check(
            checks, failed_rows, "reviews", "review_text_not_empty",
            reviews["review_text"].fillna("").str.strip().eq(""), "review_text preenchido.", "warning",
        )

    if "customers_aligned" in tables:
        aligned_customers = tables["customers_aligned"]
        add_check(
            checks, failed_rows, "customers_aligned", "customer_id_unique",
            aligned_customers["customer_id"].duplicated(keep=False), "customer_id único.",
        )
        add_foreign_key_check(
            checks, failed_rows, "customers_aligned", aligned_customers, "customer_id",
            orders, "customer_id", "orders",
        )

    if "reviews_aligned" in tables:
        aligned_reviews = tables["reviews_aligned"]
        add_check(
            checks, failed_rows, "reviews_aligned", "review_id_unique",
            aligned_reviews["review_id"].duplicated(keep=False), "review_id único.",
        )
        add_foreign_key_check(
            checks, failed_rows, "reviews_aligned", aligned_reviews, "order_id",
            orders, "order_id", "orders",
        )
        add_foreign_key_check(
            checks, failed_rows, "reviews_aligned", aligned_reviews, "customer_id",
            orders, "customer_id", "orders",
        )
        score = pd.to_numeric(aligned_reviews["review_score"], errors="coerce")
        add_check(
            checks, failed_rows, "reviews_aligned", "review_score_between_1_and_5",
            score.isna() | ~score.between(1, 5), "review_score entre 1 e 5.",
        )
        add_check(
            checks, failed_rows, "reviews_aligned", "review_text_not_empty",
            aligned_reviews["review_text"].fillna("").str.strip().eq(""),
            "review_text preenchido.",
        )

    if "reviews_olist_sample" in tables:
        olist_reviews = tables["reviews_olist_sample"]
        add_check(
            checks, failed_rows, "reviews_olist_sample", "review_id_unique",
            olist_reviews["review_id"].duplicated(keep=False), "review_id único.",
        )
        score = pd.to_numeric(olist_reviews["review_score"], errors="coerce")
        add_check(
            checks, failed_rows, "reviews_olist_sample", "review_score_between_1_and_5",
            score.isna() | ~score.between(1, 5), "review_score entre 1 e 5.",
        )
        add_check(
            checks, failed_rows, "reviews_olist_sample", "sentiment_domain",
            ~olist_reviews["sentimento"].fillna("").isin({"Positivo", "Neutro", "Negativo"}),
            "sentimento em Positivo, Neutro ou Negativo.",
        )
        add_check(
            checks, failed_rows, "reviews_olist_sample", "problem_category_domain",
            ~olist_reviews["categoria_problema"].fillna("").isin(
                {"Outro", "Logística", "Produto", "Atendimento", "Pagamento"}
            ),
            "categoria_problema em um dos valores permitidos.",
        )
        for column in ("atraso_entrega", "produto_danificado"):
            add_check(
                checks, failed_rows, "reviews_olist_sample", f"{column}_domain",
                ~olist_reviews[column].fillna("").isin({"Sim", "Não"}),
                f"{column} deve ser Sim ou Não.",
            )
        add_check(
            checks, failed_rows, "reviews_olist_sample", "review_text_not_empty",
            olist_reviews["review_text"].fillna("").str.strip().eq(""),
            "review_text preenchido.",
        )

    return checks, failed_rows


def main() -> None:
    started_at = datetime.now(timezone.utc)
    tables, optional_missing = load_tables()
    checks, failed_rows = run_quality_checks(tables)
    core_failures = [check for check in checks if check["severity"] == "error" and check["status"] == "FAIL"]
    warning_failures = [check for check in checks if check["severity"] == "warning" and check["status"] == "FAIL"]
    core_status = "ERRO" if core_failures else "SUCESSO"
    overall_status = "ERRO" if core_failures else "ALERTA" if warning_failures or optional_missing else "SUCESSO"
    ended_at = datetime.now(timezone.utc)
    rows_processed = sum(len(dataframe) for dataframe in tables.values())
    rows_with_failures = sum(len(row_indexes) for row_indexes in failed_rows.values())

    report = {
        "data_inicio": started_at.isoformat(),
        "data_fim": ended_at.isoformat(),
        "status": overall_status,
        "status_tabelas_principais": core_status,
        "linhas_processadas": rows_processed,
        "linhas_com_falha": rows_with_failures,
        "tables": {name: table_summary(dataframe) for name, dataframe in tables.items()},
        "checks": checks,
        "optional_files_missing": optional_missing,
    }

    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log_row = pd.DataFrame(
        [{
            "data_inicio": started_at.isoformat(),
            "data_fim": ended_at.isoformat(),
            "status": overall_status,
            "linhas_afetadas": rows_processed,
            "linhas_com_falha": rows_with_failures,
            "checks_com_falha": len(core_failures) + len(warning_failures),
        }]
    )
    if LOG_PATH.exists():
        log_row = pd.concat([pd.read_csv(LOG_PATH), log_row], ignore_index=True)
    log_row.to_csv(LOG_PATH, index=False, encoding="utf-8")

    print(f"Status das tabelas principais: {core_status}")
    print(f"Status geral incluindo tabelas bônus: {overall_status}")
    print(f"Linhas processadas: {rows_processed}")
    print(f"Linhas com ao menos uma falha: {rows_with_failures}")
    for check in checks:
        if check["status"] == "FAIL":
            print(
                f"{check['severity'].upper()} {check['table']}.{check['rule']}: "
                f"{check['failed_rows']} linhas; esperado: {check['expectation']}"
            )
    print(f"Relatório: {REPORT_PATH.relative_to(ROOT)}")
    print(f"Log: {LOG_PATH.relative_to(ROOT)}")

    if core_failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
