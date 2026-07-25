"""Roda seu agente sobre o conjunto de submissao e gera predict.json.

Este e o arquivo que voce ENVIA para os organizadores avaliarem. Ele NAO
contem o gabarito — so as suas respostas, casadas por `id`.

    uv run python scripts/gerar_predict.py
    uv run python scripts/gerar_predict.py --entrada benchmark/val_participante.json --saida predict.json

Cada linha de saida: {"id": <id da pergunta>, "resposta": <sua resposta>}.
Uma pergunta que falhar (excecao) sai com resposta vazia — nao interrompe o resto.
"""

import argparse
import importlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sistema", default="agents.agente_desafio", help="modulo com responder(pergunta)")
    p.add_argument("--entrada", default="benchmark/val_participante.json")
    p.add_argument("--saida", default="predict.json")
    args = p.parse_args()

    responder = importlib.import_module(args.sistema).responder
    perguntas = json.loads((RAIZ / args.entrada).read_text(encoding="utf-8"))

    predicoes = []
    for i, q in enumerate(perguntas, 1):
        try:
            resposta = responder(q["pergunta"])["resposta"]
        except Exception as e:  # noqa: BLE001 — uma falha nao derruba o restante
            print(f"  [{i:3d}/{len(perguntas)}] {q['id']}  ERRO: {type(e).__name__}: {e}")
            resposta = ""
        else:
            print(f"  [{i:3d}/{len(perguntas)}] {q['id']}  {resposta[:60]}")
        predicoes.append({"id": q["id"], "resposta": resposta})

    saida = RAIZ / args.saida
    saida.write_text(json.dumps(predicoes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(predicoes)} predicoes salvas em {saida}")
    print("Envie este arquivo para os organizadores.")


if __name__ == "__main__":
    main()
