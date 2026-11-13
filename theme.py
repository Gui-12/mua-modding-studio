"""Tema visual do MUA Studio: cores, fontes, ícones e widgets próprios.

Só biblioteca padrão (tkinter + ctypes). app.py chama setup(root) uma vez, logo depois de criar a janela.
Não importa app.py nem extras.py, então qualquer módulo pode importar daqui."""
from __future__ import annotations

import ctypes
import json
import os
import sys
import zlib
import tkinter as tk
from tkinter import ttk, font as tkfont

# CustomTkinter vem embutido em vendor/pylibs (ninguém precisa de pip)
_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "pylibs")
if os.path.isdir(_VENDOR) and _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)
import customtkinter as ctk  # noqa: E402

# ------------------------------------------------------------------ cores (tema escuro / claro)
# A escolha fica em settings.json (chave "theme") e vale a partir da próxima abertura,
# porque as cores são lidas pelos outros módulos na importação (from theme import BG...).
_HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(_HERE, "settings.json")
MODES = (("dark", "Escuro"), ("light", "Claro"))


def read_mode() -> str:
    env = os.environ.get("MUA_THEME")  # para testes: força o tema sem mexer no settings.json
    if env in dict(MODES):
        return env
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            m = json.load(f).get("theme", "dark")
        return m if m in dict(MODES) else "dark"
    except Exception:
        return "dark"


def save_mode(mode: str):
    """Grava o tema preservando o resto do settings.json."""
    data = {}
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass
    data["theme"] = mode
    try:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
    except OSError:
        pass


_DARK = dict(
    BG="#16171a", PANEL="#1e2024", SURFACE="#26292e", LINE="#2f3238", HOVER="#363940",
    FG="#dfe1e5", DIM="#8b8f98", FAINT="#5d6068", STRONG="#ffffff",
    ACCENT="#4a88ff", ACCENT_HOVER="#6a9dff", ACCENT_PRESS="#3b78ee", SEL="#263b5e", SEL_FG="#ffffff",
    SCROLL="#373a41", SCROLL_HOVER="#4a4e58",
    SYN_BLOCK="#e0a45c", SYN_KEY="#7fb4f0", SYN_VAR="#d98ee0", SYN_NUM="#9bd88f", SYN_PATH="#e6d27a",
    SYN_COMMENT="#6a8a5a", SYN_PUNCT="#6d7178",
    ERR="#ff5d5d", ERR_SOFT="#ff8080", ERR_BG="#3a2023",
    WARN="#e0b040", WARN_SOFT="#f0c869", WARN_BG="#2e2a1d",
    OK="#34d399", OK_SOFT="#a7f3d0", OK_BG="#13302a",
    PINK="#f472b6", PURPLE="#c084fc", AMBER="#fbbf24",
    CURLINE="#1d1e22", FOUND_BG="#5a4b1a", BLOCKSEL_BG="#3d3418", SHEET_FG="#fcd34d",
    INFO_FG="#a9c7ff", PURPLE_FG="#d8b4fe", RED_FG="#fca5a5", BANNER_WARN_FG="#f3dc9b", BANNER_INFO_FG="#bcd3ff",
    # bolinhas de status dos personagens
    ST_GAME="#22c55e", ST_OUT="#ef4444", ST_OTHER="#3b82f6", ST_CREATED="#facc15",
)
_LIGHT = dict(
    BG="#ffffff", PANEL="#f4f5f7", SURFACE="#e9ebef", LINE="#d7dae0", HOVER="#dde0e6",
    FG="#1f2328", DIM="#5c636e", FAINT="#969ca6", STRONG="#0b0d10",
    ACCENT="#2f6fec", ACCENT_HOVER="#4a86ff", ACCENT_PRESS="#245dcc", SEL="#d3e2ff", SEL_FG="#0b0d10",
    SCROLL="#c9cdd4", SCROLL_HOVER="#a9aeb7",
    SYN_BLOCK="#b45309", SYN_KEY="#1d5fb8", SYN_VAR="#a21caf", SYN_NUM="#15803d", SYN_PATH="#8a6a00",
    SYN_COMMENT="#5f7f4f", SYN_PUNCT="#8b9099",
    ERR="#d93636", ERR_SOFT="#c62828", ERR_BG="#fde4e4",
    WARN="#c58a12", WARN_SOFT="#8a5a00", WARN_BG="#fdf3dc",
    OK="#15a36a", OK_SOFT="#0f7a4f", OK_BG="#ddf5ea",
    PINK="#db2777", PURPLE="#9333ea", AMBER="#d97706",
    CURLINE="#f2f6fc", FOUND_BG="#ffe8a3", BLOCKSEL_BG="#fff3c4", SHEET_FG="#b4530a",
    INFO_FG="#1f4fae", PURPLE_FG="#7e22ce", RED_FG="#b91c1c", BANNER_WARN_FG="#6b4700", BANNER_INFO_FG="#1f4fad",
    ST_GAME="#16a34a", ST_OUT="#dc2626", ST_OTHER="#2563eb", ST_CREATED="#eab308",
)
MODE = read_mode()
_P = _LIGHT if MODE == "light" else _DARK
globals().update(_P)
WHITE = "#fffffe"   # texto sobre o azul de destaque (igual nos dois temas)
ctk.set_appearance_mode(MODE)

CHAR_COLORS = ("#ef4444", "#facc15", "#f59e0b", "#10b981", "#3b82f6", "#a855f7",
               "#ec4899", "#14b8a6", "#f97316", "#84cc16", "#6366f1", "#e11d48")

# ------------------------------------------------------------------ fontes (resolvidas em setup)
UI = ("Segoe UI", 10)
UI_B = ("Segoe UI", 10, "bold")
UI_S = ("Segoe UI", 9)
UI_SB = ("Segoe UI", 9, "bold")
UI_XS = ("Segoe UI", 8)
H1 = ("Segoe UI", 20, "bold")
H2 = ("Segoe UI", 10, "bold")
H3 = ("Segoe UI", 12, "bold")
CODE = ("Consolas", 11)
MONO = ("Consolas", 10)
MONO_S = ("Consolas", 9)
MONO_XS = ("Consolas", 8)
ICON = ("Segoe MDL2 Assets", 10)
ICON_S = ("Segoe MDL2 Assets", 8)
ICON_L = ("Segoe MDL2 Assets", 13)
HAS_ICONS = False

# Segoe Fluent Icons / Segoe MDL2 Assets
I = {
    "save": "", "bolt": "", "swap": "", "palette": "", "card": "",
    "help": "", "bulb": "", "search": "", "close": "", "right": "",
    "down": "", "warn": "", "error": "", "shield": "", "check": "",
    "star": "", "up_arrow": "", "down_arrow": "", "film": "", "people": "",
    "copy": "", "folder": "", "doc": "", "code": "", "settings": "",
    "robot": "", "package": "", "list": "", "more": "", "edit": "",
    "sliders": "", "info": "", "tree": "",
}
I.update(sun="", moon="")
GLYPH_FALLBACK = {"close": "✕", "right": "›", "down": "▾", "warn": "!", "error": "×", "check": "✓",
                  "up_arrow": "↑", "down_arrow": "↓", "search": "⌕"}


def glyph(name: str) -> str:
    return I.get(name, "") if HAS_ICONS else GLYPH_FALLBACK.get(name, "•")


def mix(c1: str, c2: str, t: float) -> str:
    """Mistura duas cores #rrggbb (t=0 -> c1, t=1 -> c2)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    r = "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))
    _DERIVED.setdefault(r, (c1.lower(), c2.lower(), t))  # para refazer a mistura no outro tema
    return r


# ------------------------------------------------------------------ conversão entre temas
_DERIVED: dict = {}
_CONV: dict = {}


def _conv(src: dict, dst: dict):
    """Função que leva uma cor do tema src para a cor equivalente do tema dst (None se não for do tema)."""
    key = (id(src), id(dst))
    if key in _CONV:
        return _CONV[key]
    base: dict = {}
    for k, v in src.items():
        base.setdefault(v.lower(), dst[k])

    def conv(c, depth=0):
        if not isinstance(c, str) or len(c) != 7 or not c.startswith("#"):
            return None
        c = c.lower()
        if c in base:
            return base[c]
        d = _DERIVED.get(c)
        if d and depth < 5:
            a = conv(d[0], depth + 1) or d[0]
            b = conv(d[1], depth + 1) or d[1]
            if (a, b) != (d[0], d[1]):
                return mix(a, b, d[2])
        return None
    _CONV[key] = conv
    return conv


def C(name: str) -> tuple:
    """Token do tema -> (claro, escuro) para widgets do CustomTkinter."""
    return (_LIGHT[name], _DARK[name])


def T(v):
    """Cor já resolvida no tema atual -> (claro, escuro); o CustomTkinter troca sozinho ao mudar o tema."""
    if not isinstance(v, str) or v == "transparent":
        return v
    light = v if _P is _LIGHT else (_conv(_P, _LIGHT)(v) or v)
    dark = v if _P is _DARK else (_conv(_P, _DARK)(v) or v)
    return (light, dark)


SCALE = 1.0  # fator de DPI (1.25 numa tela a 125%); resolvido em setup()


def px(n: float) -> int:
    """Pixels de desenho (Treeview, Canvas, imagens) na escala da tela."""
    return int(round(n * SCALE))


def cfont(f: tuple) -> tuple:
    """Fonte do tk (pontos) -> fonte do CustomTkinter (que conta em pixels e aplica a escala sozinho)."""
    return (f[0], round(f[1] * 4 / 3)) + tuple(f[2:])


def char_color(name: str) -> str:
    return CHAR_COLORS[zlib.crc32(name.lower().encode()) % len(CHAR_COLORS)]


# ------------------------------------------------------------------ janela escura (Windows 10/11)
def dark_titlebar(win: tk.Misc):
    if sys.platform != "win32" or getattr(win, "_mua_dark", False):
        return
    try:
        win.update_idletasks()
        hwnd = int(win.wm_frame(), 16)
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1 if MODE == "dark" else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (nova e antiga)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), ctypes.sizeof(on)) == 0:
                break

        def colorref(c):
            return ctypes.c_int(int(c[5:7], 16) << 16 | int(c[3:5], 16) << 8 | int(c[1:3], 16))

        for attr, c in ((35, PANEL), (34, LINE), (36, FG)):  # legenda, borda, texto (Windows 11)
            v = colorref(c)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
        win._mua_dark = True
    except Exception:
        pass


# ------------------------------------------------------------------ imagens geradas (sem arquivos)
_imgs: dict = {}


def _paint_dot(img, color, size, d):
    c = (size - 1) / 2
    r = d / 2
    for y in range(size):
        for x in range(size):
            if ((x - c) ** 2 + (y - c) ** 2) ** 0.5 <= r - 0.3:
                img.put(color, (x, y))


def _paint_sq(img, color, size, d):
    o = (size - d) // 2
    for y in range(d):
        for x in range(d):
            if (x in (0, d - 1)) and (y in (0, d - 1)):
                continue
            img.put(color, (o + x, o + y))


_PAINTERS = {"dot": _paint_dot, "sq": _paint_sq}


def _shape(kind: str, color: str, size: int, d: int) -> tk.PhotoImage:
    key = (kind, color.lower(), size, d)
    if key not in _imgs:
        s, dd = px(size), max(2, px(d))
        img = tk.PhotoImage(width=s, height=s)
        _PAINTERS[kind](img, color, s, dd)
        _imgs[key] = img
    return _imgs[key]


def dot(color: str, size: int = 14, d: int = 8) -> tk.PhotoImage:
    """Bolinha colorida centrada numa imagem size x size (ícone de personagem/aba)."""
    return _shape("dot", color, size, d)


def square(color: str, size: int = 14, d: int = 6) -> tk.PhotoImage:
    """Quadradinho arredondado (ícone dos itens filhos na árvore)."""
    return _shape("sq", color, size, d)


def blank(size: int = 14) -> tk.PhotoImage:
    key = ("blank", size)
    if key not in _imgs:
        _imgs[key] = tk.PhotoImage(width=px(size), height=px(size))
    return _imgs[key]


def _repaint_images(conv):
    """Repinta as bolinhas/quadradinhos no lugar: todos os widgets que usam a imagem mudam juntos."""
    new = {}
    for key, img in _imgs.items():
        if key[0] in _PAINTERS:
            kind, color, size, d = key
            nc = (conv(color) or color).lower()
            if nc != color:
                img.blank()
                _PAINTERS[kind](img, nc, img.width(), max(2, px(d)))
            key = (kind, nc, size, d)
        new.setdefault(key, img)
    _imgs.clear()
    _imgs.update(new)


def _fill(img, color, w, h, x0=0, y0=0):
    img.put(color, to=(x0, y0, w, h))


# ------------------------------------------------------------------ estilo ttk
def setup(root: tk.Tk):
    global UI, UI_B, UI_S, UI_SB, UI_XS, H1, H2, H3, CODE, MONO, MONO_S, MONO_XS, ICON, ICON_S, ICON_L, HAS_ICONS, SCALE
    # o CustomTkinter deixa o processo nítido (DPI) e escala os widgets dele; o tk comum precisa da mesma escala
    try:
        SCALE = float(ctk.ScalingTracker.get_window_scaling(root))
    except Exception:
        SCALE = max(1.0, root.winfo_fpixels("1i") / 96)
    root.tk.call("tk", "scaling", SCALE * 96 / 72)
    fams = set(tkfont.families(root))

    def pick(*cands):
        return next((c for c in cands if c in fams), cands[-1])

    sans = pick("Segoe UI Variable Text", "Segoe UI", "Arial")
    head = pick("Segoe UI Variable Display", "Segoe UI Semibold", sans)
    mono = pick("Cascadia Mono", "JetBrains Mono", "Consolas", "Courier New")
    icons = pick("Segoe Fluent Icons", "Segoe MDL2 Assets", "")
    HAS_ICONS = bool(icons)
    UI, UI_B, UI_S, UI_SB, UI_XS = (sans, 10), (sans, 10, "bold"), (sans, 9), (sans, 9, "bold"), (sans, 8)
    H1, H2, H3 = (head, 20, "bold"), (sans, 9, "bold"), (head, 12, "bold")
    CODE, MONO, MONO_S, MONO_XS = (mono, 10), (mono, 10), (mono, 9), (mono, 8)
    ICON, ICON_S, ICON_L = (icons or sans, 10), (icons or sans, 8), (icons or sans, 13)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
        try:
            tkfont.nametofont(name).configure(family=sans, size=10)
        except tk.TclError:
            pass

    _style(root)
    dark_titlebar(root)
    root.bind_class("Toplevel", "<Map>", lambda e: dark_titlebar(e.widget) if isinstance(e.widget, tk.Toplevel) else None, add="+")
    return ttk.Style(root)


def _style(root):
    """Estilos ttk e opções padrão dos widgets tk. Roda de novo a cada troca de tema."""
    if isinstance(root, ctk.CTk):
        root.configure(fg_color=T(PANEL))
    else:
        root.configure(bg=PANEL)
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=PANEL, foreground=FG, fieldbackground=BG, bordercolor=LINE, lightcolor=PANEL,
                 darkcolor=PANEL, troughcolor=BG, font=UI, focuscolor=LINE, selectbackground=SEL,
                 selectforeground=SEL_FG, insertcolor=FG, insertwidth=1)
    st.map(".", foreground=[("disabled", FAINT)])
    for s, bg in (("TFrame", PANEL), ("Bg.TFrame", BG), ("Surface.TFrame", SURFACE)):
        st.configure(s, background=bg)
    st.configure("TLabel", background=PANEL, foreground=FG)
    st.configure("Dim.TLabel", foreground=DIM)
    st.configure("Bg.TLabel", background=BG)
    st.configure("Head.TLabel", font=UI_B)
    st.configure("Banner.TLabel", background=WARN_BG, foreground=WARN_SOFT, padding=6)

    # árvores e listas
    st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, borderwidth=0,
                 rowheight=px(26), font=UI, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL, indent=px(16))
    st.map("Treeview", background=[("selected", SEL)], foreground=[("selected", SEL_FG)])
    st.configure("Treeview.Heading", background=PANEL, foreground=DIM, relief="flat", font=UI_S,
                 bordercolor=LINE, lightcolor=PANEL, darkcolor=PANEL, padding=(6, 3))
    st.map("Treeview.Heading", background=[("active", SURFACE)])
    st.configure("Bg.Treeview", background=BG, fieldbackground=BG)
    st.layout("Treeview", [("Treeview.field", {"sticky": "nswe", "border": "0", "children": [
        ("Treeview.padding", {"sticky": "nswe", "children": [("Treeview.treearea", {"sticky": "nswe"})]})]})])

    # abas laterais (pílulas)
    st.configure("TNotebook", background=PANEL, borderwidth=0, tabmargins=(6, 6, 6, 4), bordercolor=PANEL,
                 lightcolor=PANEL, darkcolor=PANEL)
    st.configure("TNotebook.Tab", background=PANEL, foreground=DIM, padding=(6, 4), borderwidth=0, font=UI_S,
                 bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
    st.map("TNotebook.Tab", background=[("selected", SURFACE), ("active", mix(PANEL, SURFACE, .5))],
           foreground=[("selected", STRONG), ("active", FG)], bordercolor=[("selected", SURFACE)],
           lightcolor=[("selected", SURFACE)], expand=[("selected", (0, 0, 0, 0))])
    st.layout("TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
            ("Notebook.label", {"side": "top", "sticky": ""})]})]})])

    # abas do editor: linha azul em cima da aba ativa e um X para fechar
    # imagens com nome usadas pelos elementos ttk: na troca de tema são repintadas no lugar
    # (recriar com o mesmo nome deixaria as abas sem imagem)
    objs = root.__dict__.setdefault("_tab_img_objs", {})

    def named(name, w, h):
        img = objs.get(name)
        if img is None:
            img = objs[name] = tk.PhotoImage(name=name, width=w, height=h, master=root)
        else:
            img.blank()
        return img

    def tab_img(name, fill, top=None):
        s12 = px(12)
        img = named(name, s12, s12)
        _fill(img, fill, s12, s12)
        if top:
            _fill(img, top, s12, max(2, px(2)))
        return img

    def x_img(name, color):
        s16 = px(16)
        img = named(name, s16, s16)
        for i in range(px(5), px(11)):
            for t in range(max(1, px(1.2))):
                img.put(color, (i + t, i))
                img.put(color, (s16 - 1 - i + t, i))
        return img

    root._tab_imgs = (tab_img("etab_n", PANEL), tab_img("etab_h", mix(PANEL, SURFACE, .6)),
                      tab_img("etab_s", BG, ACCENT), x_img("tab_x", FAINT), x_img("tab_x_hot", ERR))
    for args, kw in ((("Editor.tab", "image", "etab_n", ("selected", "etab_s"), ("active", "etab_h")),
                      dict(border=(3, 3, 3, 2), sticky="nswe")),
                     (("tabclose", "image", "tab_x", ("active", "tab_x_hot")), dict(border=4, sticky=""))):
        try:
            st.element_create(*args, **kw)
        except tk.TclError:
            pass  # já existe (troca de tema): as imagens têm o mesmo nome e já foram refeitas
    st.layout("Closable.TNotebook", st.layout("TNotebook"))
    st.configure("Closable.TNotebook", background=PANEL, tabmargins=(6, 6, 6, 0), bordercolor=PANEL,
                 lightcolor=BG, darkcolor=BG)
    st.layout("Closable.TNotebook.Tab", [("Editor.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
            ("Notebook.label", {"side": "left", "sticky": ""}),
            ("Notebook.tabclose", {"side": "left", "sticky": ""})]})]})])
    st.configure("Closable.TNotebook.Tab", padding=(10, 6, 4, 5), foreground=DIM, font=MONO_S, background=PANEL)
    st.map("Closable.TNotebook.Tab", foreground=[("selected", STRONG), ("active", FG)],
           expand=[("selected", (0, 0, 0, 0))], background=[("selected", BG)])

    # botões
    st.configure("TButton", background=SURFACE, foreground=FG, padding=(10, 5), borderwidth=1, relief="flat",
                 bordercolor=LINE, lightcolor=SURFACE, darkcolor=SURFACE, focuscolor=SURFACE, font=UI)
    st.map("TButton", background=[("disabled", PANEL), ("pressed", HOVER), ("active", LINE)],
           lightcolor=[("pressed", HOVER), ("active", LINE)], darkcolor=[("pressed", HOVER), ("active", LINE)],
           foreground=[("disabled", FAINT)], focuscolor=[("active", LINE)])
    st.configure("Accent.TButton", background=ACCENT, foreground=WHITE, bordercolor=ACCENT, lightcolor=ACCENT,
                 darkcolor=ACCENT, focuscolor=ACCENT, font=UI_B)
    st.map("Accent.TButton", background=[("disabled", SURFACE), ("pressed", ACCENT_PRESS), ("active", ACCENT_HOVER)],
           lightcolor=[("pressed", ACCENT_PRESS), ("active", ACCENT_HOVER)],
           darkcolor=[("pressed", ACCENT_PRESS), ("active", ACCENT_HOVER)],
           bordercolor=[("disabled", LINE)], focuscolor=[("active", ACCENT_HOVER)])
    st.configure("TMenubutton", background=SURFACE, foreground=FG, padding=(10, 5), bordercolor=LINE,
                 lightcolor=SURFACE, darkcolor=SURFACE, arrowcolor=DIM, relief="flat")
    st.map("TMenubutton", background=[("active", LINE)], lightcolor=[("active", LINE)], darkcolor=[("active", LINE)])

    # campos
    field = dict(fieldbackground=BG, foreground=FG, bordercolor=LINE, lightcolor=BG, darkcolor=BG,
                 insertcolor=FG, padding=(6, 4))
    st.configure("TEntry", **field)
    st.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", BG)],
           fieldbackground=[("disabled", PANEL)], foreground=[("disabled", DIM)])
    st.configure("TCombobox", **field, background=SURFACE, arrowcolor=DIM, arrowsize=px(12))
    st.map("TCombobox", fieldbackground=[("readonly", BG), ("disabled", PANEL)], foreground=[("readonly", FG), ("disabled", DIM)],
           selectbackground=[("readonly", BG)], selectforeground=[("readonly", FG)], bordercolor=[("focus", ACCENT)],
           background=[("active", LINE)], arrowcolor=[("active", FG)])
    st.configure("TSpinbox", **field, background=SURFACE, arrowcolor=DIM)
    st.map("TSpinbox", bordercolor=[("focus", ACCENT)])
    check = dict(background=PANEL, foreground=FG, indicatorbackground=BG, indicatorforeground=WHITE,
                 upperbordercolor=LINE, lowerbordercolor=LINE, focuscolor=PANEL, indicatormargin=(0, 0, 6, 0))
    for s in ("TCheckbutton", "TRadiobutton"):
        st.configure(s, **check)
        st.map(s, background=[("active", PANEL)], indicatorbackground=[("selected", ACCENT), ("disabled", PANEL)],
               upperbordercolor=[("selected", ACCENT)], lowerbordercolor=[("selected", ACCENT)],
               foreground=[("disabled", FAINT)])
    st.configure("TLabelframe", background=PANEL, bordercolor=LINE, lightcolor=PANEL, darkcolor=PANEL)
    st.configure("TLabelframe.Label", background=PANEL, foreground=DIM, font=UI_SB)
    st.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=BG, bordercolor=LINE,
                 lightcolor=ACCENT, darkcolor=ACCENT)

    # barras de rolagem finas, sem setas
    st.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    st.layout("Horizontal.TScrollbar", [("Horizontal.Scrollbar.trough", {"sticky": "ew", "children": [
        ("Horizontal.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    st.configure("TScrollbar", troughcolor=BG, background=SCROLL, bordercolor=BG, lightcolor=SCROLL,
                 darkcolor=SCROLL, arrowsize=px(9), gripcount=0, relief="flat")
    st.map("TScrollbar", background=[("pressed", SCROLL_HOVER), ("active", SCROLL_HOVER)],
           lightcolor=[("pressed", SCROLL_HOVER), ("active", SCROLL_HOVER)],
           darkcolor=[("pressed", SCROLL_HOVER), ("active", SCROLL_HOVER)])
    st.configure("TPanedwindow", background=LINE)
    st.configure("Sash", sashthickness=3, gripcount=0, background=LINE, lightcolor=LINE, bordercolor=LINE)
    st.configure("TSeparator", background=LINE)

    for k, v in (("*TCombobox*Listbox.background", BG), ("*TCombobox*Listbox.foreground", FG),
                 ("*TCombobox*Listbox.selectBackground", SEL), ("*TCombobox*Listbox.selectForeground", SEL_FG),
                 ("*TCombobox*Listbox.font", UI), ("*Menu.background", SURFACE), ("*Menu.foreground", FG),
                 ("*Menu.activeBackground", SEL), ("*Menu.activeForeground", SEL_FG), ("*Menu.borderWidth", 0),
                 ("*Menu.activeBorderWidth", 0), ("*Menu.relief", "flat"), ("*Menu.font", UI),
                 ("*Menu.disabledForeground", FAINT), ("*Menu.selectColor", ACCENT),
                 ("*Listbox.background", BG), ("*Listbox.foreground", FG), ("*Listbox.selectBackground", SEL),
                 ("*Listbox.selectForeground", SEL_FG), ("*Listbox.highlightThickness", 0), ("*Listbox.font", UI),
                 ("*Toplevel.background", PANEL)):
        root.option_add(k, v)
    return st


# ------------------------------------------------------------------ troca de tema sem reiniciar
_RECOLOR_OPTS = ("background", "foreground", "activebackground", "activeforeground", "highlightbackground",
                 "highlightcolor", "insertbackground", "selectbackground", "selectforeground",
                 "inactiveselectbackground", "troughcolor", "disabledforeground", "readonlybackground",
                 "selectcolor", "disabledbackground")
_TAG_OPTS = ("foreground", "background", "underlinefg", "selectbackground", "selectforeground")


def _recolor_widget(w, conv):
    for o in _RECOLOR_OPTS:
        try:
            n = conv(str(w.cget(o)))
            if n:
                w.configure(**{o: n})
        except (tk.TclError, ValueError):
            pass
    try:
        if isinstance(w, tk.Text):
            for tag in w.tag_names():
                for o in _TAG_OPTS:
                    n = conv(str(w.tag_cget(tag, o)))
                    if n:
                        w.tag_configure(tag, **{o: n})
        elif isinstance(w, ttk.Treeview):
            for tag in w.tk.splitlist(w.tk.call(w, "tag", "names")):
                for o in ("foreground", "background"):
                    n = conv(str(w.tag_configure(tag, o) or ""))
                    if n:
                        w.tag_configure(tag, **{o: n})
        elif isinstance(w, tk.Canvas):
            for item in w.find_all():
                for o in ("fill", "outline"):
                    try:
                        n = conv(str(w.itemcget(item, o)))
                    except tk.TclError:
                        continue
                    if n:
                        w.itemconfigure(item, **{o: n})
        elif isinstance(w, tk.Menu):
            for i in range((w.index("end") or -1) + 1):
                for o in ("background", "foreground", "activebackground", "activeforeground"):
                    try:
                        n = conv(str(w.entrycget(i, o)))
                    except tk.TclError:
                        continue
                    if n:
                        w.entryconfigure(i, **{o: n})
    except tk.TclError:
        pass


def _recolor_tree(root, conv):
    stack = [root]
    while stack:
        w = stack.pop()
        try:
            kids = w.winfo_children()
        except tk.TclError:
            continue
        if isinstance(w, ctk.CTkBaseClass):
            # widget do CustomTkinter: ele mesmo troca as cores; só descemos nos filhos que não são peças internas dele
            inner = {id(v) for k, v in vars(w).items() if k.startswith("_") and isinstance(v, tk.Misc)}
            kids = [c for c in kids if id(c) not in inner]
        elif not isinstance(w, (ctk.CTk, ctk.CTkToplevel)):
            _recolor_widget(w, conv)
        stack.extend(kids)


def switch_mode(root, mode: str) -> bool:
    """Troca claro/escuro com o app aberto: tokens, estilos ttk, imagens, widgets tk e CustomTkinter."""
    global MODE, _P
    if mode not in dict(MODES) or mode == MODE:
        return False
    old, new = _P, (_LIGHT if mode == "light" else _DARK)
    conv = _conv(old, new)
    MODE, _P = mode, new
    globals().update(new)
    # módulos do MUA Studio que fizeram "from theme import BG, ..." recebem os valores novos
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None) or ""
        if not f or mod is sys.modules.get(__name__) or os.path.dirname(os.path.abspath(f)) != _HERE:
            continue
        d = mod.__dict__
        for k, v in old.items():
            if isinstance(d.get(k), str) and d[k].lower() == v.lower():
                d[k] = new[k]
    Banner.KINDS = Banner._kinds()
    _style(root)
    _repaint_images(conv)
    _recolor_tree(root, conv)
    ctk.set_appearance_mode(mode)
    for w in [root] + [t for t in _all_toplevels(root)]:
        w._mua_dark = False
        dark_titlebar(w)
    return True


def _all_toplevels(root):
    out, stack = [], list(root.winfo_children())
    while stack:
        w = stack.pop()
        if isinstance(w, tk.Toplevel):
            out.append(w)
        try:
            stack.extend(w.winfo_children())
        except tk.TclError:
            pass
    return out


# ------------------------------------------------------------------ widgets
def _inside(widget, e=None) -> bool:
    try:
        w = widget.winfo_containing(*widget.winfo_pointerxy())
    except (tk.TclError, KeyError):
        return False
    return w is not None and str(w).startswith(str(widget))


class ToolButton(ctk.CTkFrame):
    """Botão arredondado: ícone + texto + atalho, com hover. kind: accent | normal | ghost."""

    def __init__(self, parent, text="", icon=None, command=None, kbd=None, kind="normal", icon_color=None,
                 bg=PANEL, font=None, padx=9, pady=4):
        base = T(bg)
        if kind == "accent":
            self._n, self._h, self._p, border, fg = C("ACCENT"), C("ACCENT_HOVER"), C("ACCENT_PRESS"), C("ACCENT"), (WHITE, WHITE)
        elif kind == "ghost":
            self._n, self._h, self._p, border, fg = base, C("SURFACE"), C("HOVER"), base, C("DIM")
        else:
            self._n, self._h, self._p, border, fg = C("SURFACE"), C("LINE"), C("HOVER"), C("LINE"), C("FG")
        self._fg, self._kind, self.command, self._parts = fg, kind, command, []
        super().__init__(parent, fg_color=self._n, bg_color=base, border_width=0 if kind == "ghost" else 1,
                         border_color=border, corner_radius=6)
        row_pad = (max(1, pady - 1), max(1, pady - 1))
        if icon:
            il = ctk.CTkLabel(self, text=glyph(icon), font=cfont(ICON), text_color=T(icon_color) if icon_color else fg,
                              fg_color="transparent", width=0, height=0)
            il.pack(side="left", padx=(padx, 0 if text else padx), pady=row_pad)
            self._parts.append(il)
        self.label = None
        if text:
            tl = ctk.CTkLabel(self, text=text, font=cfont(font or (UI_B if kind == "accent" else UI)), text_color=fg,
                              fg_color="transparent", width=0, height=0)
            tl.pack(side="left", padx=(6 if icon else padx, padx if not kbd else 4), pady=row_pad)
            self._parts.append(tl)
            self.label = tl
        if kbd:
            kb, kf = (C("ACCENT_PRESS"), ("#dbe6ff", "#dbe6ff")) if kind == "accent" else (C("BG"), C("DIM"))
            kl = ctk.CTkLabel(self, text=" " + kbd + " ", font=cfont(MONO_XS), fg_color=kb, text_color=kf,
                              corner_radius=4, width=0, height=0)
            kl.pack(side="left", padx=(2, padx), pady=row_pad)
            self._parts.append(kl)
        for w in [self] + self._parts:
            w.bind("<Enter>", self._enter, add="+")
            w.bind("<Leave>", self._leave, add="+")
            w.bind("<ButtonPress-1>", self._press, add="+")
            w.bind("<ButtonRelease-1>", self._release, add="+")
        self._set_cursor("hand2")

    def _set_cursor(self, cur):
        for w in [self._canvas] + [getattr(p, "_label", p) for p in self._parts]:
            try:
                w.configure(cursor=cur)
            except (tk.TclError, ValueError, AttributeError):
                pass

    def _paint(self, c, fg=None):
        self.configure(fg_color=c)
        if fg and self._kind == "ghost" and self.label is not None:
            self.label.configure(text_color=fg)

    def _enter(self, _e=None):
        self._paint(self._h, C("FG"))

    def _leave(self, _e=None):
        if not _inside(self):
            self._paint(self._n, self._fg)

    def _press(self, _e=None):
        self._paint(self._p)

    def _release(self, _e=None):
        if _inside(self):
            self._paint(self._h)
            if self.command:
                self.after_idle(self.command)
        else:
            self._paint(self._n, self._fg)


class Toolbar(tk.Frame):
    """Barra de botões que nunca corta: o que não cabe vai para o botão 'Mais'."""

    def __init__(self, parent, bg=PANEL):
        super().__init__(parent, bg=bg)
        self._bg = bg
        self.items: list[dict] = []   # {"w", "label", "command" | "menu", "sep"}
        self.right: list = []
        self.more = ToolButton(self, "Mais", "more", self._show_more, bg=bg)
        self._hidden: list[dict] = []
        self.bind("<Configure>", lambda e: self.after_idle(self.relayout))

    def add(self, widget, label=None, command=None, menu=None, gap=6):
        self.items.append({"w": widget, "label": label, "command": command, "menu": menu, "gap": gap})
        return widget

    def separator(self):
        f = tk.Frame(self, bg=LINE, width=1, height=px(18))
        self.items.append({"w": f, "sep": True, "gap": 8})
        return f

    def add_right(self, widget):
        self.right.append(widget)
        return widget

    def relayout(self):
        try:
            width = self.winfo_width()
        except tk.TclError:
            return
        if width < 50:
            return
        for it in self.items:
            it["w"].pack_forget()
        for w in self.right:
            w.pack_forget()
        self.more.pack_forget()
        used = sum(w.winfo_reqwidth() + px(6) for w in self.right)
        more_w = self.more.winfo_reqwidth() + px(8)
        total = sum(it["w"].winfo_reqwidth() + px(it["gap"]) for it in self.items)
        avail = width - used - (0 if total + used <= width else more_w)
        shown, x = [], 0
        for it in self.items:
            need = it["w"].winfo_reqwidth() + px(it["gap"])
            if x + need > avail:
                break
            shown.append(it)
            x += need
        while shown and shown[-1].get("sep"):
            shown.pop()
        self._hidden = [it for it in self.items if it not in shown and not it.get("sep")]
        for it in shown:
            it["w"].pack(side="left", padx=(0, px(it["gap"])))
        for w in reversed(self.right):
            w.pack(side="right", padx=(px(6), 0))
        if self._hidden:
            self.more.pack(side="right", padx=(px(6), 0))

    def _show_more(self):
        m = tk.Menu(self, tearoff=0)
        for it in self._hidden:
            if it.get("menu") is not None:
                m.add_cascade(label=it["label"], menu=it["menu"])
            elif it.get("command"):
                m.add_command(label=it["label"], command=it["command"])
        m.tk_popup(self.more.winfo_rootx(), self.more.winfo_rooty() + self.more.winfo_height() + 2)

    def hidden_labels(self) -> list[str]:
        return [it["label"] for it in self._hidden]


class CommandPalette(tk.Toplevel):
    """Paleta de comandos (Ctrl+Shift+P): busca única por todas as ações e personagens."""

    def __init__(self, root, items: list[tuple[str, str, object]]):
        super().__init__(root)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=LINE)
        self.items = items
        box = tk.Frame(self, bg=PANEL)
        box.pack(fill="both", expand=True, padx=1, pady=1)
        self.var = tk.StringVar()
        se = SearchEntry(box, self.var, "Digite um comando, personagem ou arquivo...  (Esc fecha)", font=UI)
        se.pack(fill="x", padx=px(10), pady=(px(10), px(6)))
        self.entry = se.entry
        fr = tk.Frame(box, bg=PANEL)
        fr.pack(fill="both", expand=True, padx=px(6), pady=(0, px(8)))
        self.tv = ttk.Treeview(fr, columns=("hint",), show="tree", selectmode="browse", height=12)
        self.tv.column("#0", stretch=True, width=px(420))
        self.tv.column("hint", width=px(170), stretch=False, anchor="e")
        self.tv.tag_configure("dim", foreground=DIM)
        self.tv.pack(fill="both", expand=True)
        self.var.trace_add("write", lambda *a: self._fill())
        for w in (self.entry, self.tv):
            w.bind("<Escape>", lambda e: self.close())
            w.bind("<Return>", lambda e: self.run())
            w.bind("<Down>", lambda e: self._move(1))
            w.bind("<Up>", lambda e: self._move(-1))
        self.tv.bind("<Double-1>", lambda e: self.run())
        self.bind("<FocusOut>", lambda e: self.after(80, self._maybe_close))
        self._fill()
        W, H = px(640), px(400)
        root.update_idletasks()
        x = root.winfo_rootx() + (root.winfo_width() - W) // 2
        y = root.winfo_rooty() + px(70)
        self.geometry(f"{W}x{H}+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.lift()
        self.entry.focus_force()

    @staticmethod
    def _score(q: str, text: str) -> int | None:
        """Busca por letras em ordem (fuzzy). Menor = melhor; None = não casa."""
        t = text.lower()
        if not q:
            return 0
        if q in t:
            return t.index(q)
        i, gaps = 0, 0
        for ch in q:
            j = t.find(ch, i)
            if j < 0:
                return None
            gaps += j - i
            i = j + 1
        return 100 + gaps

    def _fill(self):
        q = self.var.get().lower().strip()
        tv = self.tv
        tv.delete(*tv.get_children())
        scored = []
        for n, (label, hint, fn) in enumerate(self.items):
            sc = self._score(q, label + " " + hint)
            if sc is not None:
                scored.append((sc, n))
        for sc, n in sorted(scored)[:200]:
            label, hint, _ = self.items[n]
            tv.insert("", "end", iid=str(n), text="  " + label, values=(hint,))
        kids = tv.get_children()
        if kids:
            tv.selection_set(kids[0])
            tv.see(kids[0])

    def _move(self, d):
        kids = self.tv.get_children()
        if not kids:
            return "break"
        sel = self.tv.selection()
        i = kids.index(sel[0]) + d if sel else 0
        i = max(0, min(len(kids) - 1, i))
        self.tv.selection_set(kids[i])
        self.tv.see(kids[i])
        return "break"

    def run(self):
        sel = self.tv.selection()
        if not sel:
            return "break"
        fn = self.items[int(sel[0])][2]
        self.close()
        self.master.after(10, fn)
        return "break"

    def _maybe_close(self):
        try:
            f = self.focus_get()
        except (tk.TclError, KeyError):
            f = None
        if f is None or not str(f).startswith(str(self)):
            self.close()

    def close(self):
        try:
            self.destroy()
        except tk.TclError:
            pass
        return "break"


def _master_bg(w) -> str:
    """Cor de fundo do pai (tk ou ttk), para os cantos arredondados combinarem."""
    return _bg_of(w.master)


def _bg_of(m) -> str:
    while m is not None:
        try:
            if isinstance(m, ctk.CTkBaseClass):
                c = m.cget("fg_color")
                c = c[1 if MODE == "dark" else 0] if isinstance(c, (tuple, list)) else c
                if c and c != "transparent":
                    return c
            elif isinstance(m, ttk.Widget):
                st = ttk.Style(m)
                c = st.lookup(m.cget("style") or m.winfo_class(), "background") or st.lookup(m.winfo_class(), "background")
                if c:
                    return str(c)
            else:
                return str(m.cget("background"))
        except (tk.TclError, ValueError, AttributeError):
            pass
        m = getattr(m, "master", None)
    return PANEL


_TTK_ONLY = ("style", "padding", "takefocus", "underline", "compound", "width", "cursor", "default")


class _StateMixin:
    """.state([...]) e .instate([...]) como no ttk, em cima do state= do CustomTkinter."""

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self.cget("state") == "disabled" else ()
        spec = [spec] if isinstance(spec, str) else list(spec)
        if "disabled" in spec:
            self.configure(state="disabled")
        elif "!disabled" in spec:
            self.configure(state="normal")
        self._state_changed()
        return ()

    def instate(self, spec):
        dis = self.cget("state") == "disabled"
        for s in spec:
            if (s == "disabled" and not dis) or (s == "!disabled" and dis):
                return False
        return True

    def _state_changed(self):
        pass


class Button(_StateMixin, ctk.CTkButton):
    """CTkButton arredondado que aceita o jeito ttk do app (style="Accent.TButton", .state([...])).

    reason_from: um tk.Text (prévia do diálogo); enquanto o botão está desativado, a primeira
    linha relevante da prévia aparece ao lado do botão dizendo o que falta."""

    def __init__(self, master, text="", command=None, style=None, **kw):
        for k in _TTK_ONLY:
            kw.pop(k, None)
        self._accent = style == "Accent.TButton"
        f = UI_B if self._accent else UI
        try:
            w = tkfont.Font(font=f).measure(text) / max(SCALE, 0.01) + 26
        except tk.TclError:
            w = len(text) * 7 + 26
        super().__init__(master, text=text, command=command, font=cfont(f), corner_radius=6, height=30, width=int(w),
                         border_width=0 if self._accent else 1, border_color=C("LINE"), bg_color=T(_bg_of(master)),
                         text_color_disabled=C("FAINT"), **kw)
        self._paint_kind()
        self.reason_from = None
        self._reason = None

    def _paint_kind(self):
        dis = self.cget("state") == "disabled"
        if self._accent and not dis:
            self.configure(fg_color=C("ACCENT"), hover_color=C("ACCENT_HOVER"), text_color=(WHITE, WHITE))
        else:
            self.configure(fg_color=C("SURFACE"), hover_color=C("LINE"), text_color=C("FG"))

    def _state_changed(self):
        self._paint_kind()
        if self.reason_from is not None:
            self.after(80, self._show_reason)

    def explain_with(self, text_widget):
        """Liga o botão à prévia do diálogo: desativado, ele mostra ao lado o motivo (1ª linha relevante)."""
        self.reason_from = text_widget
        if text_widget is not None:
            self.after(80, self._show_reason)

    def _show_reason(self):
        try:
            dis = self.cget("state") == "disabled"
            txt = ""
            if dis:
                lines = [ln.strip() for ln in self.reason_from.get("1.0", "end").split("\n") if ln.strip()]
                bad = [ln for ln in lines if ln.startswith(("!", "NÃO", "ERRO", "Erro"))]
                txt = (bad or lines or [""])[0].lstrip("! ")
                if len(txt) > 90:
                    txt = txt[:87] + "..."
            if self._reason is None:
                self._reason = tk.Label(self.master, font=UI_XS, bg=_master_bg(self), fg=WARN_SOFT)
            if txt:
                side = self.pack_info().get("side", "right") if self.winfo_manager() == "pack" else "right"
                self._reason.configure(text=txt)
                self._reason.pack(side=side, padx=px(10), after=self)
            else:
                self._reason.pack_forget()
        except tk.TclError:
            pass


class Check(_StateMixin, ctk.CTkCheckBox):
    """CTkCheckBox (caixa com ✓ de verdade) com a interface do ttk.Checkbutton."""

    def __init__(self, master, text="", variable=None, command=None, **kw):
        for k in _TTK_ONLY:
            kw.pop(k, None)
        on, off = kw.pop("onvalue", 1), kw.pop("offvalue", 0)
        super().__init__(master, text=text, variable=variable, command=command, onvalue=on, offvalue=off,
                         font=cfont(UI), checkbox_width=17, checkbox_height=17, corner_radius=4, border_width=2,
                         fg_color=C("ACCENT"), hover_color=C("ACCENT_HOVER"), border_color=C("FAINT"),
                         text_color=C("FG"), text_color_disabled=C("FAINT"), checkmark_color=(WHITE, WHITE),
                         bg_color=T(_bg_of(master)), **kw)


class Radio(_StateMixin, ctk.CTkRadioButton):
    """CTkRadioButton com a interface do ttk.Radiobutton."""

    def __init__(self, master, text="", variable=None, value=None, command=None, **kw):
        for k in _TTK_ONLY:
            kw.pop(k, None)
        super().__init__(master, text=text, variable=variable, value=value, command=command, font=cfont(UI),
                         radiobutton_width=17, radiobutton_height=17, border_width_unchecked=2, border_width_checked=5,
                         fg_color=C("ACCENT"), hover_color=C("ACCENT_HOVER"), border_color=C("FAINT"),
                         text_color=C("FG"), text_color_disabled=C("FAINT"), bg_color=T(_bg_of(master)), **kw)


class Flow(tk.Frame):
    """Linha de botões que quebra para a linha de baixo quando não cabe (nada fica cortado).

    Os botões são posicionados com place(): a largura vem do pai (fill="x") e a altura é calculada,
    então a linha nunca força a janela a ficar mais larga que a tela."""

    def __init__(self, parent, gap=6):
        super().__init__(parent, bg=_bg_of(parent), height=px(34))
        self.gap, self.items, self._sig = gap, [], None
        self.bind("<Configure>", lambda e: self._layout(e.width))

    def add(self, w):
        self.items.append(w)
        self._sig = None
        self.after_idle(lambda: self._layout(self.winfo_width()))
        return w

    def _layout(self, width):
        if width < 40:
            return
        g = px(self.gap)
        x = y = row_h = 0
        pos = []
        for w in self.items:
            ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
            if x and x + ww > width:
                x, y, row_h = 0, y + row_h + px(4), 0
            pos.append((w, x, y))
            x += ww + g
            row_h = max(row_h, wh)
        sig = (width, tuple((xx, yy) for _, xx, yy in pos))
        if sig == self._sig:
            return
        self._sig = sig
        for w, xx, yy in pos:
            k = SCALE if isinstance(w, ctk.CTkBaseClass) else 1  # o CustomTkinter multiplica x/y pela escala
            w.place(x=xx / k, y=yy / k)
        self.configure(height=y + row_h)


def menu_commands(menu: tk.Menu, prefix: str) -> list[tuple[str, str, object]]:
    """Todas as ações de um menu (e submenus) como itens da paleta."""
    out = []
    end = menu.index("end")
    if end is None:
        return out
    for i in range(end + 1):
        kind = menu.type(i)
        if kind in ("separator", "tearoff"):
            continue
        label = menu.entrycget(i, "label")
        if kind == "cascade":
            sub = menu.nametowidget(menu.entrycget(i, "menu"))
            out += menu_commands(sub, f"{prefix} \u203a {label}")
            continue
        acc = menu.entrycget(i, "accelerator")
        out.append((f"{prefix} \u203a {label}", acc, lambda m=menu, i=i: m.invoke(i)))
    return out


class IconButton(tk.Label):
    """Ícone clicável pequeno (fechar, anterior, próximo)."""

    def __init__(self, parent, icon, command=None, bg=PANEL, fg=DIM, hot=FG, hover_bg=SURFACE, font=None, tip=None):
        super().__init__(parent, text=glyph(icon), font=font or ICON_S, bg=bg, fg=fg, padx=5, pady=3, cursor="hand2")
        self._c = (bg, fg, hover_bg, hot)
        self.command = command
        self.bind("<Enter>", lambda e: self.configure(bg=hover_bg, fg=hot))
        self.bind("<Leave>", lambda e: self.configure(bg=bg, fg=fg))
        self.bind("<ButtonRelease-1>", lambda e: self.command and _inside(self) and self.command())


def chip(parent, text, kind="dim", bg=None, font=None, padx=6, pady=1) -> tk.Label:
    """Etiqueta colorida: err | warn | ok | info | dim | purple | amber."""
    colors = {"err": (mix(PANEL, ERR, .16), ERR_SOFT), "warn": (mix(PANEL, WARN, .16), WARN_SOFT),
              "ok": (mix(PANEL, OK, .12), OK_SOFT if MODE == "light" else OK), "info": (SEL, INFO_FG), "dim": (SURFACE, DIM),
              "purple": (mix(PANEL, PURPLE, .16), PURPLE_FG), "amber": (mix(PANEL, AMBER, .14), AMBER),
              "red": (mix(PANEL, "#ef4444", .2), RED_FG), "kbd": (BG, DIM)}
    b, f = colors.get(kind, colors["dim"])
    return tk.Label(parent, text=text, bg=bg or b, fg=f, font=font or MONO_XS, padx=padx, pady=pady)


def chip_recolor(lbl: tk.Label, kind: str):
    tmp = chip(lbl.master, "", kind)
    lbl.configure(bg=tmp.cget("bg"), fg=tmp.cget("fg"))
    tmp.destroy()


def hline(parent, color=LINE, **pack):
    f = tk.Frame(parent, bg=color, height=1)
    f.pack(fill="x", **pack)
    return f


class Banner(tk.Frame):
    """Faixa de aviso no topo do editor (amarela = atenção, verde = ok, azul = info)."""
    @staticmethod
    def _kinds():
        return {"warn": (mix(BG, AMBER, .13), mix(BG, AMBER, .32), AMBER, BANNER_WARN_FG, "warn"),
                "ok": (mix(BG, OK, .1), mix(BG, OK, .28), OK, OK_SOFT, "check"),
                "info": (mix(BG, ACCENT, .12), mix(BG, ACCENT, .3), ACCENT, BANNER_INFO_FG, "info")}

    KINDS: dict = {}

    def __init__(self, parent):
        if not Banner.KINDS:
            Banner.KINDS = Banner._kinds()
        super().__init__(parent, bg=self.KINDS["warn"][0])
        self.row = tk.Frame(self, bg=self["bg"])
        self.row.pack(fill="x")
        self.icon = tk.Label(self.row, font=ICON, bg=self["bg"])
        self.icon.pack(side="left", padx=(10, 6), pady=5)
        self.text = tk.Label(self.row, font=UI_S, bg=self["bg"], anchor="w", justify="left")
        self.text.pack(side="left", fill="x", expand=True, pady=5)
        self.close = IconButton(self.row, "close", command=self.pack_forget, bg=self["bg"])
        self.close.pack(side="right", padx=(2, 8))
        self.action = tk.Label(self.row, font=UI_SB, padx=10, pady=1, cursor="hand2")
        self._cmd = None
        self.action.bind("<ButtonRelease-1>", lambda e: self._cmd and self._cmd())
        self.line = tk.Frame(self, height=1)
        self.line.pack(fill="x", side="bottom")
        self.row.bind("<Configure>", lambda e: self.text.configure(wraplength=max(200, e.width - 260)))

    def show_msg(self, text: str, kind: str = "warn", action: tuple | None = None):
        bg, line, ic, fg, icon = self.KINDS.get(kind, self.KINDS["warn"])
        for w in (self, self.row, self.icon, self.text):
            w.configure(bg=bg)
        self.close.configure(bg=bg)
        self.close._c = (bg,) + self.close._c[1:]
        self.close.bind("<Leave>", lambda e: self.close.configure(bg=bg, fg=DIM))
        self.icon.configure(text=glyph(icon), fg=ic)
        self.text.configure(text=text, fg=fg)
        self.line.configure(bg=line)
        if action:
            self.action.configure(text=action[0], bg=ic, fg="#111111", activebackground=ic)
            self._cmd = action[1]
            self.action.pack(side="right", padx=4, pady=4, before=self.close)
        else:
            self.action.pack_forget()


class SearchEntry(tk.Frame):
    """Campo com lupa e texto de exemplo (não grava o exemplo na variável)."""

    def __init__(self, parent, textvariable: tk.StringVar, placeholder="", bg=BG, font=None):
        super().__init__(parent, bg=bg, highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT)
        tk.Label(self, text=glyph("search"), font=ICON_S, bg=bg, fg=DIM).pack(side="left", padx=(8, 2))
        self.entry = tk.Entry(self, textvariable=textvariable, bg=bg, fg=FG, insertbackground=FG, relief="flat",
                              font=font or UI_S, highlightthickness=0, borderwidth=0,
                              selectbackground=SEL, selectforeground=SEL_FG)
        self.entry.pack(side="left", fill="x", expand=True, padx=(2, 6), ipady=4)
        self.ph = tk.Label(self, text=placeholder, bg=bg, fg=FAINT, font=font or UI_S, cursor="xterm")
        self.ph.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.var = textvariable
        textvariable.trace_add("write", lambda *a: self._ph())
        self.entry.bind("<FocusIn>", lambda e: (self.configure(highlightbackground=ACCENT), self._ph()), add="+")
        self.entry.bind("<FocusOut>", lambda e: (self.configure(highlightbackground=LINE), self._ph()), add="+")
        self.after_idle(self._ph)

    def _ph(self):
        try:
            if self.var.get():
                self.ph.place_forget()
            else:
                self.ph.place(in_=self.entry, x=2, rely=.5, anchor="w")
        except tk.TclError:
            pass


def panel_header(parent, title, right=None, icon=None, icon_color=DIM, bg=PANEL):
    f = tk.Frame(parent, bg=bg)
    f.pack(fill="x")
    row = tk.Frame(f, bg=bg)
    row.pack(fill="x", padx=10, pady=6)
    if icon:
        tk.Label(row, text=glyph(icon), font=ICON_S, bg=bg, fg=icon_color).pack(side="left", padx=(0, 6))
    lbl = tk.Label(row, text=title, font=UI_SB, bg=bg, fg=FG)
    lbl.pack(side="left")
    r = None
    if right is not None:
        r = tk.Label(row, text=right, font=MONO_XS, bg=bg, fg=DIM)
        r.pack(side="right")
    hline(f)
    f.row, f.title, f.right = row, lbl, r
    return f


class Header(tk.Frame):
    """Cabeçalho: logo, menus escuros, caminho do arquivo aberto e o selo de backup."""

    def __init__(self, parent, menus: list[tuple[str, tk.Menu]], on_backup=None):
        super().__init__(parent, bg=PANEL)
        row = tk.Frame(self, bg=PANEL)
        row.pack(fill="x", padx=8, pady=3)
        logo = tk.Frame(row, bg=PANEL)
        logo.pack(side="left", padx=(2, 10))
        tk.Label(logo, text="M", font=(UI_B[0], 9, "bold"), bg=ACCENT, fg=WHITE, width=2).pack(side="left")
        tk.Label(logo, text="MUA Studio", font=UI_B, bg=PANEL, fg=STRONG).pack(side="left", padx=(6, 0))
        self.menu_btns = []
        for label, menu in menus:
            b = ToolButton(row, text=label, kind="ghost", bg=PANEL, padx=7, pady=1, font=UI_S)
            b.command = lambda b=b, m=menu: m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 2)
            b.pack(side="left", padx=1)
            self.menu_btns.append(b)
        self.badge = tk.Frame(row, bg=PANEL)
        self.badge.pack(side="right")
        bd = chip(self.badge, f"{glyph('shield')}", "ok", font=ICON_S, padx=4)
        bd.pack(side="left")
        bt = chip(self.badge, "Backup automático ativo  ", "ok", font=UI_XS, padx=0, pady=2)
        bt.pack(side="left")
        for w in (bd, bt):
            w.configure(cursor="hand2")
            if on_backup:
                w.bind("<Button-1>", lambda e: on_backup())
        self.crumb = tk.Frame(row, bg=BG, highlightthickness=1, highlightbackground=LINE)
        self.crumb.pack(side="top", pady=1)
        self.set_path([])
        hline(self)

    def set_path(self, parts: list[str], first: str | None = None):
        for w in self.crumb.winfo_children():
            w.destroy()
        items = ([first] if first else []) + list(parts)
        if not items:
            tk.Label(self.crumb, text="nenhum arquivo aberto", font=UI_XS, bg=BG, fg=FAINT, padx=8).pack(side="left", pady=1)
            return
        for i, p in enumerate(items):
            if i:
                tk.Label(self.crumb, text=glyph("right"), font=(ICON_S[0], 7), bg=BG, fg=FAINT).pack(side="left")
            last = i == len(items) - 1
            if i == 0 and first:
                f, c = UI_SB, ACCENT
            else:
                f, c = (MONO_XS[0], 8, "bold") if last else MONO_XS, FG if last else DIM
            tk.Label(self.crumb, text=p, font=f, bg=BG, fg=c, padx=3).pack(side="left", pady=1,
                                                                         padx=(5 if i == 0 else 0, 5 if last else 0))


class StatusBar(tk.Frame):
    def __init__(self, parent, textvariable: tk.StringVar, on_hint=None):
        super().__init__(parent, bg=PANEL)
        hline(self, side="top")
        row = tk.Frame(self, bg=PANEL)
        row.pack(fill="x", padx=10, pady=2)
        self.dot = tk.Label(row, image=dot(OK, 12, 7), bg=PANEL)
        self.dot.pack(side="left")
        tk.Label(row, textvariable=textvariable, font=UI_S, bg=PANEL, fg=FG, anchor="w").pack(side="left", padx=(4, 0))
        self.hint = tk.Label(row, text="F12: Ir para definição", font=MONO_XS, bg=PANEL, fg=ACCENT, cursor="hand2")
        self.hint.pack(side="right")
        if on_hint:
            self.hint.bind("<Button-1>", lambda e: on_hint())
        self.ftype = tk.Label(row, font=MONO_XS, bg=PANEL, fg=DIM)
        self.ftype.pack(side="right", padx=14)
        self.cursor = tk.Label(row, font=MONO_XS, bg=PANEL, fg=DIM)
        self.cursor.pack(side="right")

    def set_kind(self, kind: str):
        self.dot.configure(image=dot({"ok": OK, "warn": WARN, "err": ERR}.get(kind, OK), 12, 7))


class FindBar(tk.Frame):
    """Localizar / substituir flutuante (canto superior direito do editor)."""

    def __init__(self, parent, var: tk.StringVar, on_next, on_prev, on_close,
                 replace_var: tk.StringVar | None = None, on_replace=None, on_replace_all=None, case_var: tk.BooleanVar | None = None):
        super().__init__(parent, bg=PANEL, highlightthickness=1, highlightbackground=HOVER)

        def field(row, v, width=26):
            box = tk.Frame(row, bg=BG, highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT)
            box.pack(side="left", pady=5)
            e = tk.Entry(box, textvariable=v, width=width, bg=BG, fg=FG, insertbackground=FG, relief="flat",
                         font=MONO_S, highlightthickness=0, borderwidth=0, selectbackground=SEL, selectforeground=SEL_FG)
            e.pack(padx=6, ipady=3)
            e.bind("<FocusIn>", lambda ev: box.configure(highlightbackground=ACCENT), add="+")
            e.bind("<FocusOut>", lambda ev: box.configure(highlightbackground=LINE), add="+")
            return e

        r1 = tk.Frame(self, bg=PANEL)
        r1.pack(fill="x")
        self.toggle = IconButton(r1, "right", self.toggle_replace, tip="Substituir")
        self.toggle.pack(side="left", padx=(5, 0))
        tk.Label(r1, text=glyph("search"), font=ICON_S, bg=PANEL, fg=DIM).pack(side="left", padx=(2, 4), pady=6)
        self.entry = field(r1, var)
        self.case_var = case_var or tk.BooleanVar(value=True)
        self.case_btn = tk.Label(r1, text="Aa", font=UI_XS, bg=PANEL, padx=5, cursor="hand2")
        self.case_btn.pack(side="left", padx=(4, 0))
        self.case_btn.bind("<ButtonRelease-1>", lambda e: (self.case_var.set(not self.case_var.get()), self._paint_case()))
        self._paint_case()
        self.info = tk.Label(r1, text="Enter / F3", font=UI_XS, bg=PANEL, fg=DIM, padx=6)
        self.info.pack(side="left")
        IconButton(r1, "up_arrow", on_prev).pack(side="left")
        IconButton(r1, "down_arrow", on_next).pack(side="left")
        IconButton(r1, "close", on_close, hot=ERR).pack(side="left", padx=(0, 5))
        self.r2 = tk.Frame(self, bg=PANEL)
        self.replace_var = replace_var or tk.StringVar()
        tk.Label(self.r2, text="⇄", font=UI_S, bg=PANEL, fg=DIM).pack(side="left", padx=(31, 4))
        self.replace_entry = field(self.r2, self.replace_var)
        for text, cmd in (("Substituir próximo", on_replace), ("Substituir todos", on_replace_all)):
            ToolButton(self.r2, text, None, cmd, kind="normal", padx=6, pady=1, font=UI_XS).pack(side="left", padx=(6, 0), pady=4)
        self.replace_shown = False

    def _paint_case(self):
        on = self.case_var.get()
        self.case_btn.configure(fg=ACCENT if on else DIM, bg=SURFACE if on else PANEL)

    def show_replace(self, on: bool = True):
        self.replace_shown = on
        if on:
            self.r2.pack(fill="x", padx=(0, 6))
        else:
            self.r2.pack_forget()
        self.toggle.configure(text=glyph("down" if on else "right"))

    def toggle_replace(self):
        self.show_replace(not self.replace_shown)


class ScrollFrame(tk.Frame):
    """Área rolável vertical (canvas + frame interno) com roda do mouse."""

    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, borderwidth=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>", self._wheel))
        self.bind("<Leave>", lambda e: None if _inside(self) else self.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        if self.canvas.yview() != (0.0, 1.0):
            self.canvas.yview_scroll(-e.delta // 120, "units")

    def top(self):
        self.canvas.yview_moveto(0)


class CardGrid(tk.Frame):
    """Grade que muda o número de colunas conforme a largura."""

    def __init__(self, parent, minw=180, gap=8, bg=BG):
        super().__init__(parent, bg=bg)
        self.minw, self.gap, self.items, self._cols = minw, gap, [], 0
        self.bind("<Configure>", lambda e: self._layout(e.width))

    def add(self, w):
        self.items.append(w)
        self._cols = 0
        self._layout(self.winfo_width())

    def _layout(self, width):
        cols = max(1, min(len(self.items) or 1, (max(width, 1) + px(self.gap)) // (px(self.minw) + px(self.gap))))
        if cols == self._cols:
            return
        for c in range(max(self._cols, cols, 12)):
            self.columnconfigure(c, weight=0, uniform="")
        self._cols = cols
        for c in range(cols):
            self.columnconfigure(c, weight=1, uniform="card")
        for i, w in enumerate(self.items):
            r, c = divmod(i, cols)
            w.grid(row=r, column=c, sticky="nsew", padx=(0 if c == 0 else self.gap // 2, 0 if c == cols - 1 else self.gap // 2),
                   pady=(0, self.gap))


def card(parent, bg=PANEL, hover=None, command=None, border=LINE) -> tk.Frame:
    """Cartão com borda; com command fica clicável (hover em toda a área)."""
    f = tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=border, highlightcolor=border)
    if command:
        f.configure(cursor="hand2")
        hv = hover or SURFACE

        def paint(c):
            # só repinta o que tem a cor de fundo do cartão (etiquetas e linhas mantêm a cor delas)
            stack = [f]
            while stack:
                w = stack.pop()
                try:
                    if w.cget("bg") in (bg, hv):
                        w.configure(bg=c)
                except tk.TclError:
                    pass
                stack.extend(w.winfo_children())

        def bind_all_children(_e=None):
            stack = [f]
            while stack:
                w = stack.pop()
                if not getattr(w, "_card_bound", False):
                    w.bind("<Enter>", lambda e: paint(hv), add="+")
                    w.bind("<Leave>", lambda e: None if _inside(f) else paint(bg), add="+")
                    w.bind("<ButtonRelease-1>", lambda e: _inside(f) and command(), add="+")
                    if w is not f:
                        w.configure(cursor="hand2")
                    w._card_bound = True
                stack.extend(w.winfo_children())

        f.after_idle(bind_all_children)
    return f


def dialog_header(win, title, icon=None, color=ACCENT):
    """Faixa de título no topo de um diálogo (ícone + título + linha)."""
    bg = mix(PANEL, BG, .4)
    f = tk.Frame(win, bg=bg)
    f.pack(fill="x", side="top")
    row = tk.Frame(f, bg=bg)
    row.pack(fill="x", padx=16, pady=9)
    if icon:
        tk.Label(row, text=glyph(icon), font=ICON, bg=bg, fg=color).pack(side="left", padx=(0, 8))
    tk.Label(row, text=title, font=UI_B, bg=bg, fg=STRONG).pack(side="left")
    hline(f)
    return f


def section_title(parent, text, bg=BG, color=SYN_BLOCK, pady=(18, 8)):
    lbl = tk.Label(parent, text=text.upper(), font=H2, bg=bg, fg=color, anchor="w")
    lbl.pack(fill="x", pady=pady)
    return lbl


def enable_hover(tree: ttk.Treeview, color=None):
    """Destaca a linha da árvore que está sob o mouse."""
    tree.tag_configure("hover", background=color or mix(PANEL, SURFACE, .7))
    state = {"iid": None}

    def clear():
        iid = state["iid"]
        if iid and tree.exists(iid):
            tags = [t for t in tree.item(iid, "tags") if t != "hover"]
            tree.item(iid, tags=tags)
        state["iid"] = None

    def motion(e):
        iid = tree.identify_row(e.y)
        if iid == state["iid"]:
            return
        clear()
        if iid and iid not in tree.selection():
            tree.item(iid, tags=list(tree.item(iid, "tags")) + ["hover"])
            state["iid"] = iid

    tree.bind("<Motion>", motion, add="+")
    tree.bind("<Leave>", lambda e: clear(), add="+")
    tree.bind("<<TreeviewSelect>>", lambda e: clear(), add="+")
    tree.bind("<ButtonPress-1>", lambda e: clear(), add="+")
