"""Copia um poder (talento + FightMoves + eventos + recursos) de um personagem para outro."""
from __future__ import annotations

import os
import re
import shutil

import xmlb
import zsnd
from xmlb import Node
from project import (Project, Character, EFFECT_KEYS, SOUND_KEYS, MOVE_REF_KEYS, VAR_RE, norm, strip_ext)

POWER_N = re.compile(r"^power(\d+)$", re.I)


class PowerInfo:
    """Tudo que um poder usa dentro do personagem de origem."""

    def __init__(self, proj: Project, src: Character, talent_name: str | None = None, move_name: str | None = None,
                 extra_moves=()):
        self.extra = {m.lower() for m in extra_moves}
        """Com talent_name: um poder (talento + moves). Com move_name: um FightMove solto
        (ataque, agarrão...) que não pertence a talento nenhum."""
        self.proj, self.src = proj, src
        if not src.talents_path or not src.powerstyle_path:
            raise ValueError(f"{src.display}: talentos ou powerstyle não encontrados")
        self.talents_root = proj.load(src.talents_path)
        self.ps_root = proj.load(src.powerstyle_path)
        self.moves = [m for m in self.ps_root.children if m.name == "FightMove"]
        if talent_name:
            self.talent = next((t for t in self.talents_root.children
                                if t.name == "talent" and t.get("name", "").lower() == talent_name.lower()), None)
            if self.talent is None:
                raise ValueError(f"talento '{talent_name}' não existe em {proj.rel(src.talents_path)}")
            self.talent_name = self.talent.get("name")
            self.main = self.talent.get("power", "")
        else:
            mv = next((m for m in self.moves if (m.get("name") or "").lower() == (move_name or "").lower()), None)
            if mv is None:
                raise ValueError(f"FightMove '{move_name}' não existe em {proj.rel(src.powerstyle_path)}")
            self.talent, self.talent_name, self.main = None, "", mv.get("name")
        self.events = {e.get("name", "").lower(): e for e in self.ps_root.children
                       if e.name == "event" and e.get("name")}
        self._graph()

    def _graph(self):
        tl = self.talent_name.lower()
        self.succ: dict[str, set[str]] = {}
        self.pred: dict[str, set[str]] = {}
        names = set()
        for m in self.moves:
            a = (m.get("name") or "").lower()
            names.add(a)
            for n in m.walk():
                for k, v in n.attrs:
                    if k.lower() in MOVE_REF_KEYS and (n is m or n.name == "chain"):
                        b = v.lower()
                        self.succ.setdefault(a, set()).add(b)
                        self.pred.setdefault(b, set()).add(a)
        seeds = set()
        for m in self.moves:
            nm = (m.get("name") or "").lower()
            if tl and any(r.get("item", "").lower() == tl for r in m.find_all("require")):
                seeds.add(nm)
            if (self.main and nm == self.main.lower()) or nm in self.extra:
                seeds.add(nm)
        own = set(seeds)
        changed = True
        while changed:
            changed = False
            for a in list(own):
                for b in self.succ.get(a, ()):
                    if b in own or b not in names:
                        continue
                    if not (self.pred.get(b, set()) - own - {b}):
                        own.add(b)
                        changed = True
        self.seeds = seeds
        self.own = own  # moves exclusivos deste poder
        shared = set()
        for a in own:
            shared |= {b for b in self.succ.get(a, ()) if b not in own}
        self.shared = shared  # moves comuns para onde o poder encadeia (idle, run...)

    def move_names(self) -> list[tuple[str, bool]]:
        """[(nome, exclusivo?)] na ordem do arquivo."""
        out, seen = [], set()
        for m in self.moves:
            nm = m.get("name") or ""
            l = nm.lower()
            if l in seen:
                continue
            if l in self.own:
                out.append((nm, True))
                seen.add(l)
            elif l in self.shared:
                out.append((nm, False))
                seen.add(l)
        return out


class FileChange:
    def __init__(self, path: str, root: Node, notes: list[str], new_file: bool = False):
        self.path, self.root, self.notes, self.new_file = path, root, notes, new_file


class Plan:
    def __init__(self):
        self.changes: list[FileChange] = []
        self.copies: list[tuple[str, str]] = []  # (origem, destino) copiados como estão (efeitos)
        self.anim = None  # anims.AnimPlan
        self.anim_tools = None
        self.proj = None  # projeto de destino
        self.sproj = None  # projeto de origem
        self.sound_banks: dict[str, tuple] = {}  # caminho do banco de destino -> (Bank já alterado em memória, notas)
        self.warnings: list[str] = []
        self.info: list[str] = []
        self.errors: list[str] = []

    def describe(self, proj: Project) -> str:
        L = []
        if self.errors:
            L.append("NÃO É POSSÍVEL APLICAR:")
            L += [f"  ! {e}" for e in self.errors]
            L.append("")
        L += self.info
        L.append("")
        L.append("ARQUIVOS QUE SERÃO ALTERADOS (todos com backup):")
        for c in self.changes:
            L.append(f"  {'[novo] ' if c.new_file else ''}{proj.rel(c.path)}")
            L += [f"      {n if n.startswith('-') else '+ ' + n}" for n in c.notes]
        if self.copies:
            L.append("")
            L.append("ARQUIVOS COPIADOS PARA A PASTA DO DESTINO (efeitos e o que faltava):")
            for s, d in self.copies:
                sp = self.sproj
                src = proj.rel(s) if proj.owns(s) else (f"[{sp.label}] {sp.rel(s)}" if sp is not None and sp.owns(s) else s)
                L.append(f"  {src}  ->  {proj.rel(d)}")
        if self.sound_banks:
            L.append("")
            L.append("SONS:")
            for path, (_, notes) in self.sound_banks.items():
                L.append(f"  banco alterado: {proj.rel(path)}  (conferido antes de trocar)")
                L += [f"      + {n}" for n in notes]
        if self.anim is not None and (self.anim.items or self.anim.warnings):
            L.append("")
            L.append("ANIMAÇÕES:")
            if self.anim.items:
                L.append(f"  set alterado: {proj.rel(self.anim.target)}  (remontado numa pasta temporária, conferido e só então trocado)")
            for it in self.anim.items:
                src = os.path.basename(it.src_set)
                if it.mode == "novo":
                    L.append(f"      + {it.name}  de {src}  (nome livre no destino, {it.enum} mantido)")
                elif it.mode == "substitui":
                    L.append(f"      ~ {it.name}  de {src}  SUBSTITUI a do destino (só o poder trocado usava)")
                else:
                    L.append(f"      + {it.name}  de {src}  entra como {it.new_name}; no poder {it.enum} -> {it.new_enum}")
        if self.warnings:
            L.append("")
            L.append("PONTOS PARA CONFERIR NO JOGO:")
            L += [f"  * {w}" for w in self.warnings]
        return "\n".join(L)


def suggest_names(proj: Project, dst: Character) -> tuple[str, str]:
    """Sugere (nome do talento, nome do move principal) livres no destino."""
    used_n, used_p = set(), set()
    prefix = dst.name.lower()
    if dst.talents_path:
        for t in proj.load(dst.talents_path).children:
            nm = t.get("name", "")
            m = re.match(r"^(.*?)_p(?:ower)?(\d+)$", nm, re.I)
            if m:
                used_n.add(int(m.group(2)))
                prefix = m.group(1)
            m = POWER_N.match(t.get("power", "") or "")
            if m:
                used_p.add(int(m.group(1)))
    if dst.powerstyle_path:
        for mv in proj.load(dst.powerstyle_path).children:
            m = re.match(r"^power(\d+)", mv.get("name", "") or "", re.I)
            if m:
                used_p.add(int(m.group(1)))
    n = 1
    while n in used_n or n in used_p:
        n += 1
    return f"{prefix}_p{n}", f"power{n}"


def effects_folder(dst: Character) -> str:
    """Pasta effects/char/<x> que o destino mais usa."""
    count: dict[str, int] = {}
    for v in dst.referenced(EFFECT_KEYS):
        parts = norm(v).split("/")
        if len(parts) >= 3 and parts[0] == "char":
            count[parts[1]] = count.get(parts[1], 0) + 1
    return max(count, key=count.get) if count else dst.name.lower()


def build_plan(proj: Project, info: PowerInfo, dst: Character, new_talent: str, new_main: str,
               include: set[str] | None = None, add_effects_to_pkg: bool = True,
               replace: str | None = None, independent: bool = False, anim_tools=None,
               replace_moves: bool = False, copy_sounds: bool = False, npc: dict | None = None) -> Plan:
    """replace: nome do talento do destino a substituir (o novo herda nome, posição e move).
    independent: copia efeitos e entidades para as pastas/arquivos do destino.
    anim_tools: anims.AnimTools para importar as animações junto (None = não importar)."""
    plan = Plan()
    src = info.src
    sproj, proj = info.proj, dst.proj  # origem e destino podem ser pastas diferentes (outro jogo, personagem avulso)
    cross = sproj is not proj
    plan.proj, plan.sproj = proj, sproj
    if cross:
        independent = True  # entre pastas diferentes não dá para apontar para os arquivos da origem
    new_talent, new_main = (new_talent or "").strip(), (new_main or "").strip()
    if not dst.talents_path and npc is None:
        plan.errors.append(f"{dst.display}: arquivo de talentos não encontrado")
    if not dst.powerstyle_path:
        plan.errors.append(f"{dst.display}: powerstyle não encontrado")
    if plan.errors:
        return plan

    same_char = dst.name.lower() == src.name.lower() and not cross
    d_tal = proj.load(dst.talents_path).clone() if npc is None else Node("talents")
    one_file = npc is None and os.path.normcase(dst.talents_path) == os.path.normcase(dst.powerstyle_path)
    d_ps = d_tal if one_file else proj.load(dst.powerstyle_path).clone()

    # ---- substituição: tira o talento antigo e os moves que só ele usava --------
    tal_index = move_index = None
    removed_moves: list[str] = []
    removed_vars: set[str] = set()
    removed_enums: set[str] = set()
    old_desc = ""
    move_mode = info.talent is None or npc is not None  # FightMove solto, sem talento (NPC também não tem talento)

    def remove_moves(names: set[str]):
        nonlocal move_index
        keep = []
        for m in d_ps.children:
            if m.name == "FightMove" and (m.get("name") or "").lower() in names:
                if move_index is None:
                    move_index = len(keep)
                removed_moves.append(m.get("name"))
                if m.get("animenum"):
                    removed_enums.add(m.get("animenum").lower())
            else:
                keep.append(m)
        d_ps.children[:] = keep

    if npc is not None:
        replace = None
        new_main = (npc.get("move") or "power_attack").strip()
        new_talent = f"{dst.name}_{new_main}".lower()
        if replace_moves:
            nm_l = new_main.lower()
            remove_moves({(m.get("name") or "").lower() for m in d_ps.children if m.name == "FightMove"
                          and ((m.get("name") or "").lower() == nm_l or (m.get("name") or "").lower().startswith(nm_l + "_"))})
    elif move_mode:
        replace = None
        new_main = info.main
        new_talent = src.name.lower()  # prefixo usado só se algum nome colidir no destino
        if replace_moves:
            remove_moves({n.lower() for n in include} if include is not None else set(info.own))
    if replace:
        try:
            old = PowerInfo(proj, dst, replace)
        except ValueError as e:
            plan.errors.append(str(e))
            return plan
        new_talent = old.talent_name
        new_main = old.main or new_main
        old_desc = old.talent.get("descname", "")
        for i, t in enumerate(d_tal.children):
            if t.name == "talent" and t.get("name", "").lower() == new_talent.lower():
                tal_index = i
                removed_vars = {n.get("name", "").lower() for n in t.walk() if n.name == "talentvalue"}
                break
        if tal_index is not None:
            del d_tal.children[tal_index]
        remove_moves(set(old.own))

    if not re.match(r"^[A-Za-z0-9_]+$", new_talent or ""):
        plan.errors.append("nome do talento inválido (use letras, números e _)")
    if not re.match(r"^[A-Za-z0-9_]+$", new_main or ""):
        plan.errors.append("nome do move inválido (use letras, números e _)")
    if plan.errors:
        return plan

    d_moves = {(m.get("name") or "").lower() for m in d_ps.children if m.name == "FightMove"}
    d_events = {e.get("name", "").lower(): e for e in d_ps.children if e.name == "event" and e.get("name")}
    d_talents = {t.get("name", "").lower() for t in d_tal.children if t.name == "talent"}
    d_vars = {n.get("name", "").lower() for n in d_tal.walk() if n.name == "talentvalue"}
    remaining_enums = {m.get("animenum").lower() for r in ({id(d_ps): d_ps, id(d_tal): d_tal}).values()
                       for m in r.children if m.name == "FightMove" and m.get("animenum")}

    if not move_mode and new_talent.lower() in d_talents:
        plan.errors.append(f"já existe um talento chamado '{new_talent}' em {dst.display}")
    included = {n.lower() for n in include} if include is not None else set(info.own)
    if not included:
        plan.errors.append("nenhum FightMove selecionado")

    # ---- nomes novos dos moves -------------------------------------------
    main_l = (info.main or "").lower()
    move_map: dict[str, str] = {}
    taken = set(d_moves)
    for m in info.moves:
        nm = m.get("name") or ""
        l = nm.lower()
        if l not in included or l in move_map:
            continue
        if main_l and l.startswith(main_l) and not l[len(main_l):len(main_l) + 1].isdigit() \
                and (POWER_N.match(main_l) or replace or npc is not None) and (not move_mode or npc is not None):
            new = new_main + nm[len(main_l):]
        elif l in d_moves:
            new = f"{new_talent}_{nm}"
        else:
            new = nm
        base, i = new, 2
        while new.lower() in taken:
            new = f"{base}_{i}"
            i += 1
        taken.add(new.lower())
        move_map[l] = new
    special = bool(main_l) and not POWER_N.match(main_l) and not move_mode
    if npc is not None:
        if main_l in move_map and move_map[main_l].lower() != new_main.lower():
            plan.errors.append(f"{dst.display} já tem um move '{new_main}'; marque 'substituir' ou escolha outro nome")
    elif move_mode:
        added = [f"{k} -> {v}" for k, v in move_map.items() if k != v.lower()]
        if added:
            plan.warnings.append("o destino já tem moves com esses nomes e você escolheu não substituir; entraram com outro "
                                 "nome e nada no destino encadeia para eles ainda: " + ", ".join(added))
    elif main_l in move_map and move_map[main_l].lower() != new_main.lower() and (not special or replace):
        plan.errors.append(f"o move '{new_main}' já existe em {dst.display}; escolha outro nome")
    if special and not replace:
        plan.warnings.append(f"este talento usa o move especial '{info.main}' (não é powerN): se o destino já tem o seu, "
                             "o jogo pode usar só um deles")
    if plan.errors:
        return plan

    src_moves = [m.clone() for m in info.moves if (m.get("name") or "").lower() in included]

    # ---- eventos do powerstyle usados pelos moves -------------------------
    needed: list[str] = []

    def need_event(name: str):
        l = name.lower()
        if l in info.events and l not in needed:
            needed.append(l)
            inh = info.events[l].get("inherit")
            if inh:
                need_event(inh)

    for m in src_moves:
        for n in m.walk():
            if n.name == "trigger" and n.get("name"):
                need_event(n.get("name"))
            if n.get("inherit"):
                need_event(n.get("inherit"))
    event_map: dict[str, str] = {}
    new_events: list[Node] = []
    for l in needed:
        ev = info.events[l]
        if l in d_events:
            if d_events[l].same_as(ev):
                continue  # o destino já tem um evento idêntico
            cand = f"{new_talent}_{ev.get('name')}"
            if cand.lower() in d_events:
                if replace:  # sobra de uma cópia anterior deste mesmo poder: atualiza no lugar
                    d_ps.children.remove(d_events[cand.lower()])
                else:
                    i = 2
                    while f"{cand}_{i}".lower() in d_events:
                        i += 1
                    cand = f"{cand}_{i}"
            event_map[l] = cand
        new_events.append(ev.clone())

    # ---- entidades usadas (localiza na origem) --------------------------------
    ent_refs: list[tuple[str, str]] = []
    for root in src_moves + new_events:
        for n in root.walk():
            if n.get("entity"):
                ent_refs.append((n.get("entity"), n.get("filename", "")))
    ent_src: dict[str, tuple[str, Node]] = {}  # nome minúsculo -> (arquivo, nó)
    ent_names_missing = []
    for ent, fn in ent_refs:
        if ent.lower() in ent_src:
            continue
        paths = []
        if fn:
            base = fn if "/" in fn.replace("\\", "/") else f"data/entities/{fn}"
            p = sproj.resolve(base)
            if p:
                paths.append(p)
        paths += [p for p in src.entity_paths if p not in paths]
        for p in paths:
            try:
                r = sproj.load(p)
            except Exception:
                continue
            node = next((e for e in r.children if e.get("name", "").lower() == ent.lower()), None)
            if node is not None:
                ent_src[ent.lower()] = (p, node)
                break
        else:
            if ent not in ent_names_missing:
                ent_names_missing.append(ent)
    new_ents: list[Node] = [node.clone() for _, node in ent_src.values()] if independent and not same_char else []

    # ---- variáveis ---------------------------------------------------------
    talent = info.talent.clone() if not move_mode else Node("talent")
    npc_talent = info.talent if npc is not None else None
    old_t = info.talent_name
    dst_icons: dict[str, int] = {}
    for t in d_tal.children:
        if t.name == "talent" and t.get("icon_texture"):
            dst_icons[t.get("icon_texture")] = dst_icons.get(t.get("icon_texture"), 0) + 1
    if not move_mode and not same_char and dst_icons:
        sheet = max(dst_icons, key=dst_icons.get)  # a folha de ícones que o destino mais usa
        if (talent.get("icon_texture") or "").lower() != sheet.lower():
            plan.info.append(f"ícone do talento: {talent.get('icon_texture') or '(nenhum)'}  ->  {sheet}  (folha do destino)")
            talent.set("icon_texture", sheet)
    tv_parent = next((c for c in talent.children if c.name == "talentvalues"), None)
    defined = []
    for n in talent.walk():
        if n.name == "talentvalue" and n.get("name") and n.get("name") not in defined:
            defined.append(n.get("name"))
    used = set()
    for root in src_moves + new_events + new_ents + [talent]:
        for n in root.walk():
            for _, v in n.attrs:
                used.update(VAR_RE.findall(v))
    src_defs: dict[str, list[Node]] = {}
    for n in info.talents_root.walk():
        if n.name == "talentvalue" and n.get("name"):
            src_defs.setdefault(n.get("name").lower(), []).append(n)
    borrowed = []
    for v in sorted(used):
        if v.lower() in {d.lower() for d in defined}:
            continue
        if npc is not None:
            pass  # resolvidas adiante: dano vira %mdmg_*, o resto vira número
        elif move_mode:
            if v.lower() not in d_vars:
                plan.warnings.append(f"a variável %{v} não existe nos talentos do destino"
                                     + (" (é de um talento da origem)" if v.lower() in src_defs else "")
                                     + "; troque por um valor fixo ou por uma variável do destino")
        elif v.lower() in src_defs and not same_char:
            if tv_parent is None:
                tv_parent = Node("talentvalues")
                talent.children.insert(0, tv_parent)
            for d in src_defs[v.lower()]:
                tv_parent.children.append(d.clone())
            defined.append(src_defs[v.lower()][0].get("name"))
            borrowed.append(v)
        elif v.lower() not in src_defs and v.lower() not in d_vars:
            plan.warnings.append(f"a variável %{v} não está definida nos talentos da origem nem do destino")
    if borrowed:
        plan.warnings.append("variáveis que pertenciam a outros talentos da origem foram copiadas para o talento novo "
                             "(passam a escalar com o nível dele): " + ", ".join("%" + b for b in borrowed))

    var_map: dict[str, str] = {}
    taken_v = set(d_vars)
    for v in defined:
        if v.lower().startswith(old_t.lower()):
            new = new_talent + v[len(old_t):]
        else:
            new = f"{new_talent}_{v.rsplit('_', 1)[-1]}"
        base, i = new, 2
        while new.lower() in taken_v:
            new = f"{base}{i}"
            i += 1
        taken_v.add(new.lower())
        var_map[v.lower()] = new

    tal_re = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(old_t) + r"(?![A-Za-z0-9])", re.I)

    def rewrite(root: Node):
        for n in root.walk():
            for a in n.attrs:
                k, v = a[0].lower(), a[1]
                if n.name == "talentvalue" and k == "name":
                    a[1] = var_map.get(v.lower(), v)
                    continue
                if "%" in v:
                    v = VAR_RE.sub(lambda m: "%" + var_map.get(m.group(1).lower(), m.group(1)), v)
                if k in MOVE_REF_KEYS or (n.name == "FightMove" and k == "name"):
                    v = move_map.get(v.lower(), v)
                elif (n.name == "trigger" and k == "name") or k == "inherit" or (n.name == "event" and k == "name"):
                    v = event_map.get(v.lower(), v)
                if old_t and (n.name != "entity" or k != "name"):
                    v = tal_re.sub(new_talent, v)
                a[1] = v

    if npc is not None:  # antes de renomear: as variáveis ainda têm o nome da origem
        _to_npc(plan, npc, src_moves, new_events, new_ents, src_defs, d_ps)
    for root in src_moves + new_events + new_ents + [talent]:
        rewrite(root)
    talent.set("name", new_talent)
    if move_mode:
        pass
    elif main_l in move_map:
        talent.set("power", move_map[main_l])
    elif POWER_N.match(main_l) or replace:
        talent.set("power", new_main)

    # ---- pacotes: o que o destino precisa carregar --------------------------------
    want: list[tuple[str, str]] = []  # (tipo, filename)

    def add_want(kind, fn):
        if fn and (kind, norm(fn)) not in {(k, norm(f)) for k, f in want}:
            want.append((kind, fn))

    # ---- entidades: cópia independente ou reaproveitar o arquivo da origem -----------
    ent_change = None
    if new_ents:
        ents_path = proj.resolve(f"data/entities/ents_{dst.name.lower()}") or \
            next((p for p in dst.entity_paths if os.path.basename(p).lower().startswith("ents_")), None)
        is_new = ents_path is None
        if is_new:
            ents_path = os.path.join(proj.root, "data", "entities", f"ents_{dst.name.lower()}.xmlb")
            d_ents = Node("entities")
        else:
            d_ents = proj.load(ents_path).clone()
        ents_base = os.path.basename(ents_path).rsplit(".", 1)[0]
        have_ents = {e.get("name", "").lower(): e for e in d_ents.children}
        ent_map: dict[str, str] = {}
        notes = []
        for node in new_ents:
            old_name = node.get("name")
            new_name = old_name if old_name.lower().startswith(new_talent.lower()) else f"{new_talent}_{old_name}"
            node.set("name", new_name)
            ent_map[old_name.lower()] = new_name
            if new_name.lower() in have_ents:
                d_ents.children.remove(have_ents[new_name.lower()])  # cópia anterior: atualiza
            d_ents.children.append(node)
            notes.append(f"entidade {new_name}  (cópia de {old_name})")
        for root in src_moves + new_events:
            for n in root.walk():
                e = n.get("entity")
                if e and e.lower() in ent_map:
                    n.set("entity", ent_map[e.lower()])
                    if n.get("filename") is not None:
                        n.set("filename", ents_base)
        ent_change = FileChange(ents_path, d_ents, notes, new_file=is_new)
        add_want("xml", f"data/entities/{ents_base}")
    else:
        for p, _ in ent_src.values():
            add_want("xml", strip_ext(sproj.rel(p)))
    if ent_names_missing:
        plan.warnings.append("entidades não encontradas nos arquivos da origem (confira se o destino as carrega): "
                             + ", ".join(ent_names_missing))

    # ---- recursos ------------------------------------------------------------
    effects, sounds, models, anims, skin_filters, interactions = [], [], [], [], [], []
    for root in src_moves + new_events + new_ents:
        for n in root.walk():
            for k, v in n.attrs:
                kl = k.lower()
                if not v.strip() or v.startswith("%"):
                    continue
                if kl in EFFECT_KEYS and v.replace("\\", "/") not in effects:
                    effects.append(v.replace("\\", "/"))
                elif kl in SOUND_KEYS and v not in sounds:
                    sounds.append(v)
                elif kl == "model" and v not in models:
                    models.append(v)
                elif kl == "animenum" and v not in anims and n.name == "FightMove":
                    anims.append(v)
                elif kl == "interaction" and v not in interactions:
                    interactions.append(v)
                elif kl == "skin_filter" and v not in skin_filters:
                    skin_filters.append(v)

    effects_src = list(effects)
    fx_map: dict[str, str] = {}

    # ---- efeitos: cópia para effects/char/<destino>/ -------------------------------
    if independent and not same_char:
        folder = effects_folder(dst)
        used_targets: set[str] = set()
        for fx in effects:
            parts = norm(fx).split("/")
            sp = sproj.effect_path(fx)
            if not sp or parts[0] != "char" or len(parts) < 3 or (parts[1] == folder and not cross):
                continue  # efeitos comuns do jogo (base/...) e os que já são do destino ficam onde estão
            base = parts[-1]
            ext = os.path.splitext(sp)[1]
            with open(sp, "rb") as f:
                data = f.read()

            def target(b):
                return os.path.join(proj.root, "effects", "char", folder, b + ext)

            def clash(b):
                t = target(b)
                if os.path.normcase(t) in used_targets:
                    return True
                if not os.path.isfile(t):
                    return False
                with open(t, "rb") as f:
                    return f.read() != data

            name = base
            if clash(name):
                # o destino já tem um efeito diferente com esse nome: o copiado ganha o nome de quem está dando o poder
                pre = src.name.lower()
                name = base if base.lower().startswith(pre + "_") else f"{pre}_{base}"
                i = 2
                while clash(name) and not replace:
                    name = f"{pre}_{base}_{i}"
                    i += 1
                try:
                    import ops  # import tardio: ops importa este módulo
                    who = ops.effect_usage(dst).get(f"char/{folder}/{base}".lower(), [])
                except Exception:
                    who = []
                plan.warnings.append(f"{dst.display} já tem um efeito char/{folder}/{base} diferente"
                                     + (f" (usado por: {', '.join(who)})" if who else "")
                                     + f"; o copiado entra como char/{folder}/{name} e o dele fica intacto")
            tp = target(name)
            used_targets.add(os.path.normcase(tp))
            fx_map[norm(fx)] = f"char/{folder}/{name}"
            if not os.path.isfile(tp) or open(tp, "rb").read() != data:
                plan.copies.append((sp, tp))
        if fx_map:
            for root in src_moves + new_events + new_ents:
                for n in root.walk():
                    for a in n.attrs:
                        if a[0].lower() in EFFECT_KEYS and norm(a[1]) in fx_map:
                            a[1] = fx_map[norm(a[1])]
            effects = [fx_map.get(norm(e), e) for e in effects]

    # ---- outra pasta: traz o que o poder usa e o destino não tem ---------------------
    if cross:
        queued = {os.path.normcase(d) for _, d in plan.copies}

        def bring(rels) -> bool:
            for rel in rels:
                sp = os.path.join(sproj.root, *rel.split("/"))
                if os.path.isfile(sp):
                    dp = os.path.join(proj.root, *rel.split("/"))
                    if not os.path.isfile(dp) and os.path.normcase(dp) not in queued:
                        plan.copies.append((sp, dp))
                        queued.add(os.path.normcase(dp))
                    return True
            return False

        def asset(value: str, prefixes=("",)):
            v = value.replace("\\", "/").lstrip("/")
            base = strip_ext(v)
            return bring([f"{pre}{b}{ext}" for pre in prefixes for b, exts in ((v, ("",)), (base, (".igb", ".png", ".tga", ".dds")))
                          for ext in exts])

        for fx in effects_src:
            sp = sproj.effect_path(fx)
            if not sp:
                continue
            if not proj.effect_path(fx) and norm(fx) not in fx_map:
                bring([sproj.rel(sp)])  # efeitos comuns (base/...) que o destino não tem
            try:
                for n in sproj.load(sp).walk():
                    for k, v in n.attrs:
                        if v.strip() and ("texture" in k.lower() or k.lower() == "model"):
                            asset(v, ("", "models/", "textures/"))
            except Exception:
                pass
        for m in models:
            asset(m, ("", "models/"))
        for v in interactions:
            p = sproj.resolve(v)
            if p:
                bring([sproj.rel(p)])
            bring([f"actors/{strip_ext(v.replace(chr(92), '/')).split('/')[-1]}.igb"])

    # ---- sons: copia do banco da origem para o banco do destino -----------------------
    sound_left = list(sounds)
    if copy_sounds and not same_char and sounds:
        if not dst.sounddir:
            plan.warnings.append(f"{dst.display} não tem 'sounddir' no herostat; sons não copiados")
        else:
            banks: dict[str, zsnd.Bank] = {}
            caches: dict[str, dict] = {}
            ref_map: dict[str, str] = {}
            warned = set()

            def bank(path):
                if path not in banks:
                    banks[path] = zsnd.Bank(path)
                return banks[path]

            for s in sounds:
                parts = s.replace("\\", "/").split("/")
                if len(parts) < 3 or parts[0].lower() != "char":
                    continue  # sons comuns do jogo (common/...) não pertencem a personagem
                sbank = parts[1].lower()
                dbank = dst.sounddir.lower()
                if sbank.endswith("_v"):
                    dbank = re.sub(r"_m$", "", dbank) + "_v"
                if sbank == dbank and not cross:
                    continue
                sp, dp = zsnd.bank_path(sproj.root, sbank), zsnd.bank_path(proj.root, dbank)
                if not sp or not dp:
                    key = (sbank, dbank, bool(sp))
                    if key not in warned:
                        warned.add(key)
                        plan.warnings.append((f"banco de som '{sbank}' não encontrado na pasta da origem" if not sp else
                                              f"banco de som '{dbank}' de {dst.display} não encontrado em sounds/") + "; esses sons não foram copiados")
                    continue
                try:
                    sb, db = bank(sp), bank(dp)
                    if dp not in caches:
                        caches[dp] = {}
                        if not db.roundtrips():
                            raise zsnd.ZsndError(f"o banco {os.path.basename(dp)} tem um layout que não sei regravar com segurança")
                except Exception as e:
                    if (dp, "err") not in warned:
                        warned.add((dp, "err"))
                        plan.warnings.append(f"sons não copiados: {e}")
                    continue
                if (dp, "err") in warned:
                    continue
                idx = sb.find(s)
                if not idx:
                    plan.warnings.append(f"o som {s} não existe no banco '{sbank}' da origem (lá ele já não tocava)")
                    continue
                want_audio = sorted(sb.audio(i) for i in idx)
                name = "/".join(parts[2:]).replace("/", "_")
                # sempre com o prefixo do talento: um nome "limpo" poderia ser um som que o destino já referencia
                new_ref = f"char/{dbank}/{new_talent}_{name}"
                n = 1
                while True:
                    have = db.find(new_ref)
                    if not have or sorted(db.audio(i) for i in have) == want_audio:
                        break
                    n += 1
                    new_ref = f"char/{dbank}/{new_talent}_{name}_{n}"
                if not have:
                    for i in idx:
                        db.add_from(sb, i, zsnd.pjw_hash(new_ref), caches[dp])
                    notes = plan.sound_banks.setdefault(dp, (db, []))[1]
                    notes.append(f"{s}  ->  {new_ref}" + (f"  ({len(idx)} variações)" if len(idx) > 1 else "")
                                 + f"  [{sb.file_name(idx[0])}, {sum(len(a) for a in want_audio) // 1024 or 1} KB]")
                ref_map[s.lower()] = new_ref
            if ref_map:
                for root in src_moves + new_events + new_ents:
                    for n in root.walk():
                        for a in n.attrs:
                            if a[0].lower() in SOUND_KEYS and a[1].lower() in ref_map:
                                a[1] = ref_map[a[1].lower()]
                sound_left = [ref_map.get(s.lower(), s) for s in sounds]

    # ---- animações ------------------------------------------------------------------
    anims_done = False
    if anim_tools is not None and not same_char and anims:
        if not anim_tools.available:
            plan.warnings.append("ferramenta de animação não encontrada em tools/ (animationProducer.exe); animações não importadas")
        else:
            try:
                ap = anim_tools.plan(src, dst, anims, remaining_enums, removed_enums)
                plan.anim, plan.anim_tools = ap, anim_tools
                plan.warnings += ap.warnings
                if ap.enum_map:
                    for m in src_moves:
                        e = m.get("animenum")
                        if e and e.lower() in ap.enum_map:
                            m.set("animenum", ap.enum_map[e.lower()])
                anims_done = True
                if ap.items:
                    plan.warnings.append("animações vêm do esqueleto de " + src.display + "; se os esqueletos forem "
                                         "muito diferentes (ossos extras, proporções) o movimento pode sair torto")
            except Exception as e:
                plan.warnings.append(f"não foi possível planejar as animações ({e}); animações não importadas")

    # ---- montar os arquivos de destino ------------------------------------------
    if tal_index is None:
        last = -1
        for i, t in enumerate(d_tal.children):
            if t.name == "talent" and t.get("power"):
                last = i
        tal_index = last + 1 if last >= 0 else len(d_tal.children)
    if not move_mode:
        d_tal.children.insert(min(tal_index, len(d_tal.children)), talent)
    if move_index is None or move_index > len(d_ps.children):
        d_ps.children.extend(new_events)
        d_ps.children.extend(src_moves)
    else:
        if one_file and not move_mode and move_index >= tal_index:
            move_index += 1
        d_ps.children[move_index:move_index] = new_events + src_moves

    rm_tal = [f"- talento antigo {new_talent}  ({old_desc})"] if replace else []
    rm_ps = [f"- FightMove antigo {n}" for n in removed_moves]
    tal_notes = rm_tal + ([] if move_mode else
                          [f"talento {new_talent}  ({talent.get('descname', '')})  com {len(var_map)} variáveis"])
    ps_notes = rm_ps + [f"FightMove {m.get('name')}" for m in src_moves] + [f"evento {e.get('name')}" for e in new_events]
    if one_file:
        plan.changes.append(FileChange(dst.talents_path, d_tal, tal_notes + ps_notes))
    else:
        if not move_mode:
            plan.changes.append(FileChange(dst.talents_path, d_tal, tal_notes))
        plan.changes.append(FileChange(dst.powerstyle_path, d_ps, ps_notes))
    if ent_change:
        plan.changes.append(ent_change)

    # ---- pacotes --------------------------------------------------------------------
    for v in interactions:
        add_want("fightstyle", strip_ext(v.replace("\\", "/")))
    refs = {norm(strip_ext(x)) for x in effects + sounds + models + interactions}
    refs |= {norm(strip_ext(x)).split("/")[-1] for x in interactions}
    refs |= {"models/" + norm(strip_ext(x)) for x in models} | {norm(strip_ext(x)).removeprefix("models/") for x in models}
    icon_tex = talent.get("icon_texture")
    if icon_tex:
        refs.add(norm(strip_ext(icon_tex)))
    for p in src.combat_packages:
        try:
            r = sproj.load(p)
        except Exception:
            continue
        for c in r.children:
            fn = c.get("filename", "")
            if fn and norm(strip_ext(fn)) in refs:
                if c.name == "effect" and not add_effects_to_pkg:
                    continue
                add_want(c.name, fn)

    if not same_char:
        for p in dst.combat_packages:
            try:
                r = proj.load(p).clone()
            except Exception as e:
                plan.warnings.append(f"pacote ilegível, não atualizado: {proj.rel(p)} ({e})")
                continue
            have = {(c.name, norm(strip_ext(c.get("filename", "")))) for c in r.children}
            has_fx = any(c.name == "effect" for c in r.children)
            notes = []
            for kind, fn in want:
                if (kind, norm(strip_ext(fn))) in have:
                    continue
                if kind == "effect" and not has_fx:
                    continue
                r.children.append(Node(kind, [["filename", fn]]))
                have.add((kind, norm(strip_ext(fn))))
                notes.append(f"{kind} = {fn}")
            if has_fx and add_effects_to_pkg:
                copied = {norm(strip_ext(proj.rel(d))).removeprefix("effects/") for _, d in plan.copies}
                for fx in effects:
                    if ("effect", norm(fx)) not in have and (proj.effect_path(fx) or norm(fx) in copied):
                        r.children.append(Node("effect", [["filename", fx]]))
                        have.add(("effect", norm(fx)))
                        notes.append(f"effect = {fx}")
            if notes:
                plan.changes.append(FileChange(p, r, notes))
        if not dst.combat_packages:
            plan.warnings.append(f"nenhum pacote de combate encontrado para {dst.display}; nada foi adicionado aos pacotes")

    # ---- resumo e avisos ----------------------------------------------------------------
    verb = "SUBSTITUI" if replace else "->"
    head = []
    if npc is not None:
        head.append(f"{src.display}: {info.talent_name or info.main} ({npc_talent.get('descname', '') if npc_talent is not None else 'move'})"
                    f"  ->  NPC {dst.display} ({dst.name}) como {new_main}"
                    + ("   SUBSTITUINDO: " + ", ".join(removed_moves) if removed_moves else ""))
    elif move_mode:
        head.append(f"{src.display}: FightMove {info.main}  {'SUBSTITUI o de mesmo nome em' if removed_moves else '->'}  {dst.display}"
                    "   (sem talento: ataque/move comum)")
    else:
        head.append(f"{src.display}: {old_t} ({info.talent.get('descname', '')})  {verb}  {dst.display}: {new_talent}"
                    + (f" ({old_desc})" if replace else ""))
        head.append(f"move principal: {info.main}  ->  {talent.get('power')}")
    plan.info[0:0] = head
    ren = [f"{k} -> {v}" for k, v in move_map.items() if k != v.lower()]
    if ren:
        plan.info.append("moves renomeados: " + ", ".join(ren))
    if event_map:
        plan.info.append("eventos renomeados (o destino tinha outro com o mesmo nome): "
                         + ", ".join(f"{k} -> {v}" for k, v in event_map.items()))
    now_moves = {(m.get("name") or "").lower() for m in d_ps.children if m.name == "FightMove"}
    missing_shared = sorted({b for a in included for b in info.succ.get(a, ())
                             if b not in included and b not in now_moves and b not in proj.common_moves()})
    if missing_shared:
        plan.warnings.append("o poder encadeia para moves que o destino não tem: " + ", ".join(missing_shared))
    if replace or removed_moves:
        new_ids = {id(m) for m in src_moves}
        dangling = sorted({a[1] for m in d_ps.children if m.name == "FightMove" and id(m) not in new_ids
                           for n in m.walk() for a in n.attrs
                           if a[0].lower() in MOVE_REF_KEYS and a[1].lower() in {x.lower() for x in removed_moves}
                           and a[1].lower() not in now_moves})
        if dangling:
            plan.warnings.append("outros moves do destino ainda encadeiam para moves do poder removido: " + ", ".join(dangling))
        new_vars = {v.lower() for v in var_map.values()}
        orphan = set()
        for r in (d_ps, d_tal):
            for n in r.walk():
                for _, v in n.attrs:
                    if "%" in v:
                        orphan |= {x for x in VAR_RE.findall(v) if x.lower() in removed_vars and x.lower() not in new_vars}
        if orphan:
            plan.warnings.append("variáveis do talento removido que ainda são usadas em outros lugares do destino e "
                                 "deixaram de existir: " + ", ".join("%" + o for o in sorted(orphan)))
    if not same_char:
        if anims:
            plan.info.append("animações usadas pelo poder: " + ", ".join(anims))
        if not anims_done and anims:
            d_anims = {m.get("animenum", "").lower() for m in proj.load(dst.powerstyle_path).children}
            new_a = [a for a in anims if a.lower() not in d_anims]
            plan.warnings.append("animações NÃO importadas: o poder vai tocar as animações de mesmo nome do destino"
                                 + (f"; {dst.display} ainda não usa: " + ", ".join(new_a) if new_a else ""))
        own_banks = {dst.sounddir.lower(), re.sub(r"_m$", "", dst.sounddir.lower()) + "_v"}
        foreign = sorted({s.split("/")[1] for s in sound_left
                          if s.lower().startswith("char/") and s.count("/") >= 2
                          and s.split("/")[1].lower() not in own_banks})
        if foreign:
            plan.warnings.append("sons que continuam apontando para o banco de outro personagem (" + ", ".join(foreign) +
                                 f"): só tocam se esse banco estiver carregado; o de {dst.display} é '{dst.sounddir}'")
        if not move_mode and (talent.get("icon") or any(m.get("icon") for m in src_moves)):
            plan.warnings.append(f"o número do ícone (icon = {talent.get('icon') or '?'}) veio da origem e agora aponta para a "
                                 "folha de ícones do destino: ajuste 'icon' no talento e no move para o desenho certo")
        copied = {norm(strip_ext(proj.rel(d))).removeprefix("effects/") for _, d in plan.copies}
        missing_fx = [e for e in effects if not proj.effect_path(e) and norm(e) not in copied]
        if missing_fx:
            plan.warnings.append("efeitos referenciados que não existem em effects/: " + ", ".join(missing_fx))
    if skin_filters:
        plan.warnings.append("há gatilhos com skin_filter da origem (" + ", ".join(skin_filters) +
                             "): troque pelos números de skin do destino")
    return plan


DAMAGE_KEYS = {"damage", "explodedamage", "impactdamage", "radiusdamage", "damage2"}
NPC_DROP_ATTRS = {"is_power", "icon", "combotextstarter", "combotextfinisher", "aicanuse"}
NPC_DROP_TRIGGERS = {"powerusage", "button_hint"}


def value_at_level(defs: list[Node], level: int) -> str | None:
    """Valor de uma variável de talento num nível (interpola entre os níveis definidos)."""
    pts = []
    for d in defs:
        try:
            pts.append((int(d.get("level", "1")), float(d.get("value", ""))))
        except (TypeError, ValueError):
            return d.get("value")  # valor não numérico (ex.: '3 5'): usa como está
    if not pts:
        return None
    pts.sort()
    if level <= pts[0][0]:
        v = pts[0][1]
    elif level >= pts[-1][0]:
        v = pts[-1][1]
    else:
        for (l0, v0), (l1, v1) in zip(pts, pts[1:]):
            if l0 <= level <= l1:
                v = v0 + (v1 - v0) * (level - l0) / (l1 - l0 or 1)
                break
    return str(int(round(v))) if abs(v - round(v)) < 1e-6 or abs(v) >= 20 else f"{v:.2f}".rstrip("0").rstrip(".")


def _to_npc(plan: Plan, npc: dict, moves: list[Node], events: list[Node], ents: list[Node], src_defs: dict, d_ps: Node):
    """Passa os moves copiados para o formato de NPC: dano por %mdmg_*, sem talento, sem custo, com dados de IA."""
    dmg_var = "%mdmg_low" if npc.get("damage") == "low" else "%mdmg_high"
    level = int(npc.get("level") or 1)
    fixed: dict[str, str] = {}
    unknown: set[str] = set()
    n_dmg = 0

    def number(m):
        var = m.group(1)
        defs = src_defs.get(var.lower())
        val = value_at_level(defs, level) if defs else None
        if val is None:
            unknown.add(var)
            return m.group(0)
        fixed[var] = val
        return val

    for root in moves + events + ents:
        for n in list(root.walk()):
            if n.name == "FightMove":
                n.children[:] = [c for c in n.children if c.name != "require"
                                 and not (c.name == "trigger" and (c.get("name") or "").lower() in NPC_DROP_TRIGGERS)]
                n.attrs[:] = [a for a in n.attrs if a[0].lower() not in NPC_DROP_ATTRS]
            has_dmg = False
            for a in n.attrs:
                k = a[0].lower()
                if k in DAMAGE_KEYS and "%" in a[1]:
                    a[1] = dmg_var
                    has_dmg = True
                    n_dmg += 1
                    if k == "explodedamage":
                        n.set("explodedamagescale", "difficulty")
                elif k == "powerusage":
                    a[1] = "1"
                elif "%" in a[1]:
                    a[1] = VAR_RE.sub(number, a[1])
            if has_dmg and any(a[0].lower() == "damage" for a in n.attrs):
                n.set("damagescale", "difficulty")
    first = True
    for m in moves:
        if first and npc.get("aireusetime"):
            m.set("aireusetime", str(npc["aireusetime"]))
        if first and not m.get("aitype"):
            m.set("aitype", npc.get("aitype") or "projectile")
        first = False
    plan.info.append(f"formato NPC: {n_dmg} valor(es) de dano -> {dmg_var} com damagescale = difficulty; "
                     f"require, custo de energia e ícone removidos; aitype = {moves[0].get('aitype') if moves else '-'}, "
                     f"aireusetime = {moves[0].get('aireusetime', '-') if moves else '-'}")
    if fixed:
        plan.info.append(f"variáveis trocadas pelo valor do nível {level} do talento: "
                         + ", ".join(f"%{k} = {v}" for k, v in sorted(fixed.items())))
    if unknown:
        plan.warnings.append("variáveis sem definição nos talentos da origem ficaram como estavam (o NPC não tem talentos): "
                             + ", ".join("%" + u for u in sorted(unknown)))
    if n_dmg == 0:
        plan.warnings.append("nenhum valor de dano com variável foi encontrado nos moves; confira se o poder causa dano por outro caminho")
    held = sorted({m.get("name") for m in moves for n in m.walk()
                   if (n.name == "trigger" and (n.get("name") or "").lower() == "charge")
                   or (n.name == "chain" and "hold" in (n.get("action") or "").lower())})
    if held:
        plan.warnings.append("poder de segurar/carregar botão (" + ", ".join(held) + "): a IA não segura botão; "
                             "revise as chains 'samepowerhold' para o poder seguir sozinho até o fim")
    talents = {t.get("name", "").lower() for t in plan_dst_stats(npc)}
    if npc.get("damage") != "low" and "monst_dmg_high" not in talents:
        plan.warnings.append("o NPC não tem o talento monst_dmg_high no npcstat: %mdmg_high pode valer zero; adicione o talento ou use dano baixo")
    if npc.get("damage") == "low" and "monst_dmg_low" not in talents:
        plan.warnings.append("o NPC não tem o talento monst_dmg_low no npcstat: %mdmg_low pode valer zero")


def plan_dst_stats(npc: dict) -> list[Node]:
    st = npc.get("stats")
    return [c for c in st.children if c.name == "talent"] if st is not None else []


def apply_plan(proj: Project, plan: Plan) -> list[str]:
    """Grava tudo. O set de animações é montado e conferido ANTES de qualquer gravação:
    se falhar, nada é alterado."""
    if plan.errors:
        raise ValueError("; ".join(plan.errors))
    proj = plan.proj or proj
    tools, built = plan.anim_tools, None
    try:
        if plan.anim is not None and plan.anim.items:
            built = tools.build(plan.anim)
        # bancos de som: gera, relê e confere tudo antes de gravar qualquer coisa
        sound_out: dict[str, bytes] = {}
        for path, (db, notes) in plan.sound_banks.items():
            with open(path, "rb") as f:
                if f.read() != db.original:
                    raise zsnd.ZsndError(f"{os.path.basename(path)} mudou no disco depois da prévia; atualize a prévia")
            data = db.to_bytes()
            tmp = path + ".novo~"
            try:
                with open(tmp, "wb") as f:
                    f.write(data)
                chk, old = zsnd.Bank(tmp), zsnd.Bank(path)
                if len(chk.sounds) != len(db.sounds) or len(chk.sounds) <= len(old.sounds) - 1:
                    raise zsnd.ZsndError("contagem de sons não confere")
                for i in range(len(old.sounds)):
                    if chk.sounds[i][0] != old.sounds[i][0] or chk.audio(i) != old.audio(i):
                        raise zsnd.ZsndError(f"o som {i} do banco {os.path.basename(path)} mudou ao regravar")
                for i in range(len(old.sounds), len(db.sounds)):
                    if chk.audio(i) != db.audio(i):
                        raise zsnd.ZsndError("um som novo não foi gravado corretamente")
            finally:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            sound_out[path] = data
        written = []
        for path, data in sound_out.items():
            proj.backup(path)
            with open(path + ".tmp~", "wb") as f:
                f.write(data)
            os.replace(path + ".tmp~", path)
            written.append(path)
        for s, d in plan.copies:
            proj.backup(d)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            proj.backup(d + ".txt")
            if os.path.isfile(d + ".txt"):
                os.remove(d + ".txt")  # o .txt antigo não corresponde mais ao binário
            written.append(d)
        for c in plan.changes:
            proj.save(c.path, c.root)
            written.append(c.path)
        if built:
            tools.install(plan.anim, built)
            written.append(plan.anim.target)
        return written
    finally:
        if tools is not None:
            tools.cleanup()
