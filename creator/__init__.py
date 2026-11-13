"""Criador de Personagem (módulo à parte do MUA Studio).

Atualizado separadamente do MUA Studio: tudo mora nesta pasta. O MUA Studio só chama open_creator(app);
sem ele, rode 'Run Character Creator.bat' (python -m creator).
"""
from __future__ import annotations

VERSION = "0.1.0"

_win = None


def open_creator(host, faq: str | None = None):
    """Abre (ou traz para frente) a janela do criador. host = App do MUA Studio ou StandaloneHost."""
    global _win
    from .wizard import CreatorWindow
    try:
        if _win is not None and _win.winfo_exists():
            _win.deiconify()
            _win.lift()
            _win.focus_force()
        else:
            _win = CreatorWindow(host)
    except Exception:
        _win = CreatorWindow(host)
    if faq is not None:
        _win.open_faq(faq)
    return _win
