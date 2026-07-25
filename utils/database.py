"""Acesso somente-leitura ao data/filmes.sqlite."""

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "filmes.sqlite"

SCHEMA = """\
CREATE TABLE filmes (
    id             INTEGER PRIMARY KEY,
    titulo         TEXT,     -- titulo original em ingles, ex.: 'The Godfather'
    ano            INTEGER,  -- ano de lancamento
    certificado    TEXT,     -- classificacao etaria (U, A, R, PG-13...)
    duracao_min    INTEGER,  -- duracao em minutos
    nota_imdb      REAL,     -- nota IMDb (0-10)
    metascore      INTEGER,  -- Metascore (0-100), pode ser NULL
    votos          INTEGER,  -- numero de votos no IMDb
    bilheteria_usd INTEGER,  -- bilheteria bruta em dolares, pode ser NULL
    diretor        TEXT,
    sinopse        TEXT,     -- em ingles
    tem_roteiro    INTEGER   -- 1 se o roteiro esta no indice de busca
);
CREATE TABLE filme_genero (
    filme_id INTEGER REFERENCES filmes(id),
    genero   TEXT             -- ex.: 'Drama', 'Comedy', 'Sci-Fi'
);
CREATE TABLE filme_ator (
    filme_id INTEGER REFERENCES filmes(id),
    ator     TEXT,
    posicao  INTEGER          -- 1 a 4, ordem de credito
);"""

LIMITE_LINHAS = 50


TABELAS = ("filmes", "filme_genero", "filme_ator")


def executar_sql(sql: str) -> list[dict]:
    """Executa uma consulta SELECT e devolve as linhas como dicionarios."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        linhas = con.execute(sql).fetchmany(LIMITE_LINHAS)
        return [dict(l) for l in linhas]
    finally:
        con.close()


def ler_tabela(tabela: str, limite: int = 10) -> list[dict]:
    """Le as primeiras `limite` linhas de uma tabela, como dicionarios.

    Atalho de leitura sobre executar_sql(). Valida o nome contra TABELAS
    porque o identificador de tabela nao pode ser parametrizado em SQL.
    """
    if tabela not in TABELAS:
        raise ValueError(f"tabela desconhecida: {tabela!r}; use uma de {TABELAS}")
    return executar_sql(f"SELECT * FROM {tabela} LIMIT {int(limite)}")



if __name__ == "__main__":
    # pandas so aqui: e do grupo `build`, nao das deps de runtime. Se ficar no
    # topo do modulo, quebra o agente (agente_desafio importa executar_sql daqui).
    import pandas as pd

    # Leitura dos dados do banco de dados
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    df = pd.read_sql("SELECT * FROM filmes LIMIT 10", con)  # tire o LIMIT p/ ver as 1000
    con.close()

    pd.set_option("display.max_columns", None)  # nao colapsa colunas (tira o ...)
    pd.set_option("display.width", None)  # usa a largura real do terminal
    print(df.drop(columns=["sinopse"]).to_string(index=False))  # sinopse e longa
