"""Janela do Criador de Personagem: assistente em etapas, visualizador (Insight) e FAQ.

Usa o visual (theme.py) e as ferramentas do MUA Studio, mas não depende de app.py: recebe um 'host'
com proj, created, anim_tools e all_characters() - o App do MUA Studio ou o StandaloneHost de __main__.py.
"""
from __future__ import annotations

import json
import os
import re
import tkinter as tk
import webbrowser
from tkinter import ttk, filedialog, messagebox

import theme as th
import extras
import project as pj

from . import builder, knowledge, viewer, powers
from .powers_ui import PowersPanel

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(HERE, "settings.json")
IGB_TYPES = [("Modelos Alchemy", "*.igb"), ("Todos os arquivos", "*.*")]

STEPS = [("base", "Personagem-base", "people"), ("ident", "Identidade", "card"), ("skins", "Skins e HUD", "palette"),
         ("menu", "Menu e loading", "film"), ("stats", "Atributos", "sliders"), ("powers", "Poderes", "bolt"),
         ("review", "Revisão e criar", "check")]


def load_settings() -> dict:
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(d: dict):
    try:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    except OSError:
        pass


def _lbl(parent, text="", kind="fg", font=None, **kw):
    bg = kw.pop("bg", th.PANEL)
    fg = {"fg": th.FG, "dim": th.DIM, "strong": th.STRONG, "warn": th.WARN_SOFT, "err": th.ERR_SOFT, "ok": th.OK,
          "accent": th.ACCENT}[kind]
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=font or th.UI, anchor="w", justify="left", **kw)


class FileField(tk.Frame):
    """Campo de arquivo .igb: entrada + Escolher + Ver (Insight) + Limpar, com uma dica do valor padrão."""

    def __init__(self, parent, win: "CreatorWindow", label: str, default_hint=lambda: "", on_change=None, width=46):
        super().__init__(parent, bg=th.PANEL)
        self.win = win
        self.var = tk.StringVar()
        self.default_hint = default_hint
        _lbl(self, label, width=18).pack(side="left")
        ttk.Entry(self, textvariable=self.var, width=width).pack(side="left", padx=(0, 6))
        th.Button(self, text="Escolher...", command=self.browse).pack(side="left")
        th.Button(self, text="Ver", command=self.view).pack(side="left", padx=4)
        th.Button(self, text="Limpar", command=lambda: self.var.set("")).pack(side="left")
        self.hint = _lbl(self, "", "dim", th.UI_S)
        self.hint.pack(side="left", padx=8)
        self.var.trace_add("write", lambda *a: (self.refresh(), on_change and on_change()))
        self.after_idle(self.refresh)

    def browse(self):
        p = filedialog.askopenfilename(parent=self.win, filetypes=IGB_TYPES, title="Escolha o arquivo .igb",
                                       initialdir=self.win.last_dir)
        if p:
            self.win.last_dir = os.path.dirname(p)
            self.var.set(os.path.normpath(p))

    def path(self) -> str:
        return self.var.get().strip().strip('"')

    def current(self) -> str:
        """Arquivo que vai ser usado: o escolhido ou o padrão (do personagem-base)."""
        return self.path() or (self.default_hint() or "")

    def view(self):
        self.win.view_file(self.current(), self)

    def refresh(self):
        p = self.path()
        if p:
            v = viewer.igb_version(p) if os.path.isfile(p) else None
            txt = "arquivo não encontrado" if not os.path.isfile(p) else f"igb v{v}" if v else "não parece um .igb"
            self.hint.configure(text=txt, fg=th.ERR_SOFT if not os.path.isfile(p) else th.DIM)
        else:
            d = self.default_hint()
            self.hint.configure(text=("padrão: " + os.path.basename(d)) if d else "(vazio: nenhum arquivo)", fg=th.FAINT)


class SkinRow(tk.Frame):
    def __init__(self, parent, win: "CreatorWindow", slot: builder.Slot):
        super().__init__(parent, bg=th.PANEL)
        self.win, self.slot = win, slot
        top = tk.Frame(self, bg=th.PANEL)
        top.pack(fill="x")
        self.num_lbl = _lbl(top, "", "strong", th.UI_B, width=8)
        self.num_lbl.pack(side="left")
        _lbl(top, "final:").pack(side="left")
        self.suf = tk.StringVar(value=slot.suffix)
        ttk.Entry(top, textvariable=self.suf, width=4).pack(side="left", padx=(4, 12))
        _lbl(top, "nome no menu:").pack(side="left")
        self.name = tk.StringVar(value=slot.name)
        ttk.Entry(top, textvariable=self.name, width=24).pack(side="left", padx=(4, 12))
        self.patch = tk.BooleanVar(value=slot.patch)
        th.Check(top, text="hex-edit (gravar o número na skin)", variable=self.patch, command=win.changed).pack(side="left")
        th.Button(top, text="Remover", command=lambda: win.remove_slot(self)).pack(side="right")
        base = slot.base_skin

        def dflt(kind):
            if not win.base or not base:
                return ""
            r = win.base.proj.root
            return os.path.join(r, "actors", f"{base}.igb") if kind == "skin" else os.path.join(r, "hud", f"hud_head_{base}.igb")

        self.skin = FileField(self, win, "   arquivo da skin:", lambda: dflt("skin"), win.changed)
        self.skin.var.set(slot.igb)
        self.skin.pack(fill="x", pady=(4, 0))
        self.hud = FileField(self, win, "   HUD (cabeça):", lambda: dflt("hud"), win.changed)
        self.hud.var.set(slot.hud)
        self.hud.pack(fill="x", pady=(2, 0))
        self.patch_lbl = _lbl(self, "", "dim", th.UI_XS)
        self.patch_lbl.pack(fill="x", padx=(130, 0))
        for v in (self.suf, self.name):
            v.trace_add("write", lambda *a: win.changed())
        th.hline(self, pady=(8, 8))

    def read(self) -> builder.Slot:
        s = self.slot
        s.suffix, s.name, s.patch = self.suf.get().strip(), self.name.get().strip(), self.patch.get()
        s.igb, s.hud = self.skin.path(), self.hud.path()
        return s

    def refresh(self, num: str):
        self.num_lbl.configure(text=(num + self.suf.get().strip()) if num else "?")
        src = self.skin.current()
        if src and os.path.isfile(src):
            n = builder.count_patchable(src)
            self.patch_lbl.configure(text=f"hex-edit: o nome padrão aparece {n}x - vai receber o número da skin" if n else
                                     "hex-edit: nome padrão não encontrado (skin já tratada ou outro formato) - copiada como está")
        else:
            self.patch_lbl.configure(text="")


class CreatorWindow(tk.Toplevel):
    def __init__(self, host, master=None):
        super().__init__(master or (host if isinstance(host, tk.Misc) else tk._get_default_root()))
        self.host = host
        self.settings = load_settings()
        self.title("Criar personagem do zero")
        self.configure(bg=th.PANEL)
        extras.fit(self, 1180, 860)
        th.dialog_header(self, "Criar personagem do zero", "people", th.ACCENT)
        self.viewer = viewer.Viewer(self.settings.get("insight", ""))
        self.last_dir = self.settings.get("last_dir", "")
        self.base: pj.Character | None = None
        self.plan: builder.CreatePlan | None = None
        self.step = 0
        self._job = None
        self.rows: list[SkinRow] = []
        self.chars = [c for c in host.all_characters() if c.skins and c.powerstyle_path and c.talents_path and not c.is_npc]

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(6, 8))
        self.wiz = ttk.Frame(self.nb)
        self.view_tab = ttk.Frame(self.nb)
        self.faq_tab = ttk.Frame(self.nb)
        self.edit_tab = ttk.Frame(self.nb)
        self.nb.add(self.wiz, text="  Assistente  ")
        self.nb.add(self.edit_tab, text="  Editar poderes  ")
        self.nb.add(self.view_tab, text="  Visualizar (Insight)  ")
        self.nb.add(self.faq_tab, text="  FAQ / Guia  ")
        self._build_wizard()
        self._build_edit()
        self._build_viewer()
        self._build_faq()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_step(0)

    # ================================================================== assistente
    def _build_wizard(self):
        side = tk.Frame(self.wiz, bg=th.mix(th.PANEL, th.BG, .5), width=th.px(210))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        _lbl(side, "ETAPAS", "dim", th.H2, bg=side["bg"]).pack(fill="x", padx=14, pady=(14, 8))
        self.step_lbls = []
        for i, (key, title, icon) in enumerate(STEPS):
            row = tk.Frame(side, bg=side["bg"], cursor="hand2")
            row.pack(fill="x", padx=6, pady=1)
            ic = tk.Label(row, text=th.glyph(icon), font=th.ICON, bg=side["bg"], fg=th.DIM, width=3)
            ic.pack(side="left", pady=6)
            t = tk.Label(row, text=f"{i + 1}. {title}", font=th.UI, bg=side["bg"], fg=th.FG, anchor="w")
            t.pack(side="left", fill="x", expand=True)
            for w in (row, ic, t):
                w.bind("<Button-1>", lambda e, i=i: self.show_step(i))
            self.step_lbls.append((row, ic, t))
        self.side = side

        main = ttk.Frame(self.wiz)
        main.pack(side="left", fill="both", expand=True)
        self.tip = th.Banner(main)
        self.tip.close.pack_forget()
        self.tip.pack(fill="x")
        nav = ttk.Frame(main, padding=(12, 8))
        nav.pack(side="bottom", fill="x")
        self.next_btn = th.Button(nav, text="Próximo  ›", style="Accent.TButton", command=lambda: self.show_step(self.step + 1))
        self.next_btn.pack(side="right")
        self.back_btn = th.Button(nav, text="‹  Voltar", command=lambda: self.show_step(self.step - 1))
        self.back_btn.pack(side="right", padx=8)
        self.state_lbl = _lbl(nav, "", "dim", th.UI_S)
        self.state_lbl.pack(side="left", fill="x", expand=True)
        th.hline(main, side="bottom")
        self.body = ttk.Frame(main)
        self.body.pack(fill="both", expand=True)
        self.pages = {}
        for key, *_ in STEPS:
            f = ttk.Frame(self.body, padding=(16, 12))
            self.pages[key] = f
            getattr(self, f"_page_{key}")(f)

    def show_step(self, i: int):
        i = max(0, min(i, len(STEPS) - 1))
        if i > 0 and self.base is None:
            i = 0
            self.state_lbl.configure(text="Escolha primeiro o personagem-base.", fg=th.WARN_SOFT)
        self.step = i
        key = STEPS[i][0]
        for k, f in self.pages.items():
            f.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        for j, (row, ic, t) in enumerate(self.step_lbls):
            cur = j == i
            bg = th.SEL if cur else self.side["bg"]
            for w in (row, ic, t):
                w.configure(bg=bg)
            ic.configure(fg=th.ACCENT if cur else th.DIM)
            t.configure(font=th.UI_B if cur else th.UI, fg=th.SEL_FG if cur else th.FG)
        title, text = knowledge.STEP_TIPS[key]
        self.tip.show_msg(f"{title}: {text}", "info")
        self.back_btn.state(["disabled"] if i == 0 else ["!disabled"])
        if key == "review":
            self.next_btn.pack_forget()
            self.preview()
        else:
            self.next_btn.pack(side="right")
        self.changed()

    # ---- etapa 1: base ------------------------------------------------------------------------------
    def _page_base(self, f):
        th.section_title(f, "Quem empresta o esqueleto", bg=th.PANEL, pady=(0, 8))
        row = ttk.Frame(f)
        row.pack(fill="x")
        _lbl(row, "Personagem-base:").pack(side="left")
        labels = [f"{c.display}   ({c.name})" + ("" if c.proj is self.host.proj else f"      [{c.proj.label}]") for c in self.chars]
        self.base_cb = extras.SearchCombo(row, values=labels, width=60)
        self.base_cb.pack(side="left", padx=8)
        self.base_cb.bind("<<ComboboxSelected>>", lambda e: self.after_idle(self.base_changed), add="+")
        th.Button(row, text="Ver skins no Insight", command=lambda: (self.nb.select(self.view_tab), self.view_char(self.base))).pack(side="left")
        self.base_info = extras._text(f, height=24)
        self.base_info.pack(fill="both", expand=True, pady=(10, 0))
        extras.show_plan(self.base_info, "Escolha um personagem. Ele não é alterado: tudo é copiado com o nome novo.\n\n"
                         "Dica do guia: prefira alguém com animações parecidas com as do personagem que você quer criar "
                         "(o guia usa o Beast como base para o Puck).")

    def base_changed(self):
        i = self.base_cb.current()
        if i < 0:
            return
        c = self.chars[i]
        self.base = c
        s = builder.suggest(c, self.host.proj)
        if not self.v["num"].get().strip():
            self.v["num"].set(s["num"])
        for r in list(self.rows):
            r.destroy()
        self.rows = []
        for sl in builder.default_slots(c):
            self.add_slot(sl)
        st = builder.base_stats(c)
        for k, var in self.sv.items():
            var.set(st.get(k, var.get()))
        self.fly.set(c.stats.get("moveset1", "").lower() == "moveset_flying")
        self.pp.load(c, powers.default_slots(c))
        for fld in (self.mq, self.port) + tuple(self.loads.values()):
            fld.refresh()
        L = [f"{c.display}  ({c.name})   {('[' + c.proj.label + ']') if c.proj is not self.host.proj else ''}", "",
             f"skins ({len(c.skins)}): " + ", ".join(f"{s} {n}" for s, n in c.skins),
             f"animações: {c.anims or '-'}   powerstyle: {c.powerstyle}   som: {c.sounddir or '-'}",
             f"atributos: body {c.stats.get('body', '?')}  strength {c.stats.get('strength', '?')}  mind {c.stats.get('mind', '?')}"
             f"   autospend {c.stats.get('autospend', '?')}   scale {c.stats.get('scale_factor', '1')}", "", "PODERES QUE VÊM JUNTO:"]
        try:
            for p in c.powers():
                L.append("  " + "   ".join(str(x) for x in p if x))
        except Exception as e:
            L.append(f"  ! não consegui ler os poderes: {e}")
        L += ["", "Depois de criar, troque os poderes com 'Copiar poder' e 'Remover poder' no MUA Studio."]
        extras.show_plan(self.base_info, "\n".join(L))
        self.state_lbl.configure(text="")
        self.changed()

    # ---- etapa 2: identidade --------------------------------------------------------------------------
    def _page_ident(self, f):
        th.section_title(f, "Nome e número", bg=th.PANEL, pady=(0, 8))
        g = ttk.Frame(f)
        g.pack(fill="x")
        self.v = {}
        rows = (("display", "Nome exibido:", "Como aparece no jogo (charactername). Ex.: Puck"),
                ("name", "Nome interno:", "Minúsculas, sem espaço. Vira data/talents/<nome>, ps_<nome>, pacotes <nome>_<skin>"),
                ("prefix", "Prefixo dos poderes:", "Sem _ . Os talentos ficam <prefixo>_p1, <prefixo>_p2..."),
                ("num", "Número (0-255):", "Começo dos números das skins e do set de animação"),
                ("bank", "Banco de som:", "Até 6 letras/números; vira <banco>_m.zsm e <banco>_v.zss"))
        for i, (k, label, hint) in enumerate(rows):
            _lbl(g, label).grid(row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar()
            self.v[k] = v
            ttk.Entry(g, textvariable=v, width=28).grid(row=i, column=1, sticky="w", padx=8)
            _lbl(g, hint, "dim", th.UI_S).grid(row=i, column=2, sticky="w")
            v.trace_add("write", lambda *a, k=k: self._ident_auto(k))
        self.share = tk.BooleanVar(value=False)
        th.Check(f, text="Não criar banco de som: usar o banco do personagem-base", variable=self.share,
                 command=self.changed).pack(anchor="w", pady=(10, 0))
        self.num_info = _lbl(f, "", "dim", th.UI_S, wraplength=th.px(900))
        self.num_info.pack(fill="x", pady=(14, 0))
        self._auto_lock = False

    def _ident_auto(self, key):
        """Nome exibido preenche nome interno/prefixo/banco enquanto o usuário não mexer neles."""
        if self._auto_lock:
            return
        if key == "display":
            slug = re.sub(r"[^a-z0-9]", "", self.v["display"].get().lower()
                          .translate(str.maketrans("áàâãéêíóôõúüç", "aaaaeeiooouuc")))
            self._auto_lock = True
            for k, val in (("name", slug[:20]), ("prefix", slug[:16]), ("bank", slug[:6])):
                if not getattr(self, f"_touched_{k}", False):
                    self.v[k].set(val)
            self._auto_lock = False
        elif key in ("name", "prefix", "bank"):
            setattr(self, f"_touched_{key}", True)
        self.changed()

    def _num_status(self):
        num = self.v["num"].get().strip()
        if not num:
            return self.num_info.configure(text="")
        used = {}
        for c in self.host.proj.characters + list(getattr(self.host, "created", None) and self.host.created.characters or []):
            for s, _ in c.skins:
                if s[:-2] == num:
                    used.setdefault(c.display, []).append(s)
        root = self.host.proj.root
        mq = os.path.isfile(os.path.join(root, "ui", "models", "mannequin", f"{num}01.igb"))
        txt = f"Skins vão ser {num}xx: {num}01, {num}02 ... (os 2 últimos dígitos dá para mudar na etapa Skins).   "
        if used:
            txt += "Número já usado por: " + "; ".join(f"{k} ({', '.join(v)})" for k, v in used.items()) + \
                   ". Pode dividir se as skins não se repetirem, mas o mannequin e o loading também são divididos."
            self.num_info.configure(fg=th.WARN_SOFT)
        else:
            txt += "Número livre neste herostat." + (f" Atenção: já existe ui/models/mannequin/{num}01.igb na pasta do jogo." if mq else "")
            self.num_info.configure(fg=th.OK if not mq else th.WARN_SOFT)
        self.num_info.configure(text=txt + "\nPara mod público, registre o número nas planilhas CCC do MarvelMods.")

    # ---- etapa 3: skins -----------------------------------------------------------------------------
    def _page_skins(self, f):
        top = ttk.Frame(f)
        top.pack(fill="x")
        th.section_title(top, "Roupas (até 6)", bg=th.PANEL, pady=(0, 8)).pack(side="left")
        self.add_btn = th.Button(top, text="+ Adicionar skin", command=lambda: self.add_slot())
        self.add_btn.pack(side="right")
        self.skin_scroll = th.ScrollFrame(f, bg=th.PANEL)
        self.skin_scroll.pack(fill="both", expand=True)

    def add_slot(self, slot: builder.Slot | None = None):
        if len(self.rows) >= 6:
            return
        if slot is None:
            used = {r.suf.get().strip() for r in self.rows}
            suf = next(f"{i:02d}" for i in range(1, 100) if f"{i:02d}" not in used)
            slot = builder.Slot(suffix=suf, name=f"Skin {len(self.rows) + 1}",
                                base_skin=self.base.skins[0][0] if self.base else "")
        r = SkinRow(self.skin_scroll.inner, self, slot)
        r.pack(fill="x", pady=2)
        self.rows.append(r)
        self.changed()

    def remove_slot(self, row: SkinRow):
        if len(self.rows) <= 1:
            return messagebox.showinfo("Skins", "O personagem precisa de pelo menos uma skin.", parent=self)
        row.destroy()
        self.rows.remove(row)
        self.changed()

    # ---- etapa 4: menu ----------------------------------------------------------------------------------
    def _page_menu(self, f):
        th.section_title(f, "Mannequin, loading e retrato", bg=th.PANEL, pady=(0, 8))

        def base_file(*rel_fmt):
            def get():
                if not self.base:
                    return ""
                on = self.base.skins[0][0][:-2]
                p = os.path.join(self.base.proj.root, *[r.format(n=on) for r in rel_fmt])
                return p if os.path.isfile(p) else ""
            return get

        self.mq = FileField(f, self, "Mannequin:", base_file("ui", "models", "mannequin", "{n}01.igb"), self.changed)
        self.mq.pack(fill="x", pady=3)
        _lbl(f, "Boneco do menu da S.H.I.E.L.D. Vai para ui/models/mannequin/<número>01.igb (o nome precisa ser esse).",
             "dim", th.UI_S).pack(fill="x", padx=(4, 0), pady=(0, 10))
        self.loads = {}
        for k in ("01", "02", "03"):
            fld = FileField(f, self, f"Loading {k}:", base_file("textures", "loading", "{n}" + k + ".igb"), self.changed)
            fld.pack(fill="x", pady=3)
            self.loads[k] = fld
        _lbl(f, "Telas de carregamento: textures/loading/<número>01..03.igb. Vazio = as do personagem-base, se ele tiver.",
             "dim", th.UI_S).pack(fill="x", padx=(4, 0), pady=(0, 10))
        self.port = FileField(f, self, "Retrato de conversa:", base_file("ui", "hud", "characters", "{n}01.igb"), self.changed)
        self.port.pack(fill="x", pady=3)
        _lbl(f, "Retrato usado nas conversas: ui/hud/characters/<número>01.igb.", "dim", th.UI_S).pack(fill="x", padx=(4, 0))

    # ---- etapa 5: atributos -------------------------------------------------------------------------------
    def _page_stats(self, f):
        th.section_title(f, "Atributos do herostat", bg=th.PANEL, pady=(0, 8))
        g = ttk.Frame(f)
        g.pack(fill="x")
        self.sv = {k: tk.StringVar(value=d) for k, d in (("body", "7"), ("strength", "7"), ("mind", "8"), ("autospend", "bruiser_light"),
                                                           ("scale_factor", "1"), ("team", "hero"), ("menulocation", "0"))}
        r = 0
        for k, label in (("body", "Body (vida):"), ("strength", "Strength (força):"), ("mind", "Mind (energia):")):
            _lbl(g, label).grid(row=r, column=0, sticky="w", pady=4)
            ttk.Spinbox(g, from_=1, to=20, textvariable=self.sv[k], width=6).grid(row=r, column=1, sticky="w", padx=8)
            r += 1
        self.total_lbl = _lbl(g, "", "dim", th.UI_S)
        self.total_lbl.grid(row=0, column=2, rowspan=3, sticky="w", padx=12)
        _lbl(g, "Autospend:").grid(row=r, column=0, sticky="w", pady=4)
        ttk.Combobox(g, textvariable=self.sv["autospend"], width=18, state="readonly",
                     values=("bruiser", "bruiser_light", "support", "support_heavy")).grid(row=r, column=1, sticky="w", padx=8)
        _lbl(g, "como os pontos são gastos sozinhos ao subir de nível", "dim", th.UI_S).grid(row=r, column=2, sticky="w", padx=12)
        r += 1
        _lbl(g, "Tamanho (scale_factor):").grid(row=r, column=0, sticky="w", pady=4)
        ttk.Entry(g, textvariable=self.sv["scale_factor"], width=8).grid(row=r, column=1, sticky="w", padx=8)
        _lbl(g, "1 = normal; Puck 0.8, Juggernaut 1.5", "dim", th.UI_S).grid(row=r, column=2, sticky="w", padx=12)
        r += 1
        _lbl(g, "Time:").grid(row=r, column=0, sticky="w", pady=4)
        ttk.Combobox(g, textvariable=self.sv["team"], width=18, state="readonly", values=("hero", "enemy")).grid(row=r, column=1, sticky="w", padx=8)
        r += 1
        _lbl(g, "Menulocation:").grid(row=r, column=0, sticky="w", pady=4)
        ttk.Entry(g, textvariable=self.sv["menulocation"], width=8).grid(row=r, column=1, sticky="w", padx=8)
        _lbl(g, "posição na seleção; 0 = escolher depois no editor de herostat (1-25, ou 40-50 com o 36 Roster Hack)",
             "dim", th.UI_S).grid(row=r, column=2, sticky="w", padx=12)
        self.fly = tk.BooleanVar(value=False)
        th.Check(f, text="Voa (moveset1 = moveset_flying)", variable=self.fly, command=self.changed).pack(anchor="w", pady=(12, 0))
        for v in self.sv.values():
            v.trace_add("write", lambda *a: self.changed())

    # ---- etapa 6: revisão --------------------------------------------------------------------------------
    def _page_powers(self, f):
        self.pp = PowersPanel(f, self.host.all_characters(), on_change=self.changed)
        self.pp.pack(fill="both", expand=True)

    def _page_review(self, f):
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.over = tk.BooleanVar(value=False)
        th.Check(top, text="Permitir sobrescrever arquivos que já existem (vão para os backups)", variable=self.over,
                 command=self.preview).pack(side="left")
        self.create_btn = th.Button(top, text="Criar personagem", style="Accent.TButton", command=self.create)
        self.create_btn.pack(side="right")
        self.out = extras._text(f)
        self.out.pack(fill="both", expand=True, pady=(10, 0))
        self.after_idle(lambda: self.create_btn.explain_with(self.out))
        self.next_box = ttk.Frame(f)
        self.next_box.pack(fill="x", pady=(8, 0))

    # ---- montagem das escolhas e prévia ---------------------------------------------------------------
    def choices(self) -> builder.Choices:
        v = {k: x.get().strip() for k, x in self.v.items()}
        ch = builder.Choices(base=self.base, display=v["display"], name=v["name"], prefix=v["prefix"], num=v["num"],
                             bank=v["bank"], share_bank=self.share.get(), overwrite=self.over.get() if hasattr(self, "over") else False)
        ch.slots = [r.read() for r in self.rows]
        ch.mannequin = self.mq.path()
        ch.loading = {k: fld.path() for k, fld in self.loads.items() if fld.path()}
        ch.portrait = self.port.path()
        ch.stats = {k: x.get() for k, x in self.sv.items()}
        ch.flying = self.fly.get()
        return ch

    def changed(self):
        if not hasattr(self, "fly"):  # ainda montando as páginas
            return
        num = self.v["num"].get().strip()
        for r in self.rows:
            r.refresh(num)
        self.add_btn.state(["disabled"] if len(self.rows) >= 6 else ["!disabled"])
        self._num_status()
        try:
            tot = sum(int(self.sv[k].get() or 0) for k in ("body", "strength", "mind"))
            ok = 22 <= tot <= 24
            self.total_lbl.configure(text=f"soma = {tot}  " + ("(ok: 22-24 é o normal)" if ok else "(o normal é 22-24)"),
                                     fg=th.OK if ok else th.WARN_SOFT)
        except ValueError:
            self.total_lbl.configure(text="use números inteiros", fg=th.ERR_SOFT)
        if STEPS[self.step][0] == "review":  # o plano completo só é montado na Revisão (com espera)
            if self._job:
                self.after_cancel(self._job)
            self._job = self.after(400, self.preview)
            return
        self._quick_check()

    def _quick_check(self):
        """Resumo na barra de baixo."""
        if not self.base:
            return
        missing = [lbl for k, lbl in (("display", "nome exibido"), ("name", "nome interno"), ("prefix", "prefixo"),
                                      ("num", "número"), ("bank", "banco de som")) if not self.v[k].get().strip()
                   and not (k == "bank" and self.share.get())]
        if missing:
            self.state_lbl.configure(text="Falta preencher: " + ", ".join(missing), fg=th.WARN_SOFT)
        else:
            self.state_lbl.configure(text=f"{self.v['display'].get()} ({self.v['name'].get()}) - número {self.v['num'].get()}, "
                                          f"{len(self.rows)} skin(s), base {self.base.display}", fg=th.DIM)

    def preview(self):
        self.plan = None
        self.create_btn.state(["disabled"])
        for w in self.next_box.winfo_children():
            w.destroy()
        try:
            self.plan = builder.build(self.choices(), self.host.proj, self.host.created.store_dir)
        except Exception as e:
            return extras.show_plan(self.out, f"NÃO foi possível montar o plano: {e}")
        extras.show_plan(self.out, self.plan.describe() + "\n\nPODERES (montados depois de criar os arquivos):\n"
                         + "\n".join(powers.describe(self.pp.slots, self.base)))
        if not self.plan.errors:
            self.create_btn.state(["!disabled"])
            self.state_lbl.configure(text="Pronto para criar.", fg=th.OK)
        else:
            self.state_lbl.configure(text=self.plan.errors[0][:140], fg=th.ERR_SOFT)

    def create(self):
        plan = self.plan
        if not plan or plan.errors:
            return
        cp = plan.clone
        if cp.clash:
            if hasattr(self.host, "editors"):
                bad = extras.dirty_tabs(self.host, [os.path.join(cp.proj.root, *c.split("/")) for c in cp.clash])
                if bad:
                    return messagebox.showwarning("Salve antes", "Arquivos que seriam sobrescritos estão abertos com alterações "
                                                  "não salvas:\n\n" + "\n".join(os.path.basename(t.path) for t in bad), parent=self)
            shown = "\n".join(cp.clash[:14]) + (f"\n... e mais {len(cp.clash) - 14}" if len(cp.clash) > 14 else "")
            if not messagebox.askyesno("Confirmar sobrescrita", f"{len(cp.clash)} arquivo(s) serão SOBRESCRITOS:\n\n{shown}\n\n"
                                       "Os atuais vão para a pasta de backups. Confirmar?", icon="warning", default="no", parent=self):
                return
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            written = builder.apply(plan, getattr(self.host, "anim_tools", None))
            if hasattr(self.host, "editors"):
                extras.reload_tabs(self.host, written)
        except Exception as e:
            self.configure(cursor="")
            return messagebox.showerror("Criar personagem", str(e), parent=self)
        name = cp.stats.get("name")
        self.host.created.reload_characters()
        pw_warn = self._apply_powers(name, cp, written)
        self.configure(cursor="")
        if hasattr(self.host, "_after_projects_changed"):
            self.host._after_projects_changed("created")
        if hasattr(self.host, "status"):
            self.host.status(f"Personagem criado: {name} ({len(written)} arquivos). Está na aba Criados.")
        extras.show_plan(self.out, f"CRIADO: {name}   ({len(written)} arquivos novos)\n\n" + plan.describe()
                         + ("\n\nPODERES - PONTOS PARA CONFERIR:\n" + "\n".join(f"  * {w}" for w in pw_warn) if pw_warn else "")
                         + "\n\nPRÓXIMOS PASSOS:\n" + "\n".join(f"  {i}. {s}" for i, s in enumerate(knowledge.NEXT_STEPS, 1)))
        self.plan = None
        self.create_btn.state(["disabled"])
        self.state_lbl.configure(text=f"{name} criado. Ele está na aba Criados do MUA Studio.", fg=th.OK)
        self._next_buttons(name)

    def _created(self, name: str):
        return next((c for c in self.host.created.characters if c.name.lower() == name.lower()), None)

    def _apply_powers(self, name: str, cp, written: list) -> list[str]:
        """Monta os poderes escolhidos no personagem recém-criado. Os poderes 'mantidos' do base viram os do clone."""
        new = self._created(name)
        if new is None or self.base is None:
            return ["o personagem criado não foi encontrado para montar os poderes"]
        base_pw, new_pw = self.base.powers(), new.powers()
        slots = []
        for s in self.pp.slots:
            s2 = powers.PowerSlot(**{k: getattr(s, k) for k in s.__dataclass_fields__})
            if s.src is self.base and 0 <= s.orig < len(base_pw) and s.talent == base_pw[s.orig][0] and s.orig < len(new_pw):
                s2.src, s2.talent = new, new_pw[s.orig][0]
            slots.append(s2)
        try:
            w, warns = powers.apply(new, slots, getattr(self.host, "anim_tools", None), True)
        except Exception as e:
            return [f"poderes não montados: {e} (o personagem foi criado com os poderes do base)"]
        written += w
        self._add_to_manifest(cp.snippet_path, cp.proj, w)
        if hasattr(self.host, "editors"):
            extras.reload_tabs(self.host, w)
        return warns

    @staticmethod
    def _add_to_manifest(snippet_path, proj, paths):
        """Arquivos novos dos poderes entram na lista do personagem criado (para 'Excluir' desfazer tudo)."""
        man = os.path.splitext(snippet_path)[0] + ".arquivos.json"
        try:
            with open(man, encoding="utf-8") as f:
                rels = set(json.load(f))
        except Exception:
            return
        for p in paths:
            if proj.owns(p):
                rels.add(proj.rel(p))
                if os.path.isfile(p + ".txt"):
                    rels.add(proj.rel(p) + ".txt")
        with open(man, "w", encoding="utf-8") as f:
            json.dump(sorted(rels), f, indent=1)

    # ================================================================== editar poderes de quem já existe
    def _build_edit(self):
        f = ttk.Frame(self.edit_tab, padding=(16, 12))
        f.pack(fill="both", expand=True)
        row = ttk.Frame(f)
        row.pack(fill="x")
        _lbl(row, "Personagem:").pack(side="left")
        self.ed_owner = None
        self.ed_chars = sorted(self.chars, key=lambda c: (getattr(c.proj, "kind", "") != "criado", c.display.lower()))
        self.ed_cb = extras.SearchCombo(row, values=[f"{c.display}   ({c.name})" + ("   [Criados]" if getattr(c.proj, "kind", "") == "criado" else "")
                                                     for c in self.ed_chars], width=50)
        self.ed_cb.pack(side="left", padx=8)
        self.ed_cb.bind("<<ComboboxSelected>>", lambda e: self.after_idle(self._ed_pick), add="+")
        self.ed_apply = th.Button(row, text="Aplicar nos arquivos", style="Accent.TButton", command=self._ed_apply)
        self.ed_apply.pack(side="right")
        th.Button(row, text="Descartar mudanças", command=self._ed_pick).pack(side="right", padx=8)
        _lbl(f, "Monte a lista de poderes: mantenha, troque pela técnica de outro personagem, renomeie e ajuste. "
                "Nada é gravado até 'Aplicar'; os arquivos atuais vão para os backups.", "dim", th.UI_S).pack(fill="x", pady=(8, 8))
        self.ed_out = extras._text(f, height=4)
        self.ed_out.pack(side="bottom", fill="x", pady=(8, 0))
        self.ed_pp = PowersPanel(f, self.host.all_characters(), on_change=self._ed_changed)
        self.ed_pp.pack(fill="both", expand=True)
        self.ed_apply.state(["disabled"])

    def _ed_pick(self):
        i = self.ed_cb.current()
        if i < 0:
            return
        c = self.ed_chars[i]
        self.ed_owner = c
        self.ed_pp.load(c, powers.default_slots(c))
        self.ed_apply.state(["!disabled"])
        extras.show_plan(self.ed_out, f"{c.display}: {len(self.ed_pp.slots)} poder(es). Faça as mudanças e clique em Aplicar.")

    def _ed_changed(self):
        c = self.ed_owner
        if c is not None:
            extras.show_plan(self.ed_out, "MUDANÇAS PENDENTES:\n" + "\n".join(powers.describe(self.ed_pp.slots, c)))

    def _ed_apply(self):
        c = self.ed_owner
        if c is None:
            return
        if getattr(c.proj, "kind", "") != "criado" and not messagebox.askyesno(
                "Editar poderes", f"{c.display} não é um personagem criado aqui: os arquivos dele no jogo serão alterados "
                                  "(com backup). Continuar?", parent=self):
            return
        if hasattr(self.host, "editors"):
            bad = extras.dirty_tabs(self.host, [p for p in (c.talents_path, c.powerstyle_path) if p])
            if bad:
                return messagebox.showwarning("Salve antes", "Arquivos deste personagem estão abertos com alterações não salvas:\n\n"
                                              + "\n".join(os.path.basename(t.path) for t in bad), parent=self)
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            w, warns = powers.apply(c, self.ed_pp.slots, getattr(self.host, "anim_tools", None), True)
        except Exception as e:
            self.configure(cursor="")
            return messagebox.showerror("Editar poderes", str(e), parent=self)
        self.configure(cursor="")
        snip = getattr(c.proj, "snippets", {}).get(c.name.lower())
        if snip:
            self._add_to_manifest(snip, c.proj, w)
        if hasattr(self.host, "editors"):
            extras.reload_tabs(self.host, w)
        if hasattr(self.host, "status"):
            self.host.status(f"Poderes de {c.display} gravados ({len(set(w))} arquivos)")
        self.ed_pp.load(c, powers.default_slots(c))
        extras.show_plan(self.ed_out, f"GRAVADO: {len(set(w))} arquivo(s) de {c.display}." +
                         ("\n\nPONTOS PARA CONFERIR:\n" + "\n".join(f"  * {x}" for x in warns) if warns else ""))

    def _next_buttons(self, name: str):
        h = self.host
        new = next((c for c in h.created.characters if c.name.lower() == name.lower()), None)
        acts = [("Pôr no herostat do jogo", "open_herostat", ()), ("Copiar poderes", "copy_power", ()),
                ("Mixer de animações", "anim_mixer", ()), ("Editor de áudio", "audio_editor", ()),
                ("Ficha do personagem", "open_sheet", (new,)), ("Ver no Insight", None, ())]
        flow = th.Flow(self.next_box)
        flow.pack(fill="x")
        for label, meth, args in acts:
            if meth is None:
                cmd = lambda: (self.nb.select(self.view_tab), self.view_char(new))  # noqa: E731
            elif hasattr(h, meth):
                cmd = (lambda m=getattr(h, meth), a=args: m(*a))
            else:
                continue
            flow.add(th.Button(flow, text=label, command=cmd))

    # ================================================================== visualizador
    def _build_viewer(self):
        f = ttk.Frame(self.view_tab, padding=(16, 12))
        f.pack(fill="both", expand=True)
        row = ttk.Frame(f)
        row.pack(fill="x")
        _lbl(row, "Insight:").pack(side="left")
        self.ins_var = tk.StringVar(value=self.viewer.exe)
        ttk.Entry(row, textvariable=self.ins_var, width=60).pack(side="left", padx=8)
        th.Button(row, text="Escolher insight.exe...", command=self.pick_insight).pack(side="left")
        self.ins_lbl = _lbl(row, "", "dim", th.UI_S)
        self.ins_lbl.pack(side="left", padx=10)

        row = ttk.Frame(f)
        row.pack(fill="x", pady=(12, 6))
        _lbl(row, "Personagem:").pack(side="left")
        all_chars = self.host.all_characters()
        self.vchars = [c for c in all_chars if c.skins]
        self.vchar_cb = extras.SearchCombo(row, values=[f"{c.display}   ({c.name})" + ("" if c.proj is self.host.proj else f"   [{c.proj.label}]")
                                                         for c in self.vchars], width=50)
        self.vchar_cb.pack(side="left", padx=8)
        self.vchar_cb.bind("<<ComboboxSelected>>", lambda e: self.after_idle(self._vchar_picked), add="+")
        th.Button(row, text="Abrir outro .igb...", command=self.view_other).pack(side="left", padx=4)
        th.Button(row, text="Fechar janelas do Insight", command=self.viewer.close_all).pack(side="right")

        cols = ("arquivo", "versao", "caminho")
        self.vtree = ttk.Treeview(f, columns=cols, show="tree headings", height=16)
        self.vtree.heading("#0", text="O quê")
        self.vtree.heading("arquivo", text="Arquivo")
        self.vtree.heading("versao", text="IGB")
        self.vtree.heading("caminho", text="Pasta")
        self.vtree.column("#0", width=th.px(200))
        self.vtree.column("arquivo", width=th.px(170))
        self.vtree.column("versao", width=th.px(60), anchor="center")
        self.vtree.column("caminho", width=th.px(520))
        self.vtree.pack(fill="both", expand=True)
        self.vtree.bind("<Double-1>", lambda e: self._open_selected())
        self.vtree.bind("<Return>", lambda e: self._open_selected())
        th.tree_tooltips(self.vtree)
        self.vpaths: dict[str, str] = {}
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(8, 0))
        th.Button(b, text="Abrir no Insight", style="Accent.TButton", command=self._open_selected).pack(side="left")
        self.vstatus = _lbl(b, "Duplo clique numa linha abre o modelo no Insight. Ele só mostra o modelo (não carrega "
                               "animações nem dados do jogo). Coluna IGB: arquivos v4 (mannequins, alguns HUDs) costumam abrir; "
                               "v8 (a maioria das skins) o Insight antigo não abre - é só ignorar.", "dim", th.UI_S, wraplength=th.px(800))
        self.vstatus.pack(side="left", padx=12, fill="x", expand=True)
        self._insight_state()

    def _insight_state(self):
        self.ins_lbl.configure(text="encontrado" if self.viewer.available else "não encontrado",
                               fg=th.OK if self.viewer.available else th.ERR_SOFT)

    def pick_insight(self):
        p = filedialog.askopenfilename(parent=self, title="insight.exe do Alchemy", filetypes=[("insight.exe", "*.exe")],
                                       initialdir=os.path.dirname(self.viewer.exe or viewer.DEFAULT_INSIGHT))
        if p:
            self.viewer.exe = os.path.normpath(p)
            self.ins_var.set(self.viewer.exe)
            self.settings["insight"] = self.viewer.exe
            save_settings(self.settings)
            self._insight_state()

    def _vchar_picked(self):
        i = self.vchar_cb.current()
        if i >= 0:
            self.view_char(self.vchars[i])

    def view_char(self, c):
        if c is None:
            return
        for i, x in enumerate(self.vchars):
            if x is c or (x.name.lower() == c.name.lower() and x.proj is c.proj):
                self.vchar_cb.current(i)
                break
        num = c.skins[0][0][:-2] if c.skins else ""
        assets = viewer.character_assets(c.proj.root, num, [s for s, _ in c.skins], c.name.lower())
        self._fill_tree(f"{c.display}", assets)

    def _fill_tree(self, title, assets):
        self.vtree.delete(*self.vtree.get_children())
        self.vpaths = {}
        root = self.vtree.insert("", "end", text=title, open=True)
        for label, p in assets:
            v = viewer.igb_version(p)
            iid = self.vtree.insert(root, "end", text=label, values=(os.path.basename(p), f"v{v}" if v else "?", os.path.dirname(p)))
            self.vpaths[iid] = p
        if not assets:
            self.vtree.insert(root, "end", text="(nenhum .igb encontrado na pasta deste personagem)")

    def view_other(self):
        p = filedialog.askopenfilename(parent=self, filetypes=IGB_TYPES, initialdir=self.last_dir)
        if p:
            self.last_dir = os.path.dirname(p)
            self.view_file(os.path.normpath(p))

    def _open_selected(self):
        sel = self.vtree.selection()
        if sel and sel[0] in self.vpaths:
            self.view_file(self.vpaths[sel[0]])

    def view_file(self, path: str, origin=None):
        if not path:
            return messagebox.showinfo("Visualizar", "Nenhum arquivo para ver aqui (escolha um ou um personagem-base que tenha).", parent=self)
        if not self.viewer.available:
            self.nb.select(self.view_tab)
            return messagebox.showwarning("Visualizar", "Não achei o insight.exe do Alchemy. Escolha onde ele está na aba Visualizar.",
                                          parent=self)
        try:
            p = self.viewer.open(path)
        except Exception as e:
            return self._vmsg(f"Não deu para abrir {os.path.basename(path)}: {e}", "err")
        self._vmsg(f"Abrindo {os.path.basename(path)} no Insight...", "dim")
        self._poll(p, os.path.basename(path), 0)

    def _poll(self, p, name, n):
        st = viewer.Viewer.status(p)
        if st == "esperando" and n < 16:
            return self.after(500, lambda: self._poll(p, name, n + 1))
        if st == "ok":
            self._vmsg(f"{name}: aberto no Insight (girar: arrastar com o botão esquerdo; zoom: botão direito).", "ok")
        elif st == "vazio":
            self._vmsg(f"{name}: o Insight abriu mas não conseguiu carregar este arquivo (comum em skins/HUD em formato "
                       "mais novo). Pode ignorar: não quer dizer que o arquivo esteja com problema.", "warn")
        elif st == "fechou":
            self._vmsg(f"{name}: o Insight fechou ao abrir este arquivo (formato não suportado por ele). Ignorado.", "warn")
        else:
            self._vmsg(f"{name}: enviado ao Insight.", "dim")

    def _vmsg(self, text, kind):
        fg = {"ok": th.OK, "warn": th.WARN_SOFT, "err": th.ERR_SOFT, "dim": th.DIM}[kind]
        self.vstatus.configure(text=text, fg=fg)
        if self.nb.select() != str(self.view_tab):
            self.state_lbl.configure(text=text[:160], fg=fg)

    # ================================================================== FAQ
    def _build_faq(self):
        f = ttk.Frame(self.faq_tab, padding=(16, 12))
        f.pack(fill="both", expand=True)
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.faq_q = tk.StringVar()
        se = th.SearchEntry(top, self.faq_q, "Procurar no FAQ (ex.: mannequin, skin branca, autospend)", bg=th.PANEL)
        se.pack(side="left", fill="x", expand=True)
        th.Button(top, text="Abrir o guia no MarvelMods", command=lambda: webbrowser.open(knowledge.GUIDE_URL)).pack(side="left", padx=8)
        pw = ttk.Panedwindow(f, orient="horizontal")
        pw.pack(fill="both", expand=True, pady=(10, 0))
        left = ttk.Frame(pw)
        self.faq_tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.faq_tree.pack(fill="both", expand=True)
        th.tree_tooltips(self.faq_tree)
        pw.add(left, weight=2)
        self.faq_text = extras._text(pw)
        self.faq_text.tag_configure("q", font=th.UI_B, foreground=th.STRONG, spacing3=8)
        self.faq_text.configure(font=th.UI)
        pw.add(self.faq_text, weight=3)
        self.faq_tree.bind("<<TreeviewSelect>>", lambda e: self._faq_show())
        self.faq_q.trace_add("write", lambda *a: self._faq_fill())
        self._faq_fill()

    def _faq_fill(self):
        q = self.faq_q.get().strip().lower()
        t = self.faq_tree
        t.delete(*t.get_children())
        self.faq_items = {}
        cats = {}
        first = None
        for i, (cat, ques, ans) in enumerate(knowledge.FAQ):
            if q and q not in (cat + " " + ques + " " + ans).lower():
                continue
            if cat not in cats:
                cats[cat] = t.insert("", "end", text=cat, open=True)
            iid = t.insert(cats[cat], "end", text=ques)
            self.faq_items[iid] = i
            first = first or iid
        if first:
            t.selection_set(first)
            t.see(first)
        else:
            self._faq_write([("q", "Nada encontrado."), ("", "Tente outra palavra, ou abra o guia completo no MarvelMods.")])

    def _faq_show(self):
        sel = self.faq_tree.selection()
        if not sel or sel[0] not in self.faq_items:
            return
        cat, ques, ans = knowledge.FAQ[self.faq_items[sel[0]]]
        self._faq_write([("q", ques), ("", ans), ("", "\nFonte: guia 'Creating a Character from Scratch' (MarvelMods) "
                                                          "e testes do MUA Studio neste mod.")])

    def _faq_write(self, parts):
        t = self.faq_text
        t.configure(state="normal")
        t.delete("1.0", "end")
        for tag, s in parts:
            t.insert("end", s + "\n", tag)
        t.configure(state="disabled")

    def open_faq(self, query: str = ""):
        self.nb.select(self.faq_tab)
        self.faq_q.set(query)

    # ==================================================================
    def close(self):
        self.settings["last_dir"] = self.last_dir
        save_settings(self.settings)
        self.destroy()
