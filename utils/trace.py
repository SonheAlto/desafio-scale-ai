"""Trace de execucao do agente: extrai, salva em JSON e imprime.

O trace e a principal ferramenta de diagnostico do desafio — cada chamada de
tool aparece com os argumentos EXATOS (inclusive o SQL gerado) e o retorno.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)

TRACES_DIR = Path(__file__).resolve().parent.parent / "traces"


def extrair_trace(mensagens: list[Any]) -> list[dict]:
    """Converte o historico do pydantic-ai numa lista cronologica de eventos."""
    eventos: list[dict] = []
    for msg in mensagens:
        if isinstance(msg, ModelResponse):
            for parte in msg.parts:
                if isinstance(parte, ToolCallPart):
                    eventos.append(
                        {
                            "tipo": "chamada_tool",
                            "tool": parte.tool_name,
                            "argumentos": parte.args_as_dict(),
                        }
                    )
                elif isinstance(parte, TextPart) and parte.content.strip():
                    eventos.append({"tipo": "texto_modelo", "conteudo": parte.content})
        elif isinstance(msg, ModelRequest):
            for parte in msg.parts:
                if isinstance(parte, ToolReturnPart):
                    eventos.append(
                        {
                            "tipo": "retorno_tool",
                            "tool": parte.tool_name,
                            "retorno": _serializavel(parte.content),
                        }
                    )
    return eventos


def contar_chamadas_tool(trace: list[dict]) -> int:
    """Quantas tools o agente chamou. Mede ineficiencia: um agente que contorna
    uma tool defeituosa gasta muito mais round-trips."""
    return sum(1 for ev in trace if ev.get("tipo") == "chamada_tool")


def salvar_trace(pergunta: str, resposta: str, trace: list[dict]) -> Path:
    """Grava pergunta, resposta e trace em traces/ como JSON; devolve o caminho."""
    TRACES_DIR.mkdir(exist_ok=True)
    caminho = TRACES_DIR / f"{datetime.now():%Y%m%d-%H%M%S-%f}.json"
    caminho.write_text(
        json.dumps(
            {"pergunta": pergunta, "resposta": resposta, "trace": trace},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return caminho


def imprimir_trace(trace: list[dict], largura: int = 100) -> None:
    """Imprime o trace no terminal, uma linha por evento, cortada em `largura`."""
    for ev in trace:
        if ev["tipo"] == "chamada_tool":
            args = json.dumps(ev["argumentos"], ensure_ascii=False)
            print(f"  ->  {ev['tool']}({_cortar(args, largura)})")
        elif ev["tipo"] == "retorno_tool":
            retorno = json.dumps(ev["retorno"], ensure_ascii=False)
            print(f"  <-  {ev['tool']}: {_cortar(retorno, largura)}")
        else:
            print(f"  ...  {_cortar(ev['conteudo'], largura)}")


def _cortar(s: str, n: int) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def _serializavel(x: Any) -> Any:
    try:
        json.dumps(x)
        return x
    except (TypeError, ValueError):
        return str(x)
