from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import random
import uuid

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
BRONZE = ROOT / "data" / "bronze"
OUTPUT = ROOT / "data" / "silver" / "tb_reviews_aligned_synthetic.csv"
CUSTOMERS_OUTPUT = ROOT / "data" / "silver" / "tb_customers_aligned_synthetic.csv"
SEED = 20261001
REVIEW_COUNT = 10_000
CAPITALS = {
    "AC": "Rio Branco", "AL": "Maceio", "AP": "Macapa", "AM": "Manaus",
    "BA": "Salvador", "CE": "Fortaleza", "DF": "Brasilia", "ES": "Vitoria",
    "GO": "Goiania", "MA": "Sao Luis", "MT": "Cuiaba", "MS": "Campo Grande",
    "MG": "Belo Horizonte", "PA": "Belem", "PB": "Joao Pessoa", "PR": "Curitiba",
    "PE": "Recife", "PI": "Teresina", "RJ": "Rio de Janeiro", "RN": "Natal",
    "RS": "Porto Alegre", "RO": "Porto Velho", "RR": "Boa Vista",
    "SC": "Florianopolis", "SP": "Sao Paulo", "SE": "Aracaju", "TO": "Palmas",
}

REVIEW_TEMPLATES = [
    (5, "A entrega chegou no prazo e o produto correspondeu ao anúncio. Gostei da compra."),
    (4, "O produto é bom e chegou em boas condições. A experiência foi positiva."),
    (3, "O produto atende ao básico, mas a entrega demorou um pouco mais do que eu esperava."),
    (2, "Meu pedido atrasou e tive dificuldade para acompanhar a entrega."),
    (1, "A entrega atrasou bastante e o produto chegou danificado. Fiquei insatisfeito."),
    (2, "Recebi o produto com uma peça quebrada e ainda aguardo uma solução do atendimento."),
    (1, "O produto veio danificado e a embalagem estava aberta."),
    (3, "O item é razoável, mas o atendimento demorou para responder minha dúvida."),
    (2, "O pagamento foi aprovado, mas o pedido demorou para ser enviado."),
    (5, "Compra simples, produto bem embalado e entrega dentro do prazo."),
    (4, "O produto tem boa qualidade. O frete poderia ser mais rápido."),
    (1, "O pedido não chegou na data prevista e não consegui uma atualização clara."),
]


def main() -> None:
    orders_path = BRONZE / "tb_orders.csv"
    if not orders_path.exists():
        raise FileNotFoundError(f"Pedidos não encontrados: {orders_path}")

    orders = pd.read_csv(
        orders_path,
        parse_dates=["order_purchase_timestamp", "order_delivered_customer_date"],
    )
    if not orders["order_id"].is_unique:
        raise ValueError("order_id precisa ser único antes de criar avaliações associadas.")

    count = min(REVIEW_COUNT, len(orders))
    selection = random.Random(SEED).sample(range(len(orders)), count)
    selected_orders = orders.iloc[selection].sort_values("order_id")
    randomizer = random.Random(SEED + 1)
    rows = []

    for order in selected_orders.itertuples(index=False):
        review_score, review_text = REVIEW_TEMPLATES[randomizer.randrange(len(REVIEW_TEMPLATES))]
        base_date = order.order_delivered_customer_date
        if pd.isna(base_date):
            base_date = order.order_purchase_timestamp
        review_created_at = base_date + timedelta(days=randomizer.randint(1, 14))
        rows.append(
            {
                "review_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"review:{order.order_id}")),
                "order_id": order.order_id,
                "customer_id": order.customer_id,
                "review_score": review_score,
                "review_text": review_text,
                "review_created_at": review_created_at,
                "source_type": "synthetic_aligned_to_current_orders",
            }
        )

    reviews = pd.DataFrame(rows)
    location_randomizer = random.Random(SEED + 2)
    customers = orders[["customer_id"]].drop_duplicates().sort_values("customer_id").copy()
    locations = list(CAPITALS.items())
    assigned_locations = [location_randomizer.choice(locations) for _ in range(len(customers))]
    customers["customer_state"] = [state for state, _ in assigned_locations]
    customers["customer_city"] = [city for _, city in assigned_locations]
    customers["source_type"] = "synthetic_illustrative_location_not_ibge"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    reviews.to_csv(OUTPUT, index=False, encoding="utf-8")
    customers.to_csv(CUSTOMERS_OUTPUT, index=False, encoding="utf-8")
    assert reviews["review_id"].is_unique
    assert reviews["order_id"].isin(orders["order_id"]).all()
    assert reviews["customer_id"].isin(orders["customer_id"]).all()
    assert customers["customer_id"].isin(orders["customer_id"]).all()
    print(f"Avaliações sintéticas alinhadas: {len(reviews):,}")
    print(f"Pedidos órfãos: {(~reviews['order_id'].isin(orders['order_id'])).sum()}")
    print(f"Clientes com localização ilustrativa: {len(customers):,}")
    print("Localizações não são dados reais do IBGE nem coordenadas para roteirização.")
    print(f"Saída: {OUTPUT.relative_to(ROOT)}")
    print(f"Dimensão de clientes: {CUSTOMERS_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()