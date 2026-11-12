"""Operações sobre personagens: remover poder, compilar (exportar) para uma pasta e clonar."""
from __future__ import annotations

import os
import re
import shutil

import xmlb
import zsnd
import transfer
from xmlb import Node
from project import (Project, Character, EFFECT_KEYS, SOUND_KEYS, MOVE_REF_KEYS, VAR_RE, norm, strip_ext)

IMG_EXTS = (".igb", ".png", ".tga", ".dds")


# ================================================================ remover poder
def remove_power_plan(char: Character, talent_name: str) -> transfer.Plan:
    proj = char.proj
    plan = transfer.Plan()
    plan.proj = plan.sproj = proj
    try:
        info = transfer.PowerInfo(proj, char, talent_name)
    except ValueError as e:
        plan.errors.append(str(e))
        return plan
    d_tal = proj.load(char.talents_path).clone()
    one_file = os.path.normcase(char.talents_path) == os.path.normcase(char.powerstyle_path)
    d_ps = d_tal if one_file else proj.load(char.powerstyle_path).clone()
    tl = info.talent_name.lower()
    removed_vars = set()
    for t in list(d_tal.children):
        if t.name == "talent" and t.get("name", "").lower() == tl:
            removed_vars = {n.get("name", "").lower() for n in t.walk() if n.name == "talentvalue"}
            d_tal.children.remove(t)
    gone = [m.get("name") for m in d_ps.children if m.name == "FightMove" and (m.get("name") or "").lower() in info.own]
    d_ps.children[:] = [m for m in d_ps.children if not (m.name == "FightMove" and (m.get("name") or "").lower() in info.own)]
    tal_notes = [f"- talento {info.talent_name}  ({info.talent.get('descname', '')})"]
    ps_notes = [f"- FightMove {n}" for n in gone]
    if one_file:
        plan.changes.append(transfer.FileChange(char.talents_path, d_tal, tal_notes + ps_notes))
    else:
        plan.changes.append(transfer.FileChange(char.talents_path, d_tal, tal_notes))
        plan.changes.append(transfer.FileChange(char.powerstyle_path, d_ps, ps_notes))
    # herostat do jogo: tira o talento inicial, se estiver lá
    hp = proj.herostat_path
    if hp and proj.kind == "jogo" and xmlb.is_xmlb(open(hp, "rb").read(8) + b"\0" * 16):
        hroot = proj.load(hp).clone()
        for s in hroot.children:
            if s.get("name", "").lower() == char.name.lower():
                hit = [t for t in s.children if t.name == "talent" and t.get("name", "").lower() == tl]
                if hit:
                    for t in hit:
                        s.children.remove(t)
                    plan.changes.append(transfer.FileChange(hp, hroot, [f"- talento inicial {info.talent_name} de {char.display}"]))
    elif any(t.name == "talent" and t.get("name", "").lower() == tl for t in char.stats.children):
        plan.warnings.append(f"o herostat deste personagem lista {info.talent_name} como talento inicial; tire de lá à mão")
    plan.info.append(f"REMOVER de {char.display}: {info.talent_name} ({info.talent.get('descname', '')})   move {info.main}")
    left = {(m.get("name") or "").lower() for m in d_ps.children if m.name == "FightMove"}
    dangling = sorted({a[1] for m in d_ps.children if m.name == "FightMove" for n in m.walk() for a in n.attrs
                       if a[0].lower() in MOVE_REF_KEYS and a[1].lower() in info.own and a[1].lower() not in left})
    if dangling:
        plan.warnings.append("outros moves ainda encadeiam para moves removidos: " + ", ".join(dangling))
    orphan = set()
    for r in (d_ps, d_tal):
        for n in r.walk():
            for _, v in n.attrs:
                if "%" in v:
                    orphan |= {x for x in VAR_RE.findall(v) if x.lower() in removed_vars}
    if orphan:
        plan.warnings.append("variáveis do talento removido ainda usadas em outros lugares: " + ", ".join("%" + o for o in sorted(orphan)))
    plan.warnings.append("efeitos, entidades, sons e animações do poder ficam nos arquivos (não atrapalham); só o talento e os moves saem")
    return plan


# ============================================================ arquivos do personagem
def _asset_candidates(value: str, prefixes=("", "models/", "textures/")) -> list[str]:
    v = value.replace("\\", "/").lstrip("/")
    base = strip_ext(v)
    out = []
    for pre in prefixes:
        out.append(pre + v)
        out += [pre + base + e for e in IMG_EXTS]
    return out


def character_files(char: Character, with_assets: bool = True) -> tuple[list[str], list[str]]:
    """Caminhos relativos de tudo que o personagem usa e existe na pasta, e a lista do que foi procurado e não existe."""
    proj = char.proj
    root = proj.root
    found: dict[str, str] = {}
    missing: list[str] = []

    def add(rel: str) -> bool:
        rel = rel.replace("\\", "/").lstrip("/")
        p = os.path.join(root, *rel.split("/"))
        if os.path.isfile(p):
            found.setdefault(rel.lower(), rel)
            if os.path.isfile(p + ".txt"):
                found.setdefault((rel + ".txt").lower(), rel + ".txt")
            return True
        return False

    def add_any(cands, label=None):
        for c in cands:
            if add(c):
                return True
        if label and label not in missing:
            missing.append(label)
        return False

    def add_bin(base, label=True):
        p = proj.resolve(base)
        if p:
            add(proj.rel(p))
        elif label and base not in missing:
            missing.append(base)
        return p

    for p in char.packages:
        add(proj.rel(p))
        try:
            pk = proj.load(p)
        except Exception:
            continue
        for c in pk.children:
            fn = c.get("filename", "").strip()
            if not fn:
                continue
            if c.name in ("actorskin", "actoranimdb"):
                add_any([f"actors/{fn}.igb"], f"actors/{fn}.igb")
            elif c.name == "model":
                add_any(_asset_candidates(fn, ("", "models/")), fn)
            elif c.name == "texture":
                add_any(_asset_candidates(fn, ("", "textures/")), fn)
            elif c.name in ("xml", "xml_talents", "fightstyle"):
                add_bin(fn)
            elif c.name == "effect":
                add_bin("effects/" + fn)
    for p in [char.talents_path, char.powerstyle_path] + char.entity_paths:
        if p:
            add(proj.rel(p))
    effects = [e for e in char.referenced(EFFECT_KEYS) if norm(e).startswith("char/")]
    for e in effects:
        p = add_bin("effects/" + e)
        if p and with_assets:
            try:
                for n in proj.load(p).walk():
                    for k, v in n.attrs:
                        if v.strip() and ("texture" in k.lower() or k.lower() == "model"):
                            add_any(_asset_candidates(v))
            except Exception:
                pass
    for m in char.referenced({"model"}):
        add_any(_asset_candidates(m, ("", "models/")), m)
    for v in char.referenced({"interaction"}):
        add_bin(v)
        add(f"actors/{strip_ext(v).split('/')[-1]}.igb")
    if char.talents_path:
        try:
            for t in proj.load(char.talents_path).children:
                if t.get("icon_texture"):
                    add_any(_asset_candidates(t.get("icon_texture"), ("",)))
        except Exception:
            pass
    if char.sounddir:
        for b in (char.sounddir, re.sub(r"_m$", "", char.sounddir, flags=re.I) + "_v"):
            bp = zsnd.bank_path(root, b)
            if bp:
                add(proj.rel(bp))
            else:
                missing.append(f"banco de som {b}")
    for skin, _ in char.skins:
        add_any([f"actors/{skin}.igb"], f"actors/{skin}.igb")
        add(f"hud/hud_head_{skin}.igb")
        for d in ("ui/models/mannequin", "textures/loading", "ui/hud/characters", "ui/models/characters"):
            add(f"{d}/{skin}.igb")
    if char.skins:  # manequim costuma usar o número do personagem + 01
        pre = char.skins[0][0][:-2]
        add(f"ui/models/mannequin/{pre}01.igb")
    return sorted(found.values(), key=str.lower), missing


def herostat_snippet(char: Character) -> str:
    return xmlb.format_text(char.stats).replace("XMLB stats {", "   stats {", 1)


def export_character(char: Character, out_dir: str, with_assets: bool = True) -> tuple[list[str], list[str]]:
    """Copia tudo que o personagem precisa para out_dir, na estrutura de pastas do jogo."""
    files, missing = character_files(char, with_assets)
    os.makedirs(out_dir, exist_ok=True)
    for rel in files:
        dst = os.path.join(out_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(char.proj.root, *rel.split("/")), dst)
    xmlb.write_text_file(os.path.join(out_dir, "herostat.txt"), herostat_snippet(char))
    lines = [f"{char.display}  ({char.name})  -  gerado pelo MUA Studio", "",
             "INSTALAR: copie as pastas (actors, data, effects, packages, sounds...) para a pasta do jogo",
             "e cole o conteúdo de herostat.txt dentro do herostat do jogo (data/herostat.engb).",
             "", f"skins: {', '.join(s for s, _ in char.skins)}", f"menulocation: {char.stats.get('menulocation', '-')}",
             "", f"ARQUIVOS ({len(files)}):"] + ["  " + f for f in files]
    if missing:
        lines += ["", "REFERENCIADOS MAS NÃO ENCONTRADOS NA PASTA DE ORIGEM (podem ser do jogo original):"] + ["  " + m for m in missing]
    xmlb.write_text_file(os.path.join(out_dir, "LEIAME.txt"), "\n".join(lines) + "\n")
    return files, missing


# ====================================================================== clonar
class ClonePlan:
    def __init__(self):
        self.trees: list[tuple[str, Node]] = []  # (destino, árvore já reescrita)  -> compilados
        self.copies: list[tuple[str, str]] = []  # cópias binárias (origem, destino)
        self.animsets: list[tuple[str, str, str]] = []  # (origem, destino, nome novo do set)
        self.banks: list[tuple[str, str, str, str]] = []  # (origem, destino, banco antigo, banco novo)
        self.stats: Node | None = None
        self.snippet_path = ""
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []
        self.proj: Project | None = None
        self.sound_names: list[str] = []
        self.clash: list[str] = []  # arquivos que já existem e serão sobrescritos
        self.sound_prefixes: list[tuple[str, str]] = []  # (pasta antiga do som, pasta nova) em char/<pasta>/<nome>

    def describe(self) -> str:
        p = self.proj
        L = []
        if self.errors:
            L += ["NÃO É POSSÍVEL CRIAR:"] + [f"  ! {e}" for e in self.errors] + [""]
        if self.clash:
            L += [f"ATENÇÃO: {len(self.clash)} ARQUIVO(S) JÁ EXISTEM E SERÃO SOBRESCRITOS (os atuais vão para os backups):"]
            L += [f"  ! {c}" for c in self.clash] + [""]
        n = len(self.trees) + len(self.copies) + len(self.animsets) + len(self.banks)
        L += self.info + ["", f"ARQUIVOS GRAVADOS ({n})" + (":" if self.clash else ", nada existente é alterado:")]
        for d, _ in self.trees:
            L.append(f"  {p.rel(d)}   (reescrito e compilado)")
        for s, d, n in self.animsets:
            L.append(f"  {p.rel(d)}   (set de animações de {os.path.basename(s)})")
        for s, d, ob, nb in self.banks:
            L.append(f"  {p.rel(d)}   (banco de som de {ob})")
        for s, d in self.copies:
            L.append(f"  {p.rel(d)}   (cópia de {os.path.basename(s)})")
        L.append(f"  herostat do personagem: {self.snippet_path}")
        if self.warnings:
            L += ["", "PONTOS PARA CONFERIR:"] + [f"  * {w}" for w in self.warnings]
        return "\n".join(L)


def suggest_clone(char: Character) -> dict:
    """Valores iniciais para o formulário de clonagem."""
    prefixes: dict[str, int] = {}
    if char.talents_path:
        try:
            for t in char.proj.load(char.talents_path).children:
                m = re.match(r"^(.+?)_(p|power|outfit)\d+", t.get("name", ""), re.I)
                if m:
                    prefixes[m.group(1).lower()] = prefixes.get(m.group(1).lower(), 0) + 1
        except Exception:
            pass
    return {"name": char.name.lower(), "prefix": max(prefixes, key=prefixes.get) if prefixes else char.name.lower(),
            "num": char.skins[0][0][:-2] if char.skins else "", "bank": re.sub(r"_m$", "", char.sounddir, flags=re.I)}


def used_numbers(proj: Project) -> dict[str, str]:
    return {c.skins[0][0][:-2]: c.display for c in proj.characters if c.skins}


def clone_plan(src: Character, dst_proj: Project, new_name: str, display: str, new_prefix: str, new_num: str,
               new_bank: str, store_dir: str, overwrite: bool = False, share_bank: bool = False) -> ClonePlan:
    """share_bank: não cria banco de som; o clone continua usando o banco do personagem original."""
    plan = ClonePlan()
    plan.proj = dst_proj
    sproj = src.proj
    new_name, new_prefix, new_bank, new_num = new_name.strip().lower(), new_prefix.strip().lower(), new_bank.strip().lower(), new_num.strip()
    E = plan.errors
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,19}", new_name):
        E.append("nome interno: use letras minúsculas, números e _ (2 a 20 caracteres, começando por letra)")
    if not re.fullmatch(r"[a-z][a-z0-9]{1,15}", new_prefix):
        E.append("prefixo dos talentos: só letras e números, sem _ (ex.: glantern)")
    if not share_bank and not re.fullmatch(r"[a-z][a-z0-9]{1,5}", new_bank):
        E.append("banco de som: no máximo 6 caracteres antes do _m (letras e números)")
    if not re.fullmatch(r"\d{1,3}", new_num):
        E.append("número do personagem: 1 a 3 dígitos")
    if not src.skins or not src.talents_path or not src.powerstyle_path:
        E.append(f"{src.display} não tem skins, talentos ou powerstyle legíveis")
    if E:
        return plan
    taken = plan.warnings if overwrite else E  # com 'sobrescrever' ligado viram avisos
    for c in dst_proj.characters:
        if c.name.lower() == new_name:
            taken.append(f"já existe um personagem chamado '{new_name}' no herostat")
        if c.skins and c.skins[0][0][:-2] == new_num:
            taken.append(f"o número {new_num} já é usado por {c.display}: as skins dele seriam trocadas pelas do clone")
        if not share_bank and c.sounddir.lower() == new_bank + "_m":
            taken.append(f"o banco de som {new_bank}_m já é de {c.display}")
    old_name = src.name.lower()
    old_num = src.skins[0][0][:-2]
    old_bank = re.sub(r"_m$", "", src.sounddir.lower())
    skin_map = {s: new_num + s[len(old_num):] for s, _ in src.skins if s.startswith(old_num)}

    # "apelidos" do personagem nos nomes de arquivo: nem sempre o set de animação, o powerstyle e as
    # entidades usam o nome interno do herostat (ex.: herostat 'GreenLantern', set '13_glantern')
    stems = {old_name}
    if src.anims:
        stems.add(re.sub(r"^\d+_", "", src.anims).lower())
    stems.add(re.sub(r"^ps_", "", src.powerstyle, flags=re.I).lower())
    stems.add(os.path.basename(strip_ext(src.talents_path)).lower())
    for p in src.entity_paths:
        stems.add(re.sub(r"^ents_", "", os.path.basename(strip_ext(p)), flags=re.I).lower())
    stems = sorted({s for s in stems if len(s) >= 3}, key=len, reverse=True)
    stem_re = re.compile("|".join(re.escape(s) for s in stems), re.I)

    def owned(base: str) -> bool:
        return bool(stem_re.search(base)) or bool(re.match(rf"^{re.escape(old_num)}(?!\d)", base))

    def rename_base(b: str) -> str:
        """Nome de arquivo ligado ao personagem: troca o número no começo e o apelido pelo nome interno novo."""
        n = b
        if re.match(rf"^{re.escape(old_num)}(?!\d)", n):
            n = new_num + n[len(old_num):]
        n2 = stem_re.sub(new_name, n, count=1)
        if n2 == n and re.match(rf"^{re.escape(new_num)}_", n):  # set sem apelido reconhecível: <número>_<nome novo>...
            rest = n[len(new_num) + 1:]
            m = re.search(r"(_4_combat|_combat|_victim|_\d+)$", rest, re.I)
            n2 = f"{new_num}_{new_name}" + (m.group(1) if m else "")
        return n2

    # ---- identificadores exatos: talentos, variáveis, entidades ----------------------
    t_root = sproj.load(src.talents_path)
    ids: dict[str, str] = {}
    seg: dict[str, int] = {}
    names = [t.get("name", "") for t in t_root.children if t.name == "talent" and t.get("name")]
    varnames = sorted({n.get("name", "") for n in t_root.walk() if n.name == "talentvalue" and n.get("name")})
    for n in names + varnames:
        if "_" in n:
            seg[n.split("_")[0].lower()] = seg.get(n.split("_")[0].lower(), 0) + 1
    main_seg = {s for s, c in seg.items() if c >= 3} or set(seg)
    for n in names + varnames:
        head = n.split("_")[0].lower()
        ids[n.lower()] = (new_prefix + n[len(head):]) if "_" in n and head in main_seg else f"{new_prefix}_{n}"
    ent_files = list(src.entity_paths)
    for p in ent_files:
        try:
            for e in sproj.load(p).children:
                if e.get("name"):
                    en = e.get("name")
                    ids.setdefault(en.lower(), re.sub(re.escape(old_name), new_name, en, flags=re.I)
                                   if old_name in en.lower() else f"{new_prefix}_{en}")
        except Exception:
            pass
    id_re = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(k) for k in sorted(ids, key=len, reverse=True)) + r")(?![A-Za-z0-9_])", re.I) if ids else None
    seg_re = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(s) for s in sorted(main_seg, key=len, reverse=True)) + r")(?=_)", re.I) if main_seg else None

    # ---- caminhos ---------------------------------------------------------------------
    fx_folders = sorted({norm(e).split("/")[1] for e in src.referenced(EFFECT_KEYS) if norm(e).startswith("char/") and e.count("/") >= 2
                         and os.path.isdir(os.path.join(sproj.root, "effects", "char", norm(e).split("/")[1]))
                         and (old_name in norm(e).split("/")[1] or norm(e).split("/")[1] in main_seg)})
    path_map: list[tuple[str, str]] = []  # (prefixo antigo em minúsculas, novo)
    for f in fx_folders:
        path_map.append((f"char/{f}/", f"char/{new_name}/" if len(fx_folders) == 1 or f == fx_folders[0] else f"char/{rename_base(f)}/"))
    if share_bank:
        # os sons continuam no banco original: nenhuma referência de som muda de pasta
        keep_snd = True
    else:
        keep_snd = False
    if old_bank and not share_bank:
        path_map += [(f"char/{old_bank}_m/", f"char/{new_bank}_m/"), (f"char/{old_bank}_v/", f"char/{new_bank}_v/")]
    file_map: dict[str, str] = {}  # base de arquivo (minúsculas, sem extensão) -> nova base

    def map_file(rel_base: str, new_rel_base: str):
        file_map[norm(rel_base)] = new_rel_base

    tal_base = strip_ext(sproj.rel(src.talents_path))
    ps_base = strip_ext(sproj.rel(src.powerstyle_path))
    map_file(tal_base, f"data/talents/{new_name}")
    map_file(ps_base, f"data/powerstyles/ps_{new_name}")
    map_file(os.path.basename(ps_base), f"ps_{new_name}")
    ent_new: dict[str, str] = {}
    for p in ent_files:
        b = strip_ext(sproj.rel(p))
        base = os.path.basename(b)
        if not owned(base):
            continue  # arquivo de entidades compartilhado: continua apontando para o mesmo
        nb = f"data/entities/{rename_base(base)}"
        ent_new[p] = nb
        map_file(b, nb)
        map_file(base, os.path.basename(nb))
    tools_sets = [v for v in ([src.anims] + src.package_entries("actoranimdb")) if v]
    set_map: dict[str, str] = {}
    for v in tools_sets:
        if v.lower() in set_map:
            continue
        if owned(v) and os.path.isfile(os.path.join(sproj.root, "actors", v + ".igb")):
            set_map[v.lower()] = rename_base(v)
    inter = [strip_ext(v.replace("\\", "/")) for v in src.referenced({"interaction"})]
    for v in src.package_entries("fightstyle"):  # fightstyles de interação listados só no pacote
        b = strip_ext(v.replace("\\", "/"))
        if "powerstyles/" not in b.lower() and norm(b) not in {norm(x) for x in inter}:
            inter.append(b)
    for v in inter:
        base = v.split("/")[-1]
        if owned(base) and sproj.resolve(v):
            map_file(v, v[:len(v) - len(base)] + rename_base(base))
            map_file(base, rename_base(base))
    icon_map: dict[str, str] = {}
    for t in t_root.children:
        it = t.get("icon_texture")
        if it and old_name in it.lower() or (it and any(s in os.path.basename(it).lower() for s in main_seg)):
            b = strip_ext(it.replace("\\", "/"))
            icon_map[norm(b)] = b[:len(b) - len(os.path.basename(b))] + f"{new_name}_icons"

    def rw(v: str, key: str = "") -> str:
        if not v:
            return v
        if keep_snd and key in SOUND_KEYS:
            return v
        low = norm(v)
        for old, new in path_map:
            if low.startswith(old):
                return new + v.replace("\\", "/")[len(old):]
        b = norm(strip_ext(v))
        if b in file_map:
            return file_map[b] + v[len(strip_ext(v)):]
        if b in icon_map:
            return icon_map[b] + v[len(strip_ext(v)):]
        if b in set_map:
            return set_map[b]
        if v in skin_map:
            return skin_map[v]
        m = re.fullmatch(r"(.*hud_head_)(\d+)", v, re.I)
        if m and m.group(2) in skin_map:
            return m.group(1) + skin_map[m.group(2)]
        if key == "skin_filter":
            return " ".join(skin_map.get(x, x) for x in v.split())
        if id_re:
            v = id_re.sub(lambda mm: ids[mm.group(1).lower()], v)
        if seg_re:
            v = seg_re.sub(new_prefix, v)
        return v

    def rewrite(root: Node) -> Node:
        r = root.clone()
        for n in r.walk():
            for a in n.attrs:
                a[1] = rw(a[1], a[0].lower())
        return r

    droot = dst_proj.root

    def out(rel: str) -> str:
        return os.path.join(droot, *rel.split("/"))

    def tree(src_path: str, new_rel_base: str):
        ext = os.path.splitext(src_path)[1]
        try:
            plan.trees.append((out(new_rel_base + ext), rewrite(sproj.load(src_path))))
        except Exception as e:
            plan.warnings.append(f"não foi possível ler {sproj.rel(src_path)} ({e}); arquivo não clonado")

    tree(src.talents_path, f"data/talents/{new_name}")
    tree(src.powerstyle_path, f"data/powerstyles/ps_{new_name}")
    for p, nb in ent_new.items():
        tree(p, nb)
    for v in inter:
        if norm(v) in file_map:
            tree(sproj.resolve(v), file_map[norm(v)])
            ig = os.path.join(sproj.root, "actors", v.split("/")[-1] + ".igb")
            if os.path.isfile(ig):
                plan.animsets.append((ig, out(f"actors/{file_map[norm(v.split('/')[-1])]}.igb"), file_map[norm(v.split("/")[-1])]))
    for p in src.packages:
        m = re.match(r"^(.+?)_(\d+)(_nc)?\.pkgb$", os.path.basename(p), re.I)
        if m and m.group(2) in skin_map:
            tree(p, f"packages/generated/characters/{new_name}_{skin_map[m.group(2)]}{m.group(3) or ''}")
    for i, f in enumerate(fx_folders):
        d = os.path.join(sproj.root, "effects", "char", f)
        nf = path_map[i][1].split("/")[1]
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith((".xmlb", ".engb")):
                tree(os.path.join(d, fn), f"effects/char/{nf}/{fn.rsplit('.', 1)[0]}")
    for v, nv in set_map.items():
        plan.animsets.append((os.path.join(sproj.root, "actors", v + ".igb"), out(f"actors/{nv}.igb"), nv))
    for s, ns in skin_map.items():
        for rel in (f"actors/{s}.igb", f"hud/hud_head_{s}.igb", f"ui/models/mannequin/{s}.igb", f"textures/loading/{s}.igb"):
            sp = os.path.join(sproj.root, *rel.split("/"))
            if os.path.isfile(sp):
                plan.copies.append((sp, out(rel.replace(s, ns))))
    mq = os.path.join(sproj.root, "ui", "models", "mannequin", f"{old_num}01.igb")
    if os.path.isfile(mq) and f"{old_num}01" not in skin_map:
        plan.copies.append((mq, out(f"ui/models/mannequin/{new_num}01.igb")))
    for ob, nb in icon_map.items():
        for e in IMG_EXTS:
            sp = os.path.join(sproj.root, *(ob + e).split("/"))
            if os.path.isfile(sp):
                plan.copies.append((sp, out(nb + e)))
    for suf in ("_m", "_v"):
        bp = zsnd.bank_path(sproj.root, old_bank + suf) if old_bank and not share_bank else None
        if bp:
            lang = os.path.relpath(bp, os.path.join(sproj.root, "sounds")).split(os.sep)[0]
            nbn = new_bank + suf
            plan.banks.append((bp, out(f"sounds/{lang}/{nbn[0]}/{nbn[1]}/{nbn}{os.path.splitext(bp)[1]}"), old_bank + suf, nbn))
    # nomes de som conhecidos (para recalcular os códigos dentro do banco novo)
    snd = set()
    for c in sproj.characters:
        for p in [c.powerstyle_path] + (c.entity_paths if c is src else []):
            if not p:
                continue
            try:
                for n in sproj.load(p).walk():
                    for k, v in n.attrs:
                        if k.lower() in SOUND_KEYS and v.lower().startswith("char/") and v.count("/") >= 2:
                            snd.add(v.replace("\\", "/").split("/", 2)[2].lower())
            except Exception:
                pass
    plan.sound_names = sorted(snd)
    # pastas em que os sons do personagem podem ter sido nomeados (nem sempre é o nome do banco) e para onde vão
    for folder in dict.fromkeys([f"{old_bank}_m", f"{old_bank}_v"] + fx_folders + [old_name] + list(stems)):
        if folder.strip("_"):
            new_ref = rw(f"char/{folder}/x", "sound")
            plan.sound_prefixes.append((folder, new_ref.split("/")[1]))

    # ---- herostat --------------------------------------------------------------------
    st = src.stats.clone()
    for a in st.attrs:
        k = a[0].lower()
        if k == "name":
            a[1] = new_name
        elif k == "charactername":
            a[1] = display or new_name
        elif k == "powerstyle":
            a[1] = f"ps_{new_name}"
        elif k == "sounddir" and not share_bank:
            a[1] = f"{new_bank}_m"
        elif k == "skin":
            a[1] = skin_map.get(a[1], a[1])
        elif k == "characteranims":
            a[1] = set_map.get(a[1].lower(), a[1])
        elif k == "menulocation":
            a[1] = "0"
    for n in st.walk():
        if n is st:
            continue
        for a in n.attrs:
            a[1] = rw(a[1], a[0].lower())
    plan.stats = st
    plan.snippet_path = os.path.join(store_dir, f"{new_name}.txt")

    targets = [d for d, _ in plan.trees] + [d for _, d in plan.copies] + [d for _, d, _ in plan.animsets] + [d for _, d, _, _ in plan.banks]
    clash = [dst_proj.rel(t) for t in targets if os.path.exists(t)]
    if os.path.exists(plan.snippet_path):
        clash.append(plan.snippet_path)
    if clash and overwrite:
        plan.clash = clash
    elif clash:
        E.append(f"{len(clash)} arquivo(s) já existem (marque 'Permitir sobrescrever' para continuar): "
                 + ", ".join(clash[:8]) + (" ..." if len(clash) > 8 else ""))
    plan.info += [f"CLONAR {src.display} ({src.name})  ->  {display or new_name} ({new_name})",
                  f"número {old_num} -> {new_num}   skins: " + ", ".join(f"{a}->{b}" for a, b in skin_map.items()),
                  f"talentos: {', '.join(sorted(main_seg))}_...  ->  {new_prefix}_...   ({len(names)} talentos, {len(varnames)} variáveis)",
                  (f"banco de som: continua usando {old_bank}_m, o do original (nenhum banco novo é criado)" if share_bank else
                   f"banco de som: {old_bank}_m -> {new_bank}_m, criado do zero") if old_bank else "banco de som: a origem não tem sounddir",
                  f"efeitos: {', '.join('char/' + f for f in fx_folders) or '(nenhuma pasta própria)'} -> char/{new_name}"]
    if len(skin_map) < len(src.skins):
        plan.warnings.append("algumas skins da origem não começam com o número do personagem e não foram clonadas")
    plan.warnings.append("os .igb de skin são cópias com o nome novo; se alguma skin aparecer sem textura, o número antigo está gravado dentro do arquivo")
    plan.warnings.append("menulocation foi zerado: escolha a posição no editor de herostat ao colocar o personagem no jogo")
    return plan


def clone_apply(plan: ClonePlan, anim_tools=None) -> list[str]:
    if plan.errors:
        raise ValueError("; ".join(plan.errors))
    proj = plan.proj
    written = []
    for d, root in plan.trees:
        proj.save(d, root)
        written.append(d)
    for s, d in plan.copies:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        proj.backup(d)
        shutil.copy2(s, d)
        written.append(d)
    for s, d, name in plan.animsets:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        proj.backup(d)
        done = False
        if anim_tools is not None and anim_tools.available:
            try:
                built = anim_tools.assemble(s, set(), [], set_name=name)
                shutil.copy2(built, d)
                done = True
            except Exception as e:
                plan.warnings.append(f"set {os.path.basename(d)}: não consegui regravar com o nome novo ({e}); ficou como cópia simples")
            finally:
                anim_tools.cleanup()
        if not done:
            shutil.copy2(s, d)
        written.append(d)
    for s, d, ob, nb in plan.banks:
        # banco feito do zero: arquivo vazio e cada som copiado para ele já com o nome novo
        old = zsnd.Bank(s)
        names = set(plan.sound_names) | {  # nomes que o próprio jogo chama (falas e sons padrão)
            "epitaph", "bored", "cantgo", "cmdattackany", "cmdattacktarget", "cmdfollow", "iseeyou", "levelup", "lowhealth",
            "nopower", "nowork", "respaffirm", "tauntkd", "throwtaunt", "tooheavy", "victory", "xtreme", "pain", "death",
            "jump", "land", "pickup", "throw", "lift", "locked", "stats", "sight", "incoming", "flyloop", "footstep"}
        for i in range(len(old.sounds)):  # o nome do .wav de cada som também é candidato a nome
            st = os.path.splitext(old.file_name(i))[0].lower()
            names |= {st, st.replace(" ", "_"), re.sub(r"[ _]?\(?\d+\)?$", "", st)}
        # código antigo -> código novo. Um som com variações usa códigos seguidos: nome, nome+1, nome+2...
        known: dict[int, int] = {}
        have = {x[0] for x in old.sounds}
        suffix = ob[-2:]
        prefixes = [(ob, nb)] + [(a, b) for a, b in plan.sound_prefixes if a != ob and not (a.endswith(("_m", "_v")) and a[-2:] != suffix)]
        for old_folder, new_folder in prefixes:
            for n in names:
                if not n:
                    continue
                ho, hn = zsnd.pjw_hash(f"char/{old_folder}/{n}"), zsnd.pjw_hash(f"char/{new_folder}/{n}")
                k = 0
                while ho + k in have and k < 32:
                    known.setdefault(ho + k, hn + k)
                    k += 1
        new = zsnd.Bank.empty(d)
        cache: dict = {}
        hit, unnamed = 0, []
        for i, snd in enumerate(old.sounds):
            if snd[0] in known:
                new.add_from(old, i, known[snd[0]], cache)
                hit += 1
            else:
                new.add_from(old, i, snd[0], cache)
                unnamed.append(old.file_name(i))
        data = new.to_bytes()
        os.makedirs(os.path.dirname(d), exist_ok=True)
        proj.backup(d)
        with open(d + ".tmp~", "wb") as f:
            f.write(data)
        chk = zsnd.Bank(d + ".tmp~")
        if len(chk.sounds) != len(old.sounds) or any(chk.audio(i) != old.audio(i) for i in range(len(old.sounds))):
            os.remove(d + ".tmp~")
            raise zsnd.ZsndError(f"o banco novo {os.path.basename(d)} não conferiu com o original")
        os.replace(d + ".tmp~", d)
        plan.info.append(f"{os.path.basename(d)}: criado do zero com {len(old.sounds)} sons; {hit} com o nome novo (char/{nb}/...)")
        if unnamed:
            plan.warnings.append(f"{os.path.basename(d)}: {len(unnamed)} som(ns) foram copiados com o mesmo número que tinham no banco "
                                 f"original, porque o nome deles não é conhecido (o zsmeditor também mostra só o número): " + ", ".join(sorted(set(unnamed))[:18])
                                 + (" ..." if len(set(unnamed)) > 18 else ""))
        written.append(d)
    os.makedirs(os.path.dirname(plan.snippet_path), exist_ok=True)
    if os.path.isfile(plan.snippet_path):
        shutil.copy2(plan.snippet_path, plan.snippet_path + ".bak")
    xmlb.write_text_file(plan.snippet_path, xmlb.format_text(plan.stats).replace("XMLB stats {", "   stats {", 1))
    written.append(plan.snippet_path)
    # lista do que foi criado, para poder excluir o personagem depois sem adivinhar
    import json
    with open(os.path.splitext(plan.snippet_path)[0] + ".arquivos.json", "w", encoding="utf-8") as f:
        json.dump(sorted({proj.rel(w) for w in written if proj.owns(w)} | {proj.rel(w) + ".txt" for w in written
                                                                         if proj.owns(w) and os.path.isfile(w + ".txt")}), f, indent=1)
    return written


# ============================================================== excluir personagem criado
def created_files(char: Character) -> tuple[list[str], list[str]]:
    """(arquivos do personagem criado que podem ser apagados, arquivos mantidos por serem usados por outro personagem)."""
    import json
    proj = char.proj
    root = proj.root
    snippet = getattr(proj, "snippets", {}).get(char.name.lower(), "")
    manifest = os.path.splitext(snippet)[0] + ".arquivos.json" if snippet else ""
    rels: list[str] = []
    if manifest and os.path.isfile(manifest):
        try:
            with open(manifest, encoding="utf-8") as f:
                rels = [r for r in json.load(f) if isinstance(r, str)]
        except Exception:
            rels = []
    if not rels:  # personagem criado antes de existir a lista: só o que leva o nome ou o número dele
        name = char.name.lower()
        cand = [proj.rel(p) for p in char.packages + [char.talents_path, char.powerstyle_path] if p]
        cand += [proj.rel(p) for p in char.entity_paths if name in os.path.basename(p).lower()]
        for s, _ in char.skins:
            cand += [f"actors/{s}.igb", f"hud/hud_head_{s}.igb", f"ui/models/mannequin/{s}.igb", f"textures/loading/{s}.igb"]
        for d, pat in (("actors", name), ("textures/ui", name + "_icons")):
            full = os.path.join(root, *d.split("/"))
            if os.path.isdir(full):
                cand += [f"{d}/{f}" for f in os.listdir(full) if pat in f.lower()]
        fx = os.path.join(root, "effects", "char", name)
        if os.path.isdir(fx):
            cand += [f"effects/char/{name}/{f}" for f in os.listdir(fx)]
        if char.sounddir:
            for b in (char.sounddir, re.sub(r"_m$", "", char.sounddir, flags=re.I) + "_v"):
                bp = zsnd.bank_path(root, b)
                if bp:
                    cand.append(proj.rel(bp))
        rels = cand + [c + ".txt" for c in cand]
    # nunca apaga o que pertence a outro personagem do herostat
    others = []
    try:
        hs = proj.resolve("data/herostat")
        others = [Character(proj, s) for s in proj.load(hs).children if s.name == "stats" and s.get("name")
                  and s.get("name").lower() != char.name.lower()] if hs else []
    except Exception:
        pass
    protected = set()
    for o in others:
        for s, _ in o.skins:
            protected |= {f"actors/{s}.igb", f"hud/hud_head_{s}.igb"}
        for p in o.packages + [o.talents_path, o.powerstyle_path] + o.entity_paths:
            if p:
                protected |= {proj.rel(p).lower(), proj.rel(p).lower() + ".txt"}
        if o.anims:
            protected.add(f"actors/{o.anims.lower()}.igb")
        if o.sounddir:
            for b in (o.sounddir, re.sub(r"_m$", "", o.sounddir, flags=re.I) + "_v"):
                bp = zsnd.bank_path(root, b)
                if bp:
                    protected.add(proj.rel(bp).lower())
    protected = {p.lower() for p in protected}
    seen, files, kept = set(), [], []
    for r in rels:
        r = r.replace("\\", "/")
        if r.lower() in seen or not os.path.isfile(os.path.join(root, *r.split("/"))):
            continue
        seen.add(r.lower())
        (kept if r.lower() in protected else files).append(r)
    return sorted(files, key=str.lower), sorted(kept, key=str.lower)


def delete_created(char: Character, remove_files: bool) -> dict:
    """Tira o personagem da aba Criados. Com remove_files, também apaga os arquivos dele do jogo
    (cada um vai antes para a pasta de backups) e tira o bloco dele do herostat do jogo."""
    proj = char.proj
    out = {"files": 0, "herostat": False, "kept": []}
    if remove_files:
        files, kept = created_files(char)
        out["kept"] = kept
        for r in files:
            p = os.path.join(proj.root, *r.split("/"))
            proj.backup(p)
            os.remove(p)
            proj._cache.pop(p, None)
            out["files"] += 1
        fx = os.path.join(proj.root, "effects", "char", char.name.lower())
        if os.path.isdir(fx) and not os.listdir(fx):
            os.rmdir(fx)
        hs = proj.resolve("data/herostat")
        if hs:
            root = proj.load(hs).clone()
            hit = [s for s in root.children if s.name == "stats" and s.get("name", "").lower() == char.name.lower()]
            if hit:
                for s in hit:
                    root.children.remove(s)
                proj.save(hs, root)
                out["herostat"] = True
    snippet = getattr(proj, "snippets", {}).get(char.name.lower())
    if snippet and os.path.isfile(snippet):
        gone = os.path.join(os.path.dirname(snippet), "excluidos")
        os.makedirs(gone, exist_ok=True)
        for p in (snippet, os.path.splitext(snippet)[0] + ".arquivos.json", snippet + ".bak"):
            if os.path.isfile(p):
                os.replace(p, os.path.join(gone, os.path.basename(p)))
    return out


# ================================================== organizar poderes (requisitos e tiers)
# Tabelas padrão da comunidade: requisito = [(nível do poder, nível do personagem)], tiers = [(custo, quantidade, hard?)]
_T = lambda *t: [(c, n, False) for c, n in t] + [(3, 4, True), (4, 1, True)]
SLOT_TABLES = {
    "padrao": {  # até 5 poderes + 2 boosts + xtreme
        "power": [
            ([(1, 1), (5, 13), (6, 16), (9, 25), (10, 28), (14, 52), (15, 72)], _T((1, 5), (2, 4), (3, 1))),
            ([(1, 5), (5, 14), (6, 17), (9, 26), (10, 29), (14, 53), (15, 73)], _T((1, 5), (2, 4), (3, 1))),
            ([(1, 10), (3, 13), (4, 16), (7, 25), (8, 28), (12, 52), (13, 72)], _T((1, 3), (2, 4), (3, 1))),
            ([(1, 17), (4, 26), (5, 29), (9, 53), (10, 73)], _T((2, 4), (3, 1))),
            ([(1, 20), (3, 26), (4, 29), (8, 53), (9, 73)], _T((2, 3), (3, 1)))],
        "boost": [
            ([(1, 2), (5, 14), (6, 17), (9, 26), (10, 29), (14, 53), (15, 73)], _T((1, 5), (2, 4), (3, 1))),
            ([(1, 14), (2, 17), (5, 26), (6, 29), (10, 53), (11, 73)], _T((1, 1), (2, 4), (3, 1)))]},
    "estendido": {  # até 7 poderes + 3 boosts + xtreme (máximo de 10 no total)
        "power": [
            ([(1, 1), (5, 13), (6, 16), (9, 25), (10, 28), (14, 52), (15, 72)], _T((1, 5), (2, 4), (3, 1))),
            ([(1, 5), (5, 14), (6, 17), (9, 26), (10, 29), (14, 53), (15, 73)], _T((1, 5), (2, 4), (3, 1))),
            ([(1, 10), (3, 13), (4, 16), (7, 25), (8, 28), (12, 52), (13, 72)], _T((1, 3), (2, 4), (3, 1))),
            ([(1, 15), (2, 18), (5, 27), (6, 30), (10, 53), (11, 73)], _T((1, 1), (2, 4), (3, 1))),
            ([(1, 17), (4, 26), (5, 29), (9, 53), (10, 73)], _T((2, 4), (3, 1))),
            ([(1, 20), (3, 26), (4, 29), (8, 53), (9, 73)], _T((2, 3), (3, 1))),
            ([(1, 23), (2, 26), (3, 29), (7, 53), (8, 73)], _T((2, 2), (3, 1)))],
        "boost": [
            ([(1, 2), (5, 14), (6, 17), (9, 26), (10, 29), (14, 53), (15, 73)], _T((1, 5), (2, 4), (3, 1))),
            ([(1, 7), (4, 14), (5, 17), (8, 26), (9, 29), (13, 53), (14, 73)], _T((1, 4), (2, 4), (3, 1))),
            ([(1, 14), (2, 17), (5, 26), (6, 29), (10, 53), (11, 73)], _T((1, 1), (2, 4), (3, 1)))]},
}
XTREME_SLOT = ([(1, 10), (8, 45)], [(2, 1, False), (0, 7, False)])
KIND_LABEL = {"power": "Poder", "boost": "Boost", "xtreme": "Xtreme"}


def talent_kind(t: Node) -> str:
    ty, pw = (t.get("type") or "").lower(), (t.get("power") or "").lower()
    if "xtreme" in ty or "xtreme" in pw:
        return "xtreme"
    return "boost" if ty == "boost" else "power"


def power_talents(char: Character) -> list[tuple[str, str, str, str]]:
    """[(talento, nome exibido, tipo detectado, nível de desbloqueio atual)] dos talentos com poder, na ordem do arquivo."""
    out = []
    if not char.talents_path:
        return out
    for t in char.proj.load(char.talents_path).children:
        if t.name == "talent" and t.get("power"):
            req = _req_var(t)
            vals = [n for n in t.walk() if n.name == "talentvalue" and req and n.get("name", "").lower() == req.lower()]
            first = min(vals, key=lambda n: int(n.get("level", "99") or 99)).get("value", "?") if vals else "?"
            out.append((t.get("name", ""), t.get("descname", ""), talent_kind(t), first))
    return out


def _req_var(t: Node) -> str | None:
    for lv in t.children:
        if lv.name == "level":
            for r in lv.children:
                if r.name == "require" and (r.get("cat") or "").lower() == "level":
                    m = VAR_RE.search(r.get("level", ""))
                    return m.group(1) if m else None
    return None


def slot_tables(order: list[tuple[str, str]]) -> tuple[str, dict[str, tuple]]:
    """order = [(talento, 'power'|'boost'|'xtreme')] na ordem desejada. Devolve (nome da tabela, {talento: (req, tiers, rótulo)})."""
    powers = [t for t, k in order if k == "power"]
    boosts = [t for t, k in order if k == "boost"]
    xt = [t for t, k in order if k == "xtreme"]
    mode = "padrao" if len(powers) <= 5 and len(boosts) <= 2 else "estendido"
    tab = SLOT_TABLES[mode]
    if len(powers) > len(tab["power"]) or len(boosts) > len(tab["boost"]) or len(xt) > 1:
        raise ValueError(f"a regra cobre no máximo 7 poderes, 3 boosts e 1 xtreme (você tem {len(powers)}, {len(boosts)} e {len(xt)})")
    res = {}
    for i, t in enumerate(powers):
        res[t.lower()] = tab["power"][i] + (f"{i + 1}º Poder",)
    bt = tab["boost"]
    if mode == "estendido" and len(boosts) == 2:
        bt = [bt[0], bt[2]]  # a tabela do '2º boost' só vale quando há três
    for i, t in enumerate(boosts):
        res[t.lower()] = bt[i] + (f"{i + 1}º Boost",)
    for t in xt:
        res[t.lower()] = XTREME_SLOT + ("Xtreme",)
    return mode, res


def organize_plan(char: Character, order: list[tuple[str, str]], rescale: bool = True, reorder: bool = True) -> transfer.Plan:
    proj = char.proj
    plan = transfer.Plan()
    plan.proj = plan.sproj = proj
    try:
        mode, slots = slot_tables(order)
    except ValueError as e:
        plan.errors.append(str(e))
        return plan
    root = proj.load(char.talents_path).clone()
    talents = {t.get("name", "").lower(): t for t in root.children if t.name == "talent"}
    notes = []
    total = len(order)
    plan.info.append(f"ORGANIZAR PODERES de {char.display}: tabela {'padrão (até 5 poderes + 2 boosts)' if mode == 'padrao' else 'estendida (até 7 poderes + 3 boosts)'}"
                     f", {total} no total")
    if total > 10:
        plan.warnings.append(f"{total} poderes no total: acima de 10 o jogo trava para quem joga no teclado")
    for name, _kind in order:
        t = talents.get(name.lower())
        if t is None:
            plan.errors.append(f"talento '{name}' não existe no arquivo")
            continue
        req, tiers, label = slots[name.lower()]
        new_max = req[-1][0]
        tv = next((c for c in t.children if c.name == "talentvalues"), None)
        if tv is None:
            tv = Node("talentvalues")
            t.children.insert(0, tv)
        lv = next((c for c in t.children if c.name == "level"), None)
        if lv is None:
            lv = Node("level")
            t.children.append(lv)
        var = _req_var(t)
        if not var:
            var = f"{t.get('name')}_req"
            rq = next((r for r in lv.children if r.name == "require" and (r.get("cat") or "").lower() == "level"), None)
            if rq is None:
                rq = Node("require", [["cat", "level"]])
                lv.children.append(rq)
            rq.set("level", f"%{var}")
        # --- demais variáveis: reescala para o novo número de níveis ---------------
        groups: dict[str, list[Node]] = {}
        for n in tv.children:
            if n.name == "talentvalue" and n.get("name"):
                groups.setdefault(n.get("name"), []).append(n)
        old_levels = [int(n.get("level")) for g, ns in groups.items() if g.lower() != var.lower() for n in ns if (n.get("level") or "").isdigit()]
        old_max = max(old_levels) if old_levels else new_max
        scaled = []
        new_children = [c for c in tv.children if not (c.name == "talentvalue" and c.get("name"))]
        new_children += [Node("talentvalue", [["level", str(l)], ["name", var], ["value", str(v)]]) for l, v in req]
        for g, ns in groups.items():
            if g.lower() == var.lower():
                continue
            if not rescale or old_max == new_max or len(ns) < 2 or not all((n.get("level") or "").isdigit() for n in ns):
                new_children += ns
                continue
            # mesmos pontos e mesmos valores, só com o nível levado para a nova escala (1 continua 1, o último vira o novo máximo)
            ns = sorted(ns, key=lambda n: int(n.get("level")))
            placed: dict[int, Node] = {}
            for n in ns:
                c = n.clone()
                nl = int(round(1 + (int(n.get("level")) - 1) * (new_max - 1) / max(old_max - 1, 1)))
                c.set("level", str(max(1, min(new_max, nl))))
                placed[int(c.get("level"))] = c
            new_children += [placed[k] for k in sorted(placed)]
            scaled.append(g)
        tv.children[:] = new_children
        # --- tiers --------------------------------------------------------------------
        first_tier = next((i for i, c in enumerate(lv.children) if c.name == "tier"), 0)
        rest = [c for c in lv.children if c.name != "tier"]
        new_tiers = []
        for cost, count, hard in tiers:
            n = Node("tier", [["cost", str(cost)], ["count", str(count)]])
            if hard:
                n.attrs.append(["difficulty", "hard"])
            new_tiers.append(n)
        lv.children[:] = rest[:first_tier] + new_tiers + rest[first_tier:]
        notes.append(f"{label}: {t.get('descname') or name} ({name})  desbloqueia no nível {req[0][1]}, {new_max} níveis de poder, "
                     f"{len(tiers)} tiers" + (f"; valores reescalados de {old_max} para {new_max} níveis: {', '.join(scaled)}" if scaled else ""))
    if plan.errors:
        return plan
    if reorder:
        picked = [talents[n.lower()] for n, _ in order]
        ids = {id(t) for t in picked}
        first = next(i for i, c in enumerate(root.children) if id(c) in ids)
        before = [c for c in root.children[:first] if id(c) not in ids]
        after = [c for c in root.children[first:] if id(c) not in ids]
        root.children[:] = before + picked + after
        notes.append("talentos reordenados no arquivo: " + ", ".join(n for n, _ in order))
    plan.changes.append(transfer.FileChange(char.talents_path, root, notes))
    plan.warnings.append("os valores de dano e custo foram mantidos nos pontos equivalentes da curva; confira se os números finais fazem sentido para o novo lugar do poder")
    return plan


def _interp(defs: list[Node], pos: float) -> str | None:
    pts = []
    for d in defs:
        try:
            pts.append((int(d.get("level")), float(d.get("value"))))
        except (TypeError, ValueError):
            return None
    if not pts:
        return None
    pts.sort()
    if pos <= pts[0][0]:
        v = pts[0][1]
    elif pos >= pts[-1][0]:
        v = pts[-1][1]
    else:
        v = pts[-1][1]
        for (l0, v0), (l1, v1) in zip(pts, pts[1:]):
            if l0 <= pos <= l1:
                v = v0 + (v1 - v0) * (pos - l0) / (l1 - l0 or 1)
                break
    whole = all(abs(p[1] - round(p[1])) < 1e-9 for p in pts)
    return str(int(round(v))) if whole else f"{v:.2f}".rstrip("0").rstrip(".")
