"""Livro-caixa de tokens/custo. Acumula em traces/custo.jsonl e corta no teto.

Preco CONSERVADOR (teto da classe Flash) para o corte ser seguro: se o custo
real for menor, paramos antes do necessario — nunca depois. Ajuste PRECO_* se
confirmar o preco exato do modelo no console.
"""

import json
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "traces" / "custo.jsonl"

PRECO_ENTRADA = 0.30 / 1_000_000   # USD por token de entrada (teto Flash)
PRECO_SAIDA = 2.50 / 1_000_000     # USD por token de saida (teto Flash)
TETO_USD = 20.0


class OrcamentoEstourado(RuntimeError):
    pass


def _custo(entrada: int, saida: int) -> float:
    return entrada * PRECO_ENTRADA + saida * PRECO_SAIDA


def total_gasto() -> float:
    """Soma o custo_usd de todas as linhas ja registradas no ledger."""
    if not LEDGER.exists():
        return 0.0
    total = 0.0
    for linha in LEDGER.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            total += json.loads(linha)["custo_usd"]
    return total


def registrar(entrada: int, saida: int, rotulo: str = "") -> float:
    """Registra uma chamada e devolve o total acumulado. Estoura se passar do teto."""
    LEDGER.parent.mkdir(exist_ok=True)
    custo = _custo(entrada, saida)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(
            {"rotulo": rotulo, "entrada": entrada, "saida": saida, "custo_usd": round(custo, 6)}
        ) + "\n")
    total = total_gasto()
    if total > TETO_USD:
        raise OrcamentoEstourado(
            f"Teto de US${TETO_USD:.2f} atingido (acumulado US${total:.4f}). Parando."
        )
    return total
