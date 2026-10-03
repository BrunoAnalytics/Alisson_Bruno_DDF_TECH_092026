from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
BRONZE = ROOT / "data" / "bronze"
SILVER = ROOT / "data" / "silver"
STAR_SCHEMA_PATH = ROOT / "data" / "gold" / "ecommerce_star.duckdb"
REQUIRED_FILES = (
    "tb_orders.csv",
    "tb_order_items.csv",
    "tb_products_unstructured.csv",
)

st.set_page_config(
    page_title="E-commerce | Dadosfera",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #172c2a;
        --muted: #657572;
        --surface: #f1f6f4;
        --line: #dce7e2;
        --teal: #087e75;
        --coral: #e76f51;
        --gold: #d49a21;
    }
    .stApp,
    [data-testid="stAppViewContainer"] {
        background: var(--surface);
        color: var(--ink) !important;
    }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1600px; padding-top: 1.4rem; padding-bottom: 2rem; }
    h1, h2, h3, p, label, [data-testid="stWidgetLabel"] {
        color: var(--ink) !important;
    }
    [data-testid="stCaptionContainer"] p { color: var(--muted) !important; }
    .eyebrow {
        color: var(--teal);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .kpi-card {
        min-height: 112px;
        padding: 15px 16px;
        border-radius: 6px;
        color: #fff;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .kpi-label { font-size: 0.78rem; opacity: 0.9; }
    .kpi-value { font-size: 1.25rem; font-weight: 700; line-height: 1.25; overflow-wrap: anywhere; }
    .kpi-detail { font-size: 0.72rem; opacity: 0.86; }
    .kpi-teal { background: #087e75; }
    .kpi-blue { background: #24669a; }
    .kpi-cyan { background: #178e9b; }
    .kpi-green { background: #368263; }
    .kpi-coral { background: #d7664c; }
    .kpi-gold { background: #ad7718; }
    h1, h2, h3 { color: var(--ink); }
    h2, h3 { margin-bottom: 0.45rem; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Carregando os dados do projeto...")
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if STAR_SCHEMA_PATH.exists():
        import duckdb

        with duckdb.connect(str(STAR_SCHEMA_PATH), read_only=True) as connection:
            orders = connection.execute(
                """
                SELECT order_id, customer_id, order_status,
                       purchase_date AS order_purchase_timestamp
                FROM vw_analitico_pedidos
                """
            ).df()
            items = connection.execute(
                """
                SELECT order_id, order_item_id, product_id,
                       item_price AS price, freight_value
                FROM vw_analitico_pedidos_itens
                """
            ).df()
            products = connection.execute(
                """
                SELECT product_key AS product_id,
                       category_name AS product_category_name_raw
                FROM dim_produto
                """
            ).df()
            demo_table_exists = connection.execute(
                """
                SELECT COUNT(*) > 0
                FROM information_schema.tables
                WHERE table_name = 'tb_products_enriched_sample'
                """
            ).fetchone()[0]
            product_feature_sample = (
                connection.execute(
                    """
                    SELECT product_id, title_raw, description_raw, category_extracted,
                           material_extracted, key_features_json, source_type, extraction_method
                    FROM tb_products_enriched_sample
                    ORDER BY product_id
                    """
                ).df()
                if demo_table_exists
                else pd.DataFrame()
            )
            real_review_table_exists = connection.execute(
                """
                SELECT COUNT(*) > 0
                FROM information_schema.tables
                WHERE table_name = 'fato_avaliacoes_olist_enriquecidas'
                """
            ).fetchone()[0]
            olist_reviews = (
                connection.execute(
                    """
                    SELECT review_id, order_id, review_score, review_text, sentimento,
                           categoria_problema, atraso_entrega, produto_danificado,
                           source_type, enrichment_provider, enrichment_model
                    FROM fato_avaliacoes_olist_enriquecidas
                    ORDER BY review_id
                    """
                ).df()
                if real_review_table_exists
                else pd.DataFrame()
            )
        orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"])
        orders["order_status"] = orders["order_status"].fillna("sem status").str.strip().str.lower()
        return orders, items, products, product_feature_sample, olist_reviews

    missing_files = [name for name in REQUIRED_FILES if not (BRONZE / name).exists()]
    if missing_files:
        raise FileNotFoundError(
            "Arquivos ausentes em data/bronze: " + ", ".join(missing_files)
        )

    orders = pd.read_csv(
        BRONZE / "tb_orders.csv",
        parse_dates=["order_purchase_timestamp", "order_delivered_customer_date"],
    )
    items = pd.read_csv(BRONZE / "tb_order_items.csv")
    products = pd.read_csv(BRONZE / "tb_products_unstructured.csv")

    orders["order_status"] = orders["order_status"].fillna("sem status").str.strip().str.lower()
    items["price"] = pd.to_numeric(items["price"], errors="coerce").fillna(0)
    items["freight_value"] = pd.to_numeric(items["freight_value"], errors="coerce").fillna(0)
    products["product_category_name_raw"] = (
        products["product_category_name_raw"].fillna("Sem categoria").str.strip()
    )
    products["product_category_name_raw"] = products["product_category_name_raw"].replace(
        "", "Sem categoria"
    )
    product_feature_path = SILVER / "tb_products_enriched_sample.csv"
    product_feature_sample = (
        pd.read_csv(product_feature_path) if product_feature_path.exists() else pd.DataFrame()
    )
    real_review_path = SILVER / "tb_reviews_aligned_real.csv"
    olist_reviews = pd.read_csv(real_review_path) if real_review_path.exists() else pd.DataFrame()
    return orders, items, products, product_feature_sample, olist_reviews


def format_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def render_kpi(column, label: str, value: str, detail: str, color: str) -> None:
    column.markdown(
        f"""
        <div class="kpi-card {color}" role="group" aria-label="{label}">
            <span class="kpi-label">{label}</span>
            <strong class="kpi-value">{value}</strong>
            <span class="kpi-detail">{detail}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


try:
    orders_df, items_df, products_df, product_feature_sample_df, olist_reviews_df = load_data()
except (FileNotFoundError, ValueError, KeyError) as error:
    st.error(f"Não foi possível carregar os dados: {error}")
    st.info("Confira se os três CSVs estão em data/bronze e se mantêm os cabeçalhos esperados.")
    st.stop()

st.markdown('<div class="eyebrow">Dadosfera / E-commerce / Camada Bronze</div>', unsafe_allow_html=True)
st.title("Performance do e-commerce")
st.caption("Pedidos, receita dos itens e categorias no período selecionado.")

first_day = orders_df["order_purchase_timestamp"].min().date()
last_day = orders_df["order_purchase_timestamp"].max().date()
available_statuses = sorted(orders_df["order_status"].dropna().unique().tolist())

filter_columns = st.columns((1.1, 1.5, 1.2))
with filter_columns[0]:
    date_selection = st.date_input(
        "Data de compra",
        value=(first_day, last_day),
        min_value=first_day,
        max_value=last_day,
    )
with filter_columns[1]:
    selected_statuses = st.multiselect(
        "Status do pedido",
        options=available_statuses,
        default=available_statuses,
    )
with filter_columns[2]:
    st.markdown(
        f"<div style='padding-top:1.8rem;color:#657572'>Período disponível<br><strong>{first_day:%d/%m/%Y} a {last_day:%d/%m/%Y}</strong></div>",
        unsafe_allow_html=True,
    )

if isinstance(date_selection, tuple) and len(date_selection) == 2:
    start_day, end_day = date_selection
else:
    start_day = end_day = date_selection

date_column = orders_df["order_purchase_timestamp"].dt.date
order_mask = date_column.between(start_day, end_day)
order_mask &= orders_df["order_status"].isin(selected_statuses)
filtered_orders = orders_df.loc[order_mask].copy()

if filtered_orders.empty:
    st.warning("Nenhum pedido corresponde aos filtros selecionados.")
    st.stop()

filtered_items = items_df.loc[items_df["order_id"].isin(filtered_orders["order_id"])].copy()
item_revenue = float(filtered_items["price"].sum())
order_count = int(filtered_orders["order_id"].nunique())
average_order_value = item_revenue / order_count if order_count else 0
average_freight = float(filtered_items["freight_value"].mean()) if not filtered_items.empty else 0
canceled_count = int(filtered_orders["order_status"].eq("canceled").sum())
cancellation_rate = float(canceled_count / order_count * 100) if order_count else 0
item_count = int(len(filtered_items))

metric_columns = st.columns(3)
render_kpi(metric_columns[0], "Pedidos", f"{order_count:,}".replace(",", "."), "no período", "kpi-teal")
render_kpi(metric_columns[1], "Receita dos itens", format_brl(item_revenue), "sem incluir frete", "kpi-blue")
render_kpi(metric_columns[2], "Itens vendidos", f"{item_count:,}".replace(",", "."), "linhas de pedido", "kpi-cyan")

metric_columns = st.columns(3)
render_kpi(metric_columns[0], "Ticket médio", format_brl(average_order_value), "receita / pedidos", "kpi-green")
render_kpi(metric_columns[1], "Cancelamento", f"{cancellation_rate:.1f}%", f"{canceled_count:,} pedidos".replace(",", "."), "kpi-coral")
render_kpi(metric_columns[2], "Frete médio", format_brl(average_freight), "por item", "kpi-gold")

orders_for_charts = filtered_orders[["order_id", "order_purchase_timestamp", "order_status"]]
items_for_charts = filtered_items.merge(orders_for_charts, on="order_id", how="inner")
items_for_charts = items_for_charts.merge(
    products_df[["product_id", "product_category_name_raw"]],
    on="product_id",
    how="left",
)
items_for_charts["product_category_name_raw"] = items_for_charts[
    "product_category_name_raw"
].fillna("Produto sem categoria")

status_column, monthly_column = st.columns((0.82, 1.6))
with status_column:
    st.subheader("Pedidos por status")
    status_counts = (
        filtered_orders["order_status"]
        .value_counts()
        .rename_axis("Status")
        .reset_index(name="Pedidos")
    )
    status_figure = px.bar(
        status_counts,
        x="Pedidos",
        y="Status",
        orientation="h",
        color="Status",
        color_discrete_sequence=["#087e75", "#e76f51", "#d49a21", "#526e68"],
        template="plotly_white",
    )
    status_figure.update_layout(
        showlegend=False,
        margin=dict(l=8, r=8, t=8, b=8),
        height=300,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b38",
    )
    status_figure.update_yaxes(categoryorder="total ascending", title=None)
    status_figure.update_xaxes(title=None, gridcolor="#e7eeeb")
    st.plotly_chart(status_figure, width="stretch")

with monthly_column:
    st.subheader("Pedidos por mês")
    items_for_charts["month"] = (
        items_for_charts["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    )
    monthly_revenue = items_for_charts.groupby("month", as_index=False)["price"].sum()
    monthly_orders = (
        filtered_orders.assign(
            month=filtered_orders["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
        )
        .groupby("month", as_index=False)
        .agg(pedidos=("order_id", "nunique"))
    )
    monthly_summary = monthly_orders.merge(monthly_revenue, on="month", how="left").fillna(0)
    monthly_summary["ticket_medio"] = monthly_summary["price"] / monthly_summary["pedidos"]
    monthly_summary = monthly_summary.sort_values("month", ascending=False).head(8)
    monthly_summary = monthly_summary.rename(
        columns={"month": "Mês", "pedidos": "Pedidos", "price": "Receita dos itens", "ticket_medio": "Ticket médio"}
    )
    monthly_summary["Mês"] = monthly_summary["Mês"].dt.strftime("%b/%Y")
    monthly_orders_figure = px.bar(
        monthly_orders.sort_values("month"),
        x="month",
        y="pedidos",
        labels={"month": "Mês", "pedidos": "Pedidos"},
        color_discrete_sequence=["#24669a"],
        template="plotly_white",
    )
    monthly_orders_figure.update_layout(
        margin=dict(l=8, r=8, t=8, b=8),
        height=300,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b38",
    )
    monthly_orders_figure.update_xaxes(title=None, gridcolor="#e7eeeb")
    monthly_orders_figure.update_yaxes(title=None, gridcolor="#e7eeeb")
    st.plotly_chart(monthly_orders_figure, width="stretch")

revenue_column, category_column = st.columns((1.25, 1))
with revenue_column:
    st.subheader("Evolução da receita dos itens")
    revenue_figure = px.line(
        monthly_revenue.sort_values("month"),
        x="month",
        y="price",
        markers=True,
        labels={"month": "Mês", "price": "Receita dos itens"},
        color_discrete_sequence=["#087e75"],
        template="plotly_white",
    )
    revenue_figure.update_layout(
        margin=dict(l=8, r=8, t=8, b=8),
        height=320,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b38",
    )
    revenue_figure.update_xaxes(title=None, gridcolor="#e7eeeb")
    revenue_figure.update_yaxes(title=None, gridcolor="#e7eeeb")
    st.plotly_chart(revenue_figure, width="stretch")

with category_column:
    st.subheader("Receita por categoria")
    category_revenue = (
        items_for_charts.groupby("product_category_name_raw", as_index=False)["price"]
        .sum()
        .sort_values("price", ascending=False)
        .head(8)
    )
    category_figure = px.bar(
        category_revenue,
        x="price",
        y="product_category_name_raw",
        orientation="h",
        labels={"price": "Receita dos itens", "product_category_name_raw": "Categoria"},
        color_discrete_sequence=["#e76f51"],
        template="plotly_white",
    )
    category_figure.update_layout(
        yaxis={"categoryorder": "total ascending"},
        margin=dict(l=8, r=8, t=8, b=8),
        height=320,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b38",
    )
    category_figure.update_xaxes(title=None, gridcolor="#e7eeeb")
    st.plotly_chart(category_figure, width="stretch")

detail_chart_column, recent_orders_column = st.columns((1, 1.4))
with detail_chart_column:
    st.subheader("Frete médio por categoria")
    category_freight = (
        items_for_charts.groupby("product_category_name_raw", as_index=False)["freight_value"]
        .mean()
        .sort_values("freight_value", ascending=False)
        .head(8)
    )
    freight_figure = px.bar(
        category_freight,
        x="freight_value",
        y="product_category_name_raw",
        orientation="h",
        labels={"freight_value": "Frete médio (R$)", "product_category_name_raw": "Categoria"},
        color_discrete_sequence=["#ad7718"],
        template="plotly_white",
    )
    freight_figure.update_layout(
        yaxis={"categoryorder": "total ascending"},
        margin=dict(l=8, r=8, t=8, b=8),
        height=320,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b38",
    )
    freight_figure.update_xaxes(title=None, gridcolor="#e7eeeb")
    st.plotly_chart(freight_figure, width="stretch")

with recent_orders_column:
    st.subheader("Pedidos recentes")
    recent_orders = (
        filtered_orders.sort_values("order_purchase_timestamp", ascending=False)
        .loc[:, ["order_id", "order_purchase_timestamp", "order_status"]]
        .head(12)
        .rename(
            columns={
                "order_id": "Pedido",
                "order_purchase_timestamp": "Data da compra",
                "order_status": "Status",
            }
        )
    )
    st.dataframe(recent_orders, hide_index=True, width="stretch", height=320)

st.subheader("Resumo mensal")
st.dataframe(
    monthly_summary.style.format(
        {"Receita dos itens": "R$ {:,.2f}", "Ticket médio": "R$ {:,.2f}"},
        thousands=".",
        decimal=",",
    ),
    hide_index=True,
    width="stretch",
)

st.subheader("PoC de atributos de produtos")
st.caption(
    "Demonstração sintética e isolada; estes produtos não pertencem ao Bronze nem alteram as métricas de vendas."
)
if product_feature_sample_df.empty:
    st.info("A amostra não está disponível. Recrie a camada Gold para carregá-la no DuckDB.")
else:
    st.dataframe(
        product_feature_sample_df[
            ["title_raw", "category_extracted", "material_extracted", "key_features_json"]
        ],
        hide_index=True,
        width="stretch",
    )

st.subheader("Reviews Olist enriquecidas")
st.caption(
    "Amostra classificada no Colab com Groq; os order_id Olist não correspondem aos pedidos sintéticos locais e não são usados nos KPIs de vendas."
)
if olist_reviews_df.empty:
    st.info("A amostra Olist não está disponível no Silver/Gold local.")
else:
    sentiment_column, issue_column = st.columns(2)
    with sentiment_column:
        st.plotly_chart(
            px.bar(
                olist_reviews_df["sentimento"].value_counts().rename_axis("Sentimento").reset_index(name="Reviews"),
                x="Sentimento",
                y="Reviews",
                color="Sentimento",
                color_discrete_map={"Positivo": "#368263", "Neutro": "#d49a21", "Negativo": "#d7664c"},
                template="plotly_white",
                title="Sentimento na amostra Olist",
            ),
            width="stretch",
        )
    with issue_column:
        st.plotly_chart(
            px.bar(
                olist_reviews_df["categoria_problema"].value_counts().rename_axis("Categoria").reset_index(name="Reviews"),
                x="Categoria",
                y="Reviews",
                color_discrete_sequence=["#24669a"],
                template="plotly_white",
                title="Categoria do problema na amostra Olist",
            ),
            width="stretch",
        )
    st.dataframe(
        olist_reviews_df[
            ["review_score", "review_text", "sentimento", "categoria_problema", "atraso_entrega", "produto_danificado"]
        ].head(20),
        hide_index=True,
        width="stretch",
    )

st.caption(
    f"Fonte: {'DuckDB Gold local' if STAR_SCHEMA_PATH.exists() else 'CSVs sintéticos locais em data/bronze'} · Frete médio por item: {format_brl(average_freight)}"
)