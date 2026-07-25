"""Constroi data/chroma/ a partir de data/roteiros/*.txt e data/filmes.sqlite.

    uv run python scripts/build_index.py
"""

import shutil
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from utils.retrieval import CHROMA_DIR, COLECAO, FastEmbed  # noqa: E402

LOTE = 256


def main() -> None:
    from utils.chunking import chunk_roteiro
    chroma_dir = CHROMA_DIR

    con = sqlite3.connect(RAIZ / "data" / "filmes.sqlite")
    filmes = con.execute(
        "SELECT id, titulo, ano FROM filmes WHERE tem_roteiro = 1 ORDER BY titulo"
    ).fetchall()
    con.close()

    import re
    import unicodedata

    def slug(s: str) -> str:
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

    chunks = []
    for filme_id, titulo, ano in filmes:
        caminho = RAIZ / "data" / "roteiros" / f"{slug(titulo)}.txt"
        if not caminho.exists():
            print(f"  !! roteiro ausente: {titulo}")
            continue
        novos = chunk_roteiro(titulo, ano, caminho.read_text(encoding="utf-8"))
        for c in novos:
            c["filme_id"] = filme_id
        chunks.extend(novos)

    print(f"{len(filmes)} filmes -> {len(chunks)} chunks")

    shutil.rmtree(chroma_dir, ignore_errors=True)
    import chromadb

    cliente = chromadb.PersistentClient(path=str(chroma_dir))
    col = cliente.get_or_create_collection(
        name=COLECAO, embedding_function=FastEmbed(), metadata={"hnsw:space": "cosine"}
    )

    for i in range(0, len(chunks), LOTE):
        lote = chunks[i : i + LOTE]
        col.add(
            ids=[f"{slug(c['filme'])}-{c['n_cena']}-{c['parte']}" for c in lote],
            documents=[c["texto"] for c in lote],
            metadatas=[
                {
                    "filme_id": c["filme_id"],
                    "filme": c["filme"],
                    "ano": c["ano"],
                    "cena": c["n_cena"],
                    "personagens": ", ".join(c["personagens"][:8]),
                }
                for c in lote
            ],
        )
        print(f"  indexado {min(i + LOTE, len(chunks))}/{len(chunks)}", flush=True)

    print(f"pronto: {col.count()} chunks em {chroma_dir}")


if __name__ == "__main__":
    main()
