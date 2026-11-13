"""Editor de áudio: dois bancos de som lado a lado (.zsm/.zss), para ouvir, copiar, renomear,
remover, importar e exportar sons, no mesmo espírito do mixer de animações."""
from __future__ import annotations

import os
import re
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import theme as th
import zsnd
import xmlb
import project as pj
from extras import fit, SearchCombo, BG, FG, DIM, PANEL, SEL, WARN, SYN_NUM

try:
    import winsound
except ImportError:  # fora do Windows: sem reprodução
    winsound = None

STANDARD = ("epitaph", "bored", "cantgo", "cmdattackany", "cmdattacktarget", "cmdfollow", "iseeyou", "levelup", "lowhealth",
            "nopower", "nowork", "respaffirm", "tauntkd", "throwtaunt", "tooheavy", "victory", "xtreme", "pain", "death",
            "jump", "land", "pickup", "throw", "lift", "locked", "stats", "sight", "incoming", "flyloop", "footstep")


def scan_sound_refs(projects) -> set[str]:
    """Todas as referências de som (char/<pasta>/<nome>) que aparecem nos arquivos das pastas carregadas."""
    refs = set()
    for proj in projects:
        for d in ("data/powerstyles", "data/entities", "data/fightstyles"):
            full = os.path.join(proj.root, *d.split("/"))
            if not os.path.isdir(full):
                continue
            for f in os.listdir(full):
                if not f.lower().endswith((".engb", ".xmlb")):
                    continue
                try:
                    root = proj.load(os.path.join(full, f))
                except Exception:
                    continue
                for n in root.walk():
                    for k, v in n.attrs:
                        if k.lower() in pj.SOUND_KEYS and v.count("/") >= 1 and v.strip():
                            refs.add(v.strip().replace("\\", "/").lower())
    return refs


class Side:
    def __init__(self):
        self.char = None
        self.proj = None
        self.path = ""
        self.bank: zsnd.Bank | None = None
        self.names: dict[int, str] = {}
        self.dirty = False
        self.paths: list[tuple[str, str]] = []  # (rótulo, caminho)

    @property
    def bank_name(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0].lower() if self.path else ""


class AudioEditor(tk.Toplevel):
    def __init__(self, app, left=None, right=None):
        super().__init__(app)
        self.app = app
        self.title("Editor de áudio")
        self.configure(bg=PANEL)
        fit(self, 1320, 800)
        th.dialog_header(self, "Editor de áudio", "list", th.PINK)
        self.transient(app)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.chars = app.all_characters() + app.proj.npcs()
        self.labels = [f"{c.display}   ({c.name})" + ("      [NPC]" if c.is_npc else "" if c.proj is app.proj else f"      [{c.proj.label}]")
                       for c in self.chars]
        self._refs = None
        self._tmp = tempfile.mkdtemp(prefix="muaaudio_")
        self.s = {"A": Side(), "B": Side()}
        self.w = {}
        self.msg = ttk.Label(self, style="Dim.TLabel", padding=(12, 0, 12, 10), wraplength=1280, justify="left", text=(
            "Escolha um personagem (ou abra um .zsm/.zss) de cada lado. Copiar leva o áudio e o registro do som; o nome no banco de destino "
            "vira char/<banco>/<nome>. Nada é gravado até 'Salvar banco' (o arquivo anterior vai para os backups)."))
        self.msg.pack(side="bottom", anchor="w")
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)
        for col, key in ((0, "A"), (2, "B")):
            self._build_side(body, col, key)
        mid = ttk.Frame(body, padding=10)
        mid.grid(row=0, column=1)
        th.Button(mid, text="Copiar  >>", style="Accent.TButton", command=lambda: self.copy("A", "B")).pack(pady=6)
        th.Button(mid, text="<<  Copiar", command=lambda: self.copy("B", "A")).pack(pady=6)
        th.Button(mid, text="Parar som", command=self.stop).pack(pady=(24, 6))
        if winsound is None:
            self.msg.configure(text="Reprodução indisponível neste sistema; o resto funciona.")
        for key, ch in (("A", left), ("B", right)):
            if ch is not None:
                i = next((i for i, c in enumerate(self.chars) if c is ch or (c.name == ch.name and c.proj is ch.proj and c.is_npc == ch.is_npc)), -1)
                if i >= 0:
                    self.w[key]["char"].current(i)
                    self.char_changed(key)

    # ---- montagem ---------------------------------------------------------------------
    def _build_side(self, parent, col, key):
        f = ttk.Frame(parent)
        f.grid(row=0, column=col, sticky="nsew")
        w = {}
        w["char"] = SearchCombo(f, values=self.labels)
        w["char"].pack(fill="x")
        w["char"].bind("<<ComboboxSelected>>", lambda e: self.char_changed(key))
        r = ttk.Frame(f)
        r.pack(fill="x", pady=6)
        w["bank"] = ttk.Combobox(r, state="readonly")
        w["bank"].pack(side="left", fill="x", expand=True)
        w["bank"].bind("<<ComboboxSelected>>", lambda e: self.bank_changed(key))
        th.Button(r, text="Abrir arquivo...", command=lambda: self.open_file(key)).pack(side="left", padx=6)
        w["save"] = th.Button(r, text="Salvar banco", style="Accent.TButton", command=lambda: self.save(key))
        w["save"].pack(side="left")
        w["info"] = ttk.Label(f, style="Dim.TLabel", wraplength=600, justify="left")
        w["info"].pack(anchor="w")
        lf = ttk.Frame(f)
        lf.pack(fill="both", expand=True, pady=(4, 0))
        cols = ("nome", "wav", "dur", "kb")
        tv = ttk.Treeview(lf, columns=cols, show="headings", selectmode="extended")
        for c, title, wd in zip(cols, ("Nome no banco", "Arquivo", "Duração", "KB"), (290, 150, 60, 50)):
            tv.heading(c, text=title)
            tv.column(c, width=wd, stretch=c == "nome", anchor="e" if c in ("dur", "kb") else "w")
        tv.tag_configure("used", foreground=SYN_NUM)
        tv.tag_configure("unknown", foreground=DIM)
        sb = ttk.Scrollbar(lf, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)
        tv.bind("<Double-1>", lambda e: self.play(key))
        tv.bind("<space>", lambda e: (self.play(key), "break")[1])
        tv.bind("<Delete>", lambda e: self.remove(key))
        w["tv"] = tv
        bf = th.Flow(f)  # quebra em duas linhas quando a janela é estreita (nenhum botão fica cortado)
        bf.pack(fill="x", pady=(6, 0))
        for text, fn in (("Tocar", self.play), ("Renomear...", self.rename), ("Remover", self.remove),
                         ("Importar .wav...", self.import_wav), ("Exportar .wav...", self.export_wav),
                         ("Copiar referência", self.copy_ref)):
            bf.add(th.Button(bf, text=text, command=lambda k=key, fn=fn: fn(k)))
        self.w[key] = w

    # ---- nomes ------------------------------------------------------------------------
    def refs(self) -> set[str]:
        if self._refs is None:
            self.configure(cursor="watch")
            self.update_idletasks()
            self._refs = scan_sound_refs(self.app.all_projects())
            self.configure(cursor="")
        return self._refs

    def resolve_names(self, side: Side):
        """Código -> nome legível. O arquivo só guarda o código; o nome vem das referências dos arquivos,
        dos nomes padrão do jogo e do nome do .wav. Variações usam códigos seguidos (nome, nome+1, ...)."""
        b = side.bank
        side.names = {}
        if b is None:
            return
        have = {s[0] for s in b.sounds}
        bank = side.bank_name
        base = re.sub(r"_[mv]$", "", bank)
        folders = {bank, base, base + "_m", base + "_v"}
        if side.char is not None:
            folders |= {side.char.name.lower(), re.sub(r"^\d+_", "", side.char.anims or "").lower()}
        refs = self.refs()
        tails = {r.split("/", 2)[2] for r in refs if r.count("/") >= 2} | set(STANDARD)
        for i in range(len(b.sounds)):
            st = os.path.splitext(b.file_name(i))[0].lower()
            tails |= {st, st.replace(" ", "_"), re.sub(r"[ _]?\(?\d+\)?$", "", st)}
        cands = set(r for r in refs if r.split("/")[1:2] and r.split("/")[1] in folders)
        cands |= {f"char/{f}/{t}" for f in folders if f for t in tails if t}
        exact = {}
        for c in cands:
            h = zsnd.pjw_hash(c)
            if h in have:
                exact.setdefault(h, c)
        side.names.update(exact)
        for h, c in list(exact.items()):
            k = 1
            while h + k in have and h + k not in exact and k < 32:
                side.names.setdefault(h + k, f"{c}  +{k}")
                k += 1

    def label(self, side: Side, code: int) -> str:
        return side.names.get(code, f"#{code}")

    # ---- carregar ---------------------------------------------------------------------
    def char_changed(self, key):
        side = self.s[key]
        i = self.w[key]["char"].current()
        if i < 0 or not self.ask_discard(key):
            return
        c = self.chars[i]
        side.char, side.proj = c, c.proj
        paths = []
        sd = (c.sounddir or "").lower()
        if sd:
            for b in dict.fromkeys([sd, re.sub(r"_m$", "", sd) + "_v"]):
                p = zsnd.bank_path(c.proj.root, b)
                if p:
                    paths.append((os.path.basename(p), p))
                elif re.fullmatch(r"[a-z0-9]{1,6}_[mv]", b):
                    ext = ".zsm" if b.endswith("_m") else ".zss"
                    paths.append((f"(novo) {b}{ext}", os.path.join(c.proj.root, "sounds", "eng", b[0], b[1], b + ext)))
        side.paths = paths
        self.w[key]["bank"].configure(values=[p[0] for p in paths])
        if paths:
            self.w[key]["bank"].current(0)
            self.bank_changed(key, force=True)
        else:
            self.w[key]["bank"].set("")
            side.bank, side.path = None, ""
            self.fill(key)
            self.w[key]["info"].configure(text=f"{c.display} não tem 'sounddir'" + (" (NPC: o som costuma ficar no banco do mapa)" if c.is_npc else ""))

    def bank_changed(self, key, force=False):
        side = self.s[key]
        i = self.w[key]["bank"].current()
        if i < 0 or (not force and not self.ask_discard(key)):
            return
        label, path = side.paths[i]
        self.load(key, path, new=label.startswith("(novo)"))

    def open_file(self, key):
        if not self.ask_discard(key):
            return
        p = filedialog.askopenfilename(parent=self, filetypes=[("Bancos de som", "*.zsm *.zss"), ("Todos", "*.*")],
                                       initialdir=os.path.join(self.app.proj.root, "sounds"))
        if p:
            side = self.s[key]
            side.char, side.proj = None, self.app.project_for_path(p)
            side.paths = [(os.path.basename(p), os.path.normpath(p))]
            self.w[key]["bank"].configure(values=[side.paths[0][0]])
            self.w[key]["bank"].current(0)
            self.w[key]["char"].set("")
            self.load(key, os.path.normpath(p))

    def load(self, key, path, new=False):
        side = self.s[key]
        try:
            side.bank = zsnd.Bank.empty(path) if new else zsnd.Bank(path)
        except Exception as e:
            side.bank = None
            messagebox.showerror("Editor de áudio", f"Não foi possível abrir {os.path.basename(path)}:\n\n{e}", parent=self)
            return
        side.path = path
        side.dirty = False  # banco novo só vira arquivo quando receber algum som e for salvo
        side.new = new
        self.resolve_names(side)
        self.fill(key)

    def fill(self, key, select=()):
        side, w = self.s[key], self.w[key]
        tv = w["tv"]
        tv.delete(*tv.get_children())
        b = side.bank
        if b is None:
            w["info"].configure(text="")
            return
        used = set()
        missing = []
        if side.char is not None:
            for r in side.char.referenced(pj.SOUND_KEYS):
                rl = r.lower()
                h = zsnd.pjw_hash(rl)
                if rl.startswith("char/") and rl.split("/")[1] in (side.bank_name, re.sub(r"_[mv]$", "", side.bank_name)):
                    if b.find(h):
                        used.add(h)
                    else:
                        missing.append(r)
        rows = sorted(range(len(b.sounds)), key=lambda i: (self.label(side, b.sounds[i][0]).startswith("#"), self.label(side, b.sounds[i][0])))
        for i in rows:
            code = b.sounds[i][0]
            lab = self.label(side, code)
            tag = "used" if code in used else "unknown" if lab.startswith("#") else ""
            tv.insert("", "end", iid=str(i), values=(lab, b.file_name(i), f"{b.duration(i):.2f}s", f"{len(b.audio(i)) // 1024 or 1}"),
                      tags=(tag,) if tag else ())
        for i in select:
            if tv.exists(str(i)):
                tv.selection_add(str(i))
                tv.see(str(i))
        known = sum(1 for s in b.sounds if s[0] in side.names)
        txt = (f"{os.path.relpath(side.path, side.proj.root) if side.proj and side.proj.owns(side.path) else side.path}   |   "
               f"{len(b.sounds)} sons, {known} com nome conhecido" + ("   |   ALTERADO, falta salvar" if side.dirty else "")
               + ("   |   banco ainda não existe: será criado ao salvar" if getattr(side, "new", False) and not os.path.exists(side.path) else ""))
        if missing:
            txt += f"\nO personagem usa {len(missing)} som(ns) que não existem neste banco: " + ", ".join(sorted(missing)[:8]) + (" ..." if len(missing) > 8 else "")
        w["info"].configure(text=txt, foreground=WARN if side.dirty else DIM)
        w["save"].configure(text="Salvar banco *" if side.dirty else "Salvar banco")

    def picked(self, key) -> list[int]:
        return [int(i) for i in self.w[key]["tv"].selection()]

    def changed(self, key, select=()):
        self.s[key].dirty = True
        self.fill(key, select)

    # ---- ações ------------------------------------------------------------------------
    def play(self, key):
        side, sel = self.s[key], self.picked(key)
        if not sel or side.bank is None:
            return
        if winsound is None:
            return self.msg.configure(text="Reprodução indisponível neste sistema.")
        p = os.path.join(self._tmp, f"play_{key}_{sel[0]}.wav")
        try:
            with open(p, "wb") as f:
                f.write(side.bank.wav_bytes(sel[0]))
            winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception as e:
            self.msg.configure(text=f"Não foi possível tocar: {e}")

    def stop(self):
        if winsound is not None:
            winsound.PlaySound(None, 0)

    def norm_name(self, side: Side, text: str) -> str:
        t = text.strip().replace("\\", "/").strip("/").lower()
        if "/" not in t:
            t = f"char/{side.bank_name}/{t}"
        elif t.count("/") == 1:
            t = "char/" + t
        return t

    def ask_name(self, side: Side, title: str, initial: str) -> str | None:
        t = simpledialog.askstring(title, "Nome do som (só o nome, ou o caminho completo char/<banco>/<nome>).\n"
                                   f"Só o nome vira char/{side.bank_name}/<nome>.", initialvalue=initial, parent=self)
        if not t or not t.strip():
            return None
        t = self.norm_name(side, t)
        if not re.fullmatch(r"[a-z0-9_./ ()-]+", t):
            messagebox.showerror(title, "Use letras, números, _ e /.", parent=self)
            return None
        return t

    def _make_room(self, side: Side, codes: set[int], title: str) -> bool:
        """Se algum código já existe no banco, pergunta se substitui (remove os antigos)."""
        clash = [i for i, s in enumerate(side.bank.sounds) if s[0] in codes]
        if not clash:
            return True
        names = ", ".join(sorted({self.label(side, side.bank.sounds[i][0]) for i in clash})[:6])
        if not messagebox.askyesno(title, f"Já existe(m) no banco de destino: {names}\n\nSubstituir?", parent=self):
            return False
        keep = [i for i in range(len(side.bank.sounds)) if i not in set(clash)]
        side.bank = side.bank.rebuilt(keep)
        side.bank.path = side.path
        return True

    def copy(self, a, b):
        src, dst = self.s[a], self.s[b]
        sel = self.picked(a)
        if not sel or src.bank is None:
            return self.msg.configure(text="Selecione os sons de um lado.")
        if dst.bank is None:
            return self.msg.configure(text="Escolha o banco de destino do outro lado.")
        if src.path == dst.path:
            return self.msg.configure(text="Os dois lados estão no mesmo banco.")
        plan = []
        for i in sel:
            code = src.bank.sounds[i][0]
            lab = src.names.get(code)
            if lab:
                m = re.match(r"^(.*?)(?:\s+\+(\d+))?$", lab)
                full, k = m.group(1), int(m.group(2) or 0)
                parts = full.split("/", 2)
                new = f"char/{dst.bank_name}/{parts[2]}" if len(parts) == 3 else self.norm_name(dst, full)
                plan.append((i, zsnd.pjw_hash(new) + k, new + (f"  +{k}" if k else "")))
            else:
                stem = re.sub(r"[ ()]", "_", os.path.splitext(src.bank.file_name(i))[0].lower()).strip("_")
                new = self.ask_name(dst, "Nome do som no destino", stem)
                if not new:
                    continue
                plan.append((i, zsnd.pjw_hash(new), new))
        codes = {c for _, c, _ in plan}
        if len(codes) != len(plan):
            return messagebox.showerror("Copiar", "Dois sons iriam para o mesmo nome no destino; renomeie antes.", parent=self)
        if not plan or not self._make_room(dst, codes, "Copiar"):
            return
        cache: dict = {}
        start = len(dst.bank.sounds)
        for i, code, lab in plan:
            dst.bank.add_from(src.bank, i, code, cache)
            dst.names[code] = lab
        self.changed(b, range(start, len(dst.bank.sounds)))
        self.msg.configure(text=f"{len(plan)} som(ns) copiados para {os.path.basename(dst.path)}: "
                           + ", ".join(lab for _, _, lab in plan[:6]) + (" ..." if len(plan) > 6 else "")
                           + "   (use 'Copiar referência' para colar o nome no powerstyle)")

    def rename(self, key):
        side, sel = self.s[key], self.picked(key)
        if not sel or side.bank is None:
            return
        first = self.label(side, side.bank.sounds[sel[0]][0])
        init = re.sub(r"\s+\+\d+$", "", first).split("/")[-1] if not first.startswith("#") else \
            os.path.splitext(side.bank.file_name(sel[0]))[0].lower()
        new = self.ask_name(side, "Renomear" + (f" {len(sel)} sons (viram variações: nome, +1, +2...)" if len(sel) > 1 else ""), init)
        if not new:
            return
        h = zsnd.pjw_hash(new)
        codes = {h + k for k in range(len(sel))}
        others = {s[0] for j, s in enumerate(side.bank.sounds) if j not in set(sel)}
        if codes & others:
            return messagebox.showerror("Renomear", f"Já existe um som com esse nome no banco: {new}", parent=self)
        for k, i in enumerate(sel):
            side.bank.sounds[i][0] = h + k
            side.names[h + k] = new + (f"  +{k}" if k else "")
        self.changed(key, sel)

    def remove(self, key):
        side, sel = self.s[key], self.picked(key)
        if not sel or side.bank is None:
            return
        if not messagebox.askyesno("Remover", f"Remover {len(sel)} som(ns) deste banco?\n\n(Só sai do arquivo ao salvar; há backup.)", parent=self):
            return
        keep = [i for i in range(len(side.bank.sounds)) if i not in set(sel)]
        side.bank = side.bank.rebuilt(keep)
        side.bank.path = side.path
        self.changed(key)

    def import_wav(self, key):
        side = self.s[key]
        if side.bank is None:
            return self.msg.configure(text="Escolha um banco primeiro.")
        files = filedialog.askopenfilenames(parent=self, filetypes=[("Áudio WAV", "*.wav")])
        added, notes = [], []
        for p in files:
            stem = re.sub(r"[ ()]", "_", os.path.splitext(os.path.basename(p))[0].lower()).strip("_")
            name = self.ask_name(side, f"Nome para {os.path.basename(p)}", stem)
            if not name:
                continue
            try:
                samples, rate, note = zsnd.read_wav(p)
            except Exception as e:
                messagebox.showerror("Importar", f"{os.path.basename(p)}: {e}", parent=self)
                continue
            code = zsnd.pjw_hash(name)
            if not self._make_room(side, {code}, "Importar"):
                continue
            side.bank.add_pcm(code, samples, rate, os.path.basename(p))
            side.names[code] = name
            added.append(len(side.bank.sounds) - 1)
            if note:
                notes.append(f"{os.path.basename(p)}: {note}")
        if added:
            self.changed(key, added)
            self.msg.configure(text=f"{len(added)} som(ns) importados (convertidos para o ADPCM do jogo)" + ("; " + "; ".join(notes) if notes else ""))

    def export_wav(self, key):
        side, sel = self.s[key], self.picked(key)
        if not sel or side.bank is None:
            return
        out = filedialog.askdirectory(parent=self, title="Pasta para os .wav")
        if not out:
            return
        used = set()
        for i in sel:
            lab = self.label(side, side.bank.sounds[i][0])
            base = re.sub(r"[^a-z0-9_+-]+", "_", lab.split("/")[-1].lower()).strip("_") if not lab.startswith("#") else \
                os.path.splitext(side.bank.file_name(i))[0]
            name, n = base, 2
            while name.lower() in used:
                name, n = f"{base}_{n}", n + 1
            used.add(name.lower())
            with open(os.path.join(out, name + ".wav"), "wb") as f:
                f.write(side.bank.wav_bytes(i))
        self.msg.configure(text=f"{len(sel)} arquivo(s) .wav gravados em {out}")

    def copy_ref(self, key):
        side, sel = self.s[key], self.picked(key)
        refs = []
        for i in sel:
            lab = side.names.get(side.bank.sounds[i][0])
            if lab and "+" not in lab:
                refs.append(lab)
        if not refs:
            return self.msg.configure(text="Selecione um som com nome conhecido (variações +1, +2 tocam junto com o nome principal).")
        self.clipboard_clear()
        self.clipboard_append("\n".join(refs))
        self.msg.configure(text="Copiado para a área de transferência: " + ", ".join(refs) + "   (cole em  sound = ... ; )")

    # ---- gravar ------------------------------------------------------------------------
    def save(self, key) -> bool:
        side = self.s[key]
        if side.bank is None or not side.path:
            return False
        b = side.bank
        b.sort_tables()
        data = b.to_bytes()
        os.makedirs(os.path.dirname(side.path), exist_ok=True)
        tmp = side.path + ".novo~"
        try:
            with open(tmp, "wb") as f:
                f.write(data)
            chk = zsnd.Bank(tmp)
            if len(chk.sounds) != len(b.sounds) or any(chk.sounds[i][0] != b.sounds[i][0] or chk.audio(i) != b.audio(i)
                                                       for i in range(len(b.sounds))):
                raise zsnd.ZsndError("o arquivo gerado não confere com o que está na tela")
            proj = side.proj or self.app.project_for_path(side.path)
            proj.backup(side.path)
            os.replace(tmp, side.path)
        except Exception as e:
            if os.path.isfile(tmp):
                os.remove(tmp)
            messagebox.showerror("Salvar banco", f"Nada foi gravado.\n\n{e}", parent=self)
            return False
        names = side.names
        side.bank = zsnd.Bank(side.path)
        side.names = names
        side.dirty = False
        for k, other in self.s.items():  # o mesmo banco aberto dos dois lados
            if other is not side and other.path == side.path:
                other.bank, other.names, other.dirty = zsnd.Bank(side.path), dict(names), False
                self.fill(k)
        side.paths = [(os.path.basename(p) if l.startswith("(novo)") and p == side.path else l, p) for l, p in side.paths]
        self.w[key]["bank"].configure(values=[p[0] for p in side.paths])
        self.fill(key)
        self.app.status(f"Banco de som salvo: {side.path}  ({len(b.sounds)} sons; o anterior foi para os backups)")
        self.msg.configure(text=f"Salvo: {os.path.basename(side.path)} com {len(b.sounds)} sons.")
        return True

    def ask_discard(self, key) -> bool:
        side = self.s[key]
        if not side.dirty:
            return True
        r = messagebox.askyesnocancel("Banco alterado", f"Salvar as alterações em {os.path.basename(side.path)}?", parent=self)
        if r is None:
            return False
        return self.save(key) if r else True

    def close(self):
        for k in ("A", "B"):
            if not self.ask_discard(k):
                return
        self.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)
        self.destroy()
