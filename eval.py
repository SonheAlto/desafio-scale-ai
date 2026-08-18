"""Avalia um sistema contra o benchmark.

    uv run python eval.py                                  # benchmark completo (test, 84)
    uv run python eval.py --split mini                     # benchmark mini (28, rapido)
    uv run python eval.py --n 8                            # so as 8 primeiras

Correcao deterministica, sem LLM-judge: a resposta conta como certa se QUALQUER
alias do gabarito, normalizado, aparece na resposta normalizada.
"""

import argparse
import importlib
import json
import re
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

from utils.trace import contar_chamadas_tool  # noqa: E402


def normalizar(s: str) -> str:
    """Minusculo, sem acento, sem separador de milhar, so [a-z0-9] entre espacos."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[.,](?=\d{3}\b)", "", s)  # separador de milhar: 534.858.444 -> 534858444
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return f" {s.strip()} "


def _alias_presente(r: str, alias: str) -> bool:
    a = normalizar(alias).strip()
    if not a:
        return False
    # alias curto e numerico: exige casar a palavra inteira (evita "8" em "1988")
    if a.isdigit() and len(a) < 4:
        return bool(re.search(rf"(?<![0-9]){a}(?![0-9])", r))
    return a in r


def acertou(resposta: str, q: dict) -> bool:
    """Confere se `resposta` contem os aliases do gabarito de `q` (ver modulo)."""
    r = normalizar(resposta)
    # resposta composta: cada grupo de aliases precisa aparecer
    if q.get("respostas_todas"):
        return all(
            any(_alias_presente(r, alias) for alias in grupo)
            for grupo in q["respostas_todas"]
        )
    return any(_alias_presente(r, alias) for alias in q["respostas_aceitas"])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sistema", default="desafio", help="modulo do agente (default: agente_desafio)")
    p.add_argument("--split", default="test", choices=["test", "mini"], help="test (84) ou mini (28, iteracao rapida)")
    p.add_argument("--n", type=int, default=0, help="limita a N perguntas (0 = todas), ex: --n 10")
    args = p.parse_args()

    modulo = {"desafio": "agents.agente_desafio"}.get(
        args.sistema, args.sistema
    )
    responder = importlib.import_module(modulo).responder

    caminho = RAIZ / "benchmark" / f"{args.split}.json"
    perguntas = json.loads(caminho.read_text(encoding="utf-8"))
    if args.n:
        perguntas = perguntas[: args.n]

    resultados = []
    traces_completos = []
    acertos: list[bool] = []
    chamadas: list[int] = []
    t0 = time.time()
    for i, q in enumerate(perguntas, 1):
        resposta, erro, n_tools, rationale, trace = "", None, 0, "", []
        for tentativa in range(4):
            try:
                saida = responder(q["pergunta"])
                resposta = saida["resposta"]
                trace = saida.get("trace", [])
                rationale = saida.get("rationale", "")
                n_tools = contar_chamadas_tool(trace)
                erro = None
                break
            except Exception as e:  # noqa: BLE001 — falha do sistema conta como erro
                erro = f"{type(e).__name__}: {e}"
                # rate limit (free tier: 5 req/min): espera e tenta de novo
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    espera = 20 * (tentativa + 1)
                    print(f"      rate limit; aguardando {espera}s...")
                    time.sleep(espera)
                else:
                    break
        ok = bool(resposta) and acertou(resposta, q)
        acertos.append(ok)
        chamadas.append(n_tools)
        resultados.append({**q, "resposta_dada": resposta, "rationale": rationale, "acertou": ok, "erro": erro, "n_tools": n_tools})
        traces_completos.append({"pergunta": q["pergunta"], "resposta_dada": resposta, "acertou": ok, "rationale": rationale, "trace": trace})
        simbolo = "V" if ok else "X"
        print(f"[{i:3d}/{len(perguntas)}] {simbolo}  ({q.get('categoria', 'sem_categoria')}) {q['pergunta'][:70]}")

    total_ok = sum(acertos)
    total = len(acertos)
    media_ch = sum(chamadas) / len(chamadas) if chamadas else 0
    print(f"\n{'acertos':>8} {'acuracia':>9} {'tools/q':>9}")
    print("-" * 28)
    print(f"{total_ok:>4}/{total:<3} {100 * total_ok / total:>8.1f}% {media_ch:>8.1f}")
    print(f"\ntempo: {time.time() - t0:.0f}s")
    from utils.cost import total_gasto

    print(f"custo acumulado (livro-caixa): US${total_gasto():.4f}")

    destino = RAIZ / "resultados" / f"{args.sistema.replace('.', '-')}-{args.split}.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"detalhe salvo em {destino}")

    # Trace completo por pergunta (tool calls, args, retornos) + rationale.
    # Vai para traces/ (gitignored): pesado demais para versionar, mas permite
    # abrir "por que errou" sem re-rodar. O resultados/ acima guarda so o rationale.
    traces_dir = RAIZ / "traces"
    traces_dir.mkdir(exist_ok=True)
    dtraces = traces_dir / f"eval-{args.sistema.replace('.', '-')}-{args.split}.json"
    dtraces.write_text(json.dumps(traces_completos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"traces completos em {dtraces}")


if __name__ == "__main__":
    main()
