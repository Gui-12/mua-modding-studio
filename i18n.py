"""Idioma do MUA Studio: pt-BR (oficial, texto original do código) ou inglês.

O código-fonte continua escrito em português; quando o idioma é inglês, os textos são
traduzidos na hora em que chegam aos widgets do tkinter (rótulos, menus, títulos, caixas
de diálogo, árvores, saídas de texto marcadas). Nenhum dado de arquivo é tocado.
A escolha fica em settings.json (chave "lang") e vale a partir da próxima abertura."""
from __future__ import annotations

import json
import os
import re
import tkinter as tk
from tkinter import ttk

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(HERE, "settings.json")

LANGS = [("pt-BR", "Português (Brasil)"), ("en", "English")]
DEFAULT = "pt-BR"
OPT_KEYS = ("text", "title", "label", "message", "detail")

_lang = DEFAULT
_exact: dict[str, str] = {}
_templates: list[tuple[re.Pattern, str]] = []
_fragments: list[tuple[str, str]] = []
_cache: dict[str, str] = {}
_installed = False


def current() -> str:
    return _lang


def read_saved() -> str:
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            v = json.load(f).get("lang", DEFAULT)
        return v if v in dict(LANGS) else DEFAULT
    except Exception:
        return DEFAULT


def save(lang: str):
    """Grava o idioma preservando o resto do settings.json."""
    try:
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["lang"] = lang
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
    except OSError:
        pass


def _load_table(lang: str):
    global _exact, _templates, _fragments
    _exact, _templates, _fragments = {}, [], []
    _cache.clear()
    if lang == "pt-BR":
        return
    mod = __import__("lang_" + lang.replace("-", "_").lower())
    table = mod.EN if lang == "en" else getattr(mod, "TABLE")
    for pt, tr in table.items():
        if "{}" in pt:
            pat = "".join("(.*?)" if p == "{}" else re.escape(p) for p in re.split(r"(\{\})", pt))
            _templates.append((re.compile(pat + r"\Z", re.S), tr))
        else:
            _exact[pt] = tr
            if len(pt.strip()) >= 8:
                _fragments.append((pt, tr))
    _templates.sort(key=lambda t: -len(t[0].pattern))
    _fragments.sort(key=lambda t: -len(t[0]))


def _one(s: str) -> str | None:
    r = _exact.get(s)
    if r is not None:
        return r
    for rx, tr in _templates:
        m = rx.match(s)
        if m:
            try:
                return tr.format(*m.groups())
            except (IndexError, KeyError, ValueError):
                return None
    return None


def tr(s, fragments: bool = True):
    """Traduz um texto de interface (devolve o mesmo texto se não houver tradução)."""
    if _lang == DEFAULT or not isinstance(s, str) or not s or not _has_letters(s):
        return s
    hit = _cache.get(s)
    if hit is not None:
        return hit
    out = _one(s)
    if out is None and "\n" in s:
        parts = [_one(p) or p for p in s.split("\n")]
        joined = "\n".join(parts)
        if joined != s:
            out = joined
    if out is None and fragments:
        cur = s
        for pt, en in _fragments:
            if pt in cur:
                cur = cur.replace(pt, en)
        if cur != s:
            out = cur
    if out is None:
        out = s
    if len(_cache) < 20000:
        _cache[s] = out
    return out


_LETTERS = re.compile(r"[A-Za-zÀ-ÿ]{2}")


def _has_letters(s: str) -> bool:
    return bool(_LETTERS.search(s))


def _tr_dict(d, keys=OPT_KEYS):
    if not d:
        return d
    out = None
    for k in keys:
        v = d.get(k)
        if isinstance(v, str):
            t = tr(v)
            if t is not v:
                if out is None:
                    out = dict(d)
                out[k] = t
    return out if out is not None else d


def install(lang: str | None = None):
    """Escolhe o idioma e instala os ganchos no tkinter (uma vez só)."""
    global _lang, _installed
    _lang = lang or read_saved()
    _load_table(_lang)
    if _installed or _lang == DEFAULT:
        return
    _installed = True

    # opções de widgets, menus, canvas, diálogos de arquivo/cor (todos passam por Misc._options)
    orig_options = tk.Misc._options

    def _options(self, cnf, kw=None):
        if isinstance(kw, dict):
            kw = _tr_dict(kw)
        if isinstance(cnf, dict):
            cnf = _tr_dict(cnf)
        return orig_options(self, cnf, kw)
    tk.Misc._options = _options

    # ttk usa o seu próprio formatador (Notebook.add, Treeview.heading/insert...)
    orig_fmt = ttk._format_optdict

    def _format_optdict(optdict, script=False, ignore=None):
        return orig_fmt(_tr_dict(optdict, ("text",)), script, ignore)
    ttk._format_optdict = _format_optdict

    # título das janelas
    orig_title = tk.Wm.wm_title

    def wm_title(self, string=None):
        return orig_title(self, tr(string) if isinstance(string, str) else string)
    tk.Wm.wm_title = wm_title
    tk.Wm.title = wm_title

    # variáveis (StringVar usada em rótulos): só tradução exata/modelo, sem trechos
    orig_set = tk.Variable.set

    def vset(self, value):
        if isinstance(value, str):
            value = tr(value, fragments=False)
        return orig_set(self, value)
    tk.Variable.set = vset

    # caixas de mensagem
    from tkinter import messagebox
    orig_show = messagebox._show

    def _show(title=None, message=None, *a, **kw):
        return orig_show(tr(title), tr(message), *a, **kw)
    messagebox._show = _show

    # saídas de texto marcadas (prévias): só widgets com _i18n = True
    orig_insert = tk.Text.insert

    def insert(self, index, chars, *args):
        if getattr(self, "_i18n", False) and isinstance(chars, str):
            chars = tr(chars)
        return orig_insert(self, index, chars, *args)
    tk.Text.insert = insert


def mark_output(widget):
    """Marca um tk.Text como saída de programa (e não conteúdo de arquivo) para ser traduzido."""
    widget._i18n = True
    return widget
