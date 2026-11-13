"""Poderes montados pela interface: lista "Poder 1..N", cada um vindo de um personagem/talento,
com nome, ajuste fino (valores por nível) e opções simples do powerstyle e das entidades.

Inspiração: o criador de poderes do Freedom Force (escolhe o tipo, ajusta por magnitude: tipo de dano,
empurrão, custo...) e o Z Warriors do BT3 (aprende a técnica de qualquer lutador, renomeia e faz o
ajuste fino com barras, mostrando "x% do original").

Não altera transfer.py nem ops.py: usa transfer.build_plan / ops.remove_power_plan / ops.organize_plan.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import ops
import transfer
from project import Character, VAR_RE

# ------------------------------------------------------------------ rótulos simples
# sufixo do talentvalue -> (rótulo, explicação)
VAR_LABELS: list[tuple[str, str, str]] = [
    (r"req", "Nível para liberar", "Nível do personagem em que o poder fica disponível (e os níveis das melhorias)."),
    (r"pwr\d*|ep|cost|pow", "Custo de energia", "Quanto de energia (barra azul) o poder gasta."),
    (r"dmg\d*|dam|dm\d|expl_dmg|atk", "Dano", "Dano por acerto. Dois números = mínimo e máximo."),
    (r"lif\d*|life|dur|time", "Duração", "Quanto tempo o efeito dura (segundos)."),
    (r"spd|speed", "Velocidade", "Bônus de velocidade."),
    (r"def|ar|ref", "Defesa", "Bônus de defesa / resistência."),
    (r"kb", "Empurrão", "Força com que os inimigos são arremessados."),
    (r"rng|rad|size", "Alcance / tamanho", "Raio ou alcance do poder."),
    (r"num|cnt|num_att", "Quantidade", "Quantidade de projéteis, golpes ou criaturas."),
    (r"hlt|hlth|heal", "Vida", "Vida recuperada ou vida da criatura."),
    (r"pct|chance|crit", "Chance (%)", "Porcentagem de chance."),
    (r"str|hvy|atk_bonus|dam_boost|bld|bla", "Bônus de ataque", "Bônus de dano / força."),
]

DAMAGE_TYPES = [("dmg_physical", "Físico"), ("dmg_energy", "Energia"), ("dmg_fire", "Fogo"), ("dmg_cold", "Gelo"),
                ("dmg_electricity", "Elétrico"), ("dmg_mental", "Mental"), ("dmg_blade", "Lâmina"),
                ("dmg_radiation", "Radiação"), ("dmg_wind", "Vento")]
KNOCKBACK = [("0", "Nenhum"), ("100", "Baixo"), ("190", "Médio"), ("300", "Alto"), ("500", "Muito alto"), ("800", "Extremo")]
ATTACK_TRIGGERS = ("punch", "radial", "projectile")

# campos do powerstyle (gatilhos dos moves do poder) e das entidades que a interface mostra
# chave -> (rótulo, explicação, tipo)  tipo: choice_dmg | choice_kb | scale | bool | int
FIELDS: dict[str, tuple[str, str, str]] = {
    "damagetype": ("Tipo de dano", "Que tipo de dano o golpe causa (o inimigo resiste ou é fraco a cada tipo).", "choice_dmg"),
    "knockback": ("Empurrão", "Quanto os inimigos são arremessados ao serem atingidos.", "choice_kb"),
    "maxrange": ("Alcance", "Distância máxima do golpe ou do projétil (% do original).", "scale"),
    "speed": ("Velocidade do projétil", "Quão rápido o projétil voa (% do original).", "scale"),
    "count": ("Quantidade de projéteis", "Quantos projéteis saem por uso.", "int"),
    "pierce": ("Atravessa inimigos", "O projétil continua depois de acertar alguém.", "bool"),
    "charge_time": ("Tempo de carga", "Segundos segurando o botão até carregar (% do original).", "scale"),
    "ent_scale": ("Tamanho do projétil", "Tamanho do modelo do projétil (% do original).", "scale"),
    "ent_lifetime": ("Duração do projétil", "Quanto tempo o projétil/entidade fica no mundo (% do original).", "scale"),
    "ent_exploderadius": ("Raio da explosão", "Raio do dano quando o projétil explode (% do original).", "scale"),
}


def var_label(var: str, talent: str) -> tuple[str, str]:
    suf = var[len(talent):].lstrip("_") if var.lower().startswith(talent.lower()) else var.rsplit("_", 1)[-1]
    for rx, lab, exp in VAR_LABELS:
        if re.fullmatch(rx, suf, re.I):
            return lab, exp
    return suf or var, "Valor usado pelo poder (variável %" + var + ")."


# ------------------------------------------------------------------ dados de um poder
@dataclass
class PowerSlot:
    """Um "Poder N" da lista. src = personagem de onde vem o talento (None = o próprio poder do personagem)."""
    src: Character | None = None
    talent: str = ""  # talento no personagem de origem
    orig: int = -1  # índice do poder original do personagem (lista powers()) que este slot ocupa; -1 = poder novo
    name: str = ""  # descname novo ("" = manter)
    short: str = ""  # descshort novo
    desc: str = ""  # description nova
    var_scale: dict[int, float] = field(default_factory=dict)  # ordem da variável no talento -> multiplicador
    fields: dict[str, str] = field(default_factory=dict)  # damagetype/knockback/count/pierce -> valor
    field_scale: dict[str, float] = field(default_factory=dict)  # maxrange/speed/charge_time/ent_* -> multiplicador
    anims: bool = True
    sounds: bool = True

    def changes(self) -> int:
        return (sum(1 for v in self.var_scale.values() if abs(v - 1) > 1e-6) + len(self.fields)
                + sum(1 for v in self.field_scale.values() if abs(v - 1) > 1e-6)
                + sum(1 for x in (self.name, self.short, self.desc) if x))


class PowerData:
    """Leitura de um poder (de qualquer personagem) para a interface."""

    def __init__(self, char: Character, talent: str):
        self.char = char
        self.info = transfer.PowerInfo(char.proj, char, talent)
        self.talent = self.info.talent
        self.name = self.info.talent_name
        self.moves = [m for m in self.info.moves if (m.get("name") or "").lower() in self.info.own]
        main = next((m for m in self.moves if (m.get("name") or "").lower() == (self.info.main or "").lower()), None)
        self.animenum = main.get("animenum", "") if main is not None else ""

    @property
    def descname(self):
        return self.talent.get("descname", "")

    @property
    def descshort(self):
        return self.talent.get("descshort", "")

    @property
    def description(self):
        return self.talent.get("description", "")

    def variables(self) -> list[tuple[int, str, str, str, list[tuple[int, str]]]]:
        """[(ordem, variável, rótulo, explicação, [(nível, valor)])] na ordem em que aparecem no talento."""
        out: dict[str, list] = {}
        for n in self.talent.walk():
            if n.name == "talentvalue" and n.get("name"):
                out.setdefault(n.get("name"), []).append((int(n.get("level", "0") or 0), n.get("value", "")))
        res = []
        for i, (var, vals) in enumerate(out.items()):
            lab, exp = var_label(var, self.name)
            res.append((i, var, lab, exp, sorted(vals)))
        return res

    def triggers(self, kinds=ATTACK_TRIGGERS + ("charge",)):
        for m in self.moves:
            for n in m.walk():
                if n.name == "trigger" and (n.get("name") or "").lower() in kinds:
                    yield n

    def entities(self) -> list:
        names = {(t.get("entity") or "").lower() for t in self.triggers(("projectile", "spawn")) if t.get("entity")}
        out = []
        for p in self.char.entity_paths:
            try:
                for n in self.char.proj.load(p).walk():
                    if n.name == "entity" and (n.get("name") or "").lower() in names:
                        out.append(n)
            except Exception:
                pass
        return out

    def fields(self) -> dict[str, list[str]]:
        """Campos ajustáveis que este poder tem, com os valores atuais (literais; %variáveis ficam no ajuste fino)."""
        found: dict[str, list[str]] = {}
        for t in self.triggers():
            for k, v in t.attrs:
                k = k.lower()
                if k in FIELDS and not VAR_RE.search(v):
                    found.setdefault(k, []).append(v)
        for e in self.entities():
            for k in ("scale", "lifetime", "exploderadius"):
                if e.get(k) and not VAR_RE.search(e.get(k)):
                    found.setdefault(f"ent_{k}", []).append(e.get(k))
        return found

    def kind(self) -> str:
        t = {(x.get("name") or "").lower() for x in self.triggers(ATTACK_TRIGGERS)}
        s = (self.descshort or "").strip()
        if s:
            return s
        return "Projétil" if "projectile" in t else "Área" if "radial" in t else "Corpo a corpo" if "punch" in t else "Bônus / outro"


# ------------------------------------------------------------------ ajustes
def scale_value(value: str, k: float, keep_int: bool = True) -> str:
    """Multiplica cada número de um valor ('17 19' -> '26 29'). keep_int: inteiro continua inteiro
    (dano, energia); sem ele, 1 x 1.5 vira 1.5 (tamanho, alcance, duração)."""
    def one(tok: str) -> str:
        try:
            if keep_int and re.fullmatch(r"-?\d+", tok):
                return str(max(0, round(int(tok) * k)) if int(tok) >= 0 else round(int(tok) * k))
            f = float(tok)
            return f"{f * k:.3f}".rstrip("0").rstrip(".")
        except ValueError:
            return tok
    return " ".join(one(t) for t in value.split())


def preview_values(vals: list[tuple[int, str]], k: float) -> str:
    if not vals:
        return ""
    a, b = vals[0], vals[-1]
    f = (lambda v: scale_value(v, k)) if abs(k - 1) > 1e-6 else (lambda v: v)
    return f"nível {a[0]}: {f(a[1])}" + (f"   ·   nível {b[0]}: {f(b[1])}" if len(vals) > 1 else "")


def _apply_to_power(char: Character, talent_name: str, slot: PowerSlot) -> list[str]:
    """Aplica nome, ajuste fino e campos no talento/powerstyle/entidades do personagem. Devolve arquivos gravados."""
    proj = char.proj
    written = []
    tal_root = proj.load(char.talents_path).clone()
    talent = next((t for t in tal_root.children if t.name == "talent" and t.get("name", "").lower() == talent_name.lower()), None)
    if talent is None:
        raise ValueError(f"talento {talent_name} não encontrado em {os.path.basename(char.talents_path)}")
    one_file = os.path.normcase(char.talents_path) == os.path.normcase(char.powerstyle_path)
    changed_tal = False
    for key, val in (("descname", slot.name), ("descshort", slot.short), ("description", slot.desc)):
        if val:
            talent.set(key, val)
            changed_tal = True
    order: dict[str, int] = {}
    for n in talent.walk():
        if n.name == "talentvalue" and n.get("name"):
            i = order.setdefault(n.get("name"), len(order))
            k = slot.var_scale.get(i, 1.0)
            if abs(k - 1) > 1e-6 and n.get("value"):
                if var_label(n.get("name"), talent_name)[0] == "Nível para liberar":
                    continue  # nível de liberação não se multiplica (é ajustado por 'Organizar')
                n.set("value", scale_value(n.get("value"), k))
                changed_tal = True
    ps_root = tal_root if one_file else proj.load(char.powerstyle_path).clone()
    info = transfer.PowerInfo(proj, char, talent_name)
    own = info.own
    changed_ps = False
    ent_names = set()
    for m in ps_root.children:
        if m.name != "FightMove" or (m.get("name") or "").lower() not in own:
            continue
        for n in m.walk():
            if n.name != "trigger":
                continue
            kind = (n.get("name") or "").lower()
            if kind in ("projectile", "spawn") and n.get("entity"):
                ent_names.add(n.get("entity").lower())
            if kind not in ATTACK_TRIGGERS + ("charge",):
                continue
            for a in n.attrs:
                k = a[0].lower()
                if VAR_RE.search(a[1]):
                    continue
                if k in slot.fields and kind != "charge":
                    if k in ("damagetype", "knockback", "pierce") or (k == "count" and kind == "projectile"):
                        a[1] = slot.fields[k]
                        changed_ps = True
                elif k in slot.field_scale and abs(slot.field_scale[k] - 1) > 1e-6:
                    a[1] = scale_value(a[1], slot.field_scale[k], keep_int=k not in ("charge_time",))
                    changed_ps = True
    if changed_tal or (one_file and changed_ps):
        proj.save(char.talents_path, tal_root)
        written.append(char.talents_path)
    if changed_ps and not one_file:
        proj.save(char.powerstyle_path, ps_root)
        written.append(char.powerstyle_path)
    ent_keys = {k[4:]: v for k, v in slot.field_scale.items() if k.startswith("ent_") and abs(v - 1) > 1e-6}
    if ent_keys and ent_names:
        for p in char.entity_paths:
            root = proj.load(p).clone()
            hit = False
            for n in root.walk():
                if n.name == "entity" and (n.get("name") or "").lower() in ent_names:
                    for a in n.attrs:
                        if a[0].lower() in ent_keys and not VAR_RE.search(a[1]):
                            a[1] = scale_value(a[1], ent_keys[a[0].lower()], keep_int=False)
                            hit = True
            if hit:
                proj.save(p, root)
                written.append(p)
    return written


def default_slots(char: Character) -> list[PowerSlot]:
    """Os poderes do personagem na ordem de liberação (o Xtreme por último)."""
    pw = char.powers()
    info = {t: (k, req) for t, _, k, req in ops.power_talents(char)}

    def key(i):
        t = pw[i][0]
        k, req = info.get(t, ("power", "99"))
        try:
            r = int(req)
        except ValueError:
            r = 99
        return (k == "xtreme", r, i)

    return [PowerSlot(src=char, talent=pw[i][0], orig=i) for i in sorted(range(len(pw)), key=key)]


def describe(slots: list[PowerSlot], owner: Character | None) -> list[str]:
    own_pw = owner.powers() if owner else []
    L = []
    for i, s in enumerate(slots, 1):
        try:
            d = PowerData(s.src, s.talent)
            nm = s.name or d.descname
        except Exception as e:
            L.append(f"  ! Poder {i}: {s.talent} de {s.src.display if s.src else '?'} não pode ser lido ({e})")
            continue
        own = s.src is owner or (owner is not None and s.src is not None and s.orig >= 0 and s.talent == own_pw[s.orig][0])
        L.append(f"  Poder {i}: {nm}   " + ("(mantido)" if own else f"(de {s.src.display}: {d.descname})")
                 + (f"   {s.changes()} ajuste(s)" if s.changes() else ""))
    used = {s.orig for s in slots if s.orig >= 0}
    gone = [own_pw[i][1] or own_pw[i][0] for i in range(len(own_pw)) if i not in used]
    if gone:
        L.append("  removidos: " + ", ".join(gone))
    return L


def apply(owner: Character, slots: list[PowerSlot], anim_tools=None, organize: bool = True,
          find_owner=None) -> tuple[list[str], list[str]]:
    """Monta os poderes de 'owner' conforme os slots. find_owner() relê o personagem depois de cada gravação.
    Devolve (arquivos gravados, avisos). Um poder com problema vira aviso, os outros continuam."""
    refresh = find_owner or (lambda: owner)
    written, warns = [], []
    orig = owner.powers()
    orig_names = [t for t, _, _ in orig]
    used = {s.orig for s in slots if s.orig >= 0}
    # 1) poderes originais que saíram da lista
    for i, t in enumerate(orig_names):
        if i in used:
            continue
        ch = refresh()
        plan = ops.remove_power_plan(ch, t)
        if plan.errors:
            warns.append(f"não consegui remover {t}: {'; '.join(plan.errors)}")
            continue
        written += transfer.apply_plan(ch.proj, plan)
    # 2) poderes vindos de outro personagem (ou de outro talento)
    final: list[tuple[int, PowerSlot, str]] = []  # (número, slot, talento no personagem)
    for n, s in enumerate(slots, 1):
        ch = refresh()
        keep = s.orig >= 0 and s.src is not None and s.talent == orig_names[s.orig] and \
            (s.src is owner or s.src.name.lower() == owner.name.lower() and s.src.proj.root == owner.proj.root)
        if keep:
            final.append((n, s, orig_names[s.orig]))
            continue
        try:
            info = transfer.PowerInfo(s.src.proj, s.src, s.talent)
        except Exception as e:
            warns.append(f"Poder {n}: {e}")
            continue
        replace = orig_names[s.orig] if s.orig >= 0 else None
        if replace:
            nt, nm = replace, next((m for t, _, m in orig if t == replace), "")
        else:
            nt, nm = transfer.suggest_names(ch.proj, ch)
        plan = transfer.build_plan(ch.proj, info, ch, nt, nm, replace=replace, independent=True,
                                   anim_tools=anim_tools if (s.anims and anim_tools is not None and anim_tools.available) else None,
                                   copy_sounds=s.sounds)
        if plan.errors:
            warns.append(f"Poder {n} ({info.talent.get('descname', s.talent)}): " + "; ".join(plan.errors))
            continue
        warns += [f"Poder {n}: {w}" for w in plan.warnings]
        written += transfer.apply_plan(ch.proj, plan)
        final.append((n, s, nt))
    # 3) nome, ajuste fino e campos
    for n, s, t in final:
        if s.changes():
            try:
                written += _apply_to_power(refresh(), t, s)
            except Exception as e:
                warns.append(f"Poder {n}: ajustes não aplicados ({e})")
    # 4) ordem e níveis de liberação
    if organize and final:
        ch = refresh()
        root = ch.proj.load(ch.talents_path)
        kinds = {t.get("name", "").lower(): ops.talent_kind(t) for t in root.children if t.name == "talent"}
        order = [(t, kinds.get(t.lower(), "power")) for _, _, t in final if t.lower() in kinds]
        plan = ops.organize_plan(ch, order)
        if plan.errors:
            warns.append("ordem/níveis não reorganizados: " + "; ".join(plan.errors) + " (use 'Organizar poderes' depois)")
        else:
            written += transfer.apply_plan(ch.proj, plan)
    return written, warns
