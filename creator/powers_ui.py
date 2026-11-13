"""Painel de poderes: lista "Poder 1..N" + editor (técnica, nome, ajuste fino) sem mexer em código.

Inspirado no Z Warriors (BT3): cada slot aprende a técnica de qualquer lutador, renomeia e faz ajuste fino
com barras mostrando "% do original"; e no criador de poderes do Freedom Force: escolhas por magnitude
(tipo de dano, empurrão) em vez de números soltos.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import theme as th
import extras

from . import powers as P

SHORT_TYPES = ("Melee", "Projectile", "Radial", "Special", "Boost", "Xtreme", "Summon", "Trap")


def _lbl(parent, text="", kind="fg", font=None, **kw):
    bg = kw.pop("bg", th.PANEL)
    fg = {"fg": th.FG, "dim": th.DIM, "strong": th.STRONG, "warn": th.WARN_SOFT, "ok": th.OK, "accent": th.ACCENT,
          "faint": th.FAINT}[kind]
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=font or th.UI, anchor="w", justify="left", **kw)


class ScaleRow(tk.Frame):
    """Barra de 25% a 300% do original, com o valor e a prévia ao lado (ajuste fino estilo BT3)."""

    def __init__(self, parent, label, explain, value: float, on_change, preview=None, lo=25, hi=300):
        super().__init__(parent, bg=th.PANEL)
        self.on_change, self.preview = on_change, preview
        top = tk.Frame(self, bg=th.PANEL)
        top.pack(fill="x")
        _lbl(top, label, "strong", th.UI_B, width=22).pack(side="left")
        self.slider = th.ctk.CTkSlider(top, from_=lo, to=hi, number_of_steps=(hi - lo) // 5, width=th.px(260) / th.SCALE,
                                       button_color=th.C("ACCENT"), button_hover_color=th.C("ACCENT_HOVER"),
                                       progress_color=th.C("ACCENT"), fg_color=th.C("SURFACE"), bg_color=th.T(th.PANEL),
                                       command=self._moved)
        self.slider.set(round(value * 100))
        self.slider.pack(side="left", padx=(0, 10))
        self.pct = _lbl(top, "", "accent", th.UI_B, width=6)
        self.pct.pack(side="left")
        th.Button(top, text="100%", command=lambda: (self.slider.set(100), self._moved(100))).pack(side="left", padx=6)
        self.prev = _lbl(self, "", "dim", th.MONO_S)
        self.prev.pack(fill="x", padx=(4, 0))
        _lbl(self, explain, "faint", th.UI_XS).pack(fill="x", padx=(4, 0))
        self._show(value)

    def _show(self, k):
        self.pct.configure(text=f"{round(k * 100)}%", fg=th.ACCENT if abs(k - 1) > 1e-6 else th.DIM)
        if self.preview:
            self.prev.configure(text=self.preview(k))

    def _moved(self, v):
        k = round(float(v)) / 100
        self._show(k)
        self.on_change(k)


class PowersPanel(tk.Frame):
    """owner: personagem dono dos poderes (para saber o que é 'mantido'); chars: de quem dá para aprender."""

    def __init__(self, parent, chars, on_change=None):
        super().__init__(parent, bg=th.PANEL)
        self.chars = [c for c in chars if not getattr(c, "is_npc", False) and c.talents_path and c.powerstyle_path]
        self.on_change = on_change
        self.owner = None
        self.slots: list[P.PowerSlot] = []
        self.cur: P.PowerSlot | None = None
        self.data: P.PowerData | None = None
        self._busy = False

        left = tk.Frame(self, bg=th.PANEL, width=th.px(330))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        bar = tk.Frame(left, bg=th.PANEL)
        bar.pack(fill="x", pady=(0, 6))
        th.Button(bar, text="+ Poder", command=self.add).pack(side="left")
        th.Button(bar, text="Remover", command=self.remove).pack(side="left", padx=4)
        th.Button(bar, text="↑", command=lambda: self.move(-1)).pack(side="left")
        th.Button(bar, text="↓", command=lambda: self.move(1)).pack(side="left", padx=4)
        self.tree = ttk.Treeview(left, columns=("info",), show="tree", selectmode="browse")
        self.tree.column("#0", width=th.px(190))
        self.tree.column("info", width=th.px(120))
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._select())
        th.tree_tooltips(self.tree)
        self.count_lbl = _lbl(left, "", "dim", th.UI_XS)
        self.count_lbl.pack(fill="x", pady=(4, 0))

        right = tk.Frame(self, bg=th.PANEL)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.head = _lbl(right, "", "strong", th.H3)
        self.head.pack(fill="x")
        self.sub = _lbl(right, "", "dim", th.UI_S)
        self.sub.pack(fill="x", pady=(0, 6))
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)
        self._tab_tech()
        self._tab_name()
        self.fine = th.ScrollFrame(self.nb, bg=th.PANEL)
        self.nb.add(self.fine, text="  Ajuste fino  ")

    # ---------------------------------------------------------------- dados
    def load(self, owner, slots: list[P.PowerSlot]):
        self.owner = owner
        self.slots = list(slots)
        self.refresh_list(select=0)

    def refresh_list(self, select: int | None = None):
        t = self.tree
        keep = select if select is not None else (self.slots.index(self.cur) if self.cur in self.slots else 0)
        t.delete(*t.get_children())
        for i, s in enumerate(self.slots):
            try:
                d = P.PowerData(s.src, s.talent)
                nm, kind = s.name or d.descname or s.talent, d.kind()
            except Exception:
                nm, kind = s.talent or "(vazio)", "?"
            own = self._is_own(s)
            info = ("" if own else f"de {s.src.display}") + (f"  ✎{s.changes()}" if s.changes() else "")
            t.insert("", "end", iid=str(i), text=f"Poder {i + 1}: {nm}", values=(info or kind,))
        self.count_lbl.configure(text=f"{len(self.slots)} poder(es). O jogo mostra até 7 poderes, 3 boosts e 1 Xtreme "
                                      "na tela de poderes.")
        if self.slots:
            keep = max(0, min(keep, len(self.slots) - 1))
            t.selection_set(str(keep))
            t.see(str(keep))
        else:
            self.cur = None
            self._fill()
        if self.on_change:
            self.on_change()

    def _is_own(self, s: P.PowerSlot) -> bool:
        o = self.owner
        if o is None or s.src is None or s.orig < 0:
            return False
        try:
            return s.src.name.lower() == o.name.lower() and s.src.proj.root == o.proj.root and s.talent == o.powers()[s.orig][0]
        except IndexError:
            return False

    def _select(self):
        sel = self.tree.selection()
        if not sel:
            return
        self.cur = self.slots[int(sel[0])]
        self._fill()

    def _changed(self, relist=False):
        if self._busy:
            return
        if relist:
            self.refresh_list()
        else:
            if self.cur in self.slots:
                i = self.slots.index(self.cur)
                info = ("" if self._is_own(self.cur) else f"de {self.cur.src.display}") + \
                       (f"  ✎{self.cur.changes()}" if self.cur.changes() else "")
                nm = self.cur.name or (self.data.descname if self.data else self.cur.talent)
                self.tree.item(str(i), text=f"Poder {i + 1}: {nm}", values=(info,))
            if self.on_change:
                self.on_change()

    # ---------------------------------------------------------------- lista
    def add(self):
        src = self.owner if self.owner is not None else (self.chars[0] if self.chars else None)
        if src is None:
            return
        pw = src.powers()
        s = P.PowerSlot(src=src, talent=pw[0][0] if pw else "", orig=-1)
        self.slots.append(s)
        self.refresh_list(select=len(self.slots) - 1)
        self.nb.select(0)

    def remove(self):
        if self.cur in self.slots:
            i = self.slots.index(self.cur)
            self.slots.remove(self.cur)
            self.cur = None
            self.refresh_list(select=max(0, i - 1))

    def move(self, d):
        if self.cur not in self.slots:
            return
        i = self.slots.index(self.cur)
        j = i + d
        if 0 <= j < len(self.slots):
            self.slots[i], self.slots[j] = self.slots[j], self.slots[i]
            self.refresh_list(select=j)

    # ---------------------------------------------------------------- abas
    def _tab_tech(self):
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text="  Técnica  ")
        _lbl(f, "De quem é a técnica?", "strong", th.UI_B).pack(fill="x")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(6, 4))
        _lbl(row, "Personagem:", width=12).pack(side="left")
        self.src_cb = extras.SearchCombo(row, values=[f"{c.display}   ({c.name})" + ("" if getattr(c.proj, "kind", "jogo") == "jogo"
                                                                                      else f"   [{c.proj.label}]") for c in self.chars], width=44)
        self.src_cb.pack(side="left", padx=6)
        self.src_cb.bind("<<ComboboxSelected>>", lambda e: self.after_idle(self._src_picked), add="+")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=4)
        _lbl(row, "Poder:", width=12).pack(side="left")
        self.tal_cb = ttk.Combobox(row, state="readonly", width=60)
        self.tal_cb.pack(side="left", padx=6)
        self.tal_cb.bind("<<ComboboxSelected>>", lambda e: self._tal_picked())
        self.tal_names: list[str] = []
        self.anim_var = tk.BooleanVar(value=True)
        self.snd_var = tk.BooleanVar(value=True)
        self.anim_chk = th.Check(f, text="Trazer as animações junto (se o personagem não tiver as mesmas)", variable=self.anim_var,
                                 command=self._opts)
        self.anim_chk.pack(anchor="w", pady=(10, 2))
        self.snd_chk = th.Check(f, text="Copiar os sons para o banco do personagem", variable=self.snd_var, command=self._opts)
        self.snd_chk.pack(anchor="w")
        self.tech_info = extras._text(f, height=12)
        self.tech_info.pack(fill="both", expand=True, pady=(10, 0))
        self.tech_info.configure(font=th.UI_S)

    def _tab_name(self):
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text="  Nome  ")
        self.nv = {k: tk.StringVar() for k in ("name", "short")}
        g = ttk.Frame(f)
        g.pack(fill="x")
        _lbl(g, "Nome do poder:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(g, textvariable=self.nv["name"], width=40).grid(row=0, column=1, sticky="w", padx=8)
        _lbl(g, "Tipo (aparece embaixo do nome):").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(g, textvariable=self.nv["short"], values=SHORT_TYPES, width=20).grid(row=1, column=1, sticky="w", padx=8)
        self.orig_name = _lbl(g, "", "faint", th.UI_XS)
        self.orig_name.grid(row=2, column=1, sticky="w", padx=8)
        _lbl(f, "Descrição (texto da tela de poderes):").pack(fill="x", pady=(12, 4))
        self.desc = tk.Text(f, height=6, bg=th.BG, fg=th.FG, insertbackground=th.FG, font=th.UI, wrap="word",
                            relief="flat", padx=8, pady=6)
        self.desc.pack(fill="x")
        _lbl(f, "Códigos como $PT_CHARGE, %variável e $DMG_PHYSICAL o jogo troca sozinho; pode deixar como estão.",
             "faint", th.UI_XS).pack(fill="x", pady=(4, 0))
        th.Button(f, text="Voltar ao nome e descrição originais", command=self._reset_name).pack(anchor="w", pady=(10, 0))
        for k, v in self.nv.items():
            v.trace_add("write", lambda *a, k=k: self._name_edit(k))
        self.desc.bind("<KeyRelease>", lambda e: self._name_edit("desc"))

    # ---------------------------------------------------------------- preencher
    def _fill(self):
        s = self.cur
        self._busy = True
        try:
            if s is None:
                self.head.configure(text="Nenhum poder")
                self.sub.configure(text="Use '+ Poder' para adicionar.")
                self.data = None
                return
            try:
                self.data = P.PowerData(s.src, s.talent)
            except Exception as e:
                self.data = None
                self.head.configure(text=s.talent or "(escolha um poder)")
                self.sub.configure(text=f"não consegui ler: {e}", fg=th.WARN_SOFT)
            d = self.data
            i = self.slots.index(s) + 1
            if d:
                self.head.configure(text=f"Poder {i}: {s.name or d.descname}")
                self.sub.configure(text=f"{d.kind()}   ·   técnica de {s.src.display} ({d.descname})   ·   animação {d.animenum or '-'}",
                                   fg=th.DIM)
            # técnica
            idx = next((k for k, c in enumerate(self.chars) if s.src is not None and c.name.lower() == s.src.name.lower()
                        and c.proj.root == s.src.proj.root), -1)
            if idx >= 0:
                self.src_cb.current(idx)
            self._fill_talents(s.src)
            if s.talent in self.tal_names:
                self.tal_cb.current(self.tal_names.index(s.talent))
            self.anim_var.set(s.anims)
            self.snd_var.set(s.sounds)
            own = self._is_own(s)
            for w in (self.anim_chk, self.snd_chk):
                w.state(["disabled"] if own else ["!disabled"])
            L = []
            if d:
                L += [d.descname + (f"  ({d.descshort})" if d.descshort else ""), "", d.description, "",
                      f"Moves deste poder no powerstyle: {', '.join(m.get('name') for m in d.moves)}"]
                L.append("Este é um poder do próprio personagem: fica como está (só os ajustes são aplicados)." if own else
                         f"Vai ser copiado de {s.src.display} com efeitos, entidades" + (", animações" if s.anims else "")
                         + (" e sons." if s.sounds else ".") + (" Substitui o poder original desta posição." if s.orig >= 0 else ""))
            extras.show_plan(self.tech_info, "\n".join(L))
            # nome
            self.nv["name"].set(s.name)
            self.nv["short"].set(s.short)
            self.desc.delete("1.0", "end")
            self.desc.insert("1.0", s.desc or (d.description if d else ""))
            self.orig_name.configure(text=f"original: {d.descname} ({d.descshort})" if d else "")
            self._fill_fine()
        finally:
            self._busy = False

    def _fill_talents(self, ch):
        pw = ch.powers() if ch is not None else []
        self.tal_names = [t for t, _, _ in pw]
        vals = []
        for t, nm, mv in pw:
            vals.append(f"{nm or t}   ({t})")
        self.tal_cb.configure(values=vals)

    def _fill_fine(self):
        inner = self.fine.inner
        for w in inner.winfo_children():
            w.destroy()
        s, d = self.cur, self.data
        if not d:
            return
        th.section_title(inner, "Valores por nível (talento)", bg=th.PANEL, pady=(8, 6))
        any_var = False
        for i, var, lab, exp, vals in d.variables():
            if lab == "Nível para liberar":
                continue
            any_var = True
            ScaleRow(inner, lab, exp + f"   ({var})", s.var_scale.get(i, 1.0),
                     lambda k, i=i: self._set_scale(s.var_scale, i, k),
                     preview=lambda k, vals=vals: P.preview_values(vals, k)).pack(fill="x", pady=(0, 10), padx=4)
        if not any_var:
            _lbl(inner, "Este poder não tem valores por nível.", "dim").pack(fill="x", padx=4)
        fields = d.fields()
        th.section_title(inner, "Golpe e projétil (powerstyle e entidades)", bg=th.PANEL, pady=(12, 6))
        if not fields:
            _lbl(inner, "Nada simples para ajustar aqui (o poder não tem golpe, área ou projétil com valores fixos).",
                 "dim").pack(fill="x", padx=4)
        for key in P.FIELDS:
            if key not in fields:
                continue
            lab, exp, kind = P.FIELDS[key]
            cur = sorted(set(fields[key]))
            if kind in ("choice_dmg", "choice_kb"):
                opts = P.DAMAGE_TYPES if kind == "choice_dmg" else P.KNOCKBACK
                row = tk.Frame(inner, bg=th.PANEL)
                row.pack(fill="x", pady=(0, 10), padx=4)
                _lbl(row, lab, "strong", th.UI_B, width=22).pack(side="left")
                labels = ["(manter: " + ", ".join(self._opt_label(opts, v) for v in cur) + ")"] + [b for _, b in opts]
                cb = ttk.Combobox(row, values=labels, state="readonly", width=28)
                val = s.fields.get(key)
                cb.current(1 + [a for a, _ in opts].index(val) if val in [a for a, _ in opts] else 0)
                cb.pack(side="left")
                cb.bind("<<ComboboxSelected>>", lambda e, cb=cb, key=key, opts=opts: self._set_field(key, None if cb.current() == 0 else opts[cb.current() - 1][0]))
                _lbl(inner, exp, "faint", th.UI_XS).pack(fill="x", padx=8, pady=(0, 10))
                row.pack_configure(pady=(0, 2))
            elif kind == "scale":
                ScaleRow(inner, lab, exp, s.field_scale.get(key, 1.0), lambda k, key=key: self._set_scale(s.field_scale, key, k),
                         preview=lambda k, cur=cur, key=key: "atual: " + ", ".join(P.scale_value(v, k, key in ("maxrange", "speed"))
                                                                                 if abs(k - 1) > 1e-6 else v for v in cur)).pack(fill="x", pady=(0, 10), padx=4)
            elif kind == "bool":
                v = tk.BooleanVar(value=(s.fields.get(key, "true" if "true" in cur else "false") == "true"))
                th.Check(inner, text=f"{lab}   (atual: {', '.join(cur)})", variable=v,
                         command=lambda v=v, key=key: self._set_field(key, "true" if v.get() else "false")).pack(anchor="w", padx=4, pady=(0, 10))
            elif kind == "int":
                row = tk.Frame(inner, bg=th.PANEL)
                row.pack(fill="x", pady=(0, 10), padx=4)
                _lbl(row, lab, "strong", th.UI_B, width=22).pack(side="left")
                v = tk.StringVar(value=s.fields.get(key, cur[0] if len(cur) == 1 else ""))
                ttk.Spinbox(row, from_=1, to=30, textvariable=v, width=6).pack(side="left")
                _lbl(row, f"atual: {', '.join(cur)}", "dim", th.UI_S).pack(side="left", padx=10)
                _lbl(inner, exp, "faint", th.UI_XS).pack(fill="x", padx=8, pady=(0, 10))
                row.pack_configure(pady=(0, 2))
                v.trace_add("write", lambda *a, v=v, key=key, cur=cur: self._set_field(
                    key, v.get().strip() if v.get().strip().isdigit() and v.get().strip() not in (cur if len(cur) == 1 else []) else None))
        th.Button(inner, text="Voltar todos os ajustes ao original", command=self._reset_fine).pack(anchor="w", padx=4, pady=(6, 12))
        self.fine.top()

    @staticmethod
    def _opt_label(opts, v):
        return next((b for a, b in opts if a == v), v)

    # ---------------------------------------------------------------- eventos
    def _src_picked(self):
        i = self.src_cb.current()
        if i < 0 or self.cur is None:
            return
        c = self.chars[i]
        self._fill_talents(c)
        if self.tal_names:
            self.tal_cb.current(0)
            self._tal_picked(c)

    def _tal_picked(self, ch=None):
        s = self.cur
        i = self.tal_cb.current()
        if s is None or i < 0:
            return
        ch = ch or self.chars[self.src_cb.current()]
        s.src, s.talent = ch, self.tal_names[i]
        s.var_scale, s.fields, s.field_scale = {}, {}, {}  # ajustes valiam para a técnica anterior
        s.name = s.short = s.desc = ""
        self._fill()
        self._changed(relist=True)

    def _opts(self):
        if self.cur:
            self.cur.anims, self.cur.sounds = self.anim_var.get(), self.snd_var.get()
            self._changed()

    def _name_edit(self, key):
        s, d = self.cur, self.data
        if self._busy or s is None:
            return
        if key == "desc":
            txt = self.desc.get("1.0", "end").strip()
            s.desc = "" if d and txt == d.description.strip() else txt
        else:
            setattr(s, key, self.nv[key].get().strip())
        self._changed()

    def _reset_name(self):
        if self.cur:
            self.cur.name = self.cur.short = self.cur.desc = ""
            self._fill()
            self._changed()

    def _set_scale(self, d: dict, key, k):
        if abs(k - 1) < 1e-6:
            d.pop(key, None)
        else:
            d[key] = k
        self._changed()

    def _set_field(self, key, val):
        if self.cur is None:
            return
        if val is None:
            self.cur.fields.pop(key, None)
        else:
            self.cur.fields[key] = val
        self._changed()

    def _reset_fine(self):
        if self.cur:
            self.cur.var_scale, self.cur.fields, self.cur.field_scale = {}, {}, {}
            self._fill_fine()
            self._changed()
