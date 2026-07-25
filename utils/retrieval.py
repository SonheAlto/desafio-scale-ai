"""Indice vetorial dos roteiros: fastembed (ONNX, sem torch) + ChromaDB local.

O indice ja vem construido em data/chroma/. Para reconstruir:
    uv run python scripts/build_index.py
"""

import argparse
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import EmbeddingFunction

DATA = Path(__file__).resolve().parent.parent / "data"
CHROMA_DIR = DATA / "chroma"
COLECAO = "roteiros"
# Os roteiros estao em ingles e as consultas devem ser feitas em ingles (o
# agente traduz). bge-small-en-v1.5: 384d, ONNX, roda local sem GPU nem API.
MODELO_EMBEDDING = "BAAI/bge-small-en-v1.5"


class FastEmbed(EmbeddingFunction):
    """Funcao de embedding do ChromaDB baseada em fastembed (ONNX, sem torch)."""

    def __init__(self, modelo: str = MODELO_EMBEDDING):
        from fastembed import TextEmbedding

        self._modelo = TextEmbedding(model_name=modelo)
        self._nome = modelo

    def __call__(self, input):  # noqa: A002 — assinatura exigida pelo Chroma
        return [e.tolist() for e in self._modelo.embed(list(input))]

    @staticmethod
    def name() -> str:
        return "fastembed"


@lru_cache(maxsize=None)
def colecao(chroma_dir: Path = CHROMA_DIR):
    """Retorna a colecao do ChromaDB em `chroma_dir`, criando se necessario."""
    cliente = chromadb.PersistentClient(path=str(chroma_dir))
    return cliente.get_or_create_collection(
        name=COLECAO,
        embedding_function=FastEmbed(),
        metadata={"hnsw:space": "cosine"},
    )


def buscar(consulta: str, k: int = 5, filme: str | None = None,
           chroma_dir: Path = CHROMA_DIR) -> list[dict]:
    """Busca semantica nos roteiros. `filme` restringe a um titulo exato."""
    where = {"filme": filme} if filme else None
    r = colecao(chroma_dir).query(query_texts=[consulta], n_results=k, where=where)
    saida = []
    for texto, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
        saida.append(
            {
                "texto": texto,
                "filme_id": meta.get("filme_id"),
                "filme": meta["filme"],
                "ano": meta["ano"],
                "cena": meta["cena"],
                "personagens": meta.get("personagens", ""),
                "score": round(1 - dist, 4),
            }
        )
    return saida


LARGURAS_TABELA = {
    "filme": 25,
    "filme_id": 8,
    "ano": 5,
    "cena": 5,
    "personagens": 30,
    "texto": 60,
}
ORDEM_TABELA = ("filme", "filme_id", "ano", "cena", "personagens", "texto")


def _linha_tabela(filme: str, filme_id: str, ano: int, personagens: str, cena: int, texto: str) -> str:
    campos = {
        "filme": str(filme)[: LARGURAS_TABELA["filme"]],
        "filme_id": str(filme_id)[: LARGURAS_TABELA["filme_id"]],
        "ano": str(ano)[: LARGURAS_TABELA["ano"]],
        "cena": str(cena)[: LARGURAS_TABELA["cena"]],
        "personagens": str(personagens)[: LARGURAS_TABELA["personagens"]],
        "texto": texto.replace("\n", " ")[: LARGURAS_TABELA["texto"]],
    }
    return " | ".join(campos[c].ljust(LARGURAS_TABELA[c]) for c in ORDEM_TABELA)


def imprimir_chunks(n: int = 15, busca: str | None = None, filme: str | None = None, chroma_dir: Path = CHROMA_DIR) -> None:
    """Mostra chunks do indice em formato de tabela. Sem `busca`, lista os
    primeiros do indice; com `busca`, faz busca semantica (em ingles)."""
    print(_linha_tabela("filme", "filme_id", "ano", "personagens", "cena", "texto"))
    print("-" * (sum(LARGURAS_TABELA.values()) + 3 * (len(LARGURAS_TABELA) - 1)))

    if busca:
        for r in buscar(busca, k=n, filme=filme, chroma_dir=chroma_dir):
            print(_linha_tabela(r["filme"], r["filme_id"], r["ano"], r["personagens"], r["cena"], r["texto"]))
        return

    where = {"filme": filme} if filme else None
    r = colecao(chroma_dir).get(limit=n, where=where, include=["documents", "metadatas"])
    for doc, meta in zip(r["documents"], r["metadatas"]):
        print(_linha_tabela(meta["filme"], meta["filme_id"], meta["ano"],meta["personagens"], meta["cena"], doc))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=15)
    p.add_argument("--busca", help="busca semantica (em ingles)")
    p.add_argument("--filme", help="restringe a um titulo exato")
    args = p.parse_args()
    imprimir_chunks(n=args.n, busca=args.busca, filme=args.filme)
