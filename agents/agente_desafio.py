"""Agente de perguntas sobre cinema.

Entrypoint: responder(pergunta) -> {"resposta": str, "trace": list}

#Modelo via env MODELO_LLM (default: gpt-5.4-mini, key em OPENAI_API_KEY).
Modelo via env MODELO_LLM (default: gpt-5.4-mini, key em OPENAI_API_KEY).
"""

import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.usage import UsageLimits

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
load_dotenv(RAIZ / ".env")

from utils.cost import registrar as registrar_custo  # noqa: E402
from utils.database import executar_sql  # noqa: E402
from utils.observabilidade import configurar_logfire, logar_resposta  # noqa: E402
from utils.retrieval import buscar  # noqa: E402
from utils.trace import extrair_trace  # noqa: E402

MODELO = os.environ.get("MODELO_LLM", "openai:gpt-5.4-mini-2026-03-17")

configurar_logfire()  # no-op sem LOGFIRE_TOKEN


class RespostaAgente(BaseModel):
    rationale: str = Field(description="Raciocinio breve: quais tools voce usou e por que, e como chegou na resposta.")
    resposta: str = Field(description="A resposta final, direta e curta, em portugues. Se a pergunta pede um numero, o numero exato.")


INSTRUCOES = """\
Voce e um assistente especialista em cinema. Responda perguntas usando as tools
disponiveis.

Regras:
- Os roteiros e os dados do banco estao em INGLES. Formule buscas e consultas
  em ingles; responda ao usuario em portugues.
- Preencha primeiro o rationale (quais tools usou e por que) e so depois a
  resposta. Se a pergunta pede um numero, de o numero exato retornado pela tool.

Formato do campo resposta (a explicacao fica so no rationale):
- Va direto ao fato pedido, sem repetir a pergunta e sem ressalvas.
- Numero: so o numero (com unidade se fizer sentido), sem frase.
- Nome/titulo: o nome exato, sem comentarios extras.
- Pergunta com varias partes (ex: dois filmes, dois fatos): inclua todas as
  partes na resposta, uma apos a outra.
"""

agente = Agent(instructions=INSTRUCOES, retries=3, output_type=RespostaAgente)


@agente.tool_plain
def buscar_roteiros(consulta: str, k: int = 1) -> list[dict]:
    """Busca trechos dos roteiros dos filmes.

    Args:
        consulta: o que procurar, em ingles.
        k: quantos trechos retornar.
    """
    return buscar(consulta, k=max(1, min(int(k), 8)))


@agente.tool_plain
def consultar_sql(sql: str) -> list[dict]:
    """Consulta o banco de dados de filmes.

    Args:
        sql: a consulta SELECT (dialeto SQLite).
    """
    interna = sql.strip().rstrip(";")
    try:
        return executar_sql(interna)
    except sqlite3.Error as e:
        raise ModelRetry(f"Erro de SQL: {e}") from e


def responder(pergunta: str) -> dict:
    """Assinatura fixa do desafio: pergunta -> {"resposta", "trace"}."""
    resultado = agente.run_sync(pergunta, model=MODELO, usage_limits=UsageLimits(request_limit=10))
    uso = resultado.usage
    registrar_custo(uso.input_tokens, uso.output_tokens, rotulo="desafio")
    logar_resposta(resultado.output.resposta, resultado.output.rationale)
    return {
        "resposta": resultado.output.resposta,
        "rationale": resultado.output.rationale,
        "trace": extrair_trace(resultado.all_messages()),
    }


if __name__ == "__main__":
    from utils.trace import imprimir_trace, salvar_trace

    pergunta = " ".join(sys.argv[1:]) or "Qual filme de Christopher Nolan tem a maior bilheteria?"
    r = responder(pergunta)
    print(f"\nPERGUNTA: {pergunta}\n")
    imprimir_trace(r["trace"])
    print(f"\nRESPOSTA: {r['resposta']}")
    print(f"\ntrace salvo em {salvar_trace(pergunta, r['resposta'], r['trace'])}")
