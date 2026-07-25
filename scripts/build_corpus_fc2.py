"""Reconstroi o corpus de roteiros usando SOMENTE o Film Corpus 2.0 (UCSC/NLDS).

DESTRUTIVO e reproduzivel: zera tem_roteiro nos 1000 filmes, apaga os
data/roteiros/*.txt atuais e regrava apenas os filmes do FC2 que casam com o
Top 1000 (medido: 237 distintos). A base SQL (1000 filmes) fica intacta.

Fonte: data/raw/film_corpus2/imsdb_raw_nov_2015/<genero>/<slug>.txt
Rode:  uv run python scripts/build_corpus_fc2.py
Depois: uv run python scripts/build_index.py   (reconstroi o indice Chroma)
"""

import glob
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "data" / "filmes.sqlite"
ROTEIROS = RAIZ / "data" / "roteiros"
FC2 = RAIZ / "data" / "raw" / "film_corpus2" / "imsdb_raw_nov_2015"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = re.sub(r"^(the|a|an)\s+", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# Casamentos conferidos a mao que o matcher automatico nao pega:
# - nome de arquivo FC2 malformado ('...the' sobrando);
# - IMDb abrevia o titulo ('Mulholland Dr.' vs 'mulhollanddrive').
FORCADOS = {
    "planetoftheapesthe": "Planet of the Apes",
    "mulhollanddrive": "Mulholland Dr.",
}


def casar(base: str, imdb: dict[str, str]) -> str | None:
    """Casa um nome de arquivo FC2 a uma chave do IMDb, ou None.

    Trata a convencao 'Title, The'/'Title, A' que o IMSDb grava como
    'titlethe'/'titlea'. GUARDA: o strip do artigo so vale se o titulo do IMDb
    realmente comeca com esse artigo — senao 'queenthe' (= The Queen) casaria
    com 'Queen', que e outro filme.
    """
    if base in FORCADOS:
        return norm(FORCADOS[base])
    b = norm(base)
    if b in imdb:
        return b
    if b.endswith("the") and b[:-3] in imdb and imdb[b[:-3]].lower().startswith("the "):
        return b[:-3]
    if b.endswith("a") and b[:-1] in imdb and re.match(r"an? ", imdb[b[:-1]].lower()):
        return b[:-1]
    return None


_TAG = re.compile(r"<[^>]{1,60}>")
_JS = re.compile(r"(window\s*!?=|top\.location|location\.href|document\.)")


def limpar(texto: str) -> str:
    """Tira o cabecalho HTML/JS do scrape do IMSDb, preservando o roteiro."""
    texto = _TAG.sub("", texto)
    linhas = [ln for ln in texto.split("\n") if not _JS.search(ln)]
    texto = "\n".join(linhas)
    return texto.strip() + "\n"


def main() -> None:
    con = sqlite3.connect(DB)
    imdb = {norm(t): t for (t,) in con.execute("SELECT titulo FROM filmes")}

    # casa cada arquivo FC2 a um titulo do IMDb (1o arquivo vence)
    casados: dict[str, str] = {}
    for p in sorted(glob.glob(str(FC2 / "*" / "*.txt"))):
        c = casar(os.path.basename(p)[:-4], imdb)
        if c and c not in casados:
            casados[c] = p
    print(f"FC2 casa {len(casados)} filmes do Top 1000.")

    # ZERA o estado atual: tem_roteiro=0 em tudo e apaga os .txt existentes
    con.execute("UPDATE filmes SET tem_roteiro = 0")
    con.commit()
    ROTEIROS.mkdir(parents=True, exist_ok=True)
    apagados = 0
    for antigo in ROTEIROS.glob("*.txt"):
        antigo.unlink()
        apagados += 1
    print(f"apagados {apagados} roteiros antigos; tem_roteiro zerado.")

    escritos, pulados = 0, 0
    for k, p in casados.items():
        titulo = imdb[k]
        texto = limpar(Path(p).read_text(encoding="utf-8", errors="ignore"))
        if len(texto) < 2000:  # scrape vazio/quebrado: pula
            print(f"  ~ pulado (curto demais): {titulo}")
            pulados += 1
            continue
        (ROTEIROS / f"{slug(titulo)}.txt").write_text(texto, encoding="utf-8")
        con.execute("UPDATE filmes SET tem_roteiro = 1 WHERE titulo = ?", (titulo,))
        escritos += 1

    con.commit()
    total_db = con.execute("SELECT COUNT(*) FROM filmes WHERE tem_roteiro = 1").fetchone()[0]
    con.close()
    total_disco = len(list(ROTEIROS.glob("*.txt")))
    print(f"roteiros escritos: {escritos} (pulados: {pulados})")
    print(f"tem_roteiro=1 no banco: {total_db} | .txt no disco: {total_disco}")
    assert total_db == total_disco == escritos, "INCONSISTENTE: banco != disco"
    print("OK: banco e disco consistentes. proximo: uv run python scripts/build_index.py")


if __name__ == "__main__":
    main()
