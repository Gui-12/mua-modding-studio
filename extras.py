"""Telas extras do MUA Studio: remover poder, editor de herostat, compilar personagem,
mixer de animações e clonar personagem. (Não importa app.py: recebe o objeto da janela.)"""
from __future__ import annotations

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import xmlb
import ops
import transfer
import anims
import project as pj

from theme import BG, PANEL, FG, DIM, SEL  # noqa: E402  cores do tema (theme.py)


def fit(win, w: int, h: int):
    """Abre a janela no tamanho pedido, mas nunca maior que a tela (com folga para a barra de tarefas)."""
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w, h = min(w, sw - 60), min(h, sh - 110)
    win.geometry(f"{w}x{h}+{max((sw - w) // 2, 0)}+{max((sh - h) // 2 - 30, 0)}")


class SearchCombo(ttk.Combobox):
    """Lista de escolha em que dá para digitar um pedaço do nome: a lista mostra só o que combina
    e Enter escolhe o primeiro. current() continua devolvendo a posição na lista completa."""

    def __init__(self, parent, values=(), **kw):
        kw.pop("state", None)
        super().__init__(parent, values=list(values), **kw)
        self.all_values = list(values)
        self._last = ""
        self.bind("<KeyRelease>", self._typed)
        self.bind("<Return>", self._commit)
        self.bind("<FocusOut>", self._commit, True)
        self.bind("<<ComboboxSelected>>", self._picked, True)
        self.bind("<FocusIn>", lambda e: self.selection_range(0, "end"), True)

    def set_values(self, values):
        self.all_values = list(values)
        self["values"] = self.all_values

    def current(self, newindex=None):
        if newindex is None:
            v = self.get()
            return self.all_values.index(v) if v in self.all_values else -1
        self.set(self.all_values[newindex])
        self._last = self.get()
        self["values"] = self.all_values
        return newindex

    def _matches(self):
        q = self.get().strip().lower()
        return [v for v in self.all_values if q in v.lower()] if q else list(self.all_values)

    def _typed(self, e):
        if e.keysym in ("Return", "Escape", "Up", "Down", "Left", "Right", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        self["values"] = self._matches() or self.all_values

    def _picked(self, _e=None):
        self._last = self.get()
        self.after_idle(lambda: self.winfo_exists() and self.configure(values=self.all_values))

    def _commit(self, _e=None):
        v = self.get()
        if v in self.all_values:
            if v != self._last:
                self._last = v
                self["values"] = self.all_values
                self.event_generate("<<ComboboxSelected>>")
            return
        m = self._matches() if v.strip() else []
        if m:
            self.set(m[0])
            self._last = m[0]
            self["values"] = self.all_values
            self.icursor("end")
            self.event_generate("<<ComboboxSelected>>")
        else:
            self.set(self._last)
            self["values"] = self.all_values


def _text(parent, **kw) -> tk.Text:
    t = tk.Text(parent, bg=BG, fg=FG, font=("Consolas", 10), wrap="word", borderwidth=0, highlightthickness=0, padx=8, pady=6, **kw)
    t._i18n = True  # saída do programa (prévias/mensagens): traduzida conforme o idioma
    t.tag_configure("warn", foreground="#e0b040")
    t.tag_configure("err", foreground="#ff8080")
    t.tag_configure("head", foreground="#7fb4f0")
    return t


def show_plan(t: tk.Text, text: str):
    t.configure(state="normal")
    t.delete("1.0", "end")
    for line in text.split("\n"):
        s = line.lstrip()
        tag = "err" if s.startswith("!") or line.startswith("NÃO") else "warn" if s.startswith("*") or line.startswith("PONTOS") \
            else "head" if (line.isupper() or line.endswith(":")) and line.strip() else ""
        t.insert("end", line + "\n", tag)
    t.configure(state="disabled")


def char_index(chars, c) -> int:
    """Posição do personagem na lista, mesmo que a lista tenha sido recarregada depois (objeto novo, mesmo personagem)."""
    if c is None:
        return -1
    for i, x in enumerate(chars):
        if x is c:
            return i
    for i, x in enumerate(chars):
        if x.name.lower() == c.name.lower() and x.proj.kind == c.proj.kind and x.proj.root == c.proj.root:
            return i
    return -1


def dirty_tabs(app, paths) -> list:
    ps = {os.path.normcase(p) for p in paths}
    return [t for t in app.editors() if t.modified and os.path.normcase(t.path) in ps]


def reload_tabs(app, paths):
    ps = {os.path.normcase(p) for p in paths}
    for t in app.editors():
        if os.path.normcase(t.path) in ps:
            t.load()


def confirm_plan(app, title: str, text: str, ok_label: str = "Aplicar") -> bool:
    d = tk.Toplevel(app)
    d.title(title)
    d.configure(bg=PANEL)
    fit(d, 860, 560)
    d.transient(app)
    t = _text(d)
    t.pack(fill="both", expand=True, padx=12, pady=12)
    show_plan(t, text)
    res = {"ok": False}
    b = ttk.Frame(d, padding=(12, 0, 12, 12))
    b.pack(fill="x", side="bottom", before=t)
    ttk.Button(b, text="Cancelar", command=d.destroy).pack(side="right")
    ttk.Button(b, text=ok_label, style="Accent.TButton", command=lambda: (res.update(ok=True), d.destroy())).pack(side="right", padx=8)
    d.grab_set()
    app.wait_window(d)
    return res["ok"]


# ================================================================ remover poder
def remove_power(app, char: pj.Character, talent_name: str, ask: bool = True) -> bool:
    plan = ops.remove_power_plan(char, talent_name)
    if plan.errors:
        messagebox.showerror("Remover poder", "\n".join(plan.errors), parent=app)
        return False
    bad = dirty_tabs(app, [c.path for c in plan.changes])
    if bad:
        messagebox.showwarning("Salve antes", "Arquivos abertos com alterações não salvas:\n\n" + "\n".join(os.path.basename(t.path) for t in bad), parent=app)
        return False
    if ask and not confirm_plan(app, "Remover poder", plan.describe(char.proj), "Remover"):
        return False
    written = transfer.apply_plan(char.proj, plan)
    char.proj._vars = None
    reload_tabs(app, written)
    app.fill_characters()
    app.status(f"Poder removido de {char.display}: {talent_name}  ({len(written)} arquivo(s), com backup)")
    return True


# ========================================================= excluir personagem criado
def delete_created(app, char: pj.Character) -> bool:
    files, kept = ops.created_files(char)
    in_game = app.proj.character(char.name) is not None
    d = tk.Toplevel(app)
    d.title("Excluir personagem criado")
    d.configure(bg=PANEL)
    fit(d, 820, 600)
    d.transient(app)
    ttk.Label(d, text=f"Excluir {char.display}  ({char.name})", font=("Segoe UI", 13, "bold"), padding=(12, 12, 12, 4)).pack(anchor="w")
    b = ttk.Frame(d, padding=12)
    b.pack(fill="x", side="bottom")
    t = _text(d)
    t.pack(fill="both", expand=True, padx=12)
    show_plan(t, "\n".join(
        [f"ARQUIVOS DO PERSONAGEM NO JOGO ({len(files)}):"] + [f"  {f}" for f in files]
        + (["", "MANTIDOS (outro personagem do herostat usa):"] + [f"  * {k}" for k in kept] if kept else [])
        + ["", "ESCOLHA:", "  'Só tirar da lista' apenas some com ele da aba Criados; os arquivos e o herostat ficam como estão.",
           "  'Excluir também os arquivos' apaga os arquivos acima (cada um vai antes para a pasta de backups)"
           + (" e tira o personagem do herostat do jogo." if in_game else ".")]))
    res = {"mode": None}
    ttk.Button(b, text="Cancelar", command=d.destroy).pack(side="right")
    ttk.Button(b, text=f"Excluir também os {len(files)} arquivos", style="Accent.TButton",
               command=lambda: (res.update(mode="files"), d.destroy())).pack(side="right", padx=8)
    ttk.Button(b, text="Só tirar da lista", command=lambda: (res.update(mode="list"), d.destroy())).pack(side="right")
    d.grab_set()
    app.wait_window(d)
    if not res["mode"]:
        return False
    if res["mode"] == "files":
        paths = [os.path.join(char.proj.root, *f.split("/")) for f in files] + ([app.proj.herostat_path] if in_game else [])
        bad = dirty_tabs(app, paths)
        if bad:
            messagebox.showwarning("Salve antes", "Arquivos abertos com alterações não salvas:\n\n" + "\n".join(os.path.basename(x.path) for x in bad), parent=app)
            return False
        if not messagebox.askyesno("Confirmar exclusão", f"Apagar {len(files)} arquivo(s) de {char.display}"
                                   + (" e tirá-lo do herostat" if in_game else "") + "?\n\nCópias ficam na pasta de backups.\n\nConfirmar isso?",
                                   icon="warning", default="no", parent=app):
            return False
        for tab in list(app.editors()):
            if any(os.path.normcase(tab.path) == os.path.normcase(p) for p in paths[:len(files)]):
                app.tabs.forget(tab)
                tab.destroy()
    try:
        out = ops.delete_created(char, res["mode"] == "files")
    except Exception as e:
        messagebox.showerror("Excluir", str(e), parent=app)
        return False
    app.created.reload_characters()
    if out["herostat"]:
        app.reload_project()
    app._after_projects_changed("created")
    app.status(f"{char.display} excluído dos Criados" + (f"; {out['files']} arquivo(s) apagados (cópias nos backups)" if out["files"] else "")
               + ("; tirado do herostat" if out["herostat"] else ""))
    return True


# ============================================================= compilar personagem
def export_character(app, char: pj.Character, parent_dir: str | None = None) -> str | None:
    parent_dir = parent_dir or filedialog.askdirectory(parent=app, title=f"Onde criar a pasta de {char.display}?")
    if not parent_dir:
        return None
    out = os.path.join(parent_dir, re.sub(r'[\\/:*?"<>|]', "_", f"{char.display} ({char.name})"))
    if os.path.isdir(out) and os.listdir(out):
        if not messagebox.askyesno("Compilar personagem", f"A pasta já existe e tem arquivos:\n{out}\n\nCopiar por cima?", parent=app):
            return None
    app.configure(cursor="watch")
    app.update_idletasks()
    try:
        files, missing = ops.export_character(char, out)
    except Exception as e:
        messagebox.showerror("Compilar personagem", str(e), parent=app)
        return None
    finally:
        app.configure(cursor="")
    app.status(f"{char.display} compilado: {len(files)} arquivos em {out}")
    messagebox.showinfo("Compilar personagem", f"{len(files)} arquivos copiados para:\n{out}\n\n"
                        + (f"{len(missing)} itens referenciados não estavam na pasta (veja LEIAME.txt); costumam ser arquivos do jogo original."
                           if missing else "Nenhum arquivo referenciado ficou faltando."), parent=app)
    return out


# ================================================================ editor de herostat
class HerostatTab(ttk.Frame):
    """Lista do herostat do jogo: trocar posições, substituir, adicionar e remover personagens."""

    def __init__(self, app):
        super().__init__(app.tabs)
        self.app, self.proj = app, app.proj
        self.store = os.path.join(os.path.dirname(os.path.abspath(__file__)), "herostat_guardados")
        self.dirty = False
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill="x")
        self.save_btn = ttk.Button(top, text="Salvar herostat", style="Accent.TButton", command=self.save)
        self.save_btn.pack(side="right")  # empacotado primeiro: nunca fica escondido numa janela estreita
        for text, cmd in (("Trocar os 2 selecionados", self.swap), ("Mudar posição...", self.set_pos),
                          ("Substituir por...", self.replace), ("Adicionar...", self.add),
                          ("Tirar", self.remove), ("Abrir como texto", self.open_text)):
            ttk.Button(top, text=text, command=cmd).pack(side="left", padx=(0, 6))
        self.info = ttk.Label(self, style="Dim.TLabel", padding=(10, 0))
        self.info.pack(anchor="w")
        fr = ttk.Frame(self)
        fr.pack(fill="both", expand=True, padx=10, pady=8)
        cols = ("pos", "nome", "interno", "skin", "ps", "jog")
        self.tv = ttk.Treeview(fr, columns=cols, show="headings", selectmode="extended")
        for c, title, w in zip(cols, ("Posição no menu", "Nome", "Nome interno", "Skin", "Powerstyle", "Jogável"), (120, 240, 180, 100, 200, 80)):
            self.tv.heading(c, text=title)
            self.tv.column(c, width=w, stretch=c in ("nome", "ps"))
        sb = ttk.Scrollbar(fr, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<Double-1>", lambda e: self.set_pos())
        self.load()

    # ---- dados ---------------------------------------------------------------
    def load(self):
        self.root = self.proj.load(self.proj.herostat_path).clone() if self.proj.herostat_path else xmlb.Node("characters")
        self.dirty = False
        self.fill()

    def heroes(self) -> list[xmlb.Node]:
        return [s for s in self.root.children if s.name == "stats" and s.get("name")]

    @staticmethod
    def pos(s: xmlb.Node) -> int:
        try:
            return int(s.get("menulocation", "") or -1)
        except ValueError:
            return -1

    def fill(self, select: list[str] = ()):
        self.tv.delete(*self.tv.get_children())
        hs = sorted(self.heroes(), key=lambda s: (self.pos(s) < 0, self.pos(s), s.get("name").lower()))
        seen: dict[int, int] = {}
        for s in hs:
            seen[self.pos(s)] = seen.get(self.pos(s), 0) + 1
        for s in hs:
            p = self.pos(s)
            self.tv.insert("", "end", iid=s.get("name"), values=(
                (str(p) if p >= 0 else "-") + ("   (repetida!)" if p >= 0 and seen[p] > 1 else ""), s.get("charactername", ""),
                s.get("name"), s.get("skin", ""), s.get("powerstyle", ""), s.get("playable", "")))
        for n in select:
            if self.tv.exists(n):
                self.tv.selection_add(n)
                self.tv.see(n)
        self.info.configure(text=f"{len(hs)} personagens em {self.proj.rel(self.proj.herostat_path or '')}"
                            + ("     ALTERAÇÕES NÃO SALVAS: clique em 'Salvar herostat'" if self.dirty else ""))

    def node(self, name: str) -> xmlb.Node | None:
        return next((s for s in self.heroes() if s.get("name") == name), None)

    def changed(self, select=()):
        """Cada alteração é gravada e compilada na hora (data/herostat.engb + .txt, com backup)."""
        self.dirty = True
        self.fill(select)
        if self.save():
            self.fill(select)

    def selected(self, n: int | None = None) -> list[xmlb.Node] | None:
        sel = [self.node(i) for i in self.tv.selection()]
        if n is not None and len(sel) != n:
            self.app.status(f"Selecione {n} personagem(ns) na lista" + (" (Ctrl+clique para o segundo)" if n == 2 else ""))
            return None
        return sel

    # ---- ações ----------------------------------------------------------------
    def swap(self, names: tuple[str, str] | None = None):
        sel = [self.node(n) for n in names] if names else self.selected(2)
        if not sel:
            return
        a, b = sel
        pa, pb = a.get("menulocation", ""), b.get("menulocation", "")
        a.set("menulocation", pb)
        b.set("menulocation", pa)
        self.changed([a.get("name"), b.get("name")])

    def set_pos(self, name: str | None = None, value: int | None = None):
        s = self.node(name) if name else (self.selected(1) or [None])[0]
        if s is None:
            return
        if value is None:
            value = simpledialog.askinteger("Posição no menu", f"Nova posição de {s.get('charactername', s.get('name'))}\n"
                                            "(se outro personagem já estiver nela, os dois trocam de lugar):",
                                            initialvalue=max(self.pos(s), 0), minvalue=0, maxvalue=999, parent=self)
            if value is None:
                return
        other = next((h for h in self.heroes() if h is not s and self.pos(h) == value), None)
        if other is not None:
            other.set("menulocation", s.get("menulocation", "0"))
        s.set("menulocation", str(value))
        self.changed([s.get("name")])

    def free_pos(self) -> int:
        used = {self.pos(h) for h in self.heroes()}
        p = 0
        while p in used:
            p += 1
        return p

    def candidates(self) -> list[tuple[str, xmlb.Node]]:
        have = {h.get("name").lower() for h in self.heroes()}
        out = []
        for p in self.app.all_projects():
            if p is self.proj:
                continue
            for c in p.characters:
                if c.name.lower() not in have:
                    out.append((f"{c.display}   ({c.name})      [{p.label}]", c.stats))
        if os.path.isdir(self.store):
            for f in sorted(os.listdir(self.store)):
                for s in pj.read_herostat_snippet(os.path.join(self.store, f)):
                    if s.get("name", "").lower() not in have:
                        out.append((f"{s.get('charactername', s.get('name'))}   ({s.get('name')})      [guardado ao ser tirado do herostat]", s))
        return out

    def pick(self, title: str) -> xmlb.Node | None:
        cands = self.candidates()
        if not cands:
            messagebox.showinfo(title, "Não há personagens fora do herostat para escolher.\n\nEles vêm das abas Criados, Avulsos e "
                                "Outro jogo, e dos que você tirou do herostat por aqui.", parent=self)
            return None
        d = tk.Toplevel(self)
        d.title(title)
        d.configure(bg=PANEL)
        fit(d, 620, 420)
        d.transient(self.app)
        lb = tk.Listbox(d, bg=BG, fg=FG, selectbackground=SEL, font=("Segoe UI", 10), borderwidth=0, highlightthickness=0, activestyle="none")
        lb.pack(fill="both", expand=True, padx=12, pady=12)
        for label, _ in cands:
            lb.insert("end", label)
        lb.selection_set(0)
        res = {}
        ttk.Label(d, style="Dim.TLabel", wraplength=590, justify="left", padding=(12, 0), text=(
            "Isto só escreve o personagem no herostat. Os arquivos dele (actors, data, packages...) precisam estar na pasta do jogo: "
            "os da aba Criados já estão; os de Avulsos e Outro jogo, instale com 'Compilar personagem'.")).pack(anchor="w")
        b = ttk.Frame(d, padding=12)
        b.pack(fill="x")
        ttk.Button(b, text="Cancelar", command=d.destroy).pack(side="right")
        ttk.Button(b, text="Escolher", style="Accent.TButton",
                   command=lambda: (res.update(i=lb.curselection()), d.destroy())).pack(side="right", padx=8)
        lb.bind("<Double-1>", lambda e: (res.update(i=lb.curselection()), d.destroy()))
        d.grab_set()
        self.wait_window(d)
        return cands[res["i"][0]][1].clone() if res.get("i") else None

    def add(self, stats: xmlb.Node | None = None, position: int | None = None):
        s = stats or self.pick("Adicionar personagem ao herostat")
        if s is None:
            return
        if self.node(s.get("name")) is not None:
            return self.app.status(f"{s.get('name')} já está no herostat")
        s.set("menulocation", str(self.free_pos() if position is None else position))
        team = next((i for i, h in enumerate(self.root.children) if h.get("name", "").lower() == "team_character"), len(self.root.children))
        self.root.children.insert(team, s)
        self.changed([s.get("name")])

    def _stash(self, s: xmlb.Node):
        os.makedirs(self.store, exist_ok=True)
        xmlb.write_text_file(os.path.join(self.store, f"{s.get('name').lower()}.txt"),
                             xmlb.format_text(s).replace("XMLB stats {", "   stats {", 1))

    def remove(self, name: str | None = None):
        sel = [self.node(name)] if name else self.selected()
        if not sel:
            return self.app.status("Selecione o personagem a tirar")
        for s in sel:
            self._stash(s)
            self.root.children.remove(s)
        self.changed()
        self.app.status(f"{len(sel)} personagem(ns) tirado(s) do herostat; o bloco de cada um ficou guardado e pode voltar por 'Adicionar personagem'")

    def replace(self, name: str | None = None, stats: xmlb.Node | None = None):
        old = self.node(name) if name else (self.selected(1) or [None])[0]
        if old is None:
            return
        new = stats or self.pick(f"Quem entra no lugar de {old.get('charactername', old.get('name'))}?")
        if new is None:
            return
        new.set("menulocation", old.get("menulocation", "0"))
        self._stash(old)
        i = self.root.children.index(old)
        self.root.children[i] = new
        self.changed([new.get("name")])
        self.app.status(f"{new.get('name')} entrou na posição {new.get('menulocation')}; {old.get('name')} saiu e ficou guardado")

    def open_text(self):
        sel = self.tv.selection()
        self.app.open_file(self.proj.herostat_path, r"^\s*name\s*=\s*" + re.escape(sel[0]) + r"\s*;" if sel else None)

    def save(self) -> bool:
        if not self.proj.herostat_path:
            return False
        if dirty_tabs(self.app, [self.proj.herostat_path]):
            messagebox.showwarning("Salve antes", "O herostat está aberto no editor de texto com alterações não salvas.", parent=self)
            return False
        names = [h.get("name").lower() for h in self.heroes()]
        if len(set(names)) != len(names):
            messagebox.showerror("Herostat", "Há nomes internos repetidos.", parent=self)
            return False
        self.proj.save(self.proj.herostat_path, self.root)
        self.dirty = False
        reload_tabs(self.app, [self.proj.herostat_path])
        self.app.reload_project()
        self.load()
        self.app.status(f"Herostat salvo e compilado: {self.proj.rel(self.proj.herostat_path)}  (o anterior foi para os backups)")
        return True


# ================================================================ mixer de animações
class AnimMixer(tk.Toplevel):
    def __init__(self, app, left_char=None, right_char=None):
        super().__init__(app)
        self.app, self.tools = app, app.anim_tools
        self.title("Mixer de animações")
        self.configure(bg=PANEL)
        fit(self, 1180, 760)
        self.transient(app)
        self.chars = app.all_characters()
        self.labels = [f"{c.display}   ({c.name})" + ("" if c.proj is app.proj else f"      [{c.proj.label}]") for c in self.chars]
        self.side = {}
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)
        for col, key in ((0, "A"), (2, "B")):
            f = ttk.Frame(body)
            f.grid(row=0, column=col, sticky="nsew")
            cb = SearchCombo(f, values=self.labels)
            cb.pack(fill="x")
            sb_ = ttk.Combobox(f, state="readonly")
            sb_.pack(fill="x", pady=6)
            lf = ttk.Frame(f)
            lf.pack(fill="both", expand=True)
            lb = tk.Listbox(lf, bg=BG, fg=FG, selectbackground=SEL, font=("Consolas", 10), selectmode="extended", borderwidth=0,
                            highlightthickness=0, activestyle="none", exportselection=False)
            sc = ttk.Scrollbar(lf, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=sc.set)
            sc.pack(side="right", fill="y")
            lb.pack(fill="both", expand=True)
            bf = ttk.Frame(f)
            bf.pack(fill="x", pady=(6, 0))
            ttk.Button(bf, text="Renomear...", command=lambda k=key: self.rename(k)).pack(side="left")
            ttk.Button(bf, text="Remover", command=lambda k=key: self.delete(k)).pack(side="left", padx=6)
            ttk.Button(bf, text="Extrair para pasta...", command=lambda k=key: self.extract(k)).pack(side="left")
            self.side[key] = {"char": cb, "set": sb_, "list": lb, "sets": [], "names": []}
            cb.bind("<<ComboboxSelected>>", lambda e, k=key: self.char_changed(k))
            sb_.bind("<<ComboboxSelected>>", lambda e, k=key: self.fill(k))
        mid = ttk.Frame(body, padding=10)
        mid.grid(row=0, column=1)
        ttk.Button(mid, text="Copiar  >>", style="Accent.TButton", command=lambda: self.copy("A", "B")).pack(pady=6)
        ttk.Button(mid, text="<<  Copiar", command=lambda: self.copy("B", "A")).pack(pady=6)
        self.msg = ttk.Label(self, style="Dim.TLabel", padding=(12, 0, 12, 10), wraplength=1140, justify="left", text=(
            "Escolha um personagem e um set de cada lado. Cada operação remonta o set numa pasta temporária, confere que nenhuma "
            "animação sumiu e só então troca o arquivo (o original vai para os backups). O jogo só reconhece nomes que estão na shared_anims."))
        self.msg.pack(anchor="w", side="bottom", before=body)
        if not self.tools.available:
            self.msg.configure(text="Ferramenta de animação não encontrada em tools/ (animationProducer.exe e sgOptimizer.exe).", foreground="#ff8080")
        for key, ch in (("A", left_char), ("B", right_char)):
            if char_index(self.chars, ch) >= 0:
                self.side[key]["char"].current(char_index(self.chars, ch))
                self.char_changed(key)

    def _char(self, key):
        i = self.side[key]["char"].current()
        return self.chars[i] if i >= 0 else None

    def _set(self, key):
        s = self.side[key]
        i = s["set"].current()
        return s["sets"][i] if 0 <= i < len(s["sets"]) else None

    def busy(self, on: bool):
        self.configure(cursor="watch" if on else "")
        self.update_idletasks()

    def char_changed(self, key):
        s, c = self.side[key], self._char(key)
        s["sets"] = self.tools.char_sets(c) if c else []
        s["set"].configure(values=[os.path.basename(p) for p in s["sets"]])
        s["set"].set("")
        if s["sets"]:
            best = max(range(len(s["sets"])), key=lambda i: os.path.getsize(s["sets"][i]))
            s["set"].current(best)
        self.fill(key)

    def fill(self, key):
        s, c, sp = self.side[key], self._char(key), self._set(key)
        s["list"].delete(0, "end")
        s["names"] = []
        if not sp:
            return
        self.busy(True)
        try:
            names = sorted(self.tools.names(sp))
        except Exception as e:
            self.msg.configure(text=str(e))
            return
        finally:
            self.busy(False)
        table = self.tools.enums(c.proj)
        by_name: dict[str, list[str]] = {}
        for e, n in table.items():
            by_name.setdefault(n, []).append(e)
        used: dict[str, list[str]] = {}
        if c.powerstyle_path:
            try:
                for m in c.proj.load(c.powerstyle_path).children:
                    e = (m.get("animenum") or "").lower()
                    if e in table:
                        used.setdefault(table[e], []).append(m.get("name", ""))
            except Exception:
                pass
        s["names"] = names
        for n in names:
            en = ", ".join(by_name.get(n, [])) or "fora da shared_anims!"
            s["list"].insert("end", f"{n:<24} {en:<26} " + (("usado por " + ", ".join(used[n][:4])) if n in used else ""))

    def picked(self, key) -> list[str]:
        s = self.side[key]
        return [s["names"][i] for i in s["list"].curselection()]

    def valid_name(self, key, name: str) -> bool:
        c = self._char(key)
        if not re.fullmatch(r"[a-z0-9_]+", name):
            messagebox.showerror("Nome inválido", "Use letras minúsculas, números e _.", parent=self)
            return False
        if name not in set(self.tools.enums(c.proj).values()):
            return messagebox.askyesno("Nome fora da tabela", f"'{name}' não está na shared_anims: o jogo não vai conseguir tocar essa "
                                       "animação por nome.\n\nUsar assim mesmo?", parent=self)
        return True

    def run(self, key, drop, adds, done: str):
        c, sp = self._char(key), self._set(key)
        self.busy(True)
        try:
            self.tools.change_set(c.proj, sp, drop, adds)
        except Exception as e:
            self.busy(False)
            messagebox.showerror("Nada foi alterado", str(e), parent=self)
            return False
        self.busy(False)
        self.msg.configure(text=done + f"   ({os.path.basename(sp)}, original nos backups)")
        for k in ("A", "B"):
            if self._set(k) == sp:
                self.fill(k)
        return True

    def copy(self, src, dst):
        names, ssp, dsp = self.picked(src), self._set(src), self._set(dst)
        if not names or not ssp or not dsp:
            return self.msg.configure(text="Selecione as animações de um lado e um set do outro.")
        if ssp == dsp:
            return self.msg.configure(text="Os dois lados estão no mesmo set; para duplicar dentro dele use Renomear.")
        have = set(self.side[dst]["names"])
        adds, drop = [], set()
        for n in names:
            new = n
            if n in have:
                new = simpledialog.askstring("Já existe no destino", f"'{n}' já existe em {os.path.basename(dsp)}.\n\n"
                                             "Deixe o mesmo nome para SUBSTITUIR, ou digite outro nome para entrar ao lado:",
                                             initialvalue=n, parent=self)
                if new is None:
                    continue
                new = new.strip().lower()
            if new != n and not self.valid_name(dst, new):
                continue
            if new in have:
                drop.add(new)
            adds.append((ssp, n, new))
        if adds:
            self.run(dst, drop, adds, f"{len(adds)} animação(ões) copiadas: " + ", ".join(f"{a}->{b}" if a != b else a for _, a, b in adds))

    def rename(self, key):
        names, sp = self.picked(key), self._set(key)
        if len(names) != 1:
            return self.msg.configure(text="Selecione uma animação para renomear.")
        new = simpledialog.askstring("Renomear animação", f"Novo nome para '{names[0]}':", initialvalue=names[0], parent=self)
        if not new or new.strip().lower() == names[0]:
            return
        new = new.strip().lower()
        if new in self.side[key]["names"]:
            return messagebox.showerror("Renomear", f"'{new}' já existe neste set.", parent=self)
        if self.valid_name(key, new):
            self.run(key, {names[0]}, [(sp, names[0], new)], f"{names[0]} renomeada para {new}")

    def delete(self, key):
        names = self.picked(key)
        if names and messagebox.askyesno("Remover", f"Remover {len(names)} animação(ões) deste set?\n\n" + ", ".join(names), parent=self):
            self.run(key, set(names), [], f"{len(names)} animação(ões) removidas")

    def extract(self, key):
        names, sp = self.picked(key) or self.side[key]["names"], self._set(key)
        if not sp:
            return
        out = filedialog.askdirectory(parent=self, title="Pasta para os .igb individuais")
        if not out:
            return
        out = os.path.join(out, os.path.splitext(os.path.basename(sp))[0])
        self.busy(True)
        try:
            done = self.tools.extract_to(sp, names, out)
        except Exception as e:
            self.busy(False)
            return messagebox.showerror("Extrair", str(e), parent=self)
        self.busy(False)
        self.msg.configure(text=f"{len(done)} animações extraídas para {out}")


# ================================================================ editor de npcstat
class NpcstatTab(ttk.Frame):
    """Lista e formulário do data/npcstat: editar, duplicar, criar NPC a partir de um herói, remover."""
    FIELDS = (("charactername", "Nome exibido", ""), ("skin", "Skin", "número do .igb em actors/"),
              ("characteranims", "Animações", "um set só; NPC não usa _4_combat"), ("powerstyle", "Powerstyle", "vazio = não luta"),
              ("sounddir", "Som", "normalmente fica no banco do mapa"), ("team", "Time", "enemy ou hero"),
              ("level", "Nível", ""), ("body", "Body", ""), ("mind", "Mind", ""), ("strength", "Strength", "dano dos golpes comuns"),
              ("specific_health", "Vida fixa", "número ou código tipo M_HLTH36"), ("npchealthscale", "Vida x", "2.3 = 230%"),
              ("npcdamagescale", "Dano x", "0.7 = 70%"), ("scale_factor", "Tamanho x", ""),
              ("combolevel", "Combo", "basic, veryeasy, easy, medium, hard, popup, popsmash"),
              ("dangerrating", "Danger rating", "50 = imune a morte instantânea"), ("spawnorbs", "Orbes", "quantos solta ao apanhar"),
              ("aiforceranged", "Luta de longe", "true = mantém distância e usa projéteis"))
    VILLAIN_TALENTS = (("might", "1"), ("monst_dmg_high", "3"), ("monst_dmg_low", "3"), ("monst_health", "3"),
                       ("fightstyle_villain", "1"), ("villain_resistances", "1"))

    def __init__(self, app):
        super().__init__(app.tabs)
        self.app, self.proj = app, app.proj
        self.path = self.proj.resolve("data/npcstat")
        self.dirty = False
        self.pending: list[tuple[str, xmlb.Node]] = []  # arquivos novos (powerstyle, pacotes) gravados junto no Salvar
        self.current: xmlb.Node | None = None
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill="x")
        self.filter = tk.StringVar()
        ttk.Label(top, text="Filtrar:").pack(side="left")
        ttk.Entry(top, textvariable=self.filter, width=22).pack(side="left", padx=6)
        self.fight_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="só os que lutam", variable=self.fight_only, command=self.fill).pack(side="left", padx=(0, 10))
        ttk.Button(top, text="Salvar npcstat", style="Accent.TButton", command=self.save).pack(side="right")
        for text, cmd in (("Novo NPC de herói...", self.new_from_hero), ("Duplicar...", self.duplicate),
                          ("Remover", self.remove), ("Abrir como texto", self.open_text)):
            ttk.Button(top, text=text, command=cmd).pack(side="left", padx=(0, 6))
        self.info = ttk.Label(self, style="Dim.TLabel", padding=(10, 0))
        self.info.pack(anchor="w")
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=8)
        lf = ttk.Frame(body)
        cols = ("nome", "interno", "skin", "ps", "nivel", "vida", "dano")
        self.tv = ttk.Treeview(lf, columns=cols, show="headings", selectmode="browse")
        for c, title, w in zip(cols, ("Nome", "Nome interno", "Skin", "Powerstyle", "Nível", "Vida", "Dano x"), (170, 170, 70, 150, 50, 90, 60)):
            self.tv.heading(c, text=title)
            self.tv.column(c, width=w, stretch=c in ("nome", "interno", "ps"))
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.show())
        body.add(lf, weight=3)
        rf = ttk.Frame(body, padding=(12, 0, 0, 0))
        self.title_lbl = ttk.Label(rf, font=("Segoe UI", 13, "bold"), text="Selecione um NPC")
        self.title_lbl.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.vars: dict[str, tk.StringVar] = {}
        for i, (key, label, hint) in enumerate(self.FIELDS, 1):
            ttk.Label(rf, text=label).grid(row=i, column=0, sticky="w")
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(rf, textvariable=v, width=24).grid(row=i, column=1, sticky="w", padx=8, pady=1)
            ttk.Label(rf, text=hint, style="Dim.TLabel").grid(row=i, column=2, sticky="w")
        r = len(self.FIELDS) + 1
        ttk.Label(rf, text="Talentos (um por linha: nome nível)").grid(row=r, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.tal = tk.Text(rf, bg=BG, fg=FG, insertbackground=FG, font=("Consolas", 10), height=7, width=44, borderwidth=0, highlightthickness=0, padx=6, pady=4)
        self.tal.grid(row=r + 1, column=0, columnspan=3, sticky="ew")
        ttk.Label(rf, text="Outros campos (um por linha: campo = valor)").grid(row=r + 2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.other = tk.Text(rf, bg=BG, fg=FG, insertbackground=FG, font=("Consolas", 10), height=6, width=44, borderwidth=0, highlightthickness=0, padx=6, pady=4)
        self.other.grid(row=r + 3, column=0, columnspan=3, sticky="ew")
        bf = ttk.Frame(rf)
        bf.grid(row=r + 4, column=0, columnspan=3, sticky="w", pady=10)
        ttk.Button(bf, text="Aplicar e salvar", style="Accent.TButton", command=self.apply_form).pack(side="left")
        ttk.Button(bf, text="Pôr talentos padrão de vilão", command=self.villain_talents).pack(side="left", padx=6)
        ttk.Button(bf, text="Converter poder de herói para este NPC...", command=self.convert).pack(side="left")
        self.note = ttk.Label(rf, style="Dim.TLabel", wraplength=470, justify="left")
        self.note.grid(row=r + 5, column=0, columnspan=3, sticky="w")
        body.add(rf, weight=2)
        self.filter.trace_add("write", lambda *a: self.fill())
        self.load()

    # ---- dados ----------------------------------------------------------------
    def load(self):
        self.root = self.proj.load(self.path).clone() if self.path else xmlb.Node("characters")
        self.dirty = False
        self.pending = []
        self.current = None
        self.fill()

    def npcs(self) -> list[xmlb.Node]:
        return [s for s in self.root.children if s.name == "stats" and s.get("name")]

    def node(self, name: str) -> xmlb.Node | None:
        return next((s for s in self.npcs() if s.get("name") == name), None)

    def fill(self, select: str | None = None):
        q = self.filter.get().lower().strip()
        self.tv.delete(*self.tv.get_children())
        seen = set()
        for s in sorted(self.npcs(), key=lambda s: (s.get("charactername", "").lower(), s.get("name").lower())):
            if self.fight_only.get() and not s.get("powerstyle"):
                continue
            if q and q not in s.get("name").lower() and q not in s.get("charactername", "").lower() and q not in s.get("powerstyle", "").lower():
                continue
            if s.get("name") in seen:
                continue
            seen.add(s.get("name"))
            self.tv.insert("", "end", iid=s.get("name"), values=(
                s.get("charactername", ""), s.get("name"), s.get("skin", ""), s.get("powerstyle", ""), s.get("level", ""),
                s.get("specific_health", "") or (("x" + s.get("npchealthscale")) if s.get("npchealthscale") else ""), s.get("npcdamagescale", "")))
        if select and self.tv.exists(select):
            self.tv.selection_set(select)
            self.tv.see(select)
        n = self.npcs()
        self.info.configure(text=f"{len(n)} NPCs ({sum(1 for s in n if s.get('powerstyle'))} com powerstyle) em {self.proj.rel(self.path or '')}"
                            + ("     ALTERAÇÕES NÃO SALVAS: clique em 'Salvar npcstat'" if self.dirty else ""))

    def show(self):
        sel = self.tv.selection()
        s = self.node(sel[0]) if sel else None
        self.current = s
        known = {k for k, _, _ in self.FIELDS}
        for k in known:
            self.vars[k].set(s.get(k, "") if s is not None else "")
        self.tal.delete("1.0", "end")
        self.other.delete("1.0", "end")
        if s is None:
            return self.title_lbl.configure(text="Selecione um NPC")
        self.title_lbl.configure(text=f"{s.get('charactername', '')}   ({s.get('name')})")
        self.tal.insert("1.0", "\n".join(f"{t.get('name', '')} {t.get('level', '1')}" for t in s.children if t.name == "talent"))
        self.other.insert("1.0", "\n".join(f"{k} = {v}" for k, v in s.attrs if k not in known and k != "name"))
        extra = [c.name for c in s.children if c.name != "talent"]
        ps = s.get("powerstyle")
        self.note.configure(text=(("Blocos mantidos como estão: " + ", ".join(extra) + ". ") if extra else "")
                            + ("" if not ps else "Powerstyle existe na pasta. " if self.proj.resolve(f"data/powerstyles/{ps}")
                               or any(os.path.basename(p).lower().startswith(ps.lower() + ".") for p, _ in self.pending)
                               else f"ATENÇÃO: data/powerstyles/{ps} não existe nesta pasta. "))

    def changed(self, select=None):
        """Cada alteração é gravada e compilada na hora (data/npcstat.engb + .txt, com backup)."""
        self.dirty = True
        self.fill(select)
        if self.save():
            self.fill(select)
            self.show()

    # ---- formulário --------------------------------------------------------------
    def apply_form(self, quiet: bool = False) -> bool:
        s = self.current
        if s is None:
            return False
        known = [k for k, _, _ in self.FIELDS]
        attrs = [["name", s.get("name")]]
        for k in known:
            v = self.vars[k].get().strip()
            if v:
                attrs.append([k, v])
        for ln, line in enumerate(self.other.get("1.0", "end").split("\n"), 1):
            line = line.strip().rstrip(";").strip()
            if not line:
                continue
            if "=" not in line:
                messagebox.showerror("Outros campos", f"Linha {ln}: use  campo = valor", parent=self)
                return False
            k, v = (x.strip() for x in line.split("=", 1))
            if not re.fullmatch(r"[A-Za-z0-9_]+", k) or k == "name" or k in known:
                messagebox.showerror("Outros campos", f"Linha {ln}: campo inválido ou repetido: {k}", parent=self)
                return False
            attrs.append([k, v])
        talents = []
        for ln, line in enumerate(self.tal.get("1.0", "end").split("\n"), 1):
            parts = line.replace("=", " ").split()
            if not parts:
                continue
            if len(parts) > 2 or (len(parts) == 2 and not parts[1].isdigit()):
                messagebox.showerror("Talentos", f"Linha {ln}: use  nome nível   (ex.: monst_dmg_high 3)", parent=self)
                return False
            talents.append(xmlb.Node("talent", [["level", parts[1] if len(parts) == 2 else "1"], ["name", parts[0]]]))
        s.attrs[:] = sorted(attrs, key=lambda a: a[0].lower())
        pos = next((i for i, c in enumerate(s.children) if c.name == "talent"), len(s.children))
        rest = [c for c in s.children if c.name != "talent"]
        s.children[:] = rest[:pos] + talents + rest[pos:]
        self.changed(s.get("name"))
        if not quiet:
            self.app.status(f"{s.get('name')} atualizado, salvo e compilado em {self.proj.rel(self.path)}")
        return True

    def villain_talents(self):
        if self.current is None:
            return
        have = {l.split()[0].lower() for l in self.tal.get("1.0", "end").split("\n") if l.split()}
        add = [f"{n} {lv}" for n, lv in self.VILLAIN_TALENTS if n not in have]
        if add:
            cur = self.tal.get("1.0", "end").strip()
            self.tal.delete("1.0", "end")
            self.tal.insert("1.0", (cur + "\n" if cur else "") + "\n".join(add))

    # ---- ações ---------------------------------------------------------------------
    def ask_name(self, title: str, initial: str) -> str | None:
        name = simpledialog.askstring(title, "Nome interno do NPC (único, sem espaços; não pode ser igual ao de um herói):",
                                      initialvalue=initial, parent=self)
        if not name:
            return None
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,31}", name):
            messagebox.showerror(title, "Use letras, números e _ (começando por letra).", parent=self)
            return None
        low = name.lower()
        if any(s.get("name").lower() == low for s in self.npcs()) or any(c.name.lower() == low for c in self.proj.characters):
            messagebox.showerror(title, f"Já existe um NPC ou herói chamado '{name}'.", parent=self)
            return None
        return name

    def duplicate(self, new_name: str | None = None):
        s = self.current
        if s is None:
            return self.app.status("Selecione o NPC a duplicar")
        name = new_name or self.ask_name("Duplicar NPC", s.get("name") + "_2")
        if not name:
            return
        c = s.clone()
        c.set("name", name)
        self.root.children.insert(self.root.children.index(s) + 1, c)
        self.changed(name)
        self.app.status(f"{name} criado como cópia de {s.get('name')} (mesma skin e mesmo powerstyle); ajuste e salve")

    def new_from_hero(self, hero: pj.Character | None = None, name: str | None = None):
        if hero is None:
            heroes = self.proj.characters
            d = tk.Toplevel(self)
            d.title("Novo NPC a partir de herói")
            d.configure(bg=PANEL)
            fit(d, 460, 480)
            d.transient(self.app)
            lb = tk.Listbox(d, bg=BG, fg=FG, selectbackground=SEL, font=("Segoe UI", 10), borderwidth=0, highlightthickness=0, activestyle="none")
            lb.pack(fill="both", expand=True, padx=12, pady=12)
            for c in heroes:
                lb.insert("end", f"{c.display}   ({c.name})")
            res = {}
            b = ttk.Frame(d, padding=12)
            b.pack(fill="x")
            ttk.Button(b, text="Cancelar", command=d.destroy).pack(side="right")
            ttk.Button(b, text="Escolher", style="Accent.TButton", command=lambda: (res.update(i=lb.curselection()), d.destroy())).pack(side="right", padx=8)
            lb.bind("<Double-1>", lambda e: (res.update(i=lb.curselection()), d.destroy()))
            d.grab_set()
            self.wait_window(d)
            if not res.get("i"):
                return
            hero = heroes[res["i"][0]]
        name = name or self.ask_name("Novo NPC", hero.name + "_npc")
        if not name or not hero.skins:
            return
        skin = hero.skins[0][0]
        ps = f"ps_{name.lower()}"
        st = xmlb.Node("stats", sorted([["name", name], ["charactername", hero.display], ["skin", skin], ["characteranims", hero.anims],
                                        ["powerstyle", ps], ["sounddir", hero.sounddir], ["team", "enemy"], ["level", "10"],
                                        ["body", "40"], ["mind", "40"], ["strength", "40"], ["specific_health", "800"],
                                        ["npchealthscale", "2"], ["npcdamagescale", "0.7"], ["combolevel", "basic"], ["dangerrating", "50"]],
                                       key=lambda a: a[0]))
        st.children = [xmlb.Node("talent", [["level", lv], ["name", n]]) for n, lv in self.VILLAIN_TALENTS]
        self.root.children.append(st)
        root = self.proj.root
        ps_path = os.path.join(root, "data", "powerstyles", ps + ".xmlb")
        files = []
        if not self.proj.resolve(f"data/powerstyles/{ps}"):
            files.append((ps_path, xmlb.Node("PowerStyle")))

        def pk(with_ps: bool) -> xmlb.Node:
            r = xmlb.Node("packagedef")
            r.children = [xmlb.Node("actorskin", [["filename", skin]]), xmlb.Node("actoranimdb", [["filename", hero.anims]]),
                          xmlb.Node("model", [["filename", f"HUD/hud_head_{skin}"]])]
            if with_ps:
                r.children.append(xmlb.Node("fightstyle", [["filename", f"data/powerstyles/{ps}"]]))
            return r

        for suffix, with_ps in (("", True), ("_nc", False)):
            p = os.path.join(root, "packages", "generated", "characters", f"{name.lower()}_{skin}{suffix}.pkgb")
            if not os.path.exists(p):
                files.append((p, pk(with_ps)))
        self.pending += files
        self.changed(name)
        self.app.status(f"NPC {name} criado a partir de {hero.display}. Ao salvar, também serão criados: "
                        + ", ".join(os.path.basename(p) for p, _ in files))

    def remove(self):
        s = self.current
        if s is None:
            return
        if messagebox.askyesno("Remover NPC", f"Tirar {s.get('name')} do npcstat?\n\nSe algum mapa ou missão usa esse NPC, o jogo pode travar ao carregá-lo.", parent=self):
            self.root.children.remove(s)
            self.current = None
            self.changed()
            self.show()

    def open_text(self):
        sel = self.tv.selection()
        self.app.open_file(self.path, r"^\s*name\s*=\s*" + re.escape(sel[0]) + r"\s*;" if sel else None)

    def convert(self):
        if self.dirty:
            if not messagebox.askyesno("Converter poder", "O npcstat tem alterações não salvas. Salvar agora e abrir o conversor?", parent=self) or not self.save():
                return
        d = self.app.npc_power()
        sel = self.tv.selection()
        if sel:
            i = next((i for i, n in enumerate(d.npcs) if n.name == sel[0]), -1)
            if i >= 0:
                d.dst_cb.current(i)
                d.dst_changed()
            else:
                show_plan(d.out, f"NÃO dá para converter para {sel[0]}: ele não tem powerstyle (ou o arquivo não existe).")

    def save(self) -> bool:
        if not self.path:
            return False
        if dirty_tabs(self.app, [self.path]):
            messagebox.showwarning("Salve antes", "O npcstat está aberto no editor de texto com alterações não salvas.", parent=self)
            return False
        names = [s.get("name").lower() for s in self.npcs()]
        dup = sorted({n for n in names if names.count(n) > 1})
        mine = {s.get("name").lower() for s in self.proj.load(self.path).children if s.get("name")}
        new_dup = [n for n in dup if n not in mine or names.count(n) > [x.get("name", "").lower() for x in self.proj.load(self.path).children].count(n)]
        if new_dup:
            messagebox.showerror("NPCStat", "Nomes internos repetidos: " + ", ".join(new_dup), parent=self)
            return False
        keep = self.tv.selection()
        for p, node in self.pending:
            if not os.path.exists(p):
                self.proj.save(p, node)
        self.proj.save(self.path, self.root)
        self.proj._npcs = None
        n_new = len(self.pending)
        reload_tabs(self.app, [self.path])
        self.load()
        if keep:
            self.fill(keep[0])
        self.app.status("npcstat salvo e compilado (com backup)" + (f"; {n_new} arquivo(s) novo(s) criados" if n_new else ""))
        return True


# ============================================================ poder de herói -> NPC
class NpcPowerDialog(tk.Toplevel):
    MOVES = ("power_attack", "power_smash", "power_boost", "power_xtreme")

    def __init__(self, app, src=None, talent=None):
        super().__init__(app)
        self.app = app
        self.title("Converter poder de herói para NPC")
        self.configure(bg=PANEL)
        fit(self, 1120, 860)
        self.transient(app)
        self.chars = app.all_characters()
        self.npcs = app.proj.npcs()
        self.info = self.plan = None
        self.powers = []
        self._done = ""
        f = ttk.Frame(self, padding=12)
        f.pack(fill="x")
        f.columnconfigure(1, weight=1)
        f.columnconfigure(3, weight=1)
        ttk.Label(f, text="Herói:").grid(row=0, column=0, sticky="w")
        self.src_cb = SearchCombo(f, values=[
            f"{c.display}   ({c.name})" + ("" if c.proj is app.proj else f"      [{c.proj.label}]") for c in self.chars])
        self.src_cb.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(f, text="NPC:").grid(row=0, column=2, sticky="w")
        self.dst_cb = SearchCombo(f, values=[f"{c.display}   ({c.name})   {c.powerstyle}" for c in self.npcs])
        self.dst_cb.grid(row=0, column=3, sticky="ew", padx=8)
        ttk.Label(f, text="Poder:").grid(row=1, column=0, sticky="w", pady=8)
        self.pow_cb = ttk.Combobox(f, state="readonly")
        self.pow_cb.grid(row=1, column=1, sticky="ew", padx=8)
        self.npc_info = ttk.Label(f, style="Dim.TLabel", wraplength=480, justify="left")
        self.npc_info.grid(row=1, column=2, columnspan=2, sticky="w", padx=8)
        self.desc = ttk.Label(f, style="Dim.TLabel", wraplength=1080, justify="left")
        self.desc.grid(row=2, column=0, columnspan=4, sticky="w")
        o = ttk.Frame(f)
        o.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.move_var = tk.StringVar(value="power_attack")
        self.dmg_var = tk.StringVar(value="high")
        self.level_var = tk.StringVar(value="8")
        self.reuse_var = tk.StringVar(value="6")
        self.replace_var = tk.BooleanVar(value=True)
        self.anim_var = tk.BooleanVar(value=app.anim_tools.available)
        self.snd_var = tk.BooleanVar(value=True)
        ttk.Label(o, text="Entra no NPC como").grid(row=0, column=0, sticky="w")
        self.move_cb = ttk.Combobox(o, textvariable=self.move_var, values=self.MOVES, width=18)
        self.move_cb.grid(row=0, column=1, padx=6)
        ttk.Checkbutton(o, text="substituir o move de mesmo nome do NPC", variable=self.replace_var, command=self.preview).grid(row=0, column=2, columnspan=3, sticky="w")
        ttk.Label(o, text="Dano").grid(row=1, column=0, sticky="w", pady=6)
        df = ttk.Frame(o)
        df.grid(row=1, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(df, text="alto (%mdmg_high)", value="high", variable=self.dmg_var, command=self.preview).pack(side="left", padx=6)
        ttk.Radiobutton(df, text="baixo (%mdmg_low)", value="low", variable=self.dmg_var, command=self.preview).pack(side="left")
        ttk.Label(o, text="Recarga da IA (aireusetime, s)").grid(row=1, column=3, sticky="e", padx=(20, 0))
        ttk.Entry(o, textvariable=self.reuse_var, width=6).grid(row=1, column=4, padx=6)
        ttk.Label(o, text="Outros valores (duração, alcance...) no nível").grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Combobox(o, textvariable=self.level_var, values=[str(i) for i in range(1, 16)], width=4, state="readonly").grid(row=2, column=2, sticky="w")
        ttk.Label(o, text="do talento do herói", style="Dim.TLabel").grid(row=2, column=3, sticky="w")
        ttk.Checkbutton(o, text="Importar as animações para o set do NPC", variable=self.anim_var, command=self.preview).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Checkbutton(o, text="Copiar os sons para o banco do NPC (se ele tiver banco próprio)", variable=self.snd_var,
                        command=self.preview).grid(row=3, column=3, columnspan=3, sticky="w", pady=(6, 0))
        self.out = _text(self)
        self.out.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        b = ttk.Frame(self, padding=12)
        b.pack(fill="x", side="bottom", before=self.out)
        ttk.Button(b, text="Atualizar prévia", command=self.preview).pack(side="left")
        ttk.Button(b, text="Fechar", command=self.destroy).pack(side="right")
        self.apply_btn = ttk.Button(b, text="Converter e compilar", style="Accent.TButton", command=self.apply)
        self.apply_btn.pack(side="right", padx=8)
        self._job = None
        self.src_cb.bind("<<ComboboxSelected>>", lambda e: self.src_changed())
        self.pow_cb.bind("<<ComboboxSelected>>", lambda e: self.power_changed())
        self.dst_cb.bind("<<ComboboxSelected>>", lambda e: self.dst_changed())
        self.move_cb.bind("<<ComboboxSelected>>", lambda e: self.preview())
        for v in (self.move_var, self.reuse_var, self.level_var):
            v.trace_add("write", lambda *a: self._schedule())
        if not self.npcs:
            show_plan(self.out, "NÃO achei NPCs com powerstyle em data/npcstat desta pasta.")
        if char_index(self.chars, src) >= 0:
            self.src_cb.current(char_index(self.chars, src))
            self.src_changed(talent)
        else:
            self.preview()

    def _schedule(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(400, self.preview)

    def src_changed(self, talent=None):
        c = self.chars[self.src_cb.current()]
        self.powers = c.powers()
        self.pow_cb.configure(values=[f"{dn or tn}   [{tn} / {mv}]" for tn, dn, mv in self.powers])
        self.pow_cb.set("")
        if self.powers:
            self.pow_cb.current(next((i for i, p in enumerate(self.powers) if talent and p[0].lower() == talent.lower()), 0))
        self.power_changed()

    def power_changed(self):
        self.info = None
        i = self.pow_cb.current()
        if self.src_cb.current() >= 0 and i >= 0:
            c = self.chars[self.src_cb.current()]
            try:
                self.info = transfer.PowerInfo(c.proj, c, self.powers[i][0])
                t = self.info.talent
                self.desc.configure(text=f"{t.get('descname', '')}  [{t.get('descshort', '-')}]   {t.get('description', '')}"
                                    f"      moves: {', '.join(n for n, own in self.info.move_names() if own)}")
            except Exception as e:
                self.desc.configure(text=str(e))
        self.preview()

    def dst_changed(self):
        i = self.dst_cb.current()
        if i >= 0:
            n = self.npcs[i]
            moves, tal = [], [f"{t.get('name')} {t.get('level', '')}" for t in n.stats.children if t.name == "talent"]
            if n.powerstyle_path:
                try:
                    moves = [m.get("name") for m in n.proj.load(n.powerstyle_path).children if m.name == "FightMove" and m.get("name")]
                except Exception:
                    pass
            self.move_cb.configure(values=list(dict.fromkeys(list(self.MOVES) + [m for m in moves if m.lower().startswith("power")])))
            self.npc_info.configure(text=("moves atuais: " + ", ".join(moves[:14]) if moves else "powerstyle não encontrado nesta pasta")
                                    + "\ntalentos: " + ", ".join(tal) + f"   |   dano x{n.stats.get('npcdamagescale', '1')}   som: {n.sounddir or '-'}")
        self.preview()

    def preview(self):
        self._job = None
        self.plan = None
        self.apply_btn.state(["disabled"])
        if self.info is None or self.dst_cb.current() < 0:
            return show_plan(self.out, "Escolha o herói, o poder e o NPC que vai receber.")
        dst = self.npcs[self.dst_cb.current()]
        if not dst.powerstyle_path:
            return show_plan(self.out, f"NÃO achei o powerstyle {dst.powerstyle} do NPC em data/powerstyles.")
        try:
            reuse = self.reuse_var.get().strip()
            if reuse and not re.fullmatch(r"\d+(\.\d+)?", reuse):
                return show_plan(self.out, "NÃO é um número: recarga da IA.")
            self.configure(cursor="watch")
            self.update_idletasks()
            self.plan = transfer.build_plan(dst.proj, self.info, dst, "", "", None, True, independent=True,
                                            anim_tools=self.app.anim_tools if self.anim_var.get() else None,
                                            replace_moves=self.replace_var.get(), copy_sounds=self.snd_var.get(),
                                            npc={"move": self.move_var.get(), "damage": self.dmg_var.get(), "level": self.level_var.get(),
                                                 "aireusetime": reuse, "stats": dst.stats})
        except Exception as e:
            return show_plan(self.out, f"NÃO foi possível montar o plano: {e}")
        finally:
            self.configure(cursor="")
        done, self._done = self._done, ""
        show_plan(self.out, (done + "\n\nPRÓXIMA CONVERSÃO (com a seleção atual):\n\n" if done else "") + self.plan.describe(dst.proj))
        if not self.plan.errors:
            self.apply_btn.state(["!disabled"])

    def apply(self):
        if not self.plan or self.plan.errors:
            return
        bad = dirty_tabs(self.app, [c.path for c in self.plan.changes])
        if bad:
            return messagebox.showwarning("Salve antes", "Arquivos abertos com alterações não salvas:\n\n"
                                          + "\n".join(os.path.basename(t.path) for t in bad), parent=self)
        if not messagebox.askyesno("Converter", f"Gravar e compilar {len(self.plan.changes)} arquivo(s)?\nOs originais ficam nos backups.", parent=self):
            return
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            written = transfer.apply_plan(self.plan.proj, self.plan)
        except Exception as e:
            self.configure(cursor="")
            return messagebox.showerror("Nada foi alterado" if isinstance(e, anims.AnimError) else "Erro", str(e), parent=self)
        self.configure(cursor="")
        reload_tabs(self.app, written)
        dst = self.npcs[self.dst_cb.current()]
        self.app.status(f"Poder convertido para o NPC {dst.display}: {len(written)} arquivo(s) gravados")
        self._done = f"FEITO: {self.info.talent_name} -> NPC {dst.display} como {self.move_var.get()}   ({len(written)} arquivo(s), originais nos backups)"
        self.dst_changed()
        self.lift()


# ============================================================ organizar poderes
class OrganizeDialog(tk.Toplevel):
    """Escolhe a ordem dos poderes/boosts/xtreme e aplica a tabela padrão de requisitos e tiers."""

    def __init__(self, app, char: pj.Character):
        super().__init__(app)
        self.app, self.char = app, char
        self.title(f"Organizar poderes de {char.display}")
        self.configure(bg=PANEL)
        fit(self, 1080, 760)
        self.transient(app)
        self.rows = [[n, d, k, lv] for n, d, k, lv in ops.power_talents(char)]  # [talento, nome, tipo, nível atual]
        self.plan = None
        ttk.Label(self, style="Dim.TLabel", wraplength=1040, justify="left", padding=(12, 10, 12, 0), text=(
            "A ordem da lista define o número de cada poder (1º Poder, 2º Poder... 1º Boost...). Use Subir/Descer e, se preciso, troque o tipo. "
            "Ao aplicar, o requisito de nível (%..._req) e os tiers de cada talento são reescritos pela tabela padrão dos mods.")).pack(anchor="w")
        b = ttk.Frame(self, padding=12)
        b.pack(fill="x", side="bottom")
        mid = ttk.Panedwindow(self, orient="horizontal")
        mid.pack(fill="both", expand=True, padx=12, pady=8)
        lf = ttk.Frame(mid)
        cols = ("slot", "nome", "talento", "antes", "depois")
        self.tv = ttk.Treeview(lf, columns=cols, show="headings", selectmode="browse", height=12)
        for c, title, w in zip(cols, ("Fica como", "Poder", "Talento", "Nível hoje", "Nível novo"), (90, 190, 130, 70, 70)):
            self.tv.heading(c, text=title)
            self.tv.column(c, width=w, stretch=c == "nome")
        self.tv.pack(fill="both", expand=True)
        bf = ttk.Frame(lf)
        bf.pack(fill="x", pady=6)
        ttk.Button(bf, text="Subir", command=lambda: self.move(-1)).pack(side="left")
        ttk.Button(bf, text="Descer", command=lambda: self.move(1)).pack(side="left", padx=6)
        for kind in ("power", "boost", "xtreme"):
            ttk.Button(bf, text=f"É {ops.KIND_LABEL[kind]}", command=lambda k=kind: self.set_kind(k)).pack(side="left", padx=(0, 6))
        self.rescale = tk.BooleanVar(value=True)
        self.reorder = tk.BooleanVar(value=True)
        ttk.Checkbutton(lf, text="Reescalar dano/custo quando o número de níveis do poder mudar", variable=self.rescale, command=self.preview).pack(anchor="w")
        ttk.Checkbutton(lf, text="Reordenar os talentos no arquivo nessa ordem", variable=self.reorder, command=self.preview).pack(anchor="w")
        mid.add(lf, weight=2)
        self.out = _text(mid)
        mid.add(self.out, weight=3)
        ttk.Button(b, text="Fechar", command=self.destroy).pack(side="right")
        self.apply_btn = ttk.Button(b, text="Aplicar e compilar", style="Accent.TButton", command=self.apply)
        self.apply_btn.pack(side="right", padx=8)
        self.fill()

    def order(self):
        return [(r[0], r[2]) for r in self.rows]

    def fill(self, select: int | None = None):
        self.tv.delete(*self.tv.get_children())
        try:
            _, slots = ops.slot_tables(self.order())
        except ValueError:
            slots = {}
        for i, (name, desc, kind, lv) in enumerate(self.rows):
            s = slots.get(name.lower())
            self.tv.insert("", "end", iid=str(i), values=(s[2] if s else ops.KIND_LABEL[kind] + " ?", desc or name, name, lv, s[0][0][1] if s else "-"))
        if select is not None and self.rows:
            self.tv.selection_set(str(max(0, min(select, len(self.rows) - 1))))
        self.preview()

    def sel(self) -> int | None:
        s = self.tv.selection()
        return int(s[0]) if s else None

    def move(self, d: int):
        i = self.sel()
        if i is None or not 0 <= i + d < len(self.rows):
            return
        self.rows[i], self.rows[i + d] = self.rows[i + d], self.rows[i]
        self.fill(i + d)

    def set_kind(self, kind: str):
        i = self.sel()
        if i is not None:
            self.rows[i][2] = kind
            self.fill(i)

    def preview(self):
        self.plan = None
        self.apply_btn.state(["disabled"])
        if not self.rows:
            return show_plan(self.out, "Este personagem não tem talentos com poder.")
        try:
            self.plan = ops.organize_plan(self.char, self.order(), self.rescale.get(), self.reorder.get())
        except Exception as e:
            return show_plan(self.out, f"NÃO foi possível montar o plano: {e}")
        show_plan(self.out, self.plan.describe(self.char.proj))
        if not self.plan.errors:
            self.apply_btn.state(["!disabled"])

    def apply(self):
        if not self.plan or self.plan.errors:
            return
        if dirty_tabs(self.app, [self.char.talents_path]):
            return messagebox.showwarning("Salve antes", "O arquivo de talentos está aberto com alterações não salvas.", parent=self)
        if not messagebox.askyesno("Organizar poderes", "Reescrever requisitos e tiers no arquivo de talentos?\nO original fica nos backups.", parent=self):
            return
        written = transfer.apply_plan(self.char.proj, self.plan)
        self.char.proj._vars = None
        reload_tabs(self.app, written)
        self.app.fill_characters()
        self.app.status(f"Poderes de {self.char.display} organizados: requisitos e tiers reescritos (com backup)")
        self.rows = [[n, d, k, lv] for (n, d, _k, lv), (_, _, k, _) in zip(ops.power_talents(self.char), self.rows)]
        self.fill()
        show_plan(self.out, "FEITO: requisitos e tiers gravados em " + self.char.proj.rel(self.char.talents_path) + "\n\n" + self.out.get("1.0", "end"))


# ================================================================ clonar personagem
class CloneDialog(tk.Toplevel):
    def __init__(self, app, src=None):
        super().__init__(app)
        self.app = app
        self.title("Clonar personagem / criar novo mod")
        self.configure(bg=PANEL)
        fit(self, 1040, 780)
        self.transient(app)
        self.chars = app.all_characters()
        self.plan = None
        f = ttk.Frame(self, padding=12)
        f.pack(fill="x")
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text="Clonar de:").grid(row=0, column=0, sticky="w")
        self.src_cb = SearchCombo(f, values=[
            f"{c.display}   ({c.name})" + ("" if c.proj is app.proj else f"      [{c.proj.label}]") for c in self.chars])
        self.src_cb.grid(row=0, column=1, columnspan=3, sticky="ew", padx=8, pady=3)
        self.vars = {}
        rows = (("display", "Nome exibido:", "Como aparece no jogo (ex.: Sinestro)"),
                ("name", "Nome interno:", "Vira data/talents/<nome>, ps_<nome>, ents_<nome>, effects/char/<nome>, pacotes <nome>_<skin>"),
                ("prefix", "Prefixo dos talentos:", "O que identifica os poderes: <prefixo>_p1, <prefixo>_p1_dmg..."),
                ("num", "Número do personagem:", "Começo do número das skins e do set de animações"),
                ("bank", "Banco de som:", "No máximo 6 caracteres; o arquivo fica <banco>_m.zsm e <banco>_v.zss"))
        for i, (key, label, hint) in enumerate(rows, 1):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w")
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(f, textvariable=v, width=26).grid(row=i, column=1, sticky="w", padx=8, pady=3)
            ttk.Label(f, text=hint, style="Dim.TLabel").grid(row=i, column=2, sticky="w")
            v.trace_add("write", lambda *a: self._schedule())
        self.share_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Não criar banco de som: o clone usa o banco do personagem original (todas as falas e sons continuam tocando)",
                        variable=self.share_var, command=self.preview).grid(row=len(rows) + 3, column=0, columnspan=4, sticky="w")
        self.over_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Permitir sobrescrever arquivos que já existem (pede confirmação antes de gravar)",
                        variable=self.over_var, command=self.preview).grid(row=len(rows) + 1, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.used = ttk.Label(f, style="Dim.TLabel", wraplength=1000, justify="left")
        self.used.grid(row=len(rows) + 2, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.out = _text(self)
        self.out.pack(fill="both", expand=True, padx=12)
        b = ttk.Frame(self, padding=12)
        b.pack(fill="x", side="bottom", before=self.out)
        ttk.Button(b, text="Fechar", command=self.destroy).pack(side="right")
        self.apply_btn = ttk.Button(b, text="Criar personagem", style="Accent.TButton", command=self.apply)
        self.apply_btn.pack(side="right", padx=8)
        self._job = None
        self._loading = False
        self.src_cb.bind("<<ComboboxSelected>>", lambda e: self.src_changed())
        nums = sorted(ops.used_numbers(app.proj), key=lambda x: (len(x), x))
        self.used.configure(text="Números já usados no herostat: " + ", ".join(nums))
        if char_index(self.chars, src) >= 0:
            self.src_cb.current(char_index(self.chars, src))
            self.src_changed()
        else:
            self.preview()

    def src_changed(self):
        c = self.chars[self.src_cb.current()]
        s = ops.suggest_clone(c)
        self._loading = True
        self.vars["display"].set(c.display + " 2")
        self.vars["name"].set(s["name"] + "2")
        self.vars["prefix"].set(s["prefix"] + "2")
        used = set(ops.used_numbers(self.app.proj))
        n = 100
        while str(n) in used:
            n += 1
        self.vars["num"].set(str(n))
        self.vars["bank"].set((s["bank"][:5] or s["name"][:5]) + "2")
        self._loading = False
        self.preview()

    def _schedule(self):
        if self._loading:
            return
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(350, self.preview)

    def preview(self):
        self._job = None
        self.plan = None
        self.apply_btn.state(["disabled"])
        if self.src_cb.current() < 0:
            return show_plan(self.out, "Escolha o personagem que servirá de base.")
        v = {k: x.get() for k, x in self.vars.items()}
        try:
            self.plan = ops.clone_plan(self.chars[self.src_cb.current()], self.app.proj, v["name"], v["display"], v["prefix"],
                                       v["num"], v["bank"], self.app.created.store_dir, overwrite=self.over_var.get(),
                                       share_bank=self.share_var.get())
        except Exception as e:
            return show_plan(self.out, f"NÃO foi possível montar o plano: {e}")
        show_plan(self.out, self.plan.describe())
        if not self.plan.errors:
            self.apply_btn.state(["!disabled"])

    def apply(self):
        if not self.plan or self.plan.errors:
            return
        if self.plan.clash:
            bad = dirty_tabs(self.app, [os.path.join(self.plan.proj.root, *c.split("/")) for c in self.plan.clash])
            if bad:
                return messagebox.showwarning("Salve antes", "Arquivos que seriam sobrescritos estão abertos com alterações não salvas:\n\n"
                                              + "\n".join(os.path.basename(t.path) for t in bad), parent=self)
            shown = "\n".join(self.plan.clash[:14]) + (f"\n... e mais {len(self.plan.clash) - 14}" if len(self.plan.clash) > 14 else "")
            extra = [w for w in self.plan.warnings if "já existe" in w or "já é" in w]
            if not messagebox.askyesno("Confirmar sobrescrita", f"{len(self.plan.clash)} arquivo(s) que já existem serão SOBRESCRITOS:\n\n{shown}\n\n"
                                       + ("\n".join(extra) + "\n\n" if extra else "")
                                       + "Os arquivos atuais vão para a pasta de backups.\n\nConfirmar isso?", icon="warning", default="no", parent=self):
                return
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            written = ops.clone_apply(self.plan, self.app.anim_tools)
            reload_tabs(self.app, written)
        except Exception as e:
            self.configure(cursor="")
            return messagebox.showerror("Clonar", str(e), parent=self)
        self.configure(cursor="")
        name = self.plan.stats.get("name")
        self.app.created.reload_characters()
        self.app._after_projects_changed("created")
        self.app.status(f"Personagem criado: {name}  ({len(written)} arquivos novos). Está na aba Criados; use 'Editar Herostat' para pôr no jogo.")
        show_plan(self.out, f"CRIADO: {name}   ({len(written)} arquivos novos)\n\n" + self.plan.describe()
                  + "\n\nPRÓXIMO PASSO:\n  Abra 'Editar Herostat/NPCStat > Herostat' e use 'Adicionar personagem' ou 'Substituir por' para colocá-lo no jogo.")
        self.plan = None
        self.apply_btn.state(["disabled"])
