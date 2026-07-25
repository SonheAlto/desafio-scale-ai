"""Observabilidade opcional via Pydantic Logfire.

Ativa so quando LOGFIRE_TOKEN esta no ambiente. Sem token (o caso dos
participantes), e um no-op silencioso: o trace.py local continua sendo a
ferramenta de diagnostico do desafio. Logfire, quando ligado, instrumenta o
pydantic-ai e envia spans (tools, tokens, latencia) para o dashboard.
"""

import os

_configurado = False


def configurar_logfire() -> bool:
    """Configura o Logfire uma vez, se houver LOGFIRE_TOKEN. Devolve se ligou."""
    global _configurado
    if _configurado or not os.environ.get("LOGFIRE_TOKEN"):
        return _configurado
    try:
        import logfire
    except ImportError:
        return False
    logfire.configure(
        service_name="desafio-cinema",
        console=False,
        # instancia US (nao e o default) — o token e da regiao US.
        advanced=logfire.AdvancedOptions(base_url="https://logfire-us.pydantic.dev"),
    )
    logfire.instrument_pydantic_ai()
    _configurado = True
    return True


def logar_resposta(resposta: str, rationale: str) -> None:
    """Emite um span com a resposta final (texto pesquisavel no Live view).

    Com saida estruturada, a resposta vai numa tool call `final_result`, entao o
    'Final output' do Logfire fica vazio; este span expoe a resposta em texto.
    No-op se o Logfire nao estiver configurado.
    """
    if not _configurado:
        return
    import logfire

    logfire.info("resposta final", resposta=resposta, rationale=rationale)
