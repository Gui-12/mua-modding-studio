"""MUA Studio - IDE para os arquivos de personagem do Marvel Ultimate Alliance.
Abre os binários (.engb/.xmlb/.pkgb) direto, valida, compila ao salvar e copia poderes."""
from __future__ import annotations

import colorsys
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, colorchooser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n  # noqa: E402
i18n.install()  # idioma escolhido (pt-BR é o oficial); precisa vir antes de qualquer widget
import xmlb  # noqa: E402
import project as pj  # noqa: E402
import transfer  # noqa: E402
import anims  # noqa: E402
import ops  # noqa: E402
import extras  # noqa: E402
import audio_ui  # noqa: E402

import theme as th  # noqa: E402
from theme import BG, PANEL, FG, DIM, ACCENT, SEL, LINE, SURFACE  # noqa: E402

FONT = ("Consolas", 11)  # trocadas por theme.CODE / theme.UI em setup_style
UI = ("Segoe UI", 10)

LINE_BLOCK = re.compile(r"^(\s*)(XMLB\s+)?(\S+)\s*\{\s*$")
LINE_KV = re.compile(r"^(\s*)([^=\s]+)(\s*=\s*)(.*?)(\s*;?\s*)$")


def setup_style(root: tk.Tk):
    """Todo o visual mora em theme.py; aqui só se pegam as fontes escolhidas."""
    global FONT, UI
    th.setup(root)
    FONT, UI = th.CODE, th.UI


# ============================================================== aba do editor
class EditorTab(ttk.Frame):
    def __init__(self, app: "App", path: str):
        super().__init__(app.tabs)
        self.app = app
        self.proj = app.project_for_path(path)
        self.compilable = pj.is_editable(path)
        self.bin_path = pj.binary_of(path) if self.compilable else None
        self.path = self.bin_path or path
        self.char = self.proj.character_for_path(self.path) if self.compilable else None
        self.problems: list[tuple[int, str, str]] = []
        self.colors: dict[int, str] = {}
        self.tree: xmlb.Node | None = None
        self._job = None
        self._alt_text: str | None = None

        self.banner = th.Banner(self)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        self.gutter = tk.Canvas(body, width=66, bg=BG, highlightthickness=0)
        self.gutter.pack(side="left", fill="y")
        tk.Frame(body, width=1, bg=th.mix(BG, LINE, .6)).pack(side="left", fill="y")
        self.text = tk.Text(body, wrap="none", undo=True, maxundo=-1, bg=BG, fg=FG, insertbackground=FG,
                            selectbackground=SEL, selectforeground=th.SEL_FG, font=FONT, borderwidth=0,
                            highlightthickness=0, padx=12, pady=8, tabs=("3c",), inactiveselectbackground=SEL,
                            spacing1=1, spacing3=1, insertwidth=2)
        vs = ttk.Scrollbar(body, orient="vertical", command=self._yview)
        hs = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=lambda a, b: (vs.set(a, b), self.draw_gutter()), xscrollcommand=hs.set)
        vs.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        hs.pack(fill="x")

        # localizar flutuante, no canto superior direito do editor
        self.find_var = tk.StringVar()
        self.replace_var = tk.StringVar()
        self.case_var = tk.BooleanVar(value=True)  # a busca diferencia maiúsculas (string exata)
        self.find_bar = th.FindBar(body, self.find_var, on_next=self.find_next,
                                   on_prev=lambda: self.find_next(back=True), on_close=self.hide_find,
                                   replace_var=self.replace_var, on_replace=self.replace_next,
                                   on_replace_all=self.replace_all, case_var=self.case_var)
        re_ = self.find_bar.replace_entry
        re_.bind("<Return>", lambda e: (self.replace_next(), "break")[1])
        re_.bind("<Control-Return>", lambda e: (self.replace_all(), "break")[1])
        re_.bind("<Escape>", lambda e: self.hide_find())
        fe = self.find_bar.entry
        fe.bind("<Return>", lambda e: self.find_next())
        fe.bind("<Shift-Return>", lambda e: self.find_next(back=True))
        fe.bind("<F3>", lambda e: (self.find_next(), "break")[1])
        fe.bind("<Escape>", lambda e: self.hide_find())
        self.find_entry = fe
        self.find_info = self.find_bar.info

        t = self.text
        t.tag_configure("block", foreground=th.SYN_BLOCK, font=FONT + ("bold",))
        t.tag_configure("key", foreground=th.SYN_KEY)
        t.tag_configure("var", foreground=th.SYN_VAR)
        t.tag_configure("num", foreground=th.SYN_NUM)
        t.tag_configure("path", foreground=th.SYN_PATH)
        t.tag_configure("punct", foreground=th.SYN_PUNCT)
        t.tag_configure("comment", foreground=th.SYN_COMMENT)
        t.tag_configure("err", underline=True, underlinefg=th.ERR, background=th.ERR_BG)
        t.tag_configure("warn", underline=True, underlinefg=th.WARN, background=th.WARN_BG)
        t.tag_configure("found", background=th.FOUND_BG)
        t.tag_configure("curline", background=th.CURLINE)
        t.tag_lower("curline")
        t.bind("<<Modified>>", self._on_modified)
        t.bind("<KeyRelease>", lambda e: self._cursor_moved())
        t.bind("<ButtonRelease-1>", lambda e: self._cursor_moved())
        t.bind("<Control-Button-1>", self._ctrl_click)
        t.bind("<Configure>", lambda e: self.draw_gutter())
        t.bind("<Tab>", self._tab)
        t.bind("<Button-3>", self._context_menu)
        t.bind("<Control-Button-3>", self._toggle_block)
        t.tag_configure("blocksel", background=th.BLOCKSEL_BG)
        t.tag_lower("blocksel")
        self.sel_blocks: set[int] = set()  # linha inicial de cada bloco marcado com Ctrl+botão direito
        t.bind("<F3>", lambda e: (self.find_next(), "break")[1])
        t.bind("<Shift-F3>", lambda e: (self.find_next(back=True), "break")[1])
        t.bind("<Return>", self._newline)
        # o campo de texto do Tk já usa Ctrl+K/O/T/F/W para outras coisas: os atalhos da IDE têm prioridade
        for seq, fn in (("<Control-s>", app.save_current), ("<Control-S>", app.save_all), ("<Control-o>", app.open_dialog),
                        ("<Control-t>", app.copy_power), ("<Control-k>", self.edit_color), ("<Control-K>", app.colors_dialog),
                        ("<Control-f>", self.show_find), ("<Control-h>", lambda: self.show_find(replace=True)),
                        ("<F12>", self.goto_definition), ("<F1>", self.explain),
                        ("<Control-w>", lambda: self.after_idle(lambda: app.close_tab(self))),
                        ("<Control-F4>", lambda: self.after_idle(lambda: app.close_tab(self)))):
            t.bind(seq, lambda e, f=fn: (f(), "break")[1])
        self.gutter.bind("<Button-1>", self._gutter_click)
        self.load()

    # ---- carga --------------------------------------------------------------
    def _yview(self, *a):
        self.text.yview(*a)
        self.draw_gutter()

    def set_banner(self, msg: str | None, alt: bool = False):
        if not msg:
            self.banner.pack_forget()
            return
        kind = "ok" if msg.startswith("Mostrando o .txt") else "info" if msg.startswith("Arquivo de texto solto") else "warn"
        self.banner.show_msg(msg, kind, ("Carregar o .txt", self.load_alt) if alt else None)
        self.banner.pack(fill="x", before=self.winfo_children()[1])

    def load(self):
        text, banner, alt = "", None, False
        self._alt_text = None
        if not self.compilable:
            text = xmlb.read_text_file(self.path)
            banner = "Arquivo de texto solto (anotação): é salvo como esta, sem compilar."
        else:
            txt_path = self.bin_path + ".txt"
            tree = bin_err = None
            if os.path.isfile(self.bin_path):
                try:
                    tree = xmlb.load_file(self.bin_path)
                except Exception as e:
                    bin_err = str(e)
            txt = xmlb.read_text_file(txt_path) if os.path.isfile(txt_path) else None
            if tree is not None:
                text = xmlb.format_text(tree)
                if txt is not None:
                    troot, terrs = xmlb.parse_text(txt)
                    if not terrs and troot is not None and troot.same_as(tree):
                        text = txt  # mesmo conteúdo: mantem a formatação do seu .txt
                    else:
                        newer = os.path.getmtime(txt_path) > os.path.getmtime(self.bin_path) + 2
                        banner = ("Mostrando o BINÁRIO (é o que o jogo carrega). O .txt ao lado tem conteúdo diferente"
                                  + (" e é MAIS NOVO" if newer else " e é mais antigo")
                                  + (f" e tem {len(terrs)} erro(s) de sintaxe." if terrs else "."))
                        alt, self._alt_text = True, txt
            elif txt is not None:
                text = txt
                banner = ("O binário não pode ser lido (" + bin_err + "). " if bin_err else "Ainda não existe binario. ") \
                    + "Mostrando o .txt; salvar vai compilar."
            else:
                banner = f"Arquivo ilegível: {bin_err}"
        self.set_text(text)
        self.set_banner(banner, alt)

    def load_alt(self):
        if self._alt_text is not None:
            self.text.replace("1.0", "end-1c", self._alt_text.replace("\r\n", "\n"))
            self.set_banner("Mostrando o .txt. Salvar (Ctrl+S) compila este conteúdo por cima do binário; há backup.")

    def set_text(self, text: str):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text.replace("\r\n", "\n").rstrip("\n") + "\n")
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.mark_set("insert", "1.0")
        self.refresh()
        self.app.update_tab_title(self)

    def get_text(self) -> str:
        return self.text.get("1.0", "end-1c")

    @property
    def modified(self) -> bool:
        return bool(self.text.edit_modified())

    # ---- edicao -----------------------------------------------------------------
    def _on_modified(self, _e=None):
        if self.modified and getattr(self, "sel_blocks", None):
            self.sel_blocks.clear()
            self.text.tag_remove("blocksel", "1.0", "end")
        self.app.update_tab_title(self)
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(280, self.refresh)

    def _tab(self, _e):
        self.text.insert("insert", "   ")
        return "break"

    def _newline(self, _e):
        line = self.text.get("insert linestart", "insert")
        ind = re.match(r"\s*", line).group(0)
        if line.rstrip().endswith("{"):
            ind += "   "
        self.text.insert("insert", "\n" + ind)
        self.text.see("insert")
        return "break"

    def _cursor_moved(self):
        self.text.tag_remove("curline", "1.0", "end")
        self.text.tag_add("curline", "insert linestart", "insert lineend+1c")
        ln, col = self.text.index("insert").split(".")
        self.app.set_cursor_status(int(ln), int(col) + 1)
        self.draw_gutter()

    def refresh(self):
        self._job = None
        text = self.get_text()
        self.highlight(text)
        if self.compilable:
            root, errs = xmlb.parse_text(text)
            self.tree = root
            known = common = None
            if root is not None and root.name.lower() == "powerstyle":
                known, common = self.proj.all_vars(), self.proj.common_moves()
            self.problems = pj.lint(self.proj, root, errs, self.char, known, common)
        else:
            self.tree, self.problems = None, []
        t = self.text
        t.tag_remove("err", "1.0", "end")
        t.tag_remove("warn", "1.0", "end")
        for ln, kind, _ in self.problems:
            t.tag_add("err" if kind == "erro" else "warn", f"{ln}.0", f"{ln}.end")
        self.draw_gutter()
        if self.app.current() is self:
            self.app.show_tab_info(self)

    def highlight(self, text: str):
        t = self.text
        for tag in ("block", "key", "var", "num", "path", "punct", "comment"):
            t.tag_remove(tag, "1.0", "end")
        self.colors = {}
        add = t.tag_add
        for i, line in enumerate(text.split("\n"), 1):
            if not line.strip():
                continue
            s = line.strip()
            if s.startswith("//"):
                add("comment", f"{i}.0", f"{i}.end")
                continue
            if s == "}":
                add("punct", f"{i}.0", f"{i}.end")
                continue
            m = LINE_BLOCK.match(line)
            if m and "=" not in line:
                add("block", f"{i}.{m.start(3)}", f"{i}.{m.end(3)}")
                add("punct", f"{i}.{m.end(3)}", f"{i}.end")
                continue
            m = LINE_KV.match(line)
            if m:
                add("key", f"{i}.{m.start(2)}", f"{i}.{m.end(2)}")
                add("punct", f"{i}.{m.start(3)}", f"{i}.{m.end(3)}")
                add("punct", f"{i}.{m.start(5)}", f"{i}.end")
                v = m.group(4)
                vs = m.start(4)
                if "%" in v:
                    for vm in re.finditer(r"%\w+", v):
                        add("var", f"{i}.{vs + vm.start()}", f"{i}.{vs + vm.end()}")
                elif re.fullmatch(r"[-+0-9. ]+", v or "x"):
                    add("num", f"{i}.{vs}", f"{i}.{m.end(4)}")
                    if pj.COLOR_KEY_RE.search(m.group(2)) and v.strip().isdigit():
                        self.colors[i] = pj.color_hex(int(v))
                elif "/" in v or "\\" in v:
                    add("path", f"{i}.{vs}", f"{i}.{m.end(4)}")

    def draw_gutter(self):
        g = self.gutter
        g.delete("all")
        perr = {ln: kind for ln, kind, _ in reversed(self.problems)}
        cur = int(self.text.index("insert").split(".")[0])
        idx = self.text.index("@0,0")
        while True:
            info = self.text.dlineinfo(idx)
            if info is None:
                break
            y, h = info[1], info[3]
            ln = int(idx.split(".")[0])
            kind = perr.get(ln)
            color = th.ERR_SOFT if kind == "erro" else th.WARN if kind else FG if ln == cur else th.FAINT
            bold = kind or ln == cur
            g.create_text(44, y + h // 2, anchor="e", text=str(ln), fill=color, font=th.MONO_S + (("bold",) if bold else ()))
            if ln == cur:
                g.create_rectangle(0, y, 3, y + h, fill=ACCENT, outline="")
            if ln in self.colors:
                m = max(3, (h - 11) // 2)
                g.create_rectangle(50, y + m, 61, y + h - m, fill=self.colors[ln], outline="#000000")
            idx = self.text.index(f"{ln + 1}.0")
            if int(idx.split(".")[0]) == ln:
                break

    def _gutter_click(self, e):
        ln = int(self.text.index(f"@0,{e.y}").split(".")[0])
        if ln in self.colors and e.x >= 46:
            self.text.mark_set("insert", f"{ln}.0")
            self.edit_color()

    def goto_line(self, ln: int):
        self.text.mark_set("insert", f"{ln}.0")
        self.text.see(f"{max(ln - 6, 1)}.0")
        self.text.see(f"{ln + 12}.0")
        self.text.see(f"{ln}.0")
        self.text.focus_set()
        self._cursor_moved()

    def goto_regex(self, pattern: str) -> bool:
        rx = re.compile(pattern, re.I)
        for i, line in enumerate(self.get_text().split("\n"), 1):
            if rx.search(line):
                self.goto_line(i)
                return True
        return False

    # ---- bloco sob o cursor / explicar poder ---------------------------------------
    def block_at_cursor(self) -> xmlb.Node | None:
        """Bloco de primeiro nível (FightMove, talent, entity...) onde o cursor está."""
        if self.tree is None:
            return None
        ln = int(self.text.index("insert").split(".")[0])
        best = None
        for n in self.tree.children:
            if n.line <= ln:
                best = n
            else:
                break
        return best

    def block_range(self, node: xmlb.Node) -> tuple[int, int]:
        """Primeira e última linha de um bloco de primeiro nível (sem as linhas em branco do fim)."""
        kids = self.tree.children
        i = kids.index(node)
        line = lambda n: self.text.get(f"{n}.0", f"{n}.end")
        if i + 1 < len(kids):
            end = kids[i + 1].line - 1
        else:
            end = int(self.text.index("end-1c").split(".")[0])
            while end > node.line and not line(end).strip():
                end -= 1
            if line(end).startswith("}"):
                end -= 1  # a chave que fecha o arquivo
        while end > node.line and not line(end).strip():
            end -= 1
        return node.line, end

    def selected_nodes(self) -> list[xmlb.Node]:
        return [n for n in self.tree.children if n.line in self.sel_blocks] if self.tree is not None else []

    def _paint_blocks(self):
        self.text.tag_remove("blocksel", "1.0", "end")
        for n in self.selected_nodes():
            a, b = self.block_range(n)
            self.text.tag_add("blocksel", f"{a}.0", f"{b}.end+1c")

    def _toggle_block(self, e):
        self.text.mark_set("insert", f"@{e.x},{e.y}")
        b = self.block_at_cursor()
        if b is not None:
            self.sel_blocks.symmetric_difference_update({b.line})
            self._paint_blocks()
            nodes = self.selected_nodes()
            self.app.status(f"{len(nodes)} bloco(s) marcados: " + ", ".join(n.get("name") or n.name for n in nodes[:12])
                            + "      (botão direito: copiar; Ctrl+botão direito: marcar/desmarcar)" if nodes else "Nenhum bloco marcado")
        return "break"

    def clear_blocks(self):
        self.sel_blocks.clear()
        self._paint_blocks()

    def copy_blocks_text(self):
        parts = []
        for n in self.selected_nodes():
            a, b = self.block_range(n)
            parts.append(self.text.get(f"{a}.0", f"{b}.end"))
        self.clipboard_clear()
        self.clipboard_append("\n\n".join(parts) + "\n")
        self.app.status(f"Texto de {len(parts)} bloco(s) copiado para a área de transferência")

    def explain(self):
        b = self.block_at_cursor()
        if b is None or not self.char:
            return self.app.status("Abra o powerstyle ou os talentos de um personagem e coloque o cursor dentro de um poder")
        talent = b if b.name == "talent" else self.char.talent_for_move(b) if b.name == "FightMove" else None
        if talent is None:
            return self.app.status(f"'{b.get('name', b.name)}' não pertence a nenhum talento (é um move comum: ataque, pulo, bloqueio...)")
        ExplainDialog(self.app, self.char, talent, b.get("name", "") if b.name == "FightMove" else "")

    def _context_menu(self, e):
        self.text.mark_set("insert", f"@{e.x},{e.y}")
        self._cursor_moved()
        b = self.block_at_cursor()
        app = self.app
        m = tk.Menu(self, tearoff=0)
        marked = self.selected_nodes()
        if marked:
            moves = [n.get("name") for n in marked if n.name == "FightMove" and n.get("name")]
            if self.char and moves and len(moves) == len(marked):
                m.add_command(label=f"Copiar os {len(moves)} FightMoves marcados para outro personagem...",
                              command=lambda: app.copy_power(self.char, None, None, moves[0], moves[1:]))
            m.add_command(label=f"Copiar os {len(marked)} blocos marcados", command=self.copy_blocks_text)
            m.add_command(label=f"Excluir os {len(marked)} blocos marcados...", command=lambda: self.delete_nodes(marked))
            m.add_command(label="Desmarcar todos", command=self.clear_blocks)
            m.add_separator()
        if b is not None and not marked:
            nm = b.get("name")
            what = f"{b.name} {nm}" if nm else b.name
            m.add_command(label=f"Copiar este bloco  ({what})", command=lambda: self.copy_nodes([b]))
            m.add_command(label=f"Excluir este bloco  ({what})...", command=lambda: self.delete_nodes([b]))
            m.add_separator()
        if b is not None and self.char and b.name in ("FightMove", "talent"):
            talent = b if b.name == "talent" else self.char.talent_for_move(b)
            if talent is not None:
                m.add_command(label=f"Explicar poder:  {talent.get('descname') or talent.get('name')}", accelerator="F1", command=self.explain)
                m.add_command(label="Copiar este poder para outro personagem...",
                              command=lambda: app.copy_power(self.char, talent.get("name")))
                m.add_command(label="Remover este poder (talento + moves)...",
                              command=lambda: extras.remove_power(app, self.char, talent.get("name")))
            if b.name == "FightMove":
                m.add_command(label=f"Copiar só o FightMove '{b.get('name')}' para outro personagem...",
                              command=lambda: app.copy_power(self.char, None, None, b.get("name")))
            m.add_separator()
        if self.char:
            m.add_command(label=f"Ficha de {self.char.display}", command=lambda: app.open_sheet(self.char))
        m.add_command(label="Ir para a definição", accelerator="F12", command=self.goto_definition)
        m.add_command(label="Editar cor da linha", accelerator="Ctrl+K", command=self.edit_color)
        m.add_command(label="Localizar", accelerator="Ctrl+F", command=self.show_find)
        m.add_command(label="Substituir", accelerator="Ctrl+H", command=lambda: self.show_find(replace=True))
        m.tk_popup(e.x_root, e.y_root)

    # ---- substituir ---------------------------------------------------------------
    def _matches(self, a: str, b: str) -> bool:
        return a == b if self.case_var.get() else a.lower() == b.lower()

    def replace_next(self):
        """Troca a ocorrência selecionada (ou a próxima depois do cursor) e vai para a seguinte."""
        q, r = self.find_var.get(), self.replace_var.get()
        if not q:
            return self.find_entry.focus_set()
        t = self.text
        try:
            a, b = t.index("sel.first"), t.index("sel.last")
            cur = t.get(a, b)
        except tk.TclError:
            a = b = None
            cur = ""
        if a is None or not self._matches(cur, q):
            t.mark_set("insert", "insert-1c")
            self.find_next()
            try:
                a, b = t.index("sel.first"), t.index("sel.last")
            except tk.TclError:
                return
            if not self._matches(t.get(a, b), q):
                return
        t.edit_separator()
        t.delete(a, b)
        t.insert(a, r)
        t.edit_separator()
        t.mark_set("insert", f"{a}+{len(r)}c")
        t.tag_remove("sel", "1.0", "end")
        left = len(self._all_positions(q))
        if left:
            self.find_next()
        else:
            t.tag_remove("found", "1.0", "end")
        self.find_info.configure(text=f"1 substituída, {left} restante(s)", fg=DIM)
        self.app.status(f"Substituído '{q}' por '{r}' (Ctrl+Z desfaz)")

    def _all_positions(self, q: str) -> list[str]:
        out, pos, t = [], "1.0", self.text
        while q:
            pos = t.search(q, pos, stopindex="end", nocase=not self.case_var.get())
            if not pos:
                break
            out.append(pos)
            pos = f"{pos}+{len(q)}c"
        return out

    def replace_all(self):
        q, r = self.find_var.get(), self.replace_var.get()
        if not q:
            return self.find_entry.focus_set()
        t = self.text
        found = self._all_positions(q)
        if not found:
            return self.find_info.configure(text="nada encontrado", fg=th.ERR_SOFT)
        t.configure(autoseparators=False)
        t.edit_separator()
        for pos in reversed(found):  # de trás para frente: as posições anteriores não mudam
            t.delete(pos, f"{pos}+{len(q)}c")
            t.insert(pos, r)
        t.edit_separator()
        t.configure(autoseparators=True)
        t.tag_remove("found", "1.0", "end")
        self.find_info.configure(text=f"{len(found)} substituída(s)", fg=DIM)
        self.app.status(f"{len(found)} ocorrência(s) de '{q}' trocadas por '{r}' (Ctrl+Z desfaz tudo de uma vez)")

    # ---- copiar / excluir blocos inteiros ----------------------------------------------
    def nodes_at_lines(self, lines) -> list[xmlb.Node]:
        if self._job or self.tree is None:  # a árvore precisa refletir o texto atual
            self.refresh()
        want = {int(x) for x in lines}
        return [n for n in (self.tree.children if self.tree is not None else []) if n.line in want]

    def copy_nodes(self, nodes):
        parts = []
        for n in nodes:
            a, b = self.block_range(n)
            parts.append(self.text.get(f"{a}.0", f"{b}.end"))
        if not parts:
            return
        self.clipboard_clear()
        self.clipboard_append("\n\n".join(parts) + "\n")
        self.app.status(f"{len(parts)} bloco(s) copiado(s): " + ", ".join(n.get("name") or n.name for n in nodes[:8]))

    def delete_nodes(self, nodes, ask: bool = True) -> bool:
        if not nodes:
            return False
        names = ", ".join(n.get("name") or n.name for n in nodes[:10]) + (" ..." if len(nodes) > 10 else "")
        if ask and not messagebox.askyesno("Excluir bloco", f"Excluir {len(nodes)} bloco(s) inteiro(s)?\n\n{names}\n\n"
                                           "(Só vale ao salvar; Ctrl+Z desfaz.)", parent=self.app):
            return False
        t = self.text
        ranges = [self.block_range(n) for n in nodes]
        last = int(t.index("end-1c").split(".")[0])
        t.configure(autoseparators=False)
        t.edit_separator()
        for a, b in sorted(ranges, reverse=True):
            end = b + 1
            while end < last and t.get(f"{end}.0", f"{end}.end").strip() == "":
                end += 1  # leva junto as linhas em branco depois do bloco
            t.delete(f"{a}.0", f"{end}.0")
        t.edit_separator()
        t.configure(autoseparators=True)
        self.sel_blocks.clear()
        self.text.tag_remove("blocksel", "1.0", "end")
        self.refresh()
        self.app.status(f"{len(nodes)} bloco(s) excluído(s): {names}   (salve com Ctrl+S; Ctrl+Z desfaz)")
        return True

    # ---- localizar ---------------------------------------------------------------
    def show_find(self, replace: bool | None = None):
        if replace is not None:
            self.find_bar.show_replace(replace)
        self.find_bar.place(relx=1.0, x=-22, y=10, anchor="ne")
        self.find_bar.lift()
        try:
            sel = self.text.get("sel.first", "sel.last")
            if sel and "\n" not in sel:
                self.find_var.set(sel)
        except tk.TclError:
            pass
        if replace and self.find_var.get():
            self.find_bar.replace_entry.focus_set()
            self.find_bar.replace_entry.selection_range(0, "end")
        else:
            self.find_entry.focus_set()
            self.find_entry.selection_range(0, "end")

    def hide_find(self):
        self.find_bar.place_forget()
        self.text.tag_remove("found", "1.0", "end")
        self.text.focus_set()

    def find_next(self, back: bool = False):
        q = self.find_var.get()
        t = self.text
        t.tag_remove("found", "1.0", "end")
        if not q:
            return
        n = 0
        pos = "1.0"
        while True:
            pos = t.search(q, pos, stopindex="end", nocase=not self.case_var.get())
            if not pos:
                break
            t.tag_add("found", pos, f"{pos}+{len(q)}c")
            pos = f"{pos}+{len(q)}c"
            n += 1
        if back:
            nc = not self.case_var.get()
            pos = t.search(q, "insert-1c", stopindex="1.0", backwards=True, nocase=nc) or \
                t.search(q, "end", stopindex="1.0", backwards=True, nocase=nc)
        else:
            nc = not self.case_var.get()
            pos = t.search(q, "insert+1c", stopindex="end", nocase=nc) or t.search(q, "1.0", stopindex="end", nocase=nc)
        self.find_info.configure(text=f"{n} ocorrência(s)" if n else "nada encontrado",
                                 fg=DIM if n else th.ERR_SOFT)
        if pos:
            t.mark_set("insert", pos)
            t.see(pos)
            t.tag_remove("sel", "1.0", "end")
            t.tag_add("sel", pos, f"{pos}+{len(q)}c")

    # ---- cores ------------------------------------------------------------------------
    def edit_color(self):
        ln = int(self.text.index("insert").split(".")[0])
        line = self.text.get(f"{ln}.0", f"{ln}.end")
        m = LINE_KV.match(line)
        if not m or not m.group(4).strip().isdigit() or not pj.COLOR_KEY_RE.search(m.group(2)):
            self.app.status("Coloque o cursor numa linha de cor (ex.: startcolor1 = 16777215 ;)")
            return
        old = int(m.group(4))
        r, g, b, a = pj.color_to_rgb(old)
        res = colorchooser.askcolor(color=(r, g, b), parent=self, title=f"{m.group(2)}  (valor atual {old})")
        if res and res[0]:
            nr, ng, nb = (int(round(x)) for x in res[0])
            self.text.replace(f"{ln}.{m.start(4)}", f"{ln}.{m.end(4)}", str(pj.rgb_to_color(nr, ng, nb, a)))

    def color_values(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        for i, line in enumerate(self.get_text().split("\n"), 1):
            m = LINE_KV.match(line)
            if m and m.group(4).strip().isdigit() and pj.COLOR_KEY_RE.search(m.group(2)):
                out.setdefault(int(m.group(4)), []).append(i)
        return out

    def replace_colors(self, mapping: dict[int, int]):
        lines = self.get_text().split("\n")
        n = 0
        for i, line in enumerate(lines):
            m = LINE_KV.match(line)
            if m and m.group(4).strip().isdigit() and pj.COLOR_KEY_RE.search(m.group(2)):
                old = int(m.group(4))
                if old in mapping and mapping[old] != old:
                    lines[i] = line[:m.start(4)] + str(mapping[old]) + line[m.end(4):]
                    n += 1
        if n:
            pos = self.text.index("insert")
            self.text.replace("1.0", "end-1c", "\n".join(lines))
            self.text.mark_set("insert", pos)
        return n

    # ---- ir para definição ------------------------------------------------------------
    def _ctrl_click(self, e):
        self.text.mark_set("insert", f"@{e.x},{e.y}")
        self.after(10, self.goto_definition)
        return "break"

    def goto_definition(self):
        app = self.app
        ln, col = (int(x) for x in self.text.index("insert").split("."))
        line = self.text.get(f"{ln}.0", f"{ln}.end")
        m = LINE_KV.match(line)
        if not m:
            return app.status("Nada para abrir nesta linha")
        key, val = m.group(2).lower(), m.group(4).strip()
        vars_ = list(re.finditer(r"%(\w+)", line))
        if vars_:
            pick = next((v for v in vars_ if v.start() <= col <= v.end()), vars_[0])
            return app.open_var(pick.group(1), self.char)
        if not val:
            return
        rx = r"^\s*name\s*=\s*" + re.escape(val) + r"\s*;"
        if key in pj.EFFECT_KEYS:
            p = self.proj.effect_path(val)
            return app.open_file(p) if p else app.status(f"Efeito não encontrado: effects/{val}")
        if key in pj.MOVE_REF_KEYS or key == "inherit" or (key == "name" and self._block_at(ln) == "trigger"):
            cur = self.text.index("insert")
            if not self.goto_regex(rx) or self.text.index("insert").split(".")[0] == cur.split(".")[0]:
                app.status(f"'{val}' não esta definido neste arquivo (e um nome interno do jogo)")
            return
        if key == "item":
            return app.open_talent(val, self.char)
        if key == "entity" and self.char:
            for p in self.char.entity_paths:
                if any(e.get("name", "").lower() == val.lower() for e in self.proj.load(p).children):
                    return app.open_file(p, rx)
            return app.status(f"Entidade '{val}' não encontrada nos arquivos do personagem")
        if key == "powerstyle":
            val = "data/powerstyles/" + val
        if key in ("filename", "interaction", "powerstyle"):
            for cand in (val, "effects/" + val, "data/entities/" + val, "data/" + val):
                p = self.proj.resolve(cand)
                if p:
                    return app.open_file(p)
            return app.status(f"Arquivo não encontrado (ou não e um arquivo de texto compilado): {val}")
        app.status("Nada para abrir nesta linha")

    def _block_at(self, ln: int) -> str:
        depth = 0
        for i in range(ln - 1, 0, -1):
            s = self.text.get(f"{i}.0", f"{i}.end").strip()
            if s == "}":
                depth += 1
            elif s.endswith("{"):
                if depth == 0:
                    return s[:-1].replace("XMLB", "").strip()
                depth -= 1
        return ""

    # ---- salvar -------------------------------------------------------------------------
    def save(self) -> bool:
        text = self.get_text()
        if not self.compilable:
            self.proj.backup(self.path)
            xmlb.write_text_file(self.path, text)
            self.text.edit_modified(False)
            self.app.update_tab_title(self)
            self.app.status(f"Salvo: {self.proj.rel(self.path)}")
            return True
        self.refresh()
        errs = [p for p in self.problems if p[1] == "erro"]
        if errs or self.tree is None:
            self.app.show_tab_info(self)
            messagebox.showerror("Não compilado", f"{len(errs)} erro(s) de sintaxe.\nPrimeiro: linha {errs[0][0]} - {errs[0][2]}"
                                 "\n\nNada foi gravado. Corrija os itens em 'Problemas'.", parent=self.app)
            self.goto_line(errs[0][0])
            return False
        try:
            self.proj.save(self.bin_path, self.tree, text)
        except Exception as e:
            messagebox.showerror("Erro ao gravar", str(e), parent=self.app)
            return False
        self.text.edit_modified(False)
        self.set_banner(None)
        self.app.update_tab_title(self)
        warns = len(self.problems)
        self.app.status(f"Compilado: {self.proj.rel(self.bin_path)}  (+ .txt)" + (f"   {warns} aviso(s)" if warns else ""))
        self.app.after_save(self)
        return True


# ==================================================================== janela
class App(tk.Tk):
    def __init__(self, root_dir: str, settings: bool = True):
        super().__init__()
        self.title("MUA Studio")
        extras.fit(self, 1500, 900)
        self.minsize(1000, 600)
        self.configure(bg=PANEL)
        setup_style(self)
        self.proj = pj.Project(root_dir)
        self.actions: dict[str, tuple] = {}
        self._acts: dict = {}  # cada árvore tem o seu dicionário de ações
        self._names: set[str] | None = None  # nomes no herostat/npcstat (cor das bolinhas)
        self.others: list[pj.Project] = []  # outras pastas de jogo
        self.loose: list[pj.Project] = []  # personagens avulsos
        self.settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json") if settings else None
        self._load_settings()
        self.created = pj.CreatedProject(self.proj.root, os.path.join(os.path.dirname(os.path.abspath(__file__)), "criados"))
        self.anim_tools = anims.AnimTools(self.proj)
        self._build()
        self.fill_characters()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.status(f"Projeto: {self.proj.root}   |   {len(self.proj.characters)} personagens no herostat")

    # ---- montagem -----------------------------------------------------------------
    def _build(self):
        find = lambda: self.current() and self.current().show_find()  # noqa: E731
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Abrir arquivo...", accelerator="Ctrl+O", command=self.open_dialog)
        m.add_command(label="Salvar e compilar", accelerator="Ctrl+S", command=self.save_current)
        m.add_command(label="Salvar todos", accelerator="Ctrl+Shift+S", command=self.save_all)
        m.add_command(label="Recarregar do disco", command=self.reload_current)
        m.add_separator()
        m.add_command(label="Carregar pasta de outro jogo...", command=self.add_game)
        m.add_command(label="Adicionar personagem avulso (pasta)...", command=self.add_loose)
        m.add_command(label="Fechar aba", accelerator="Ctrl+W", command=self.close_current)
        m.add_separator()
        m.add_command(label="Sair", command=self.quit_app)
        m_file = m
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Localizar", accelerator="Ctrl+F", command=find)
        m.add_command(label="Ir para a definição", accelerator="F12 / Ctrl+clique", command=self.goto_def)
        m.add_command(label="Editar cor da linha", accelerator="Ctrl+K", command=self.edit_color)
        m.add_command(label="Cores do arquivo...", accelerator="Ctrl+Shift+K", command=self.colors_dialog)
        m_edit = m
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Copiar poder para outro personagem...", accelerator="Ctrl+T", command=self.copy_power)
        m.add_command(label="Converter poder de herói para NPC...", command=self.npc_power)
        m.add_command(label="Organizar poderes (níveis e tiers)...", command=self.organize_powers)
        m.add_command(label="Mixer de animações...", command=self.anim_mixer)
        m.add_command(label="Editor de áudio...", command=self.audio_editor)
        m.add_command(label="Copiar efeitos e models...", command=self.copy_resources)
        m.add_command(label="Clonar personagem / criar novo mod...", command=self.clone_character)
        m.add_command(label="Compilar personagem (salvar numa pasta)...", command=self.export_character)
        m.add_command(label="Editar herostat do jogo", command=self.open_herostat)
        m.add_separator()
        m.add_command(label="Abrir pasta de backups", command=self.open_backups)
        m.add_command(label="Reler o herostat", command=self.reload_project)
        m_tools = m
        m = tk.Menu(self, tearoff=0)
        self.lang_var = tk.StringVar(value=i18n.current())
        for code, name in i18n.LANGS:
            m.add_radiobutton(label=name, value=code, variable=self.lang_var, command=lambda c=code: self.set_language(c))
        m_lang = m
        m = tk.Menu(self, tearoff=0)
        self.theme_var = tk.StringVar(value=th.MODE)
        for code, name in th.MODES:
            m.add_radiobutton(label=name, value=code, variable=self.theme_var, command=lambda c=code: self.set_theme(c))
        m_theme = m

        # cabeçalho escuro no lugar da barra de menus do Windows (que não aceita cores)
        self.header = th.Header(self, [("Arquivo", m_file), ("Editar", m_edit), ("Ferramentas", m_tools), ("Idioma", m_lang),
                                       ("Tema", m_theme)], on_backup=self.open_backups)
        self.header.pack(fill="x")

        bar = tk.Frame(self, bg=PANEL)
        bar.pack(fill="x")
        row = tk.Frame(bar, bg=PANEL)
        row.pack(fill="x", padx=10, pady=7)
        TB = th.ToolButton

        def sep():
            tk.Frame(row, bg=LINE, width=1, height=18).pack(side="left", padx=8)

        TB(row, "Salvar e compilar", "bolt", self.save_current, kbd="Ctrl+S", kind="accent").pack(side="left")
        sep()
        TB(row, "Copiar poder...", "swap", self.copy_power, kbd="Ctrl+T", icon_color=ACCENT).pack(side="left", padx=(0, 6))
        TB(row, "Cores do arquivo", "palette", self.colors_dialog, icon_color=th.PINK).pack(side="left", padx=(0, 6))
        TB(row, "Ficha do personagem", "card", self.open_sheet, icon_color=th.AMBER).pack(side="left", padx=(0, 6))
        TB(row, "Explicar poder", "bulb", self.explain, kbd="F1", icon_color=th.PURPLE).pack(side="left")
        sep()
        mm = tk.Menu(self, tearoff=0)
        mm.add_command(label="Herostat (heróis do jogo)", command=self.open_herostat)
        mm.add_command(label="NPCStat (NPCs e vilões)", command=self.open_npcstat)
        mm.add_separator()
        mm.add_command(label="Converter poder de herói para NPC...", command=self.npc_power)
        hb = TB(row, "Herostat / NPCStat  ▾", "sliders", None, icon_color=th.SYN_KEY)
        hb.command = lambda: mm.tk_popup(hb.winfo_rootx(), hb.winfo_rooty() + hb.winfo_height() + 2)
        hb.pack(side="left", padx=(0, 6))
        TB(row, "Mixer de animações", "film", self.anim_mixer, icon_color=th.OK).pack(side="left", padx=(0, 6))
        TB(row, "Editor de áudio", "list", self.audio_editor, icon_color=th.PINK).pack(side="left", padx=(0, 6))
        TB(row, "Efeitos e models", "package", self.copy_resources, icon_color=th.SYN_PATH).pack(side="left")
        TB(row, "Localizar", "search", find, kbd="Ctrl+F", icon_color=DIM).pack(side="right")
        th.hline(bar)

        self.status_var = tk.StringVar()
        self.statusbar = th.StatusBar(self, self.status_var, on_hint=self.goto_def)
        self.statusbar.pack(fill="x", side="bottom")
        self.cursor_lbl = self.statusbar.cursor

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True)

        # esquerda
        lf = tk.Frame(main, bg=PANEL)
        # legenda das bolinhas dos personagens
        leg = tk.Frame(lf, bg=PANEL)
        leg.pack(side="bottom", fill="x")
        th.hline(leg)
        lr = tk.Frame(leg, bg=PANEL)
        lr.pack(fill="x", padx=8, pady=4)
        for color, text in ((th.ST_GAME, "no jogo"), (th.ST_OUT, "fora do jogo"), (th.ST_OTHER, "outro jogo"),
                            (th.ST_CREATED, "criado")):
            tk.Label(lr, image=th.dot(color, 12, 7), text=text, compound="left", font=th.UI_XS, bg=PANEL, fg=DIM,
                     padx=2).pack(side="left", padx=(0, 6))
        left = ttk.Notebook(lf)
        left.pack(fill="both", expand=True)
        self.left = left
        self.filter_var = tk.StringVar()
        self.trees: dict[str, ttk.Treeview] = {}
        self.tree_frames = {}
        side_btn = {"created": ("Clonar personagem / novo mod...", "copy", self.clone_character),
                    "other": ("Carregar pasta de outro jogo...", "folder", self.add_game),
                    "loose": ("Adicionar personagem (pasta)...", "people", self.add_loose)}
        self.npc_filter = tk.StringVar()
        for key, title in (("main", "Heróis"), ("npc", "NPCs"), ("created", "Criados"), ("other", "Outro jogo"), ("loose", "Avulsos")):
            cf = ttk.Frame(left)
            if key == "main":
                th.SearchEntry(cf, self.filter_var, "Filtrar herói ou nome interno...").pack(fill="x", padx=8, pady=(2, 8))
            elif key == "npc":
                th.SearchEntry(cf, self.npc_filter, "Filtrar NPC, nome interno ou powerstyle...").pack(fill="x", padx=8, pady=(2, 8))
            else:
                text, icon, cmd = side_btn[key]
                TB(cf, text, icon, cmd, icon_color=ACCENT).pack(fill="x", padx=8, pady=(2, 4 if key in ("other", "loose") else 8))
                if key in ("other", "loose"):
                    TB(cf, "Limpar lista", "close", lambda k=key: self.clear_projects(k), icon_color=DIM).pack(fill="x", padx=8, pady=(0, 8))
            th.hline(cf)
            t = self._tree(cf, columns=("info",))
            t.bind("<<TreeviewOpen>>", self._char_open)
            t.bind("<Double-1>", lambda e: self._activate(e.widget))
            t.bind("<Return>", lambda e: self._activate(e.widget))
            t.bind("<Button-3>", self._char_menu)
            self.trees[key] = t
            self.tree_frames[key] = cf
            self._acts[t] = {}
            left.add(cf, text=title)
        self.ctree = self.trees["main"]
        self.actions = self._acts[self.ctree]
        self.filter_var.trace_add("write", lambda *a: self.fill_characters())
        self.npc_filter.trace_add("write", lambda *a: self.fill_npcs())
        ff = ttk.Frame(left)
        self.ftree = self._tree(ff)
        self._acts[self.ftree] = {}
        self.ftree.bind("<<TreeviewOpen>>", self._dir_open)
        self.ftree.bind("<Double-1>", lambda e: self._activate(e.widget))
        self.ftree.bind("<Return>", lambda e: self._activate(e.widget))
        left.add(ff, text="Arquivos")
        self.fill_files()
        main.add(lf, weight=0)

        # centro
        center = ttk.Panedwindow(main, orient="vertical")
        self.tabs = ttk.Notebook(center, style="Closable.TNotebook")
        self.tabs.bind("<ButtonPress-1>", self._tab_press, True)
        self.tabs.bind("<Button-3>", self._tab_menu)
        self.tabs.bind("<<NotebookTabChanged>>", lambda e: self._tab_changed())
        self.tabs.bind("<Button-2>", self._tab_middle)
        self.welcome = tk.Frame(self.tabs, bg=BG)
        self._build_welcome(self.welcome)
        self.tabs.add(self.welcome, text="Início", image=th.dot(ACCENT, 14, 7), compound="left")
        center.add(self.tabs, weight=5)

        pf = tk.Frame(center, bg=PANEL)
        ph = tk.Frame(pf, bg=th.mix(PANEL, BG, .4))
        ph.pack(fill="x")
        prow = tk.Frame(ph, bg=ph["bg"])
        prow.pack(fill="x", padx=10, pady=5)
        tk.Label(prow, text=th.glyph("error"), font=th.ICON_S, bg=ph["bg"], fg=th.ERR_SOFT).pack(side="left", padx=(0, 6))
        tk.Label(prow, text="Problemas no arquivo", font=th.UI_SB, bg=ph["bg"], fg=FG).pack(side="left", padx=(0, 10))
        self.err_chip = th.chip(prow, "0 erros", "err")
        self.err_chip.pack(side="left", padx=(0, 6))
        self.warn_chip = th.chip(prow, "0 avisos", "warn")
        self.warn_chip.pack(side="left")
        tk.Label(prow, text="Clique em um item para ir até a linha", font=th.UI_XS, bg=ph["bg"], fg=DIM).pack(side="right")
        self.prob_title = prow
        th.hline(pf)
        self.ptree = self._tree(pf, columns=("ln", "tipo", "msg"), show="", height=6)
        self.ptree.column("ln", width=74, stretch=False, anchor="e")
        self.ptree.column("tipo", width=84, stretch=False, anchor="center")
        self.ptree.column("msg", width=400, stretch=True)
        self.ptree.tag_configure("erro", foreground=th.ERR_SOFT, background=th.mix(PANEL, th.ERR, .06))
        self.ptree.tag_configure("aviso", foreground=th.WARN_SOFT)
        self.ptree.bind("<<TreeviewSelect>>", self._prob_select)
        center.add(pf, weight=1)
        main.add(center, weight=1)

        # direita
        right = tk.Frame(main, bg=PANEL)
        th.panel_header(right, "Estrutura do arquivo", "XMLB Tree", icon="tree", icon_color=th.SYN_BLOCK)
        self.outline_filter = tk.StringVar()
        th.SearchEntry(right, self.outline_filter, "Filtrar FightMove ou trigger...").pack(fill="x", padx=8, pady=8)
        self.outline_filter.trace_add("write", lambda *a: self.fill_outline())
        th.hline(right)
        self.otree = self._tree(right, columns=("ln",))
        self.otree.column("ln", width=46, stretch=False, anchor="e")
        for tag, color in (("FightMove", FG), ("talent", th.SYN_KEY), ("other", DIM)):
            self.otree.tag_configure(tag, foreground=color)
        self.otree.configure(selectmode="extended")
        self.otree.bind("<<TreeviewSelect>>", self._outline_select)
        self.otree.bind("<Button-3>", self._outline_menu)
        self.otree.bind("<Delete>", lambda e: self._outline_action("delete"))
        self.otree.bind("<Control-c>", lambda e: self._outline_action("copy"))
        main.add(right, weight=0)
        def place_sashes(tries=0):
            # espera a janela ter o tamanho de verdade; antes disso os painéis laterais abririam fechados
            w = main.winfo_width()
            if w < 700 and tries < 80:
                return self.after(50, lambda: place_sashes(tries + 1))
            main.sashpos(0, 365)
            main.sashpos(1, max(700, w - 290))
            if tries >= 0 and main.sashpos(0) < 100:  # o Tk ainda não aplicou: tenta de novo
                self.after(100, lambda: place_sashes(-1 if tries > 70 else tries + 1))

        self.after(50, place_sashes)

        for seq, fn in (("<Control-s>", self.save_current), ("<Control-S>", self.save_all), ("<Control-o>", self.open_dialog),
                        ("<Control-w>", self.close_current), ("<Control-t>", self.copy_power), ("<F12>", self.goto_def),
                        ("<Control-k>", self.edit_color), ("<Control-K>", self.colors_dialog),
                        ("<F1>", self.explain),
                        ("<Control-f>", find),
                        ("<Control-h>", lambda: self.current() and self.current().show_find(replace=True))):
            self.bind(seq, lambda e, f=fn: (f(), "break")[1])

    def _build_welcome(self, page: tk.Frame):
        box = tk.Frame(page, bg=BG)
        box.pack(fill="both", expand=True, padx=40, pady=30)
        top = tk.Frame(box, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text="M", font=(th.UI_B[0], 16, "bold"), bg=ACCENT, fg="#ffffff", width=2).pack(side="left")
        tk.Label(top, text="MUA Studio", font=th.H1, bg=BG, fg=th.STRONG).pack(side="left", padx=12)
        tk.Label(box, text="Abra, edite e compile os arquivos de personagem do Marvel Ultimate Alliance.",
                 font=th.UI, bg=BG, fg=DIM, anchor="w").pack(fill="x", pady=(6, 0))
        th.section_title(box, "Como funciona")
        grid = th.CardGrid(box, minw=230)
        grid.pack(fill="x")
        for n, title, text in (
                ("1", "Escolha um personagem", "Na lista à esquerda, abra Talentos, Powerstyle, Entidades ou um Efeito."),
                ("2", "Edite", "Erros de ' ;' e de chaves aparecem em Problemas enquanto você digita."),
                ("3", "Ctrl+S compila", "Gera o binário que o jogo lê e atualiza o .txt ao lado. Sempre fica um backup.")):
            c = th.card(grid)
            hd = tk.Frame(c, bg=PANEL)
            hd.pack(fill="x", padx=12, pady=(10, 4))
            th.chip(hd, n, "info", font=th.UI_SB, padx=7).pack(side="left")
            tk.Label(hd, text=title, font=th.UI_B, bg=PANEL, fg=th.STRONG).pack(side="left", padx=8)
            d = tk.Label(c, text=text, font=th.UI_S, bg=PANEL, fg=DIM, justify="left", anchor="w")
            d.pack(fill="x", padx=12, pady=(0, 12))
            c.bind("<Configure>", lambda e, d=d: d.configure(wraplength=max(120, e.width - 26)))
            grid.add(c)
        th.section_title(box, "Atalhos")
        sc = tk.Frame(box, bg=BG)
        sc.pack(fill="x")
        for i, (k, text) in enumerate((
                ("Ctrl+T", "copiar um poder para outro personagem"),
                ("F12 / Ctrl+clique", "abrir o efeito, a variável, o move ou a entidade da linha"),
                ("Ctrl+K", "editar a cor da linha (clique no quadradinho ao lado do número da linha)"),
                ("Ctrl+Shift+K", "trocar ou recolorir todas as cores do arquivo"),
                ("Ctrl+F", "localizar no arquivo (F3 = próximo)"),
                ("F1", "explicar o poder (ou botão direito num poder)"),
                ("Ficha do personagem", "skins, talentos do herostat e a descrição de cada poder"),
                ("Ctrl+W", "fechar a aba (botão direito na aba: fechar as outras / todas)"))):
            r, c2 = i % 4, (i // 4) * 2
            th.chip(sc, k, "kbd", bg=th.SURFACE, font=th.MONO_S, padx=7, pady=2).grid(row=r, column=c2, sticky="w", pady=3)
            tk.Label(sc, text=text, font=th.UI_S, bg=BG, fg=FG, anchor="w", wraplength=215, justify="left").grid(
                row=r, column=c2 + 1, sticky="w", padx=(10, 22))

    def _tree(self, parent, **kw) -> ttk.Treeview:
        fr = ttk.Frame(parent)
        fr.pack(fill="both", expand=True)
        kw.setdefault("show", "tree")
        tv = ttk.Treeview(fr, selectmode="browse", **kw)
        sb = ttk.Scrollbar(fr, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(4, 0))
        if "info" in kw.get("columns", ()):
            tv.column("#0", stretch=True, width=190)
            tv.column("info", width=118, stretch=False, anchor="e")
        # cores por tipo de item (árvore de personagens e de arquivos)
        for tag, opts in (("char", {"foreground": FG}),("proj", {"foreground": th.STRONG, "font": th.UI_B}),
                          ("sheet", {"foreground": th.SHEET_FG}), ("power", {"foreground": th.SYN_KEY}),
                          ("group", {"foreground": DIM, "font": th.UI_SB}), ("dim", {"foreground": DIM}),
                          ("missing", {"foreground": th.ERR_SOFT}), ("meta", {"foreground": th.FAINT, "font": th.MONO_XS}),
                          ("unused", {"foreground": th.ERR}),
                          ("dir", {"foreground": FG}), ("bin", {"foreground": FG}), ("txt", {"foreground": DIM})):
            tv.tag_configure(tag, **opts)
        th.enable_hover(tv)
        return tv

    # ---- status -------------------------------------------------------------------------
    def status(self, msg: str):
        self.status_var.set(msg)

    def set_cursor_status(self, ln, col):
        self.cursor_lbl.configure(text=f"Lin {ln}, Col {col}")

    # ---- projetos (jogo principal, outros jogos, personagens avulsos) ---------------------
    def all_projects(self) -> list[pj.Project]:
        return [self.proj] + ([self.created] if self.created.characters else []) + self.others + self.loose

    def all_characters(self) -> list[pj.Character]:
        return [c for p in self.all_projects() for c in p.characters]

    def project_for_path(self, path: str) -> pj.Project:
        best = self.proj
        for p in self.all_projects():
            for root in {p.root, getattr(p, "folder", p.root)}:
                a, b = os.path.normcase(os.path.abspath(path)), os.path.normcase(root).rstrip("\\/") + os.sep
                if a.startswith(b) and (best is self.proj and not self.proj.owns(path) or len(root) > len(best.root)):
                    best = p
        return best

    def _load_settings(self):
        import json
        if not self.settings_path or not os.path.isfile(self.settings_path):
            return
        try:
            with open(self.settings_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        for path in data.get("other", []):
            if os.path.isdir(path):
                try:
                    self.others.append(pj.Project(path))
                except Exception:
                    pass
        for path in data.get("loose", []):
            if os.path.isdir(path):
                try:
                    self.loose.append(pj.LooseProject(path))
                except Exception:
                    pass

    def _save_settings(self):
        import json
        if not self.settings_path:
            return
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump({"other": [p.root for p in self.others], "loose": [p.folder for p in self.loose],
                           "lang": self.lang_var.get() if hasattr(self, "lang_var") else i18n.read_saved(),
                           "theme": th.read_mode()}, f, indent=1)
        except OSError:
            pass

    def _known(self, path: str) -> bool:
        n = os.path.normcase(os.path.abspath(path))
        return any(n in (os.path.normcase(p.root), os.path.normcase(getattr(p, "folder", p.root))) for p in self.all_projects())

    def add_game(self, path: str | None = None):
        path = path or filedialog.askdirectory(parent=self, title="Pasta de outra cópia do jogo (a que contém data e packages)")
        if not path:
            return None
        root = pj.find_game_root(path) or pj.find_content_root(path)
        if not root or not os.path.isdir(os.path.join(root, "data")):
            messagebox.showerror("Pasta inválida", "Não achei a pasta 'data' do jogo dentro de:\n" + path, parent=self)
            return None
        if self._known(root):
            self.status("Essa pasta já está carregada")
            return None
        proj = pj.Project(root)
        self.others.append(proj)
        self._after_projects_changed("other")
        self.status(f"Outro jogo carregado: {proj.root}   |   {len(proj.characters)} personagens")
        return proj

    def add_loose(self, path: str | None = None):
        path = path or filedialog.askdirectory(parent=self, title="Pasta do personagem (a do mod, com data/actors/packages dentro)")
        if not path:
            return None
        if self._known(path):
            self.status("Essa pasta já está carregada")
            return None
        proj = pj.LooseProject(path)
        self.loose.append(proj)
        self._after_projects_changed("loose")
        self.status(f"Personagem avulso carregado: {proj.folder}   |   {len(proj.characters)} personagem(ns) encontrados"
                    + ("" if proj.characters else "  (nenhum herostat nem pacote reconhecido; use a aba Arquivos)"))
        return proj

    def remove_project(self, proj: pj.Project):
        for lst in (self.others, self.loose):
            if proj in lst:
                lst.remove(proj)
        self._after_projects_changed(None)

    def _after_projects_changed(self, show: str | None):
        self._save_settings()
        self.fill_characters()
        self.fill_files()
        if show:
            self.left.select(self.tree_frames[show])

    def _use(self, tree):
        """As funções da árvore trabalham sobre a árvore em que o usuário clicou."""
        if tree is None:
            return
        self.actions = self._acts[tree]
        if tree is not self.ftree:
            self.ctree = tree

    # ---- arvore de personagens -------------------------------------------------------------
    def _game_names(self) -> set[str]:
        """Nomes internos registrados no jogo principal (herostat + npcstat), para a cor das bolinhas."""
        if self._names is None:
            names = {c.name.lower() for c in self.proj.characters}
            try:
                names |= {c.name.lower() for c in self.proj.npcs()}
            except Exception:
                pass
            self._names = names
        return self._names

    def char_status(self, c: pj.Character) -> tuple[str, str]:
        """Cor e texto do status: verde no jogo, vermelho fora, azul outro jogo, amarelo criado."""
        p = c.proj
        if p is self.created or getattr(p, "kind", "") == "criado":
            return th.ST_CREATED, "criado no MUA Studio"
        if p in self.others:
            return th.ST_OTHER, f"de outro jogo ({p.label})"
        if p is self.proj:
            return th.ST_GAME, "no npcstat do jogo" if getattr(c, "is_npc", False) else "no herostat do jogo"
        if c.name.lower() in self._game_names():
            return th.ST_GAME, "registrado no jogo"
        return th.ST_OUT, "fora do jogo (não está no herostat nem no npcstat)"

    def fill_characters(self):
        self._names = None
        q = self.filter_var.get().lower().strip()
        for key, projs in (("main", [self.proj]), ("created", [self.created]), ("other", self.others), ("loose", self.loose)):
            t = self.trees[key]
            acts = self._acts[t]
            acts.clear()
            t.delete(*t.get_children())
            for p in projs:
                parent = ""
                if key != "main":
                    parent = t.insert("", "end", text=p.label, values=(f"{len(p.characters)} personagem(ns)",), open=True,
                                      tags=("proj",), image=th.square(ACCENT, 14, 8))
                    acts[parent] = ("proj", p)
                    if not p.characters:
                        t.insert(parent, "end", text="(nenhum personagem reconhecido; veja a aba Arquivos)", tags=("dim",))
                for c in p.characters:
                    if key == "main" and q and q not in c.display.lower() and q not in c.name.lower():
                        continue
                    iid = t.insert(parent, "end", text=c.display, values=(c.name,), tags=("char",),
                                   image=th.dot(self.char_status(c)[0], 14, 8))
                    acts[iid] = ("char", c)
                    t.insert(iid, "end", text="...")
            if key != "main" and not projs:
                t.insert("", "end", text="(nada carregado: use o botão acima)", tags=("dim",))
        self.fill_npcs()

    def fill_npcs(self):
        """Aba NPCs: os NPCs do npcstat que lutam (têm powerstyle), com o mesmo detalhamento dos heróis."""
        if "npc" not in self.trees:
            return
        t = self.trees["npc"]
        acts = self._acts[t]
        acts.clear()
        t.delete(*t.get_children())
        q = self.npc_filter.get().lower().strip()
        try:
            npcs = self.proj.npcs()
        except Exception as e:
            t.insert("", "end", text=f"(npcstat ilegível: {e})", tags=("dim",))
            return
        for c in npcs:
            if q and q not in c.display.lower() and q not in c.name.lower() and q not in c.powerstyle.lower():
                continue
            iid = t.insert("", "end", text=c.display, values=(c.powerstyle,), tags=("char",),
                           image=th.dot(self.char_status(c)[0], 14, 8))
            acts[iid] = ("char", c)
            t.insert(iid, "end", text="...")
        if not npcs:
            t.insert("", "end", text="(nenhum NPC com powerstyle em data/npcstat)", tags=("dim",))

    def clear_projects(self, key: str):
        lst = self.others if key == "other" else self.loose
        if not lst:
            return self.status("A lista já está vazia")
        what = "outros jogos" if key == "other" else "personagens avulsos"
        if not messagebox.askyesno("Limpar lista", f"Tirar os {len(lst)} {what} da lista?\n\nNada é apagado do disco; "
                                   "você pode carregá-los de novo depois.", parent=self):
            return
        open_paths = [t for t in self.editors() if any(p.owns(t.path) for p in lst)]
        dirty = [t for t in open_paths if t.modified]
        if dirty:
            return messagebox.showwarning("Salve antes", "Arquivos dessas pastas estão abertos com alterações não salvas:\n\n"
                                          + "\n".join(os.path.basename(t.path) for t in dirty), parent=self)
        for t in open_paths:
            self.tabs.forget(t)
            t.destroy()
        n = len(lst)
        lst.clear()
        self._after_projects_changed(key)
        self.status(f"{n} {what} tirados da lista")

    def fill_files(self):
        t = self.ftree
        acts = self._acts[t]
        acts.clear()
        t.delete(*t.get_children())
        projs = [p for p in self.all_projects() if p.kind != "criado"]
        for p in projs:
            parent = ""
            if len(projs) > 1:
                parent = t.insert("", "end", text=p.label + ("" if p is not self.proj else "   (jogo principal)"), open=p is self.proj)
            base = getattr(p, "folder", p.root)
            if p.kind == "avulso":
                acts[parent] = ("dir", base)
                t.insert(parent, "end", text="...")
                continue
            for d in ("data", "effects", "packages"):
                dp = os.path.join(p.root, d)
                if os.path.isdir(dp):
                    iid = t.insert(parent, "end", text=d, open=False)
                    acts[iid] = ("dir", dp)
                    t.insert(iid, "end", text="...")

    def _char_open(self, e):
        self._use(e.widget if e is not None else None)
        t = self.ctree
        iid = t.focus()
        act = self.actions.get(iid)
        if not act:
            return
        kids = t.get_children(iid)
        if not (len(kids) == 1 and t.item(kids[0], "text") == "..."):
            return
        t.delete(*kids)
        if act[0] == "char":
            self._fill_char(iid, act[1])
        elif act[0] == "lazy":
            act[1](iid)

    def _leaf(self, parent, text, action, info="", kind="", color=None):
        iid = self.ctree.insert(parent, "end", text=text, values=(info,), tags=(kind,) if kind else (),
                                image=th.square(color, 14, 6) if color else th.blank())
        self.actions[iid] = action
        return iid

    def _fill_npc(self, iid, c: pj.Character):
        proj = c.proj
        self._leaf(iid, "NPCStat", ("npcstat", c), info="atributos, vida, dano, talentos", kind="sheet", color=th.AMBER)
        pp = c.powerstyle_path
        self._leaf(iid, "Powerstyle", ("open", pp, None), info=os.path.basename(pp) if pp else f"{c.powerstyle}: não encontrado",
                   kind="" if pp else "missing", color=ACCENT)
        moves = []
        if pp:
            try:
                moves = [m for m in proj.load(pp).children if m.name == "FightMove" and m.get("name")]
            except Exception:
                pass
        g = self.ctree.insert(iid, "end", text="Moves", values=(str(len(moves)),), open=True, tags=("group",),
                              image=th.square(th.SYN_KEY, 14, 6))
        for m in moves:
            nm = m.get("name")
            self._leaf(g, nm, ("open", pp, r"^\s*name\s*=\s*" + re.escape(nm) + r"\s*;"),
                       info=" ".join(x for x in (m.get("aitype", ""), m.get("animenum", "")) if x), kind="power" if nm.lower().startswith("power") else "")
        if not moves:
            self.ctree.insert(g, "end", text="(nenhum: use 'Converter poder de herói para este NPC')", tags=("dim",))
        for p in c.entity_paths:
            self._leaf(iid, "Entidades", ("open", p, None), info=os.path.basename(p), color=th.SYN_VAR)
        tree, acts = self.ctree, self.actions

        self._resource_groups(iid, c, tree, acts)
        s = c.stats
        tree.insert(iid, "end", text=f"skin {s.get('skin', '-')}  \u00b7  anims {c.anims or '-'}  \u00b7  som {c.sounddir or '-'}",
                    tags=("meta",), image=th.blank())
        tree.insert(iid, "end", text=f"nível {s.get('level', '-')}  \u00b7  vida {s.get('specific_health', '-')}  \u00b7  "
                    f"dano x{s.get('npcdamagescale', '1')}  \u00b7  time {s.get('team', '-')}", tags=("meta",), image=th.blank())

    def _resource_groups(self, iid, c: pj.Character, tree, acts):
        """Grupos 'Efeitos usados', 'Models' e 'Pacotes' de um personagem (herói ou NPC)."""
        proj = c.proj

        def fill_fx(node, c=c):
            fx = ops.effects_with_usage(c)
            main = transfer.effects_folder(c)
            unused = 0
            for v, p, who in fx:
                parts = v.split("/")
                short = parts[-1] if len(parts) == 3 and parts[0].lower() == "char" and parts[1].lower() == main else v
                if not p:
                    info, kind = "não existe", "missing"
                elif not who:
                    info, kind = "Não usado", "unused"
                    unused += 1
                else:
                    info, kind = who[0] + (f"  +{len(who) - 1}" if len(who) > 1 else ""), ""
                self._leaf(node, short + ("" if not who else "   \u00b7  " + ", ".join(who)), ("open", p, None, ("fx", c, v)),
                           info=info, kind=kind)
            tree.item(node, values=(f"{len(fx) - unused}" + (f"  ({unused} sem uso)" if unused else ""),))
            if not fx:
                tree.insert(node, "end", text="(nenhum)", tags=("dim",))

        def fill_md(node, c=c):
            md = ops.char_models(c)
            for v, p, where in md:
                self._leaf(node, v, ("model", p, None, ("model", c, v)), info=where if p else "não existe", kind="" if p else "missing")
            tree.item(node, values=(str(len(md)),))
            if not md:
                tree.insert(node, "end", text="(nenhum)", tags=("dim",))

        def fill_pk(node, c=c):
            for p in c.packages:
                self._leaf(node, os.path.basename(p), ("open", p, None))
            if not c.packages:
                tree.insert(node, "end", text="(nenhum)", tags=("dim",))

        for label, fn, color, info in (("Efeitos", fill_fx, th.SYN_PATH, ""), ("Models", fill_md, th.SYN_VAR, ""),
                                       ("Pacotes", fill_pk, th.PINK, str(len(c.packages)))):
            g = tree.insert(iid, "end", text=label, values=(info,), image=th.square(color, 14, 6))
            acts[g] = ("lazy", fn)
            tree.insert(g, "end", text="...")

    def _fill_char(self, iid, c: pj.Character):
        if c.is_npc:
            return self._fill_npc(iid, c)
        proj = c.proj
        self._leaf(iid, "Ficha do personagem", ("sheet", c), kind="sheet", color=th.AMBER)
        hs = getattr(proj, "snippets", {}).get(c.name.lower()) or proj.herostat_path
        if hs:
            self._leaf(iid, "Herostat", ("open", hs, r"^\s*name\s*=\s*" + re.escape(c.name) + r"\s*;"),
                       info="atributos e skins" if proj.kind == "jogo" else os.path.basename(hs), color=DIM)
        tp, pp = c.talents_path, c.powerstyle_path
        self._leaf(iid, "Talentos", ("open", tp, None), info=os.path.basename(tp) if tp else "não encontrado",
                   kind="" if tp else "missing", color=th.SYN_BLOCK)
        self._leaf(iid, "Powerstyle", ("open", pp, None), info=os.path.basename(pp) if pp else "não encontrado",
                   kind="" if pp else "missing", color=ACCENT)
        powers = c.powers()
        if powers:
            g = self.ctree.insert(iid, "end", text="Poderes", values=(str(len(powers)),), open=True, tags=("group",),
                                  image=th.square(th.SYN_KEY, 14, 6))
            for tn, dn, mv in powers:
                self._leaf(g, dn or tn, ("power", c, tn, mv), info=f"[{mv}]", kind="power")
        for p in c.entity_paths:
            self._leaf(iid, "Entidades", ("open", p, None), info=os.path.basename(p), color=th.SYN_VAR)
        tree, acts = self.ctree, self.actions

        self._resource_groups(iid, c, tree, acts)
        skins = ", ".join(s for s, _ in c.skins)
        tree.insert(iid, "end", text=f"skins {skins}  \u00b7  anims {c.anims}  \u00b7  som {c.sounddir}", tags=("meta",),
                    image=th.blank())

    def _activate(self, tree):
        self._use(tree)
        act = self.actions.get(tree.focus())
        if not act:
            return
        if act[0] == "npcstat":
            self.open_npcstat(act[1].name)
        elif act[0] == "sheet":
            self.open_sheet(act[1])
        elif act[0] == "model":
            if act[1]:
                os.startfile(os.path.dirname(act[1]))
                self.status(f"Model .igb não abre no editor de texto: mostrando a pasta de {os.path.basename(act[1])}")
        elif act[0] in ("open", "file"):
            if act[1]:
                self.open_file(act[1], act[2] if len(act) > 2 else None)
        elif act[0] == "power":
            _, c, tn, mv = act
            if c.powerstyle_path:
                tab = self.open_file(c.powerstyle_path)
                if tab and not tab.goto_regex(r"^\s*name\s*=\s*" + re.escape(mv) + r"\s*;"):
                    tab.goto_regex(re.escape(tn))
        return "break"

    def _char_menu(self, e):
        self._use(e.widget)
        tree = self.ctree
        iid = tree.identify_row(e.y)
        if not iid:
            return
        tree.selection_set(iid)
        tree.focus(iid)
        act = self.actions.get(iid)
        if not act:
            return
        m = tk.Menu(self, tearoff=0)
        if act[0] == "power":
            _, c, tn, mv = act
            m.add_command(label="Explicar poder", command=lambda: self.explain_talent(c, tn))
            m.add_command(label="Copiar este poder para...", command=lambda: self.copy_power(c, tn))
            m.add_command(label="Abrir no powerstyle", command=lambda: self._activate(tree))
            m.add_command(label="Abrir o talento", command=lambda: self.open_talent(tn, c))
            m.add_command(label="Converter este poder para um NPC...", command=lambda: self.npc_power(c, tn))
            m.add_separator()
            m.add_command(label="Remover este poder (talento + moves)...", command=lambda: extras.remove_power(self, c, tn))
        elif act[0] in ("char", "npcstat") and act[1].is_npc:
            c = act[1]
            m.add_command(label="Editar no NPCStat", command=lambda: self.open_npcstat(c.name))
            m.add_command(label="Abrir o powerstyle", command=lambda: self.open_file(c.powerstyle_path) if c.powerstyle_path else None)
            m.add_command(label="Converter poder de herói para este NPC...", command=lambda: self.npc_power_to(c))
            m.add_command(label="Mixer de animações...", command=lambda: self.anim_mixer(c))
            m.add_command(label="Editor de áudio...", command=lambda: self.audio_editor(c))
            m.add_command(label="Copiar efeitos e models...", command=lambda: self.copy_resources(c))
            m.add_separator()
            m.add_command(label="Compilar NPC (salvar numa pasta)...", command=lambda: extras.export_character(self, c))
        elif act[0] == "char":
            m.add_command(label="Ficha do personagem", command=lambda: self.open_sheet(act[1]))
            m.add_command(label="Copiar um poder ou move deste personagem...", command=lambda: self.copy_power(act[1]))
            m.add_command(label="Receber um poder de outro personagem...", command=lambda: self.copy_power(None, None, act[1]))
            m.add_separator()
            m.add_command(label="Organizar poderes (níveis e tiers)...", command=lambda: self.organize_powers(act[1]))
            m.add_command(label="Mixer de animações...", command=lambda: self.anim_mixer(act[1]))
            m.add_command(label="Editor de áudio...", command=lambda: self.audio_editor(act[1]))
            m.add_command(label="Copiar efeitos e models...", command=lambda: self.copy_resources(act[1]))
            m.add_command(label="Clonar este personagem / criar novo mod...", command=lambda: self.clone_character(act[1]))
            m.add_command(label="Compilar personagem (salvar numa pasta)...", command=lambda: self.export_character(act[1]))
            if act[1].proj.kind == "criado":
                m.add_separator()
                m.add_command(label="Excluir este personagem criado...", command=lambda: extras.delete_created(self, act[1]))
        elif act[0] == "proj":
            p = act[1]
            m.add_command(label="Recarregar esta pasta", command=lambda: (p._cache.clear(), p.reload_characters(), self._after_projects_changed(None)))
            m.add_command(label="Mostrar na pasta", command=lambda: os.startfile(getattr(p, "folder", p.root)))
            m.add_command(label="Remover da lista (não apaga nada do disco)", command=lambda: self.remove_project(p))
        elif act[0] in ("open", "model") and (act[1] or len(act) > 3):
            if act[1]:
                if act[0] == "open":
                    m.add_command(label="Abrir", command=lambda: self._activate(tree))
                m.add_command(label="Mostrar na pasta", command=lambda: os.startfile(os.path.dirname(act[1])))
            if len(act) > 3:
                kind, c, ref = act[3]
                m.add_command(label=f"Copiar este {'efeito' if kind == 'fx' else 'model'} para outro personagem...",
                              command=lambda: self.copy_resources(c, [ref]))
            if len(act) > 3 and act[3][0] == "fx" and act[1]:
                m.add_command(label="Renomear efeito (atualiza powerstyle e entidades)...", command=lambda: self.rename_effect(act[3][1], act[3][2]))
                m.add_command(label="Recolorir (cores do arquivo)...", command=lambda: (self.open_file(act[1]), self.colors_dialog()))
        else:
            return
        m.tk_popup(e.x_root, e.y_root)

    # ---- arvore de arquivos -------------------------------------------------------------------
    def _dir_open(self, _e):
        self._use(self.ftree)
        t = self.ftree
        iid = t.focus()
        act = self.actions.get(iid)
        kids = t.get_children(iid)
        if not act or act[0] != "dir" or not (len(kids) == 1 and t.item(kids[0], "text") == "..."):
            return
        t.delete(*kids)
        try:
            names = sorted(os.listdir(act[1]), key=str.lower)
        except OSError:
            return
        shown = set()
        for n in names:
            p = os.path.join(act[1], n)
            if os.path.isdir(p):
                c = t.insert(iid, "end", text=n)
                self.actions[c] = ("dir", p)
                t.insert(c, "end", text="...")
        for n in names:
            p = os.path.join(act[1], n)
            if os.path.isfile(p) and pj.is_editable(p):
                b = pj.binary_of(p)
                if b.lower() in shown:
                    continue
                shown.add(b.lower())
                c = t.insert(iid, "end", text=os.path.basename(b))
                self.actions[c] = ("file", b, None)
        for n in names:  # .txt soltos (anotacoes, herostat de mod)
            p = os.path.join(act[1], n)
            if os.path.isfile(p) and n.lower().endswith((".txt", ".xml", ".json")) and not pj.is_editable(p):
                c = t.insert(iid, "end", text=n)
                self.actions[c] = ("file", p, None)

    # ---- abas -------------------------------------------------------------------------------------
    def editors(self) -> list[EditorTab]:
        return [w for w in (self.nametowidget(t) for t in self.tabs.tabs()) if isinstance(w, EditorTab)]

    def current(self) -> EditorTab | None:
        sel = self.tabs.select()
        w = self.nametowidget(sel) if sel else None
        return w if isinstance(w, EditorTab) else None

    def open_file(self, path: str | None, search: str | None = None) -> EditorTab | None:
        if not path:
            return None
        target = pj.binary_of(path) if pj.is_editable(path) else path
        for tab in self.editors():
            if os.path.normcase(tab.path) == os.path.normcase(target):
                self.tabs.select(tab)
                if search:
                    tab.goto_regex(search)
                return tab
        try:
            tab = EditorTab(self, path)
        except Exception as e:
            messagebox.showerror("Não foi possível abrir", f"{path}\n\n{e}", parent=self)
            return None
        self.tabs.add(tab, text=os.path.basename(tab.path), image=self._tab_icon(tab.path), compound="left")
        self.tabs.select(tab)
        self.update_tab_title(tab)
        if search:
            self.after(30, lambda: tab.goto_regex(search))
        tab.text.focus_set()
        return tab

    @staticmethod
    def _tab_icon(path: str):
        p = path.replace("\\", "/").lower()
        for key, color in (("/powerstyles/", ACCENT), ("/talents/", th.SYN_BLOCK), ("herostat", DIM), ("npcstat", DIM),
                           ("/effects/", th.SYN_PATH), ("/entities/", th.SYN_VAR), ("/packages/", th.PINK)):
            if key in p:
                return th.dot(color, 14, 7)
        return th.dot(th.FAINT, 14, 7)

    def update_tab_title(self, tab: EditorTab):
        try:
            self.tabs.tab(tab, text=("● " if tab.modified else "") + os.path.basename(tab.path))
        except tk.TclError:
            pass

    def _tab_changed(self):
        tab = self.current()
        if tab:
            self.show_tab_info(tab)
            parts = tab.proj.rel(tab.path).replace("\\", "/").split("/")
            first = tab.char.display if tab.char else (None if tab.proj is self.proj else tab.proj.label)
            self.header.set_path(parts, first)
            self.statusbar.ftype.configure(text="XMLB binário (little-endian)" if tab.compilable else "Texto solto")
            ln, col = tab.text.index("insert").split(".")
            self.set_cursor_status(int(ln), int(col) + 1)
        else:
            sel = self.tabs.select()
            w = self.nametowidget(sel) if sel else None
            char = getattr(w, "char", None)
            label = self.tabs.tab(sel, "text") if sel and w is not self.welcome else ""
            self.header.set_path(["Ficha do personagem"] if isinstance(w, SheetTab) else [label] if label else [],
                                 char.display if isinstance(w, SheetTab) and char else None)
            self.statusbar.ftype.configure(text="")
            self.cursor_lbl.configure(text="")
            self.ptree.delete(*self.ptree.get_children())
            self.otree.delete(*self.otree.get_children())
            self._prob_counts(0, 0)

    def _tab_at(self, e):
        try:
            return self.nametowidget(self.tabs.tabs()[self.tabs.index(f"@{e.x},{e.y}")])
        except (tk.TclError, IndexError):
            return None

    def _close_widget(self, w) -> bool:
        if isinstance(w, EditorTab):
            return self.close_tab(w)
        if isinstance(w, (extras.HerostatTab, extras.NpcstatTab)) and w.dirty:
            r = messagebox.askyesnocancel("Fechar", "Salvar as alterações desta lista antes de fechar?", parent=self)
            if r is None or (r and not w.save()):
                return False
        if w is not None:
            self.tabs.forget(w)
        return True

    def _tab_press(self, e):
        if "tabclose" in str(self.tabs.identify(e.x, e.y)):
            w = self._tab_at(e)
            self.after_idle(lambda: self._close_widget(w))
            return "break"

    def _tab_menu(self, e):
        w = self._tab_at(e)
        if w is None:
            return
        self.tabs.select(w)
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Fechar", accelerator="Ctrl+W", command=lambda: self._close_widget(w))
        m.add_command(label="Fechar as outras", command=lambda: self.close_many(keep=w))
        m.add_command(label="Fechar todas", command=self.close_many)
        if isinstance(w, EditorTab):
            m.add_separator()
            m.add_command(label="Mostrar na pasta", command=lambda: os.startfile(os.path.dirname(w.path)))
        m.tk_popup(e.x_root, e.y_root)

    def close_many(self, keep=None):
        for t in self.tabs.tabs():
            w = self.nametowidget(t)
            if w is not keep and not self._close_widget(w):
                break

    def _tab_middle(self, e):
        try:
            idx = self.tabs.index(f"@{e.x},{e.y}")
        except tk.TclError:
            return
        w = self.nametowidget(self.tabs.tabs()[idx])
        if isinstance(w, EditorTab):
            self.close_tab(w)

    def show_tab_info(self, tab: EditorTab):
        p = self.ptree
        p.delete(*p.get_children())
        for ln, kind, msg in tab.problems[:500]:
            p.insert("", "end", values=(f"Lin {ln}", kind.upper(), msg), tags=(kind,))
        ne = sum(1 for x in tab.problems if x[1] == "erro")
        self._prob_counts(ne, len(tab.problems) - ne)
        self.fill_outline()

    def _prob_counts(self, ne: int, nw: int):
        self.err_chip.configure(text=f"{ne} erro" + ("" if ne == 1 else "s"))
        self.warn_chip.configure(text=f"{nw} aviso" + ("" if nw == 1 else "s"))
        th.chip_recolor(self.err_chip, "err" if ne else "dim")
        th.chip_recolor(self.warn_chip, "warn" if nw else "dim")
        self.statusbar.set_kind("err" if ne else "warn" if nw else "ok")

    def fill_outline(self):
        o = self.otree
        o.delete(*o.get_children())
        tab = self.current()
        if not tab or tab.tree is None:
            return
        q = self.outline_filter.get().lower().strip()
        for n in tab.tree.children:
            label = n.get("name") or n.get("filename") or n.get("descname") or ""
            text = (label if n.name == "FightMove" else f"{n.name}   {label}") if label else n.name
            extra = n.get("descname") if n.name == "talent" else n.get("animenum") if n.name == "FightMove" else None
            if n.name == "FightMove" and tab.char:
                tt = tab.char.talent_for_move(n)
                if tt is not None and tt.get("descname"):
                    extra = f"{tt.get('descname')}" + (f"  ({extra})" if extra else "")
            if extra:
                text += f"   ·  {extra}"
            if q and q not in text.lower():
                continue
            kind = n.name if n.name in ("FightMove", "talent") else "other"
            color = {"FightMove": th.SYN_BLOCK, "talent": th.SYN_KEY}.get(kind, th.FAINT)
            o.insert("", "end", text=text, values=(n.line,), tags=(kind,), image=th.square(color, 14, 6))

    def _outline_menu(self, e):
        iid = self.otree.identify_row(e.y)
        if not iid:
            return
        if iid not in self.otree.selection():
            self.otree.selection_set(iid)
        n = len(self.otree.selection())
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Copiar bloco" if n == 1 else f"Copiar {n} blocos", accelerator="Ctrl+C",
                      command=lambda: self._outline_action("copy"))
        m.add_command(label="Excluir bloco..." if n == 1 else f"Excluir {n} blocos...", accelerator="Del",
                      command=lambda: self._outline_action("delete"))
        m.add_separator()
        m.add_command(label="Ctrl+clique ou Shift+clique seleciona vários", state="disabled")
        m.tk_popup(e.x_root, e.y_root)

    def _outline_action(self, what: str):
        tab = self.current()
        sel = self.otree.selection()
        if not tab or not sel:
            return
        lines = [self.otree.item(i, "values")[0] for i in sel]  # antes de reler: reler recria a lista
        nodes = tab.nodes_at_lines(lines)
        if what == "copy":
            tab.copy_nodes(nodes)
        else:
            tab.delete_nodes(nodes)
        return "break"

    def _outline_select(self, _e):
        sel = self.otree.selection()
        tab = self.current()
        if sel and tab:
            v = self.otree.item(sel[0], "values")
            if v:
                tab.goto_line(int(v[0]))

    def _prob_select(self, _e):
        sel = self.ptree.selection()
        tab = self.current()
        if sel and tab:
            tab.goto_line(int(re.sub(r"\D", "", str(self.ptree.item(sel[0], "values")[0]))))

    # ---- comandos ------------------------------------------------------------------------------------
    def open_dialog(self):
        p = filedialog.askopenfilename(parent=self, initialdir=os.path.join(self.proj.root, "data"),
                                       filetypes=[("Arquivos do MUA", "*.engb *.xmlb *.pkgb *.txt"), ("Todos", "*.*")])
        if p:
            self.open_file(os.path.normpath(p))

    def save_current(self):
        tab = self.current()
        if tab:
            tab.save()

    def save_all(self):
        for tab in self.editors():
            if tab.modified and not tab.save():
                self.tabs.select(tab)
                break

    def reload_current(self):
        tab = self.current()
        if tab and (not tab.modified or messagebox.askyesno("Recarregar", "Descartar as alterações não salvas desta aba?", parent=self)):
            tab.load()

    def after_save(self, tab: EditorTab):
        tab.proj._vars = None
        hs = [tab.proj.herostat_path] + list(getattr(tab.proj, "snippets", {}).values())
        if any(h and os.path.normcase(tab.path) == os.path.normcase(pj.binary_of(h)) for h in hs):
            self.reload_project()

    def reload_project(self):
        for p in self.all_projects():
            p._cache.clear()
            p._vars = None
            p.reload_characters()
        self.fill_files()
        self.fill_characters()
        self.status(f"Herostat relido: {len(self.proj.characters)} personagens")

    def close_tab(self, tab: EditorTab) -> bool:
        if tab.modified:
            r = messagebox.askyesnocancel("Fechar", f"Salvar e compilar {os.path.basename(tab.path)} antes de fechar?", parent=self)
            if r is None or (r and not tab.save()):
                return False
        self.tabs.forget(tab)
        tab.destroy()
        return True

    def close_current(self):
        tab = self.current()
        if tab:
            self.close_tab(tab)

    def quit_app(self):
        dirty = [t for t in self.editors() if t.modified]
        if dirty:
            r = messagebox.askyesnocancel("Sair", f"{len(dirty)} arquivo(s) com alterações não salvas.\nSalvar e compilar antes de sair?", parent=self)
            if r is None:
                return
            if r:
                for t in dirty:
                    if not t.save():
                        self.tabs.select(t)
                        return
        self.destroy()

    def set_language(self, code: str):
        """Grava o idioma escolhido e oferece reiniciar (os textos são montados na abertura)."""
        if code == i18n.current():
            return
        i18n.save(code)
        name = dict(i18n.LANGS)[code]
        if messagebox.askyesno("Idioma", f"Idioma alterado para {name}.\n\nO MUA Studio precisa ser reiniciado para aplicar. Reiniciar agora?", parent=self):
            import subprocess
            subprocess.Popen([sys.executable] + sys.argv, cwd=os.path.dirname(os.path.abspath(__file__)))
            self.quit_app()
        else:
            self.status(f"Idioma alterado para {name}. Reinicie o MUA Studio para aplicar.")
        self.lang_var.set(i18n.current())

    def set_theme(self, mode: str):
        """Grava o tema (claro/escuro) e oferece reiniciar: as cores são montadas na abertura."""
        if mode == th.read_mode():
            return
        th.save_mode(mode)
        name = dict(th.MODES)[mode]
        if messagebox.askyesno("Tema", f"Tema alterado para {name}.\n\nO MUA Studio precisa ser reiniciado para aplicar. "
                               "Reiniciar agora?", parent=self):
            import subprocess
            self.quit_app()  # pergunta dos arquivos não salvos; se cancelar, não reinicia
            try:
                alive = bool(self.winfo_exists())
            except tk.TclError:
                alive = False
            if not alive:
                subprocess.Popen([sys.executable] + sys.argv, cwd=os.path.dirname(os.path.abspath(__file__)))
        else:
            self.status(f"Tema alterado para {name}. Reinicie o MUA Studio para aplicar.")

    def goto_def(self):
        tab = self.current()
        if tab:
            tab.goto_definition()

    def edit_color(self):
        tab = self.current()
        if tab:
            tab.edit_color()

    def open_backups(self):
        os.makedirs(self.proj.backup_dir, exist_ok=True)
        os.startfile(self.proj.backup_dir)

    def open_var(self, var: str, char: pj.Character | None):
        rx = r"^\s*name\s*=\s*" + re.escape(var) + r"\s*;"
        paths = [char.talents_path] if char and char.talents_path else []
        proj = char.proj if char else self.proj
        d = os.path.join(proj.root, "data", "talents")
        for p in paths:
            if var.lower() in pj.talent_vars(proj.load(p)):
                return self.open_file(p, rx)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                if f.lower().endswith((".engb", ".xmlb")):
                    try:
                        if var.lower() in pj.talent_vars(proj.load(p)):
                            return self.open_file(p, rx)
                    except Exception:
                        pass
        self.status(f"%{var} não esta definida em nenhum arquivo de talentos")

    def open_talent(self, name: str, char: pj.Character | None):
        rx = r"^\s*name\s*=\s*" + re.escape(name) + r"\s*;"
        if char and char.talents_path:
            root = char.proj.load(char.talents_path)
            if any(t.get("name", "").lower() == name.lower() for t in root.children):
                return self.open_file(char.talents_path, rx)
        self.status(f"Talento '{name}' não esta nos talentos do personagem (pode ser um talento comum do jogo)")

    def colors_dialog(self):
        tab = self.current()
        if tab:
            ColorsDialog(self, tab)

    def copy_power(self, src=None, talent=None, dst=None, move=None, extra=()):
        tab = self.current()
        if src is None and dst is None and tab and tab.char:
            src = tab.char
        return CopyPowerDialog(self, src, talent, dst, move, extra)

    def open_herostat(self):
        if not self.proj.herostat_path:
            return self.status("Esta pasta não tem data/herostat")
        for t in self.tabs.tabs():
            w = self.nametowidget(t)
            if isinstance(w, extras.HerostatTab):
                self.tabs.select(w)
                return w
        w = extras.HerostatTab(self)
        self.tabs.add(w, text="Herostat do jogo", image=th.dot(th.SYN_KEY, 14, 7), compound="left")
        self.tabs.select(w)
        return w

    def npc_power(self, char=None, talent=None):
        return extras.NpcPowerDialog(self, char or self.selected_char(), talent)

    def npc_power_to(self, npc: pj.Character):
        d = self.npc_power()
        i = next((i for i, n in enumerate(d.npcs) if n.name == npc.name), -1)
        if i >= 0:
            d.dst_cb.current(i)
            d.dst_changed()
        return d

    def open_npcstat(self, select: str | None = None):
        if not self.proj.resolve("data/npcstat"):
            return self.status("Esta pasta não tem data/npcstat")
        for t in self.tabs.tabs():
            w = self.nametowidget(t)
            if isinstance(w, extras.NpcstatTab):
                self.tabs.select(w)
                if select:
                    w.select(select)
                return w
        w = extras.NpcstatTab(self)
        if select:
            w.select(select)
        self.tabs.add(w, text="NPCStat", image=th.dot(th.ERR_SOFT, 14, 7), compound="left")
        self.tabs.select(w)
        return w

    def organize_powers(self, char=None):
        char = char or self.selected_char()
        if not char or not char.talents_path:
            return self.status("Escolha um personagem (com arquivo de talentos) para organizar os poderes")
        return extras.OrganizeDialog(self, char)

    def rename_effect(self, char, ref: str):
        base = ref.replace("\\", "/").split("/")[-1]
        new = simpledialog.askstring("Renomear efeito", f"Novo nome para effects/{ref}\n\nSó o nome fica na mesma pasta; "
                                     "também aceita char/<pasta>/<nome>. Todo powerstyle, entidade, talento e pacote que cita "
                                     "o efeito é atualizado junto.", initialvalue=base, parent=self)
        if not new or not new.strip():
            return
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            plan, sp, dp = ops.rename_effect_plan(char, ref, new)
        finally:
            self.configure(cursor="")
        if plan.errors:
            return messagebox.showerror("Renomear efeito", "\n".join(plan.errors), parent=self)
        paths = [c.path for c in plan.changes] + [sp]
        bad = [t for t in self.editors() if t.modified and any(os.path.normcase(t.path) == os.path.normcase(x) for x in paths)]
        if bad:
            return messagebox.showwarning("Salve antes", "Arquivos abertos com alterações não salvas:\n\n"
                                          + "\n".join(os.path.basename(t.path) for t in bad), parent=self)
        if not extras.confirm_plan(self, "Renomear efeito", plan.describe(char.proj), "Renomear"):
            return
        try:
            written = ops.rename_effect_apply(plan, sp, dp)
        except Exception as e:
            return messagebox.showerror("Renomear efeito", f"Nada foi alterado.\n\n{e}", parent=self)
        for t in list(self.editors()):
            if os.path.normcase(t.path) == os.path.normcase(sp):  # a aba do arquivo antigo passa a ser a do novo
                self.tabs.forget(t)
                t.destroy()
                self.open_file(dp)
        extras.reload_tabs(self, written)
        self.fill_characters()
        new_ref = plan.info[0].split("->")[-1].strip().removeprefix("effects/")
        self.status(f"Efeito renomeado para {new_ref}: {len(plan.changes)} arquivo(s) atualizados (com backup)")

    def copy_resources(self, char=None, preselect=()):
        return extras.ResourceCopyDialog(self, char or self.selected_char(), None, preselect)

    def audio_editor(self, char=None):
        return audio_ui.AudioEditor(self, char or self.selected_char())

    def anim_mixer(self, char=None):
        return extras.AnimMixer(self, char or self.selected_char())

    def clone_character(self, char=None):
        return extras.CloneDialog(self, char or self.selected_char())

    def export_character(self, char=None):
        char = char or self.selected_char()
        if not char:
            return self.status("Escolha um personagem na lista para compilar")
        return extras.export_character(self, char)

    def selected_char(self) -> pj.Character | None:
        tab = self.current()
        if tab and tab.char:
            return tab.char
        sel = self.tabs.select()
        w = self.nametowidget(sel) if sel else None
        if isinstance(w, SheetTab):
            return w.char
        iid = self.ctree.focus()
        while iid:
            act = self.actions.get(iid)
            if act and act[0] == "char":
                return act[1]
            iid = self.ctree.parent(iid)
        return None

    def open_sheet(self, char: pj.Character | None = None):
        char = char or self.selected_char()
        if not char:
            return self.status("Escolha um personagem na lista (ou abra um arquivo dele) para ver a ficha")
        for t in self.tabs.tabs():
            w = self.nametowidget(t)
            if isinstance(w, SheetTab) and w.char.name == char.name:
                w.fill()
                self.tabs.select(w)
                return w
        w = SheetTab(self, char)
        self.tabs.add(w, text=f"Ficha: {char.display}", image=th.dot(th.AMBER, 14, 7), compound="left")
        self.tabs.select(w)
        return w

    def explain(self):
        tab = self.current()
        if tab:
            tab.explain()
        else:
            self.status("Abra o powerstyle de um personagem e coloque o cursor dentro de um poder")

    def explain_talent(self, char: pj.Character, talent_name: str):
        if char.talents_path:
            t = next((x for x in char.proj.load(char.talents_path).children
                      if x.name == "talent" and x.get("name", "").lower() == talent_name.lower()), None)
            if t is not None:
                ExplainDialog(self, char, t)


# ============================================================ ficha e explicação
def level_text(talent: xmlb.Node) -> str:
    lv = next((c for c in talent.children if c.name == "level"), None)
    return (lv.get("description") or "").replace("\\n", "   |   ") if lv is not None else ""


class SheetTab(ttk.Frame):
    """Ficha do personagem em cartões: herostat, skins, poderes (clicáveis) e outros talentos. Somente leitura."""

    def __init__(self, app: "App", char: pj.Character):
        super().__init__(app.tabs)
        self.app, self.char = app, char
        self.sf = th.ScrollFrame(self, bg=BG)
        self.sf.pack(fill="both", expand=True)
        self.fill()

    @staticmethod
    def _wrap(card: tk.Frame, *labels, pad=28):
        card.bind("<Configure>", lambda e: [l.configure(wraplength=max(120, e.width - pad)) for l in labels], add="+")

    def fill(self):
        c, proj, app = self.char, self.char.proj, self.app
        page = self.sf.inner
        for w in page.winfo_children():
            w.destroy()
        box = tk.Frame(page, bg=BG)
        box.pack(fill="both", expand=True, padx=28, pady=22)
        s = c.stats

        # cabeçalho
        top = tk.Frame(box, bg=BG)
        top.pack(fill="x")
        btns = tk.Frame(top, bg=BG)
        btns.pack(side="right", anchor="n")
        left = tk.Frame(top, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        r = tk.Frame(left, bg=BG)
        r.pack(anchor="w")
        st_color, st_text = app.char_status(c)
        tk.Label(r, image=th.dot(st_color, 20, 12), bg=BG).pack(side="left")
        tk.Label(r, text=c.display, font=th.H1, bg=BG, fg=th.STRONG).pack(side="left", padx=(6, 12))
        th.chip(r, c.name, "red", font=th.MONO_S, padx=9, pady=2).pack(side="left")
        tk.Label(r, text=st_text, font=th.UI_XS, bg=BG, fg=st_color).pack(side="left", padx=10)
        if proj is not app.proj:
            th.chip(r, proj.label, "dim", font=th.UI_XS, padx=8, pady=2).pack(side="left", padx=6)
        meta = tk.Frame(left, bg=BG)
        meta.pack(anchor="w", pady=(8, 0))
        for i, (lab, val) in enumerate((("powerstyle", c.powerstyle), ("animações", c.anims), ("banco de som", c.sounddir))):
            if i:
                tk.Label(meta, text="|", font=th.MONO_S, bg=BG, fg=th.FAINT).pack(side="left", padx=8)
            tk.Label(meta, text=lab + ":", font=th.MONO_S, bg=BG, fg=DIM).pack(side="left")
            tk.Label(meta, text=val or "-", font=th.MONO_S, bg=BG, fg=FG).pack(side="left", padx=(5, 0))
        th.ToolButton(btns, "Copiar poder deste herói", "copy", lambda: app.copy_power(c), kind="accent", bg=BG).pack(side="right")
        th.ToolButton(btns, "Recarregar", None, self.fill, bg=BG).pack(side="right", padx=8)
        th.hline(box, pady=(18, 0))

        # atributos
        th.section_title(box, "Atributos base (herostat)")
        g = th.CardGrid(box, minw=128)
        g.pack(fill="x")
        for lab, key, color in (("Corpo (body)", "body", th.STRONG), ("Mente (mind)", "mind", th.STRONG),
                                ("Força (strength)", "strength", th.STRONG), ("Nível", "level", th.STRONG),
                                ("Time", "team", th.OK), ("Autospend", "autospend", th.SYN_KEY),
                                ("Moveset", "moveset1", FG), ("Menu", "menulocation", th.AMBER)):
            v = str(s.get(key, "") or "-")
            numeric = v.lstrip("-").replace(".", "", 1).isdigit()
            cd = th.card(g)
            tk.Label(cd, text=lab, font=th.UI_XS, bg=PANEL, fg=DIM, anchor="w").pack(fill="x", padx=11, pady=(9, 0))
            vl = tk.Label(cd, text=v, font=(th.MONO[0], 15 if numeric else 9, "bold"), bg=PANEL, fg=color,
                          anchor="w", justify="left")
            vl.pack(fill="x", padx=11, pady=(3 if numeric else 7, 10))
            self._wrap(cd, vl, pad=22)
            g.add(cd)

        # skins
        th.section_title(box, f"Skins registradas ({len(c.skins)})")
        if c.skins:
            g = th.CardGrid(box, minw=190)
            g.pack(fill="x")
            for num, name in c.skins:
                cd = th.card(g)
                row = tk.Frame(cd, bg=PANEL)
                row.pack(fill="x", padx=12, pady=11)
                tk.Label(row, text=name or "(sem nome)", font=th.UI_B, bg=PANEL, fg=th.STRONG if name else DIM).pack(side="left")
                tk.Label(row, text=num, font=th.MONO_S, bg=BG, fg=th.SYN_NUM, padx=7, pady=2, highlightthickness=1,
                         highlightbackground=LINE).pack(side="right")
                g.add(cd)
        else:
            tk.Label(box, text="Nenhuma skin no herostat.", font=th.UI_S, bg=BG, fg=DIM, anchor="w").pack(fill="x")

        troot = None
        if c.talents_path:
            try:
                troot = proj.load(c.talents_path)
            except Exception:
                pass
        tal = {x.get("name", "").lower(): x for x in troot.children if x.name == "talent"} if troot else {}
        info_moves: dict[str, list] = {}
        if c.powerstyle_path:
            try:
                for m in proj.load(c.powerstyle_path).children:
                    if m.name == "FightMove":
                        tt = c.talent_for_move(m)
                        if tt is not None:
                            info_moves.setdefault(tt.get("name", "").lower(), []).append(m)
            except Exception:
                pass

        # poderes (cartões clicáveis: abrem o powerstyle no move)
        powers = [x for x in tal.values() if x.get("power")]
        th.section_title(box, f"Poderes do personagem ({len(powers)})  ·  clique para abrir no powerstyle")
        g = th.CardGrid(box, minw=380, gap=10)
        g.pack(fill="x")
        for x in powers:
            tn, mv = x.get("name", ""), x.get("power", "")
            cd = th.card(g, command=lambda mv=mv: app.open_file(c.powerstyle_path, r"^\s*name\s*=\s*" + re.escape(mv) + r"\s*;"))
            hd = tk.Frame(cd, bg=PANEL)
            hd.pack(fill="x", padx=14, pady=(12, 0))
            tk.Label(hd, text=x.get("descname") or tn, font=th.H3, bg=PANEL, fg=th.SYN_KEY).pack(side="left")
            if x.get("descshort"):
                th.chip(hd, x.get("descshort"), "purple", font=th.UI_XS, padx=7, pady=1).pack(side="right")
            tk.Label(cd, text=f"{tn}  →  {mv}", font=th.MONO_S, bg=PANEL, fg=th.SYN_NUM, anchor="w").pack(fill="x", padx=14, pady=(2, 0))
            d = tk.Label(cd, text=x.get("description", "(sem descrição)"), font=th.UI_S, bg=PANEL, fg=FG,
                         justify="left", anchor="w")
            d.pack(fill="x", padx=14, pady=(8, 0))
            labels = [d]
            lt = level_text(x)
            if lt:
                ll = tk.Label(cd, text=lt, font=th.UI_XS, bg=PANEL, fg=DIM, justify="left", anchor="w")
                ll.pack(fill="x", padx=14, pady=(6, 0))
                labels.append(ll)
            mvs = info_moves.get(tn.lower(), [])
            tk.Frame(cd, bg=LINE, height=1).pack(fill="x", padx=14, pady=(10, 0))
            ml = tk.Label(cd, text=("moves: " + ",  ".join(f"{m.get('name')} ({m.get('animenum', '-')})" for m in mvs))
                          if mvs else "nenhum FightMove encontrado no powerstyle",
                          font=th.MONO_XS, bg=PANEL, fg=DIM, justify="left", anchor="w")
            ml.pack(fill="x", padx=14, pady=(6, 0))
            labels.append(ml)
            try:
                pfx = ops.power_effects(c, tn)
            except Exception:
                pfx = []
            el = tk.Label(cd, text=("efeitos: " + ",  ".join(r.split("/")[-1] for r in pfx)) if pfx else "efeitos: nenhum",
                          font=th.MONO_XS, bg=PANEL, fg=th.SYN_PATH if pfx else DIM, justify="left", anchor="w")
            el.pack(fill="x", padx=14, pady=(4, 12))
            labels.append(el)
            self._wrap(cd, *labels)
            g.add(cd)

        # talentos do herostat
        hs = [(x.get("name", ""), x.get("level", "")) for x in s.children if x.name == "talent"]
        th.section_title(box, f"Talentos iniciais no herostat ({len(hs)})")
        if hs:
            lst = th.card(box)
            lst.pack(fill="x")
            for i, (name, lv) in enumerate(hs):
                if i:
                    tk.Frame(lst, bg=th.mix(PANEL, LINE, .6), height=1).pack(fill="x")
                row = tk.Frame(lst, bg=PANEL)
                row.pack(fill="x", padx=12, pady=5)
                tk.Label(row, text=name, font=th.MONO_S, bg=PANEL, fg=th.SYN_NUM, width=26, anchor="w").pack(side="left")
                tk.Label(row, text=f"nível {lv}" if lv else "", font=th.UI_XS, bg=PANEL, fg=DIM, width=9, anchor="w").pack(side="left")
                d = tal.get(name.lower())
                tk.Label(row, text=d.get("descname", "") if d is not None else "(talento comum do jogo)", font=th.UI_S,
                         bg=PANEL, fg=FG if d is not None else DIM, anchor="w").pack(side="left", fill="x", expand=True)

        # outros talentos
        others = [x for x in tal.values() if not x.get("power")]
        th.section_title(box, f"Outros talentos: passivos, roupas, etc. ({len(others)})")
        g = th.CardGrid(box, minw=280)
        g.pack(fill="x")
        for x in others:
            tn = x.get("name", "")
            cd = th.card(g, command=lambda tn=tn: app.open_talent(tn, c))
            hd = tk.Frame(cd, bg=PANEL)
            hd.pack(fill="x", padx=12, pady=(10, 0))
            tk.Label(hd, text=x.get("descname") or tn, font=th.UI_B, bg=PANEL, fg=th.STRONG).pack(side="left")
            if x.get("type"):
                th.chip(hd, x.get("type"), "purple", font=th.MONO_XS).pack(side="right")
            tk.Label(cd, text=tn, font=th.MONO_XS, bg=PANEL, fg=DIM, anchor="w").pack(fill="x", padx=12, pady=(2, 0))
            labels = []
            if x.get("description"):
                dl = tk.Label(cd, text=x.get("description"), font=th.UI_XS, bg=PANEL, fg=DIM, justify="left", anchor="w")
                dl.pack(fill="x", padx=12, pady=(6, 0))
                labels.append(dl)
            tk.Frame(cd, bg=PANEL, height=10).pack(fill="x")
            self._wrap(cd, *labels, pad=24)
            g.add(cd)
        tk.Frame(box, bg=BG, height=20).pack(fill="x")
        self.sf.top()


class ExplainDialog(tk.Toplevel):
    def __init__(self, app: "App", char: pj.Character, talent: xmlb.Node, move_name: str = ""):
        super().__init__(app)
        self.title("Explicar poder")
        self.configure(bg=PANEL)
        extras.fit(self, 620, 400)
        self.minsize(480, 300)
        self.transient(app)
        f = tk.Frame(self, bg=PANEL)
        f.pack(fill="both", expand=True, padx=22, pady=(18, 12))
        tags = [t for t in (talent.get("descshort", ""), "Talento ativo" if talent.get("power") else "Talento") if t]
        th.chip(f, "  •  ".join(tags).upper(), "purple", font=th.MONO_XS, padx=8, pady=2).pack(anchor="w")
        tk.Label(f, text=talent.get("descname") or talent.get("name", ""), font=(th.H1[0], 18, "bold"), bg=PANEL,
                 fg=th.STRONG, anchor="w").pack(fill="x", pady=(6, 4))
        desc = tk.Label(f, text=talent.get("description", "(sem descrição)"), font=th.UI, bg=PANEL, fg=FG,
                        justify="left", anchor="w")
        desc.pack(fill="x")
        wrap = [desc]
        lt = level_text(talent)
        if lt:
            lb = tk.Frame(f, bg=BG, highlightthickness=1, highlightbackground=LINE)
            lb.pack(fill="x", pady=(12, 0))
            ll = tk.Label(lb, text=lt, font=th.MONO_S, bg=BG, fg=DIM, justify="left", anchor="w")
            ll.pack(fill="x", padx=10, pady=8)
            wrap.append(ll)
        f.bind("<Configure>", lambda e: [w.configure(wraplength=max(200, e.width - 24)) for w in wrap])
        try:
            fx = ops.power_effects(char, talent.get("name", ""))
        except Exception:
            fx = []
        th.hline(f, pady=(14, 6))
        tk.Label(f, text=f"Efeitos deste poder ({len(fx)})" if fx else "Este poder não usa efeitos", font=th.UI_SB, bg=PANEL,
                 fg=th.SYN_PATH if fx else DIM, anchor="w").pack(fill="x")
        if fx:
            fl = tk.Frame(f, bg=PANEL)
            fl.pack(fill="x", pady=(2, 0))
            for i, ref in enumerate(fx):
                p = char.proj.effect_path(ref)
                lb = tk.Label(fl, text=ref, font=th.MONO_XS, bg=PANEL, fg=ACCENT if p else th.ERR_SOFT,
                              cursor="hand2" if p else "", anchor="w")
                lb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 18))
                if p:
                    lb.bind("<Button-1>", lambda e, p=p: (app.open_file(p), self.destroy()))
            extras.fit(self, 680, 470 + 18 * ((len(fx) + 1) // 2))
        th.hline(f, pady=(10, 6))
        meta = tk.Frame(f, bg=PANEL)
        meta.pack(fill="x")
        tk.Label(meta, text=f"{char.display}   |   talento {talent.get('name', '')}" + (f"   |   move {move_name}" if move_name else ""),
                 font=th.MONO_XS, bg=PANEL, fg=DIM).pack(side="left")
        tk.Label(meta, text=f"power = {talent.get('power', '-')}", font=(th.MONO_XS[0], 8, "bold"), bg=PANEL,
                 fg=th.SYN_NUM).pack(side="right")
        bar = tk.Frame(self, bg=th.mix(PANEL, BG, .5))
        bar.pack(fill="x", side="bottom")
        th.hline(bar, side="top")
        row = tk.Frame(bar, bg=bar["bg"])
        row.pack(fill="x", padx=16, pady=10)
        link = tk.Label(row, text="Abrir ficha do personagem", font=th.UI_S, bg=bar["bg"], fg=ACCENT, cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: (app.open_sheet(char), self.destroy()))
        th.ToolButton(row, "Fechar", None, self.destroy, kind="accent", bg=bar["bg"]).pack(side="right")
        th.ToolButton(row, "Ir para o talento", None, lambda: (app.open_talent(talent.get("name", ""), char), self.destroy()),
                      bg=bar["bg"]).pack(side="right", padx=8)
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_set()


# ================================================================ dialogo de cores
class ColorsDialog(tk.Toplevel):
    def __init__(self, app: App, tab: EditorTab):
        super().__init__(app)
        self.app, self.tab = app, tab
        self.title(f"Cores de {os.path.basename(tab.path)}")
        self.configure(bg=PANEL)
        extras.fit(self, 680, 520)
        self.transient(app)
        th.dialog_header(self, f"Cores de {os.path.basename(tab.path)}", "palette", th.PINK)
        ttk.Label(self, text="Cores usadas neste arquivo. As alterações vao para o editor; salve com Ctrl+S.",
                  style="Dim.TLabel", wraplength=490).pack(anchor="w", padx=10, pady=(10, 4))
        self.canvas = tk.Canvas(self, bg=PANEL, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=6)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-e.delta // 120, "units"))
        b = ttk.Frame(self, padding=10)
        b.pack(fill="x")
        ttk.Button(b, text="Trocar a cor selecionada...", command=self.change).pack(side="left")
        ttk.Button(b, text="Recolorir tudo para um tom...", command=self.recolor).pack(side="left", padx=8)
        ttk.Button(b, text="Fechar", command=self.destroy).pack(side="right")
        self.selected: int | None = None
        self.rows: list[int] = []
        self.fill()

    def fill(self):
        c = self.canvas
        c.delete("all")
        vals = self.tab.color_values()
        self.rows = sorted(vals, key=lambda v: -len(vals[v]))
        if self.selected not in vals:
            self.selected = self.rows[0] if self.rows else None
        for i, v in enumerate(self.rows):
            y = 8 + i * 38
            r, g, b, a = pj.color_to_rgb(v)
            sel = v == self.selected
            c.create_rectangle(4, y - 4, max(c.winfo_width(), 600) - 6, y + 28, fill=SEL if sel else PANEL,
                               outline=ACCENT if sel else LINE)
            c.create_rectangle(12, y + 1, 52, y + 23, fill=pj.color_hex(v), outline="#000000")
            c.create_text(64, y + 6, anchor="w", fill=th.STRONG if sel else FG, font=th.MONO + ("bold",), text=str(v))
            c.create_text(64 + 11 * 8, y + 6, anchor="w", fill=DIM, font=th.MONO_S,
                          text=f"RGB {r}, {g}, {b}  |  alfa {a}")
            c.create_text(64, y + 19, anchor="w", fill=th.INFO_FG if sel else DIM, font=th.UI_XS,
                          text=f"usada {len(vals[v])}x (primeira na linha {vals[v][0]})")
        if not self.rows:
            c.create_text(14, 20, anchor="w", fill=DIM, font=UI, text="Este arquivo não tem propriedades de cor.")
        c.configure(scrollregion=(0, 0, 500, 16 + len(self.rows) * 38))

    def _click(self, e):
        i = int((self.canvas.canvasy(e.y) - 4) // 38)
        if 0 <= i < len(self.rows):
            self.selected = self.rows[i]
            self.fill()

    def change(self):
        if self.selected is None:
            return
        r, g, b, a = pj.color_to_rgb(self.selected)
        res = colorchooser.askcolor(color=(r, g, b), parent=self, title="Nova cor")
        if res and res[0]:
            nr, ng, nb = (int(round(x)) for x in res[0])
            new = pj.rgb_to_color(nr, ng, nb, a)
            n = self.tab.replace_colors({self.selected: new})
            self.selected = new
            self.app.status(f"{n} linha(s) de cor alteradas")
            self.fill()

    def recolor(self):
        res = colorchooser.askcolor(parent=self, title="Tom de destino (cinzas, branco e preto são mantidos)")
        if not (res and res[0]):
            return
        th, ts, _ = colorsys.rgb_to_hsv(*(x / 255 for x in res[0]))
        mapping = {}
        for v in self.rows:
            r, g, b, a = pj.color_to_rgb(v)
            h, s, val = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s < 0.12 or val < 0.05:
                continue
            nr, ng, nb = colorsys.hsv_to_rgb(th, min(1.0, s * (ts / max(s, 0.01)) ** 0.5), val)
            mapping[v] = pj.rgb_to_color(round(nr * 255), round(ng * 255), round(nb * 255), a)
        n = self.tab.replace_colors(mapping)
        self.app.status(f"{n} linha(s) de cor recoloridas")
        self.selected = None
        self.fill()


# ============================================================ dialogo copiar poder
class CopyPowerDialog(tk.Toplevel):
    def __init__(self, app: App, src=None, talent=None, dst=None, move=None, extra=()):
        super().__init__(app)
        self.app, self.proj = app, app.proj
        self._init_move = move
        self._extra = (move or "").lower(), tuple(extra)
        self._done = ""
        self._was_move = False
        self.title("Copiar ou substituir poder / FightMove")
        self.configure(bg=PANEL)
        th.dialog_header(self, "Copiar ou substituir poder / FightMove", "swap", ACCENT)
        extras.fit(self, 1160, 900)
        self.transient(app)
        self.info: transfer.PowerInfo | None = None
        self.plan: transfer.Plan | None = None
        self.checked: dict[str, bool] = {}
        self.chars = app.all_characters()
        self.names = [f"{c.display}   ({c.name})" + ("" if c.proj is app.proj else f"      [{c.proj.label}]") for c in self.chars]

        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)
        ttk.Label(top, text="De:").grid(row=0, column=0, sticky="w")
        self.src_cb = extras.SearchCombo(top, values=self.names)
        self.src_cb.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(top, text="Para:").grid(row=0, column=2, sticky="w")
        self.dst_cb = extras.SearchCombo(top, values=self.names)
        self.dst_cb.grid(row=0, column=3, sticky="ew", padx=8)
        ttk.Label(top, text="Poder:").grid(row=1, column=0, sticky="w", pady=8)
        self.pow_cb = ttk.Combobox(top, state="readonly")
        self.pow_cb.grid(row=1, column=1, sticky="ew", padx=8)
        self.src_desc = ttk.Label(top, style="Dim.TLabel", wraplength=470, justify="left")
        self.src_desc.grid(row=1, column=2, columnspan=2, sticky="w", padx=8)
        self.mode_var = tk.StringVar(value="add")
        self.tal_var, self.main_var = tk.StringVar(), tk.StringVar()
        mf = ttk.Frame(top)
        mf.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(2, 6))
        ttk.Radiobutton(mf, text="Adicionar como poder novo:  talento", value="add", variable=self.mode_var,
                        command=self._mode_changed).grid(row=0, column=0, sticky="w")
        self.tal_entry = ttk.Entry(mf, textvariable=self.tal_var, width=22)
        self.tal_entry.grid(row=0, column=1, padx=6)
        ttk.Label(mf, text="move").grid(row=0, column=2)
        self.main_entry = ttk.Entry(mf, textvariable=self.main_var, width=12)
        self.main_entry.grid(row=0, column=3, padx=6, sticky="w")
        ttk.Radiobutton(mf, text="Substituir este poder do destino:", value="replace", variable=self.mode_var,
                        command=self._mode_changed).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.rep_cb = ttk.Combobox(mf, state="disabled", width=52)
        self.rep_cb.grid(row=1, column=1, columnspan=3, padx=6, pady=(6, 0), sticky="w")
        self.rep_cb.bind("<<ComboboxSelected>>", lambda e: (self._show_rep_desc(), self.preview()))
        self.rep_desc = ttk.Label(mf, style="Dim.TLabel", wraplength=420, justify="left")
        self.rep_desc.grid(row=1, column=4, sticky="w", padx=8, pady=(6, 0))
        self.dst_powers: list[tuple[str, str, str]] = []

        of = ttk.Frame(top)
        of.grid(row=3, column=0, columnspan=4, sticky="w")
        self.indep_var = tk.BooleanVar(value=True)
        self.anim_var = tk.BooleanVar(value=app.anim_tools.available)
        self.fx_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(of, text="Copiar efeitos e entidades para a pasta do destino (cópia independente, pode recolorir)",
                        variable=self.indep_var, command=self.preview).pack(anchor="w")
        ac = ttk.Checkbutton(of, text="Importar as animações para o set do destino" +
                             ("" if app.anim_tools.available else "   (ferramenta de animação não encontrada em tools/)"),
                             variable=self.anim_var, command=self.preview)
        ac.pack(anchor="w")
        if not app.anim_tools.available:
            ac.state(["disabled"])
        self.snd_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(of, text="Copiar os sons do poder para o banco de som do destino",
                        variable=self.snd_var, command=self.preview).pack(anchor="w")
        ttk.Checkbutton(of, text="Adicionar os efeitos aos pacotes do destino (quando o pacote lista efeitos)",
                        variable=self.fx_var, command=self.preview).pack(anchor="w")

        mid = ttk.Panedwindow(self, orient="horizontal")
        mid.pack(fill="both", expand=True, padx=12)
        lf = ttk.Frame(mid)
        ttk.Label(lf, text="FightMoves do poder (clique para marcar/desmarcar)", style="Dim.TLabel").pack(anchor="w")
        self.mv = ttk.Treeview(lf, show="tree", selectmode="none", height=12)
        self.mv.pack(fill="both", expand=True, pady=4)
        self.mv.bind("<Button-1>", self._toggle)
        mid.add(lf, weight=1)
        rf = ttk.Frame(mid)
        ttk.Label(rf, text="Prévia (nada é gravado antes de clicar em Aplicar)", style="Dim.TLabel").pack(anchor="w")
        self.out = i18n.mark_output(tk.Text(rf, bg=BG, fg=FG, font=("Consolas", 10), wrap="word", borderwidth=0, highlightthickness=0, padx=8, pady=6))
        self.out.pack(fill="both", expand=True, pady=4)
        self.out.tag_configure("warn", foreground=th.WARN)
        self.out.tag_configure("err", foreground=th.ERR_SOFT)
        self.out.tag_configure("head", foreground=th.SYN_KEY)
        mid.add(rf, weight=3)

        bot = ttk.Frame(self, padding=12)
        bot.pack(fill="x", side="bottom", before=mid)  # reservado primeiro: os botões nunca ficam fora da janela
        ttk.Button(bot, text="Atualizar prévia", command=self.preview).pack(side="left")
        ttk.Button(bot, text="Fechar", command=self.destroy).pack(side="right")
        self.apply_btn = ttk.Button(bot, text="Aplicar e compilar", style="Accent.TButton", command=self.apply)
        self.apply_btn.pack(side="right", padx=8)

        self.src_cb.bind("<<ComboboxSelected>>", lambda e: self._src_changed())
        self.dst_cb.bind("<<ComboboxSelected>>", lambda e: self._dst_changed())
        self.pow_cb.bind("<<ComboboxSelected>>", lambda e: self._power_changed())
        for v in (self.tal_var, self.main_var):
            v.trace_add("write", lambda *a: self._schedule())
        self._job = None
        self._loading = False
        if src:
            self.src_cb.current(extras.char_index(self.chars, src))
            self._src_changed(talent)
        if dst:
            self.dst_cb.current(extras.char_index(self.chars, dst))
            self._dst_changed()
        self.preview()

    def _char(self, cb) -> pj.Character | None:
        i = cb.current()
        return self.chars[i] if i >= 0 else None

    def _src_changed(self, talent=None):
        c = self._char(self.src_cb)
        self.powers = c.powers() if c else []
        labels = [f"{dn or tn}   [{tn} / {mv}]" for tn, dn, mv in self.powers]
        if c and c.powerstyle_path:  # depois dos poderes, todos os FightMoves (ataques, agarrões...) para copiar soltos
            seen = set()
            try:
                for m in c.proj.load(c.powerstyle_path).children:
                    nm = m.get("name") or ""
                    if m.name == "FightMove" and nm and nm.lower() not in seen:
                        seen.add(nm.lower())
                        self.powers.append((None, m.get("animenum", ""), nm))
                        labels.append(f"FightMove solto:  {nm}   [{m.get('animenum', '-')}]")
            except Exception:
                pass
        self.pow_cb.configure(values=labels)
        mv0, self._init_move = self._init_move, None
        idx = next((i for i, p in enumerate(self.powers) if (talent and p[0] and p[0].lower() == talent.lower())
                    or (mv0 and p[0] is None and p[2].lower() == mv0.lower())), 0)
        if self.powers:
            self.pow_cb.current(idx)
        else:
            self.pow_cb.set("")
        self._power_changed()

    def _power_changed(self):
        self.info = None
        c = self._char(self.src_cb)
        i = self.pow_cb.current()
        if c and i >= 0:
            try:
                tn, _, mv = self.powers[i]
                extra = self._extra[1] if not tn and mv.lower() == self._extra[0] else ()
                self.info = transfer.PowerInfo(c.proj, c, tn) if tn else transfer.PowerInfo(c.proj, c, move_name=mv, extra_moves=extra)
            except Exception as e:
                self._show(f"Erro ao analisar o poder: {e}", error=True)
        self.checked = {n.lower(): own for n, own in self.info.move_names()} if self.info else {}
        self._fill_moves()
        is_move = self._is_move()
        if is_move and not self._was_move:
            self.mode_var.set("replace")  # ataque comum: o normal é trocar o de mesmo nome
        self._was_move = is_move
        self._show_src_desc()
        self._mode_changed()

    def _is_move(self) -> bool:
        return self.info is not None and self.info.talent is None

    @staticmethod
    def _describe(t) -> str:
        if t is None:
            return ""
        return f"{t.get('descname') or t.get('name', '')}  [{t.get('descshort', '-')}]\n{t.get('description', '(sem descrição)')}"

    def _show_src_desc(self):
        if self.info is None:
            self.src_desc.configure(text="")
        elif self.info.talent is None:
            self.src_desc.configure(text="FightMove solto (não pertence a nenhum talento): ataque, agarrão, movimento...")
        else:
            self.src_desc.configure(text=self._describe(self.info.talent))

    def _show_rep_desc(self):
        d, i = self._char(self.dst_cb), self.rep_cb.current()
        text = ""
        if d and self.mode_var.get() == "replace" and not self._is_move() and 0 <= i < len(self.dst_powers) and d.talents_path:
            try:
                t = next((x for x in d.proj.load(d.talents_path).children
                          if x.name == "talent" and x.get("name") == self.dst_powers[i][0]), None)
                text = "Sai: " + self._describe(t)
            except Exception:
                pass
        self.rep_desc.configure(text=text)

    def _dst_changed(self):
        d = self._char(self.dst_cb)
        if d:
            self._loading = True
            t, m = transfer.suggest_names(d.proj, d)
            self.tal_var.set(t)
            self.main_var.set(m)
            self._loading = False
            self.dst_powers = d.powers()
            self.rep_cb.configure(values=[f"{dn or tn}   [{tn} / {mv}]" for tn, dn, mv in self.dst_powers])
            self.rep_cb.set("")
            if self.dst_powers:
                self.rep_cb.current(0)
        self._mode_changed()

    def _mode_changed(self):
        rep = self.mode_var.get() == "replace"
        mv = self._is_move()
        if mv:
            self.rep_cb.configure(state="normal")
            self.rep_cb.set("(os FightMoves de mesmo nome que o destino já tem)")
        elif self.rep_cb.current() < 0:
            self.rep_cb.set("")
            if self.dst_powers:
                self.rep_cb.current(0)
        self.rep_cb.configure(state="readonly" if rep and not mv else "disabled")
        for e in (self.tal_entry, self.main_entry):
            e.state(["disabled"] if rep or mv else ["!disabled"])
        self._show_rep_desc()
        self.preview()

    def _replace_name(self) -> str | None:
        if self.mode_var.get() != "replace" or self._is_move():
            return None
        i = self.rep_cb.current()
        return self.dst_powers[i][0] if 0 <= i < len(self.dst_powers) else ""

    def _fill_moves(self):
        self.mv.delete(*self.mv.get_children())
        if not self.info:
            return
        for n, own in self.info.move_names():
            mark = "[x]" if self.checked.get(n.lower()) else "[  ]"
            self.mv.insert("", "end", iid=n.lower(), text=f"{mark}  {n}" + ("" if own else "   (comum, o destino usa o dele)"))

    def _toggle(self, e):
        iid = self.mv.identify_row(e.y)
        if iid:
            self.checked[iid] = not self.checked.get(iid)
            self._fill_moves()
            self.preview()

    def _schedule(self):
        if self._loading:
            return
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(350, self.preview)

    def _show(self, text: str, error: bool = False):
        o = self.out
        o.configure(state="normal")
        o.delete("1.0", "end")
        for line in text.split("\n"):
            tag = "err" if error or line.lstrip().startswith("!") or line.startswith("NÃO") else \
                "warn" if line.lstrip().startswith("*") or line.startswith("PONTOS") else \
                "head" if line.isupper() or line.endswith(":") else ""
            o.insert("end", line + "\n", tag)
        o.configure(state="disabled")

    def preview(self):
        self._job = None
        self.plan = None
        self.apply_btn.state(["disabled"])
        src, dst = self._char(self.src_cb), self._char(self.dst_cb)
        if not src or not dst or not self.info:
            return self._show("Escolha o personagem de origem, o poder e o personagem de destino.")
        if src is dst:
            return self._show("Origem e destino são o mesmo personagem.", error=True)
        rep = self._replace_name()
        if rep == "":
            return self._show("Escolha qual poder do destino será substituído.")
        try:
            include = {k for k, v in self.checked.items() if v}
            if self.anim_var.get():
                self._show("Lendo os sets de animação (alguns segundos na primeira vez)...")
                self.configure(cursor="watch")
                self.update_idletasks()
            self.plan = transfer.build_plan(dst.proj, self.info, dst, self.tal_var.get(), self.main_var.get(),
                                            include, self.fx_var.get(), replace=rep, independent=self.indep_var.get(),
                                            anim_tools=self.app.anim_tools if self.anim_var.get() else None,
                                            replace_moves=self._is_move() and self.mode_var.get() == "replace",
                                            copy_sounds=self.snd_var.get())
        except Exception as e:
            return self._show(f"Erro ao montar o plano: {e}", error=True)
        finally:
            self.configure(cursor="")
        done, self._done = self._done, ""
        self._show((done + "\n\nPRÓXIMA CÓPIA (com a seleção atual):\n\n" if done else "") + self.plan.describe(dst.proj))
        if not self.plan.errors:
            self.apply_btn.state(["!disabled"])

    def apply(self):
        if not self.plan or self.plan.errors:
            return
        open_dirty = [t for t in self.app.editors() if t.modified and
                      any(os.path.normcase(t.path) == os.path.normcase(c.path) for c in self.plan.changes)]
        if open_dirty:
            messagebox.showwarning("Salve antes", "Estes arquivos estão abertos com alterações não salvas:\n\n"
                                   + "\n".join(os.path.basename(t.path) for t in open_dirty)
                                   + "\n\nSalve ou feche e tente de novo.", parent=self)
            return
        n_anim = len(self.plan.anim.items) if self.plan.anim is not None else 0
        if not messagebox.askyesno("Aplicar", f"Gravar e compilar {len(self.plan.changes)} arquivo(s)"
                                   + (f", copiar {len(self.plan.copies)} efeito(s)" if self.plan.copies else "")
                                   + (f", alterar {len(self.plan.sound_banks)} banco(s) de som" if self.plan.sound_banks else "")
                                   + (f" e remontar o set de animações com {n_anim} animação(ões)" if n_anim else "")
                                   + "?\nOs originais ficam na pasta de backups.", parent=self):
            return
        try:
            self.configure(cursor="watch")
            self.update_idletasks()
            written = transfer.apply_plan(self.plan.proj, self.plan)
        except Exception as e:
            messagebox.showerror("Nada foi alterado" if isinstance(e, anims.AnimError) else "Erro",
                                 str(e) + ("\n\nO set de animações não passou na conferência, então nenhum arquivo foi gravado."
                                           if isinstance(e, anims.AnimError) else ""), parent=self)
            return
        finally:
            self.configure(cursor="")
        for t in self.app.editors():
            if any(os.path.normcase(t.path) == os.path.normcase(p) for p in written):
                t.load()
        self.plan.proj._vars = None
        dst = self._char(self.dst_cb)
        new_main = self.main_var.get()
        rep = self._replace_name()
        if rep:
            new_main = next((mv for tn, _, mv in self.dst_powers if tn == rep), new_main)
        if self._is_move():
            new_main = self.info.main
        self.app.status(f"Poder {'substituído' if rep else 'copiado'}: {len(written)} arquivo(s) gravados")
        self.app.fill_characters()
        # a janela continua aberta para a próxima transferência
        self._done = (f"FEITO: {self.info.talent_name or self.info.main} -> {dst.display} como {new_main}   "
                      f"({len(written)} arquivo(s) gravados, originais nos backups)")
        self._dst_changed()
        self.lift()


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    root_dir = pj.find_game_root(start)
    if not root_dir:
        tmp = tk.Tk()
        tmp.withdraw()
        root_dir = filedialog.askdirectory(title="Escolha a pasta do jogo (a que contem data e packages)")
        tmp.destroy()
        if not root_dir or not pj.find_game_root(root_dir):
            return
    App(root_dir).mainloop()


if __name__ == "__main__":
    main()
