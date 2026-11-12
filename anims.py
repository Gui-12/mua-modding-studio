"""Animações: lista o que cada set (.igb de actors/) contém e monta um set novo
acrescentando/trocando animações, usando o animationProducer da pasta 'animation Mix tools'.

O set do destino nunca é editado no lugar: o novo arquivo é montado numa pasta temporária,
conferido (todas as animações antigas + as novas precisam estar lá) e só então substitui o original."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

from project import Project, Character

LIST_INI = """[OPTIMIZE]
optimizationCount = 1
hierarchyCheck = true

[OPTIMIZATION1]
name = igEnbayaCompressAnimations
quantizationError = 0.0001
sampleRate = -1
forceTrackCount = -1
printStatistics = true
ignoreBones =
specialCaseIniFilename =
separator = :
sortColumn = -1
"""
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class AnimError(Exception):
    pass


class AnimItem:
    def __init__(self, enum, name, src_set, new_enum, new_name, mode):
        self.enum, self.name, self.src_set = enum, name, src_set
        self.new_enum, self.new_name, self.mode = new_enum, new_name, mode  # mode: novo | substitui | renomeado


class AnimPlan:
    def __init__(self):
        self.items: list[AnimItem] = []
        self.target: str | None = None
        self.warnings: list[str] = []
        self.enum_map: dict[str, str] = {}  # animenum antigo -> novo (minúsculas)


class AnimTools:
    def __init__(self, proj: Project):
        self.proj = proj
        self.bin = self._find_bin()
        self._names: dict[str, tuple[float, list[str]]] = {}
        self._enums: dict[str, dict[str, str]] = {}

    def _find_bin(self) -> str | None:
        tools = os.path.join(self.proj.root, "tools")
        if os.path.isdir(tools):
            for d in sorted(os.listdir(tools)):
                b = os.path.join(tools, d, "bin")
                if os.path.isfile(os.path.join(b, "animationProducer.exe")) and os.path.isfile(os.path.join(b, "sgOptimizer.exe")):
                    return b
        return None

    @property
    def available(self) -> bool:
        return self.bin is not None

    # ---- tabela ea_xxx -> nome da animação ---------------------------------
    def enums(self, proj: Project | None = None) -> dict[str, str]:
        """Tabela da pasta indicada; pastas sem shared_anims (personagem avulso) usam a do jogo principal."""
        proj = proj or self.proj
        if proj.root not in self._enums:
            table = {}
            p = proj.resolve("data/shared_anims")
            if p:
                for n in proj.load(p).walk():
                    for k, v in n.attrs:
                        if k.lower().startswith("ea_"):
                            table[k.lower()] = v.strip().lower()
            self._enums[proj.root] = table
        return self._enums[proj.root] or (self.enums(self.proj) if proj is not self.proj else {})

    # ---- conteúdo de um set ---------------------------------------------------
    def set_path(self, name: str, proj: Project | None = None) -> str | None:
        p = os.path.join((proj or self.proj).root, "actors", name + ".igb")
        return p if os.path.isfile(p) else None

    def char_sets(self, c: Character) -> list[str]:
        """Sets de animação do personagem (o do herostat primeiro, depois os dos pacotes)."""
        names = [c.anims] if c.anims else []
        for v in c.package_entries("actoranimdb"):
            if v.lower() not in [n.lower() for n in names]:
                names.append(v)
        return [p for p in (self.set_path(n, c.proj) for n in names) if p]

    def names(self, igb: str) -> list[str]:
        mt = os.path.getmtime(igb)
        c = self._names.get(igb)
        if c and c[0] == mt:
            return c[1]
        if not self.bin:
            raise AnimError("ferramenta de animação não encontrada em tools/")
        with tempfile.TemporaryDirectory(prefix="muaanim_") as tmp:
            shutil.copy2(igb, os.path.join(tmp, "in.igb"))
            res = self._list(tmp, "in.igb")
        self._names[igb] = (mt, res)
        return res

    def _list(self, cwd: str, fname: str) -> list[str]:
        with open(os.path.join(cwd, "list.ini"), "w") as f:
            f.write(LIST_INI)
        r = subprocess.run([os.path.join(self.bin, "sgOptimizer.exe"), fname, "list_tmp.igb", "list.ini"],
                           cwd=cwd, capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW, timeout=300)
        out = r.stdout
        if "Loaded file" not in out:
            raise AnimError(f"não foi possível ler as animações de {fname}")
        res = [n.lower() for n in re.findall(r'Skipping igAnimation "([^"]+)"', out)]
        table = False
        for line in out.splitlines():
            if line.startswith("Name ") and "Sample rate" in line:
                table = True
                continue
            if table:
                if line.startswith("-----"):
                    break
                if line.strip():
                    res.append(line.split()[0].lower())
        return res

    def _produce(self, cwd: str, script: str):
        with open(os.path.join(cwd, "job.txt"), "w") as f:
            f.write(script)
        r = subprocess.run([os.path.join(self.bin, "animationProducer.exe"), "job.txt"], cwd=cwd,
                           capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW, timeout=600)
        bad = [l for l in (r.stdout + r.stderr).splitlines() if re.match(r"^\[\d+\]", l) and not l.rstrip().endswith("completed")]
        if r.returncode != 0 or bad:
            raise AnimError("animationProducer falhou: " + (bad[0] if bad else f"código {r.returncode}"))

    # ---- planejamento --------------------------------------------------------------
    def plan(self, src: Character, dst: Character, enums_used: list[str], remaining: set[str], removed: set[str]) -> AnimPlan:
        """enums_used: animenums dos moves copiados. remaining: animenums que os outros moves do
        destino continuam usando. removed: animenums dos moves que estão sendo substituídos."""
        ap = AnimPlan()
        ap.proj = dst.proj
        table = self.enums(dst.proj)
        src_table = self.enums(src.proj)
        by_name: dict[str, list[str]] = {}
        for e, n in table.items():
            by_name.setdefault(n, []).append(e)
        src_sets = self.char_sets(src)
        dst_sets = self.char_sets(dst)
        if not dst_sets:
            ap.warnings.append(f"nenhum set de animação encontrado em actors/ para {dst.display}; animações não importadas")
            return ap
        dst_names = {p: set(self.names(p)) for p in dst_sets}
        # alvo: o set do destino que guarda os poderes
        cands = [p for p in dst_sets if not os.path.basename(p).lower().startswith(("interact_", "fightstyle_"))] or dst_sets
        ap.target = max(cands, key=lambda p: sum(1 for n in dst_names[p] if n.startswith("power")))
        used = set().union(*dst_names.values())
        taken_names, taken_enums = set(), set()

        def free_slot(like: str):
            suffix = re.sub(r"^power_?\d+", "", like) if like.startswith("power") else ""
            pool = sorted((n for n in by_name if re.match(r"^power_?\d+", n)),
                          key=lambda n: (not (suffix and n.endswith(suffix)), not re.fullmatch(r"power_?\d+", n) if not suffix else False,
                                         int(re.search(r"\d+", n).group()), n))
            for n in pool:
                if n in used or n in taken_names:
                    continue
                for e in by_name[n]:
                    if e not in remaining and e not in taken_enums:
                        return e, n
            return None

        for enum in enums_used:
            e = enum.lower()
            if e in ap.enum_map or any(i.enum == e for i in ap.items):
                continue
            name = src_table.get(e) or table.get(e)
            if not name:
                ap.warnings.append(f"{enum} não está em data/shared_anims; animação não importada")
                continue
            src_set = next((p for p in src_sets if name in self.names(p)), None)
            if not src_set:
                ap.warnings.append(f"{enum} ({name}) não está em nenhum set de {src.display}; o destino usa a dele")
                continue
            if name not in used and name not in taken_names and e not in remaining and table.get(e) == name:
                item = AnimItem(e, name, src_set, e, name, "novo")
            elif name in dst_names[ap.target] and e in removed and e not in remaining and name not in taken_names \
                    and table.get(e) == name:
                item = AnimItem(e, name, src_set, e, name, "substitui")
            else:
                slot = free_slot(name)
                if not slot:
                    ap.warnings.append(f"sem nome de animação livre para {enum} ({name}); animação não importada")
                    continue
                item = AnimItem(e, name, src_set, slot[0], slot[1], "renomeado")
                ap.enum_map[e] = slot[0]
            taken_names.add(item.new_name)
            taken_enums.add(item.new_enum)
            ap.items.append(item)
        return ap

    # ---- execução --------------------------------------------------------------------
    def build(self, ap: AnimPlan) -> str | None:
        """Monta o set novo numa pasta temporária e confere. Devolve o caminho do arquivo pronto
        (dentro de uma pasta temporária que o chamador apaga com cleanup())."""
        if not ap.items or not ap.target:
            return None
        if not self.bin:
            raise AnimError("ferramenta de animação não encontrada em tools/")
        tmp = tempfile.mkdtemp(prefix="muaanim_")
        self._tmp = tmp
        set_name = os.path.splitext(os.path.basename(ap.target))[0]
        old = self.names(ap.target)
        shutil.copy2(ap.target, os.path.join(tmp, "dst_in.igb"))
        # 1) extrai cada animação da origem para um arquivo com o NOME DE DESTINO
        by_set: dict[str, list[AnimItem]] = {}
        for it in ap.items:
            by_set.setdefault(it.src_set, []).append(it)
        os.makedirs(os.path.join(tmp, "x"))
        for i, (sset, items) in enumerate(by_set.items()):
            shutil.copy2(sset, os.path.join(tmp, f"src{i}.igb"))
            s = f"create_animation_database\tsrc{i}\nload_actor\tsrc{i}.igb\nextract_skeleton\tdefaultSkeleton\n"
            for it in items:
                s += f"extract_animation\t{it.name}\nsave_external_animation_database\tx\\{it.name}__{i}.igb\nremove_animation\t{it.name}\n"
            self._produce(tmp, s)
            for it in items:
                one = os.path.join(tmp, "x", f"{it.name}__{i}.igb")
                if not os.path.isfile(one) or self._list(tmp, os.path.join("x", f"{it.name}__{i}.igb")) != [it.name]:
                    raise AnimError(f"não foi possível extrair '{it.name}' de {os.path.basename(sset)}")
                shutil.move(one, os.path.join(tmp, f"{it.new_name}.igb"))
        # 2) remonta o set do destino: todas as antigas (menos as substituídas) + as novas
        replaced = {it.new_name for it in ap.items if it.mode == "substitui"}
        s = f"create_animation_database\t{set_name}\nload_actor\tdst_in.igb\nextract_skeleton\tdefaultSkeleton\n"
        for n in old:
            if n not in replaced:
                s += f"extract_animation\t{n}\n"
        for it in ap.items:
            s += f"load_actor\t{it.new_name}.igb\nextract_animation\t{it.new_name}\n"
        os.makedirs(os.path.join(tmp, "out"))
        s += f"save_external_animation_database\tout\\{set_name}.igb\n"
        self._produce(tmp, s)
        out = os.path.join(tmp, "out", f"{set_name}.igb")
        if not os.path.isfile(out):
            raise AnimError("o set novo não foi gerado")
        # 3) conferência: nada pode ter sumido
        got = sorted(self._list(tmp, os.path.join("out", f"{set_name}.igb")))
        want = sorted(set(old) | {it.new_name for it in ap.items})
        if got != want:
            missing = sorted(set(want) - set(got))
            extra = sorted(set(got) - set(want))
            raise AnimError("o set gerado não confere" + (f"; faltando: {', '.join(missing)}" if missing else "")
                            + (f"; sobrando: {', '.join(extra)}" if extra else ""))
        with open(ap.target, "rb") as f:
            head_old = f.read(0x30)
        with open(out, "rb") as f:
            head_new = f.read(0x30)
        if head_old[0x2C:0x30] != head_new[0x2C:0x30]:
            raise AnimError("o set gerado saiu com versão de arquivo diferente da original (offset 0x2C); "
                            "confira o libIGCore.dll da ferramenta")
        if os.path.getsize(out) < os.path.getsize(ap.target) * 0.5:
            raise AnimError("o set gerado ficou muito menor que o original; abortado por segurança")
        return out

    # ---- operações genéricas (mixer, clonagem) ------------------------------------------
    def assemble(self, base: str, drop: set[str], adds: list[tuple[str, str, str]], set_name: str | None = None) -> str:
        """Monta um set novo a partir de 'base': tira as animações em 'drop' e acrescenta
        adds = [(set de origem, nome na origem, nome novo)]. Confere o resultado e devolve o caminho
        do arquivo pronto numa pasta temporária (chame cleanup() depois de copiar)."""
        if not self.bin:
            raise AnimError("ferramenta de animação não encontrada em tools/")
        tmp = tempfile.mkdtemp(prefix="muaanim_")
        self._tmp = tmp
        set_name = set_name or os.path.splitext(os.path.basename(base))[0]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", set_name):
            raise AnimError(f"nome de set inválido: {set_name}")
        old = self.names(base)
        drop = {d.lower() for d in drop}
        adds = [(s, a.lower(), b.lower()) for s, a, b in adds]
        new_names = [b for _, _, b in adds]
        if len(set(new_names)) != len(new_names):
            raise AnimError("duas animações entrariam com o mesmo nome")
        shutil.copy2(base, os.path.join(tmp, "dst_in.igb"))
        os.makedirs(os.path.join(tmp, "x"))
        by_set: dict[str, list[tuple[str, str]]] = {}
        for s, a, b in adds:
            by_set.setdefault(s, []).append((a, b))
        for i, (sset, items) in enumerate(by_set.items()):
            have = self.names(sset)
            shutil.copy2(sset, os.path.join(tmp, f"src{i}.igb"))
            script = f"create_animation_database\tsrc{i}\nload_actor\tsrc{i}.igb\nextract_skeleton\tdefaultSkeleton\n"
            uniq = sorted({a for a, _ in items})
            for a in uniq:
                if a not in have:
                    raise AnimError(f"'{a}' não existe em {os.path.basename(sset)}")
                script += f"extract_animation\t{a}\nsave_external_animation_database\tx\\{a}__{i}.igb\nremove_animation\t{a}\n"
            self._produce(tmp, script)
            for a, b in items:
                one = os.path.join("x", f"{a}__{i}.igb")
                if not os.path.isfile(os.path.join(tmp, one)) or self._list(tmp, one) != [a]:
                    raise AnimError(f"não foi possível extrair '{a}' de {os.path.basename(sset)}")
                shutil.copy2(os.path.join(tmp, one), os.path.join(tmp, f"{b}.igb"))
        keep = [n for n in old if n not in drop and n not in new_names]
        script = f"create_animation_database\t{set_name}\nload_actor\tdst_in.igb\nextract_skeleton\tdefaultSkeleton\n"
        for n in keep:
            script += f"extract_animation\t{n}\n"
        for b in new_names:
            script += f"load_actor\t{b}.igb\nextract_animation\t{b}\n"
        os.makedirs(os.path.join(tmp, "out"))
        script += f"save_external_animation_database\tout\\{set_name}.igb\n"
        self._produce(tmp, script)
        out = os.path.join(tmp, "out", f"{set_name}.igb")
        if not os.path.isfile(out):
            raise AnimError("o set novo não foi gerado")
        got, want = sorted(self._list(tmp, os.path.join("out", f"{set_name}.igb"))), sorted(set(keep) | set(new_names))
        if got != want:
            raise AnimError("o set gerado não confere; faltando: " + ", ".join(sorted(set(want) - set(got)))
                            + "  sobrando: " + ", ".join(sorted(set(got) - set(want))))
        with open(base, "rb") as f:
            h1 = f.read(0x30)
        with open(out, "rb") as f:
            h2 = f.read(0x30)
        if h1[0x2C:0x30] != h2[0x2C:0x30]:
            raise AnimError("o set gerado saiu com versão de arquivo diferente da original (offset 0x2C)")
        return out

    def change_set(self, proj: Project, target: str, drop: set[str], adds: list[tuple[str, str, str]]):
        """assemble + backup + troca do arquivo, tudo ou nada."""
        try:
            built = self.assemble(target, drop, adds)
            proj.backup(target)
            shutil.copy2(built, target + ".tmp~")
            os.replace(target + ".tmp~", target)
            self._names.pop(target, None)
        finally:
            self.cleanup()

    def extract_to(self, set_path: str, names: list[str], out_dir: str) -> list[str]:
        """Grava cada animação como um .igb individual (como o _extract.bat)."""
        if not self.bin:
            raise AnimError("ferramenta de animação não encontrada em tools/")
        tmp = tempfile.mkdtemp(prefix="muaanim_")
        try:
            shutil.copy2(set_path, os.path.join(tmp, "src.igb"))
            os.makedirs(os.path.join(tmp, "x"))
            script = "create_animation_database\tsrc\nload_actor\tsrc.igb\nextract_skeleton\tdefaultSkeleton\n"
            for a in names:
                script += f"extract_animation\t{a}\nsave_external_animation_database\tx\\{a}.igb\nremove_animation\t{a}\n"
            self._produce(tmp, script)
            os.makedirs(out_dir, exist_ok=True)
            done = []
            for a in names:
                p = os.path.join(tmp, "x", f"{a}.igb")
                if os.path.isfile(p):
                    shutil.copy2(p, os.path.join(out_dir, f"{a}.igb"))
                    done.append(a)
            return done
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def install(self, ap: AnimPlan, built: str):
        getattr(ap, "proj", self.proj).backup(ap.target)
        tmp = ap.target + ".tmp~"
        shutil.copy2(built, tmp)
        os.replace(tmp, ap.target)
        self._names.pop(ap.target, None)

    def cleanup(self):
        tmp = getattr(self, "_tmp", None)
        if tmp and os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
        self._tmp = None
