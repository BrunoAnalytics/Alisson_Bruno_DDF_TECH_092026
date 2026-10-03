from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "data" / "silver" / "tb_reviews_aligned_synthetic.csv"
OUTPUT_PATH = ROOT / "data" / "gold" / "tb_reviews_enriched_synthetic.csv"
MAX_SAMPLE_SIZE = 5
ALLOWED_SENTIMENTS = {"Positivo", "Neutro", "Negativo"}
ALLOWED_YES_NO_UNKNOWN = {"Sim", "Não", "Incerto"}

SYSTEM_PROMPT = """Você classifica avaliações de e-commerce em português.
Responda somente com um objeto JSON contendo:
{
  "categoria_problema": "Logística|Produto|Atendimento|Pagamento|Outro|Sem problema",
  "sentimento": "Positivo|Neutro|Negativo",
  "features": {
    "atraso_entrega": "Sim|Não|Incerto",
    "produto_danificado": "Sim|Não|Incerto"
  }
}
Não invente fatos. Use Incerto quando o texto não permitir concluir.
"""


def parse_and_validate_response(response_text: str) -> dict:
    result = json.loads(response_text)
    required_top_level = {"categoria_problema", "sentimento", "features"}
    if set(result) != required_top_level:
        raise ValueError("A resposta JSON deve conter somente as três chaves esperadas.")

    if result["sentimento"] not in ALLOWED_SENTIMENTS:
        raise ValueError("sentimento fora do domínio permitido.")
    if result["categoria_problema"] not in {
        "Logística", "Produto", "Atendimento", "Pagamento", "Outro", "Sem problema"
    }:
        raise ValueError("categoria_problema fora do domínio permitido.")

    features = result["features"]
    if set(features) != {"atraso_entrega", "produto_danificado"}:
        raise ValueError("features deve conter atraso_entrega e produto_danificado.")
    if any(value not in ALLOWED_YES_NO_UNKNOWN for value in features.values()):
        raise ValueError("As features devem usar Sim, Não ou Incerto.")
    return result


def classify_reviews(limit: int, model: str) -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Arquivo de avaliações não encontrado: {INPUT_PATH}")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Defina OPENAI_API_KEY localmente antes de autorizar chamadas à API.")

    from openai import OpenAI

    reviews = pd.read_csv(INPUT_PATH)
    if "review_text" not in reviews.columns:
        raise ValueError("A coluna review_text não existe na tabela de avaliações.")

    selected = reviews.loc[
        reviews["review_text"].fillna("").str.strip().ne(""),
        ["review_id", "order_id", "customer_id", "review_score", "review_text"],
    ]
    selected = selected.head(limit).reset_index(names="source_row")
    client = OpenAI(api_key=api_key)
    results = []

    for row in selected.itertuples(index=False):
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": row.review_text},
            ],
        )
        parsed = parse_and_validate_response(response.choices[0].message.content or "")
        results.append(
            {
                "review_id": row.review_id,
                "order_id": row.order_id,
                "customer_id": row.customer_id,
                "review_score": int(row.review_score),
                "source_row": int(row.source_row),
                "review_text": row.review_text,
                "categoria_problema": parsed["categoria_problema"],
                "sentimento": parsed["sentimento"],
                "atraso_entrega": parsed["features"]["atraso_entrega"],
                "produto_danificado": parsed["features"]["produto_danificado"],
                "model": model,
            }
        )

    return pd.DataFrame(results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classifica uma pequena amostra de avaliações; a API paga exige confirmação explícita."
    )
    parser.add_argument("--execute", action="store_true", help="Autoriza chamadas reais à API.")
    parser.add_argument(
        "--confirm-paid-api",
        action="store_true",
        help="Confirma que você verificou saldo/preço e aceita eventual cobrança.",
    )
    parser.add_argument("--limit", type=int, default=5, help="Amostra de 1 a 5 avaliações (padrão: 5).")
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        help="Modelo configurável por OPENAI_MODEL ou --model.",
    )
    arguments = parser.parse_args()

    if not 1 <= arguments.limit <= MAX_SAMPLE_SIZE:
        parser.error(f"--limit deve estar entre 1 e {MAX_SAMPLE_SIZE} para limitar custo.")

    if not INPUT_PATH.exists():
        parser.error(f"Arquivo de avaliações ausente: {INPUT_PATH}")

    if not arguments.execute:
        print(
            f"Dry-run: {arguments.limit} avaliações no máximo; nenhuma chamada foi feita. "
            "Verifique custo/modelo e só então use --execute --confirm-paid-api."
        )
        return

    if not arguments.confirm_paid_api:
        parser.error("Chamadas reais exigem --confirm-paid-api após verificar o custo.")

    enriched = classify_reviews(arguments.limit, arguments.model)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"Avaliações processadas: {len(enriched)}")
    print(f"Resultado salvo em: {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()