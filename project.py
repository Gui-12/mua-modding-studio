"""Modelo do projeto: localiza a pasta do jogo, indexa personagens pelo herostat,
resolve qual arquivo o jogo carrega e grava com backup."""
from __future__ import annotations

import os
import re
import shutil
import time

import xmlb
from xmlb import Node

BIN_EXTS = (".engb", ".xmlb", ".pkgb")
EFFECT_KEYS = {"effect", "hiteffect", "loopfx", "deatheffect", "xdeatheffect", "spawneffect",
               "touchfx", "deathfx", "impacteffect", "chargeeffect"}
SOUND_KEYS = {"sound", "deathsound", "xdeathsound", "loopsound", "spawnsound"}
MOVE_REF_KEYS = {"result", "fallback"}
# destinos de chain que o proprio jogo resolve (aparecem em dezenas de powerstyles sem FightMove)
BUILTIN_MOVES = {"null", "powers", "rollforward", "advance", "retreat", "strafeleft", "straferight",
                 "dodgeleft", "dodgeright", "sprint", "fastballland"}
COLOR_KEY_RE = re.compile(r"colou?r", re.I)
VAR_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)")


def norm(p: str) -> str:
    return p.replace("\\", "/").strip().lower()


def strip_ext(p: str) -> str:
    return re.sub(r"\.(png|igb|tga|dds|xmlb|engb|pkgb)$", "", p, flags=re.I)


def find_game_root(start: str) -> str | None:
    d = os.path.abspath(start)
    for _ in range(6):
        if os.path.isdir(os.path.join(d, "data")) and os.path.isdir(os.path.join(d, "packages")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


class Character:
    is_npc = False  # True para os personagens que vêm do npcstat

    def __init__(self, proj: "Project", stats: Node):
        self.proj = proj
        self.stats = stats
        self.name = stats.get("name", "?")
        self.display = stats.get("charactername", self.name)
        self.powerstyle = stats.get("powerstyle", "")
        self.sounddir = stats.get("sounddir", "")
        self.anims = stats.get("characteranims", "")
        self.skins = self._skins()
        self._packages = None

    def _skins(self) -> list[tuple[str, str]]:
        out = []
        first = self.stats.get("skin")
        if not first:
            return out
        out.append((first, self.stats.get("skin_01_name", "")))
        prefix = first[:-2]
        for i in range(2, 13):
            suf = self.stats.get(f"skin_{i:02d}")
            if suf:
                out.append((prefix + suf, self.stats.get(f"skin_{i:02d}_name", "")))
        return out

    # ---- arquivos -------------------------------------------------------
    @property
    def packages(self) -> list[str]:
        if self._packages is None:
            d = os.path.join(self.proj.root, "packages", "generated", "characters")
            ids = {s for s, _ in self.skins}
            found = []
            if os.path.isdir(d):
                for f in sorted(os.listdir(d)):
                    m = re.match(r"^(.+?)_(\d+)(_nc)?\.pkgb$", f, re.I)
                    if m and m.group(2) in ids:  # o número da skin e unico por personagem
                        found.append(os.path.join(d, f))
            # herói e NPC podem dividir a mesma skin: se houver pacotes com o nome exato do personagem, só eles valem
            mine = [p for p in found if re.match(r"^(.+?)_\d+(_nc)?\.pkgb$", os.path.basename(p), re.I).group(1).lower() == self.name.lower()]
            self._packages = mine or found
        return self._packages

    @property
    def combat_packages(self) -> list[str]:
        return [p for p in self.packages if not p.lower().endswith("_nc.pkgb")]

    def package_entries(self, kind: str) -> list[str]:
        """Valores 'filename' dos blocos <kind> em todos os pacotes de combate."""
        seen, out = set(), []
        for p in self.combat_packages:
            try:
                root = self.proj.load(p)
            except Exception:
                continue
            for c in root.children:
                if c.name == kind:
                    v = c.get("filename", "")
                    if v and norm(v) not in seen:
                        seen.add(norm(v))
                        out.append(v)
        return out

    @property
    def powerstyle_path(self) -> str | None:
        return self.proj.resolve(f"data/powerstyles/{self.powerstyle}") if self.powerstyle else None

    @property
    def talents_path(self) -> str | None:
        for v in self.package_entries("xml_talents"):
            p = self.proj.resolve(v)
            if p:
                return p
        return self.proj.resolve(f"data/talents/{self.name.lower()}")

    @property
    def entity_paths(self) -> list[str]:
        out = []
        for v in self.package_entries("xml"):
            p = self.proj.resolve(v)
            if p and p not in out:
                out.append(p)
        p = self.proj.resolve(f"data/entities/ents_{self.name.lower()}")
        if p and p not in out:
            out.append(p)
        return out

    def powers(self) -> list[tuple[str, str, str]]:
        """[(nome do talento, nome exibido, move principal)] dos talentos que tem 'power'."""
        p = self.talents_path
        if not p:
            return []
        try:
            root = self.proj.load(p)
        except Exception:
            return []
        return [(t.get("name", ""), t.get("descname", ""), t.get("power", ""))
                for t in root.children if t.name == "talent" and t.get("power")]

    def talent_for_move(self, move: Node) -> Node | None:
        """Talento ao qual um FightMove pertence (pelo require, powerup_tag ou pelo nome powerN...)."""
        p = self.talents_path
        if not p:
            return None
        try:
            talents = [t for t in self.proj.load(p).children if t.name == "talent"]
        except Exception:
            return None
        by_name = {t.get("name", "").lower(): t for t in talents}
        for r in move.find_all("require"):
            t = by_name.get(r.get("item", "").lower())
            if t is not None:
                return t
        t = by_name.get((move.get("powerup_tag") or "").lower())
        if t is not None:
            return t
        nm = (move.get("name") or "").lower()
        best = None
        for t in talents:
            pw = (t.get("power") or "").lower()
            if not pw:
                continue
            if nm == pw:
                return t
            if nm.startswith(pw) and not nm[len(pw):len(pw) + 1].isdigit():
                if best is None or len(pw) > len(best.get("power")):
                    best = t
        return best

    def referenced(self, keys: set[str]) -> list[str]:
        """Valores distintos de certas chaves no powerstyle + entidades do personagem."""
        seen, out = set(), []
        for p in [self.powerstyle_path] + self.entity_paths:
            if not p:
                continue
            try:
                root = self.proj.load(p)
            except Exception:
                continue
            for n in root.walk():
                for k, v in n.attrs:
                    if k.lower() in keys and v.strip() and norm(v) not in seen:
                        seen.add(norm(v))
                        out.append(v.replace("\\", "/"))
        return sorted(out, key=str.lower)


class Project:
    kind = "jogo"  # "jogo" (pasta completa do MUA) ou "avulso" (pasta de um personagem)

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.label = os.path.basename(self.root.rstrip("\\/")) or self.root
        self._cache: dict[str, tuple[float, Node]] = {}
        self.backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
        self.session = time.strftime("%Y-%m-%d_%H%M%S")
        self.characters: list[Character] = []
        self.herostat_path: str | None = None
        self.reload_characters()

    # ---- caminhos -------------------------------------------------------
    def rel(self, path: str) -> str:
        try:
            return os.path.relpath(path, self.root).replace("\\", "/")
        except ValueError:
            return path

    def resolve(self, base: str, exts=(".engb", ".xmlb", ".pkgb")) -> str | None:
        """Recebe um caminho sem extensao relativo a raiz do jogo e devolve o binário
        que o jogo carrega (prefere .engb, depois .xmlb)."""
        base = strip_ext(base.replace("\\", "/")).lstrip("/")
        full = os.path.join(self.root, *base.split("/"))
        for e in exts:
            if os.path.isfile(full + e):
                return full + e
        return None

    def effect_path(self, value: str) -> str | None:
        return self.resolve("effects/" + value.strip(), (".xmlb", ".engb"))

    # ---- carga ----------------------------------------------------------
    def load(self, path: str) -> Node:
        """Arvore somente-leitura (cacheada). Use .clone() antes de alterar."""
        mt = os.path.getmtime(path)
        c = self._cache.get(path)
        if c and c[0] == mt:
            return c[1]
        node = xmlb.load_file(path)
        self._cache[path] = (mt, node)
        return node

    def reload_characters(self):
        self.herostat_path = self.resolve("data/herostat")
        self.characters = []
        if not self.herostat_path:
            return
        root = self.load(self.herostat_path)
        for s in root.children:
            if s.name == "stats" and s.get("name"):
                self.characters.append(Character(self, s))
        self.characters.sort(key=lambda c: c.display.lower())

    def npcs(self) -> list["Character"]:
        """NPCs do data/npcstat que têm powerstyle (os que lutam)."""
        p = self.resolve("data/npcstat")
        if not p:
            return []
        mt = os.path.getmtime(p)
        c = getattr(self, "_npcs", None)
        if c is None or c[0] != mt:
            out = [Character(self, s) for s in self.load(p).children if s.name == "stats" and s.get("name") and s.get("powerstyle")]
            for x in out:
                x.is_npc = True
            out.sort(key=lambda x: (x.display.lower(), x.name.lower()))
            self._npcs = c = (mt, out)
        return c[1]

    def all_vars(self) -> set[str]:
        """Todas as variáveis de talento desta pasta (para avisar %variável inexistente)."""
        c = getattr(self, "_vars", None)
        if c is None:
            c = set()
            d = os.path.join(self.root, "data", "talents")
            seen = set()
            if os.path.isdir(d):
                for f in sorted(os.listdir(d)):
                    if f.lower().endswith((".engb", ".xmlb")) and f.rsplit(".", 1)[0].lower() not in seen:
                        seen.add(f.rsplit(".", 1)[0].lower())
                        try:
                            c |= talent_vars(self.load(os.path.join(d, f)))
                        except Exception:
                            pass
            self._vars = c
        return c

    def owns(self, path: str) -> bool:
        a, b = os.path.normcase(os.path.abspath(path)), os.path.normcase(self.root)
        return a == b or a.startswith(b.rstrip("\\/") + os.sep)

    def common_moves(self) -> set[str]:
        """FightMoves dos fightstyles comuns + os que o próprio jogo resolve (null, powers, rollforward...)."""
        c = getattr(self, "_common", None)
        if c is None:
            c = set(BUILTIN_MOVES)
            d = os.path.join(self.root, "data", "fightstyles")
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.lower().endswith((".engb", ".xmlb")):
                        try:
                            c |= {(m.get("name") or "").lower() for m in self.load(os.path.join(d, f)).children}
                        except Exception:
                            pass
            self._common = c
        return c

    def character(self, name: str) -> Character | None:
        for c in self.characters:
            if c.name.lower() == name.lower():
                return c
        return None

    def character_for_path(self, path: str) -> Character | None:
        path = os.path.normcase(os.path.abspath(binary_of(path)))
        base = os.path.basename(path)
        for c in self.characters:
            for p in (c.powerstyle_path, c.talents_path):
                if p and os.path.normcase(p) == path:
                    return c
        for c in self.characters:
            if any(os.path.normcase(p) == path for p in c.entity_paths + c.packages):
                return c
        m = re.search(r"[\\/]effects[\\/]char[\\/]([^\\/]+)[\\/]", path)
        if m:
            return self.character(m.group(1))
        return None

    # ---- gravacao -------------------------------------------------------
    def backup(self, path: str):
        if not os.path.isfile(path):
            return
        dst = os.path.join(self.backup_dir, self.session, re.sub(r"[^A-Za-z0-9_. -]", "_", self.label),
                           self.rel(path).replace("/", os.sep))
        if os.path.exists(dst):
            return  # mantem o estado do inicio da sessao
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(path, dst)

    def save(self, bin_path: str, root: Node, text: str | None = None):
        """Grava o binário e o .txt ao lado, guardando backup dos dois."""
        data = xmlb.write_binary(root)
        xmlb.read_binary(data)  # garante que o que foi gerado e legivel
        txt_path = bin_path + ".txt"
        self.backup(bin_path)
        self.backup(txt_path)
        os.makedirs(os.path.dirname(bin_path), exist_ok=True)
        tmp = bin_path + ".tmp~"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, bin_path)
        xmlb.write_text_file(txt_path, text if text is not None else xmlb.format_text(root))
        self._cache.pop(bin_path, None)


# ----------------------------------------------------------- personagem avulso
def find_content_root(start: str) -> str | None:
    """Procura para baixo (até 3 níveis) a pasta que tem a estrutura do jogo (data/, actors/ ou packages/)."""
    start = os.path.abspath(start)
    level = [start]
    for _ in range(4):
        nxt = []
        for d in level:
            try:
                names = os.listdir(d)
            except OSError:
                continue
            low = {n.lower() for n in names}
            if "data" in low or "packages" in low:
                return d
            nxt += [os.path.join(d, n) for n in names if os.path.isdir(os.path.join(d, n))]
        level = nxt[:200]
    return None


def _stats_from_xml(text: str) -> list[Node]:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        root = ET.fromstring("<r>" + re.sub(r"<\?xml[^>]*\?>", "", text) + "</r>")

    def conv(e) -> Node:
        return Node(e.tag, [[k, v] for k, v in e.attrib.items()], [conv(c) for c in e])

    return [conv(e) for e in root.iter("stats")]


def _stats_from_json(text: str) -> list[Node]:
    import json
    out: list[Node] = []

    def conv(name, obj) -> Node:
        n = Node(name)
        for k, v in obj.items():
            if isinstance(v, dict):
                n.children.append(conv(k, v))
            elif isinstance(v, list):
                n.children += [conv(k, x) for x in v if isinstance(x, dict)]
            else:
                n.attrs.append([k, str(v).lower() if isinstance(v, bool) else str(v)])
        return n

    def find(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "stats":
                    for x in (v if isinstance(v, list) else [v]):
                        if isinstance(x, dict):
                            out.append(conv("stats", x))
                else:
                    find(v)
        elif isinstance(obj, list):
            for x in obj:
                find(x)

    find(json.loads(text))
    return out


def read_herostat_snippet(path: str) -> list[Node]:
    """Lê um pedaço de herostat solto (o .txt/.xml/.json que vem junto com um mod de personagem)."""
    try:
        if is_editable(path) and os.path.isfile(binary_of(path)):
            return [n for n in xmlb.load_file(binary_of(path)).walk() if n.name == "stats"]
        text = xmlb.read_text_file(path)
    except Exception:
        return []
    t = text.lstrip("\ufeff \t\r\n")
    try:
        if t.startswith("<"):
            return _stats_from_xml(t)
        if t.startswith(("{", "[")) and '"' in t[:200]:
            return _stats_from_json(t)
    except Exception:
        return []
    if "stats" not in t:
        return []
    for cand in (t, "XMLB characters {\n" + t + "\n}"):
        root, _ = xmlb.parse_text(cand, strict=False)
        if root is not None:
            found = [n for n in root.walk() if n.name == "stats" and n.get("name")]
            if found:
                return found
    return []


class LooseProject(Project):
    """Pasta de um personagem fora do jogo (um mod baixado, um trabalho em andamento).
    Os personagens vêm do pedaço de herostat que estiver na pasta; se não houver, são deduzidos dos pacotes."""
    kind = "avulso"

    def __init__(self, folder: str):
        self.folder = os.path.abspath(folder)
        self.snippets: dict[str, str] = {}  # nome do personagem -> arquivo de herostat de onde veio
        super().__init__(find_content_root(folder) or folder)
        self.label = os.path.basename(self.folder.rstrip("\\/")) or self.folder

    def reload_characters(self):
        self.herostat_path = None
        self.characters = []
        self.snippets = {}
        seen = set()
        cands = []
        for base in {self.folder, self.root}:
            for dp, dn, fn in os.walk(base):
                depth = os.path.relpath(dp, base).count(os.sep)
                if depth >= 2:
                    dn[:] = []
                for f in fn:
                    low = f.lower()
                    if low.endswith((".txt", ".xml", ".json", ".engb", ".xmlb")) and \
                            ("herostat" in low or (dp == base and low.endswith((".txt", ".xml", ".json")))):
                        cands.append(os.path.join(dp, f))
        for p in sorted(set(cands), key=lambda x: ("herostat" not in os.path.basename(x).lower(), len(x))):
            try:
                if os.path.getsize(p) > 3_000_000:
                    continue
            except OSError:
                continue
            for s in read_herostat_snippet(p):
                nm = (s.get("name") or "").lower()
                if nm and nm not in seen and s.get("powerstyle"):
                    seen.add(nm)
                    self.characters.append(Character(self, s))
                    self.snippets[nm] = p
                    if self.herostat_path is None:
                        self.herostat_path = p
        # sem herostat: deduz dos pacotes  <nome>_<skin>.pkgb
        d = os.path.join(self.root, "packages", "generated", "characters")
        groups: dict[str, list[str]] = {}
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                m = re.match(r"^(.+?)_(\d+)\.pkgb$", f, re.I)
                if m:
                    groups.setdefault(m.group(1).lower(), []).append(m.group(2))
        known_skins = {s for c in self.characters for s, _ in c.skins}
        for name, skins in groups.items():
            if name in seen or any(s in known_skins for s in skins):
                continue
            st = Node("stats", [["name", name], ["charactername", name + " (sem herostat)"], ["skin", skins[0]]])
            for i, sk in enumerate(skins[1:], 2):
                if sk[:-2] == skins[0][:-2]:
                    st.attrs.append([f"skin_{i:02d}", sk[-2:]])
            try:
                pk = self.load(os.path.join(d, f"{name}_{skins[0]}.pkgb"))
                for c in pk.children:
                    fn = c.get("filename", "")
                    base = fn.replace("\\", "/").split("/")[-1]
                    if c.name == "fightstyle" and base.lower().startswith("ps_") and not st.get("powerstyle"):
                        st.attrs.append(["powerstyle", base])
                    if c.name == "actoranimdb" and not st.get("characteranims") and not base.lower().startswith("interact_"):
                        st.attrs.append(["characteranims", base])
            except Exception:
                pass
            self.characters.append(Character(self, st))
        self.characters.sort(key=lambda c: c.display.lower())


class CreatedProject(Project):
    """Personagens criados/clonados pelo MUA Studio: os arquivos ficam dentro da pasta do jogo,
    e o herostat de cada um fica guardado em store_dir até ser colocado no herostat do jogo."""
    kind = "criado"

    def __init__(self, game_root: str, store_dir: str):
        self.store_dir = store_dir
        self.snippets: dict[str, str] = {}
        super().__init__(game_root)
        self.label = "Criados"

    def reload_characters(self):
        self.herostat_path = None
        self.characters = []
        self.snippets = {}
        if not os.path.isdir(self.store_dir):
            return
        for f in sorted(os.listdir(self.store_dir)):
            if f.lower().endswith(".txt"):
                p = os.path.join(self.store_dir, f)
                for s in read_herostat_snippet(p):
                    if s.get("name"):
                        self.characters.append(Character(self, s))
                        self.snippets[s.get("name").lower()] = p
        self.characters.sort(key=lambda c: c.display.lower())


def binary_of(path: str) -> str:
    return path[:-4] if path.lower().endswith(".txt") and path[:-4].lower().endswith(BIN_EXTS) else path


def is_editable(path: str) -> bool:
    return binary_of(path).lower().endswith(BIN_EXTS)


# ------------------------------------------------------------------ analise
def lint(proj: Project, root: Node | None, errors: list[xmlb.XmlbError], char: Character | None = None,
         known_vars: set[str] | None = None, common_moves: set[str] | None = None) -> list[tuple[int, str, str]]:
    """Devolve [(linha, 'erro'|'aviso', mensagem)]."""
    out = [(e.line or 1, "erro", e.msg) for e in errors]
    if root is None:
        return out
    moves = {(m.get("name") or "").lower() for m in root.children if m.name == "FightMove"} | (common_moves or set()) | BUILTIN_MOVES
    is_ps = root.name.lower() == "powerstyle"
    for n in root.walk():
        for k, v in n.attrs:
            kl = k.lower()
            if "\n" in v:
                out.append((n.line, "erro", f"'{k}' engoliu a linha seguinte: falta ' ;'"))
                continue
            if kl in EFFECT_KEYS and v.strip() and not v.startswith("%"):
                if not proj.effect_path(v):
                    out.append((n.line, "aviso", f"efeito não encontrado: effects/{v}"))
            elif is_ps and kl in MOVE_REF_KEYS and n.name in ("chain", "FightMove"):
                if v.lower() not in moves:
                    out.append((n.line, "aviso", f"{k} aponta para um FightMove que não existe aqui nem nos fightstyles: {v}"))
            if known_vars is not None and "%" in v:
                for var in VAR_RE.findall(v):
                    if var.lower() not in known_vars:
                        out.append((n.line, "aviso", f"variável %{var} não está definida nos talentos"))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def talent_vars(root: Node) -> set[str]:
    return {n.get("name", "").lower() for n in root.walk() if n.name == "talentvalue"}


# -------------------------------------------------------------------- cores
def color_to_rgb(value: int) -> tuple[int, int, int, int]:
    """Cor do MUA: inteiro 0xAABBGGRR -> (r, g, b, a)."""
    return value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF


def rgb_to_color(r: int, g: int, b: int, a: int = 0) -> int:
    return (a << 24) | (b << 16) | (g << 8) | r


def color_hex(value: int) -> str:
    r, g, b, _ = color_to_rgb(value)
    return f"#{r:02x}{g:02x}{b:02x}"
