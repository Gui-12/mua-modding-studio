"""Montagem do personagem novo a partir das escolhas do assistente.

Usa o clonador do MUA Studio (ops.clone_plan) como esqueleto - talentos, powerstyle, efeitos, sets de animação
e banco de som do personagem-base, já renomeados - e depois aplica o que foi escolhido nas etapas:
skins (arquivos novos, quantidade, nomes, hex-edit), HUDs, mannequin, telas de loading, retrato e atributos.
Não altera ops.py: só lê e ajusta o plano que ele devolve.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field

import ops
from project import Character, Project

from . import viewer

STAT_KEYS_ORDERED = True  # o guia lista os campos do herostat em ordem alfabética


@dataclass
class Slot:
    """Uma roupa. suffix = 2 últimos dígitos do número da skin."""
    suffix: str
    name: str = ""
    igb: str = ""  # arquivo novo da skin ("" = usa a skin do personagem-base)
    hud: str = ""  # arquivo novo do HUD ("" = usa o HUD do personagem-base)
    base_skin: str = ""  # skin do personagem-base de onde vêm skin/HUD quando não há arquivo novo
    patch: bool = True  # hex-edit: grava o número da skin dentro da cópia


@dataclass
class Choices:
    base: Character | None = None
    display: str = ""
    name: str = ""
    prefix: str = ""
    num: str = ""
    bank: str = ""
    share_bank: bool = False
    overwrite: bool = False
    slots: list[Slot] = field(default_factory=list)
    mannequin: str = ""
    loading: dict[str, str] = field(default_factory=dict)  # "01".."03" -> arquivo
    portrait: str = ""
    stats: dict[str, str] = field(default_factory=dict)  # body, strength, mind, autospend, scale_factor, team...
    flying: bool | None = None


def default_slots(base: Character) -> list[Slot]:
    out = []
    for s, nm in base.skins[:6]:  # numeração nova 01, 02... como no guia; skin e HUD continuam vindo do base
        out.append(Slot(suffix=f"{len(out) + 1:02d}", name=nm, base_skin=s))
    return out or [Slot(suffix="01", name="Classic")]


def base_stats(base: Character) -> dict[str, str]:
    st = base.stats
    return {k: st.get(k, d) for k, d in (("body", "7"), ("strength", "7"), ("mind", "8"), ("autospend", "bruiser_light"),
                                          ("scale_factor", "1"), ("team", "hero"))} | {"menulocation": "0"}


def suggest(base: Character, proj: Project) -> dict:
    s = ops.suggest_clone(base)
    used = set(ops.used_numbers(proj))
    n = 100
    while str(n) in used and n < 255:
        n += 1
    return {"name": s["name"], "prefix": s["prefix"], "bank": s["bank"], "num": str(n)}


_patch_cache: dict[tuple, int] = {}


def count_patchable(path: str) -> int:
    """Quantas vezes o nome padrão do appearance aparece (0 = skin já tratada ou formato diferente)."""
    try:
        key = (os.path.normcase(path), os.path.getmtime(path), os.path.getsize(path))
    except OSError:
        return 0
    if key not in _patch_cache:
        with open(path, "rb") as f:
            _patch_cache[key] = viewer.patch_skin_name(f.read(), "0")[1]
    return _patch_cache[key]


class CreatePlan:
    """Plano de clonagem (ops.ClonePlan) + o que o assistente muda nele."""

    def __init__(self, clone: ops.ClonePlan):
        self.clone = clone
        self.patches: list[tuple[str, str, str]] = []  # (origem, destino, número da skin) - cópia com hex-edit
        self.notes: list[str] = []

    @property
    def errors(self):
        return self.clone.errors

    @property
    def warnings(self):
        return self.clone.warnings

    def describe(self) -> str:
        txt = self.clone.describe()
        if self.patches:
            p = self.clone.proj
            extra = [f"  {p.rel(d)}   (skin {s} com hex-edit, de {os.path.basename(src)})" for src, d, s in self.patches]
            txt = txt.replace("  herostat do personagem:", "\n".join(extra) + "\n  herostat do personagem:", 1)
        if self.notes:
            txt += "\n\nESCOLHAS DO ASSISTENTE:\n" + "\n".join(f"  {n}" for n in self.notes)
        return txt


def build(ch: Choices, proj: Project, store_dir: str) -> CreatePlan:
    E: list[str] = []
    base = ch.base
    if base is None:
        cp = ops.ClonePlan()
        cp.proj = proj
        cp.errors.append("escolha o personagem-base (etapa 1)")
        return CreatePlan(cp)
    num = ch.num.strip()
    if num.isdigit() and not 0 <= int(num) <= 255:
        E.append("número do personagem: de 0 a 255")
    slots = [s for s in ch.slots][:6]
    if not slots:
        E.append("o personagem precisa de pelo menos uma skin")
    sufs = [s.suffix for s in slots]
    for s in slots:
        if not re.fullmatch(r"\d\d", s.suffix):
            E.append(f"skin '{s.name or s.suffix}': o final do número tem que ter 2 dígitos")
        if s.igb and not os.path.isfile(s.igb):
            E.append(f"skin {s.suffix}: arquivo não encontrado: {s.igb}")
        if s.hud and not os.path.isfile(s.hud):
            E.append(f"HUD {s.suffix}: arquivo não encontrado: {s.hud}")
    if len(set(sufs)) != len(sufs):
        E.append("há duas skins com o mesmo número")
    for label, f in [("mannequin", ch.mannequin), ("retrato", ch.portrait)] + [(f"loading {k}", v) for k, v in ch.loading.items()]:
        if f and not os.path.isfile(f):
            E.append(f"{label}: arquivo não encontrado: {f}")

    cp = ops.clone_plan(base, proj, ch.name, ch.display, ch.prefix, num, ch.bank, store_dir,
                        overwrite=ch.overwrite, share_bank=ch.share_bank)
    plan = CreatePlan(cp)
    # o aviso de arquivos existentes é recalculado no fim (os destinos mudam)
    cp.errors[:] = [e for e in cp.errors if "já existem (marque" not in e] + E
    if cp.errors or cp.stats is None:
        return plan

    root = proj.root
    new_name = ch.name.strip().lower()
    old_num = base.skins[0][0][:-2]
    clone_skins = {s: num + s[len(old_num):] for s, _ in base.skins if s.startswith(old_num)}  # base -> nº do clone
    first_base = base.skins[0][0]

    def out(rel: str) -> str:
        return os.path.join(root, *rel.split("/"))

    def is_dst(d: str, rel: str) -> bool:
        return os.path.normcase(d) == os.path.normcase(out(rel))

    # ---- pacotes: um par por skin, todos iguais tirando actorskin e o HUD ------------------------------
    pk_re = re.compile(rf"^{re.escape(new_name)}_(\d+)(_nc)?\.pkgb$", re.I)
    templates: dict[str, object] = {}
    kept = []
    first_clone = clone_skins.get(first_base, "")
    for d, tree in cp.trees:
        m = pk_re.match(os.path.basename(d))
        if m and os.path.normcase(os.path.dirname(d)) == os.path.normcase(out("packages/generated/characters")):
            nc = m.group(2) or ""
            if m.group(1) == first_clone:  # modelo preferido: o pacote da primeira skin
                templates[nc] = tree
            else:
                templates.setdefault(nc, tree)
            continue
        kept.append((d, tree))
    cp.trees = kept
    for s in slots:
        skin = num + s.suffix
        for nc, tree in templates.items():
            t = tree.clone()
            for n in t.walk():
                fn = n.get("filename")
                if fn is None:
                    continue
                if n.name == "actorskin":
                    n.set("filename", skin)
                elif re.fullmatch(r"(?i)(hud/)?hud_head_\d+", fn):
                    n.set("filename", re.sub(r"\d+$", skin, fn))
            cp.trees.append((out(f"packages/generated/characters/{new_name}_{skin}{nc}.pkgb"), t))
    if not templates:
        cp.warnings.append("o personagem-base não tem pacotes legíveis: nenhum .pkgb foi gerado")

    # ---- arquivos por skin (skin, HUD) ----------------------------------------------------------
    per_skin = {f"actors/{v}.igb" for v in clone_skins.values()} | {f"hud/hud_head_{v}.igb" for v in clone_skins.values()}
    per_skin |= {f"textures/loading/{v}.igb" for v in clone_skins.values()} | {f"ui/models/mannequin/{v}.igb" for v in clone_skins.values()}
    per_skin_n = {os.path.normcase(out(r)) for r in per_skin}
    base_loading = [(sp, d) for sp, d in cp.copies if os.path.normcase(d) in per_skin_n and "loading" in d.lower()]
    cp.copies = [(sp, d) for sp, d in cp.copies if os.path.normcase(d) not in per_skin_n]
    for sp, d in base_loading:  # telas de loading do base continuam (com o número novo), se não forem trocadas
        cp.copies.append((sp, d))

    for s in slots:
        skin = num + s.suffix
        bsk = s.base_skin if s.base_skin in dict(base.skins) else first_base
        src = s.igb or os.path.join(base.proj.root, "actors", f"{bsk}.igb")
        if os.path.isfile(src):
            dst = out(f"actors/{skin}.igb")
            if s.patch and count_patchable(src):
                plan.patches.append((src, dst, skin))
            else:
                cp.copies.append((src, dst))
        else:
            cp.warnings.append(f"skin {skin}: o personagem-base não tem {bsk}.igb e nenhum arquivo foi escolhido")
        hsrc = s.hud or os.path.join(base.proj.root, "hud", f"hud_head_{bsk}.igb")
        if os.path.isfile(hsrc):
            cp.copies.append((hsrc, out(f"hud/hud_head_{skin}.igb")))
        else:
            cp.warnings.append(f"skin {skin}: sem HUD (hud/hud_head_{skin}.igb) - o canto da tela fica vazio")
        plan.notes.append(f"skin {skin} '{s.name}': " + (os.path.basename(s.igb) if s.igb else f"skin {bsk} do base")
                          + (" + hex-edit" if s.patch and os.path.isfile(src) and count_patchable(src) else "")
                          + "; HUD " + (os.path.basename(s.hud) if s.hud else f"do base ({bsk})"))

    # ---- mannequin, loading e retrato --------------------------------------------------------------
    def replace(rel: str, src: str, label: str):
        if not src:
            return
        cp.copies = [(a, d) for a, d in cp.copies if not is_dst(d, rel)]
        cp.copies.append((src, out(rel)))
        plan.notes.append(f"{label}: {os.path.basename(src)} -> {rel}")

    replace(f"ui/models/mannequin/{num}01.igb", ch.mannequin, "mannequin")
    for k in ("01", "02", "03"):
        f = ch.loading.get(k, "")
        bl = os.path.join(base.proj.root, "textures", "loading", f"{old_num}{k}.igb")
        if f:
            replace(f"textures/loading/{num}{k}.igb", f, f"loading {k}")
        elif os.path.isfile(bl):
            replace(f"textures/loading/{num}{k}.igb", bl, f"loading {k} (do base)")
    port = ch.portrait or os.path.join(base.proj.root, "ui", "hud", "characters", f"{old_num}01.igb")
    if os.path.isfile(port):
        replace(f"ui/hud/characters/{num}01.igb", port, "retrato de conversa" if ch.portrait else "retrato de conversa (do base)")
    if not any(is_dst(d, f"ui/models/mannequin/{num}01.igb") for _, d in cp.copies):
        cp.warnings.append(f"sem mannequin (ui/models/mannequin/{num}01.igb): na S.H.I.E.L.D. aparece o de quem divide o número, ou nenhum")

    # ---- herostat ---------------------------------------------------------------------------------
    st = cp.stats
    skin_keys = re.compile(r"^skin(_0[1-6](_name)?)?$", re.I)
    attrs = [a for a in st.attrs if not skin_keys.match(a[0])]
    attrs.append(["skin", num + slots[0].suffix])
    for i, s in enumerate(slots, 1):
        if i > 1:
            attrs.append([f"skin_{i:02d}", s.suffix])
        attrs.append([f"skin_{i:02d}_name", s.name or f"Skin {i}"])
    st.attrs[:] = attrs
    for k, v in ch.stats.items():
        v = str(v).strip()
        if v:
            st.set(k, v)
    if ch.flying is True:
        st.set("moveset1", "moveset_flying")
    elif ch.flying is False:
        st.attrs[:] = [a for a in st.attrs if not (a[0].lower() == "moveset1" and a[1].lower() == "moveset_flying")]
    if STAT_KEYS_ORDERED:
        st.attrs.sort(key=lambda a: a[0].lower())
    try:
        tot = sum(int(st.get(k, "0")) for k in ("body", "strength", "mind"))
        if tot > 26:
            cp.warnings.append(f"body+strength+mind = {tot}: acima de ~24 o personagem fica forte demais (nível de chefe)")
        elif tot < 18:
            cp.warnings.append(f"body+strength+mind = {tot}: abaixo do normal (~22-24)")
        if int(st.get("mind", "5")) < 4:
            cp.warnings.append("mind abaixo de 4 deixa o personagem quase sem energia")
    except ValueError:
        cp.errors.append("body, strength e mind precisam ser números inteiros")

    # ---- arquivos que já existem ----------------------------------------------------------------------
    targets = [d for d, _ in cp.trees] + [d for _, d in cp.copies] + [d for _, d, _ in cp.animsets] \
        + [d for _, d, _, _ in cp.banks] + [d for _, d, _ in plan.patches]
    clash = sorted({proj.rel(t) for t in targets if os.path.exists(t)})
    if os.path.exists(cp.snippet_path):
        clash.append(cp.snippet_path)
    cp.clash = clash if ch.overwrite else []
    if clash and not ch.overwrite:
        cp.errors.append(f"{len(clash)} arquivo(s) já existem (marque 'Permitir sobrescrever' para continuar): "
                         + ", ".join(clash[:8]) + (" ..." if len(clash) > 8 else ""))
    return plan


def apply(plan: CreatePlan, anim_tools=None) -> list[str]:
    """Grava tudo. As skins com hex-edit são preparadas numa pasta temporária e entram como cópias comuns."""
    if plan.errors:
        raise ValueError("; ".join(plan.errors))
    tmp = tempfile.mkdtemp(prefix="mua_creator_")
    cp = plan.clone
    for src, dst, skin in plan.patches:
        with open(src, "rb") as f:
            data, n = viewer.patch_skin_name(f.read(), skin)
        p = os.path.join(tmp, f"{skin}.igb")
        with open(p, "wb") as f:
            f.write(data)
        cp.copies.append((p, dst))
        cp.info.append(f"skin {skin}: hex-edit em {n} ponto(s)")
    try:
        return ops.clone_apply(cp, anim_tools)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
