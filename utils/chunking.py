"""Quebra um roteiro em blocos de tamanho fixo, sem olhar para cena/fala."""

from utils.personagens import extrair_personagens

TAMANHO_CHUNK = 2800


def chunk_roteiro(filme: str, ano: int, roteiro: str) -> list[dict]:
    """Corta o roteiro em janelas de TAMANHO_CHUNK caracteres, sem overlap."""
    chunks: list[dict] = []
    for i in range(0, len(roteiro), TAMANHO_CHUNK):
        parte = roteiro[i : i + TAMANHO_CHUNK]
        if not parte.strip():
            continue
        chunks.append(
            {
                "texto": parte,
                "filme": filme,
                "ano": ano,
                "n_cena": i // TAMANHO_CHUNK + 1,
                "parte": 1,
                "personagens": extrair_personagens(parte),
            }
        )
    return chunks
