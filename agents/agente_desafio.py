"""Agente de perguntas sobre cinema.

Entrypoint: responder(pergunta) -> {"resposta": str, "trace": list}

Modelo via env MODELO_LLM (default: gpt-5.4-mini, key em OPENAI_API_KEY).
"""

import os
import re
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
- Use consultar_sql para fatos estruturados, rankings, contagens e comparacoes.
  O schema e: filmes(id, titulo, ano, certificado, duracao_min, nota_imdb,
  metascore, votos, bilheteria_usd, diretor, sinopse, tem_roteiro),
  filme_genero(filme_id, genero) e filme_ator(filme_id, ator, posicao).
- Para JOINs, ligue filme_genero.filme_id ou filme_ator.filme_id a filmes.id.
  Para rankings, selecione todos os candidatos, use ORDER BY e LIMIT no SQL.
- Use buscar_roteiros para fatos que aparecem no texto dos roteiros. Quando a
  pergunta mencionar filmes especificos, passe o titulo em `filme` e use k=3
  ou k=5 se a resposta puder estar espalhada em mais de um trecho.
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
def buscar_roteiros(consulta: str, k: int = 3, filme: str | None = None) -> list[dict]:
    """Busca trechos dos roteiros dos filmes.

    Args:
        consulta: o que procurar, em ingles.
        k: quantos trechos retornar.
        filme: titulo exato do filme para restringir a busca, se conhecido.
    """
    # Evita retornos excessivamente grandes, sem descartar os demais trechos
    # solicitados pelo agente.
    k_seguro = max(1, min(int(k), 8))
    return buscar(consulta, k=k_seguro, filme=filme)


@agente.tool_plain
def consultar_sql(sql: str) -> list[dict]:
    """Consulta o banco de dados de filmes.

    Args:
        sql: a consulta SELECT (dialeto SQLite).
    """
    interna = sql.strip().rstrip(";")
    try:
        if not re.match(r"^(SELECT|WITH)\b", interna, flags=re.IGNORECASE):
            raise ModelRetry("A tool aceita apenas consultas SELECT ou WITH.")
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
    try:
        r = responder(pergunta)
    except Exception as e:  # noqa: BLE001 — reduz traceback de falhas externas no CLI
        if os.environ.get("DEBUG_TRACEBACK") == "1":
            raise
        mensagem = str(e)
        if "credit_balance_exhausted" in mensagem or "no credits remaining" in mensagem.lower():
            print("Erro: a API OpenAI está sem créditos. Verifique o billing da organização ou use outra chave com saldo.")
        elif "429" in mensagem or "rate limit" in mensagem.lower():
            print("Erro: limite de requisições da API OpenAI atingido. Tente novamente mais tarde.")
        else:
            print(f"Erro ao executar o agente: {type(e).__name__}: {mensagem}")
        raise SystemExit(1)
    print(f"\nPERGUNTA: {pergunta}\n")
    imprimir_trace(r["trace"])
    print(f"\nRESPOSTA: {r['resposta']}")
    print(f"\ntrace salvo em {salvar_trace(pergunta, r['resposta'], r['trace'])}")
