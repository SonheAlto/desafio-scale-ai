"""Extracao de nomes de personagens a partir das deixas de dialogo do roteiro.

Usado pelo chunker (utils/chunking.py): a deteccao de personagem e ortogonal
a como o texto e fatiado.
"""

import re

# Deixa de fora marcacoes de producao que tambem vem em caixa alta.
NAO_PERSONAGEM = {
    "FADE IN", "FADE OUT", "CUT TO", "CONTINUED", "THE END", "DISSOLVE TO",
    "SMASH CUT", "MATCH CUT", "INTERCUT", "BACK TO SCENE", "OMITTED",
    "SHOOTING SCRIPT", "FINAL DRAFT", "FIRST DRAFT", "REVISED", "TITLE",
    "CREDITS", "MAIN TITLES", "END CREDITS", "ANGLE ON", "CLOSE ON",
    "WIDE SHOT", "POV", "MONTAGE", "END MONTAGE", "FLASHBACK", "LATER",
    "CONTINUOUS", "MORE", "BEAT", "PAUSE", "SILENCE", "BLACK", "WHITE",
}


def extrair_personagens(texto: str) -> list[str]:
    """Deixas de dialogo: linha recuada, em caixa alta, curta."""
    achados: list[str] = []
    for linha in texto.split("\n"):
        recuo = len(linha) - len(linha.lstrip())
        nome = linha.strip()
        if recuo < 10 or not (2 <= len(nome) <= 40):
            continue
        nome = re.sub(r"\s*\((?:V\.O\.|O\.S\.|CONT'D|CONTD|cont'd)[^)]*\)", "", nome).strip()
        if not nome or nome != nome.upper() or not re.fullmatch(r"[A-Z0-9 .'#-]+", nome):
            continue
        if nome in NAO_PERSONAGEM or not re.search(r"[A-Z]{2}", nome):
            continue
        if nome not in achados:
            achados.append(nome)
    return achados
