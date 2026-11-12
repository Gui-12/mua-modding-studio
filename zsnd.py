"""Bancos de som do MUA PC (.zsm efeitos / .zss vozes), formato ZSNDPC.

Layout:
    "ZSND" "PC  " u32 tamanho_total u32 tamanho_cabecalho
    7 tabelas x (u32 quantidade, u32 offset_hashes, u32 offset_dados)   -> sons, samples, arquivos, 4 não usadas no PC
    sons:     hashes (u32 hash, u32 indice) ordenados por hash + registros de 24 bytes (u16 indice do sample + parâmetros)
    samples:  idem, registros de 24 bytes (u16 indice do arquivo, u32 taxa...)
    arquivos: idem, registros de 76 bytes (u32 offset, u32 tamanho, u32 formato, nome[64])
    dados de áudio

O nome de um som (ex.: char/aquam_m/p1_power) entra no banco como o hash PJW do caminho em maiúsculas.
Variações aleatórias de um som são várias entradas com o mesmo hash."""
from __future__ import annotations

import os
import struct

SOUND_REC, SAMPLE_REC, FILE_REC = 24, 24, 76


class ZsndError(Exception):
    pass


def pjw_hash(name: str) -> int:
    h = 0
    for c in name.upper().replace("\\", "/").encode("latin-1", "replace"):
        h = ((h << 4) + c) & 0xFFFFFFFF
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g & 0xFFFFFFFF
    return h


class Bank:
    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            d = f.read()
        self.original = d
        if d[:8] != b"ZSNDPC  ":
            raise ZsndError(f"{os.path.basename(path)} não é um banco de som de PC (ZSNDPC)")
        self.size_field, hdr = struct.unpack_from("<2I", d, 8)
        tabs = [struct.unpack_from("<3I", d, 0x10 + i * 12) for i in range(7)]
        if any(t[0] for t in tabs[3:]):
            raise ZsndError(f"{os.path.basename(path)} usa tabelas que este editor não conhece")
        (sc, sh, sd), (mc, mh, md), (fc, fh, fd) = tabs[:3]

        self.orders = []  # ordem original de cada tabela de hashes (nem sempre é ordenada)

        def table(count, hoff, doff, rec):
            hashes = [0] * count
            order = []
            for i in range(count):
                h, idx = struct.unpack_from("<2I", d, hoff + i * 8)
                if idx >= count:
                    raise ZsndError("tabela de hashes corrompida")
                hashes[idx] = h
                order.append(idx)
            if sorted(order) != list(range(count)):
                raise ZsndError("tabela de hashes com índices repetidos")
            self.orders.append(order)
            return [(hashes[i], d[doff + i * rec: doff + (i + 1) * rec]) for i in range(count)]

        self.sounds = [[h, bytearray(r)] for h, r in table(sc, sh, sd, SOUND_REC)]
        self.samples = [[h, bytearray(r)] for h, r in table(mc, mh, md, SAMPLE_REC)]
        self.files = []  # [hash, formato, nome(64 bytes), dados, bytes de preenchimento antes dos dados]
        pos = hdr
        for h, r in table(fc, fh, fd, FILE_REC):
            off, size, fmt = struct.unpack_from("<3I", r, 0)
            if off + size > len(d):
                raise ZsndError("arquivo de áudio aponta para fora do banco")
            pad = d[pos:off] if off >= pos else b""
            self.files.append([h, fmt, bytes(r[12:76]), d[off:off + size], pad])
            pos = max(pos, off + size)
        self.tail = d[pos:]
        for _, r in self.sounds:
            if struct.unpack_from("<H", r, 0)[0] >= len(self.samples):
                raise ZsndError("som aponta para sample inexistente")
        for _, r in self.samples:
            if struct.unpack_from("<H", r, 0)[0] >= len(self.files):
                raise ZsndError("sample aponta para arquivo inexistente")

    @classmethod
    def empty(cls, path: str = "") -> "Bank":
        """Banco novo, sem nenhum som (para montar um banco do zero)."""
        b = cls.__new__(cls)
        b.path, b.original, b.size_field = path, b"", 0
        b.sounds, b.samples, b.files, b.orders, b.tail = [], [], [], [[], [], []], b""
        return b

    # ---- consulta -------------------------------------------------------------
    def find(self, name_or_hash) -> list[int]:
        h = name_or_hash if isinstance(name_or_hash, int) else pjw_hash(name_or_hash)
        return [i for i, s in enumerate(self.sounds) if s[0] == h]

    def audio(self, sound_index: int) -> bytes:
        smp = struct.unpack_from("<H", self.sounds[sound_index][1], 0)[0]
        fil = struct.unpack_from("<H", self.samples[smp][1], 0)[0]
        return self.files[fil][3]

    def file_name(self, sound_index: int) -> str:
        smp = struct.unpack_from("<H", self.sounds[sound_index][1], 0)[0]
        fil = struct.unpack_from("<H", self.samples[smp][1], 0)[0]
        return self.files[fil][2].split(b"\0")[0].decode("latin-1")

    # ---- alteração --------------------------------------------------------------
    def add_from(self, src: "Bank", src_sound: int, new_hash: int, cache: dict | None = None):
        """Copia um som de outro banco (registro, sample e áudio) com o hash novo."""
        cache = cache if cache is not None else {}
        rec = bytearray(src.sounds[src_sound][1])
        s_smp = struct.unpack_from("<H", rec, 0)[0]
        key = (id(src), "smp", s_smp)
        if key not in cache:
            srec = bytearray(src.samples[s_smp][1])
            s_fil = struct.unpack_from("<H", srec, 0)[0]
            fkey = (id(src), "fil", s_fil)
            if fkey not in cache:
                fh, fmt, name, data = src.files[s_fil][:4]
                self.files.append([self._free(fh, self.files), fmt, name, data, b""])
                cache[fkey] = len(self.files) - 1
            struct.pack_into("<H", srec, 0, cache[fkey])
            self.samples.append([self._free(src.samples[s_smp][0], self.samples), srec])
            cache[key] = len(self.samples) - 1
        if cache[key] > 0xFFFF:
            raise ZsndError("banco cheio (mais de 65535 samples)")
        struct.pack_into("<H", rec, 0, cache[key])
        self.sounds.append([new_hash, rec])

    @staticmethod
    def _free(h: int, table) -> int:
        used = {t[0] for t in table}
        while h in used:
            h = (h + 1) & 0x0FFFFFFF
        return h

    # ---- gravação ------------------------------------------------------------------
    def to_bytes(self) -> bytes:
        ns, nm, nf = len(self.sounds), len(self.samples), len(self.files)
        sh = 0x10 + 7 * 12
        sd = sh + ns * 8
        mh = sd + ns * SOUND_REC
        md = mh + nm * 8
        fh = md + nm * SAMPLE_REC
        fd = fh + nf * 8
        hdr = fd + nf * FILE_REC

        def hashes(table, order):
            order = list(order)  # entradas originais na ordem original; as novas entram na posição ordenada
            for i in range(len(order), len(table)):
                h = table[i][0]
                pos = len(order)
                for k, j in enumerate(order):
                    if table[j][0] > h:
                        pos = k
                        break
                order.insert(pos, i)
            out = bytearray()
            for i in order:
                out += struct.pack("<2I", table[i][0], i)
            return out

        frecs = bytearray()
        blob = bytearray()
        for h, fmt, name, data, pad in self.files:
            blob += pad
            frecs += struct.pack("<3I", hdr + len(blob), len(data), fmt) + name.ljust(64, b"\0")[:64]
            blob += data
        blob += self.tail
        total = hdr + len(blob)
        size_field = total if self.size_field == len(self.original) else total + (self.size_field - len(self.original))
        out = bytearray(b"ZSNDPC  ") + struct.pack("<2I", size_field, hdr)
        out += struct.pack("<3I", ns, sh, sd) + struct.pack("<3I", nm, mh, md) + struct.pack("<3I", nf, fh, fd)
        out += struct.pack("<3I", 0, hdr, hdr) * 4
        out += hashes(self.sounds, self.orders[0]) + b"".join(bytes(r) for _, r in self.sounds)
        out += hashes(self.samples, self.orders[1]) + b"".join(bytes(r) for _, r in self.samples)
        out += hashes(self.files, self.orders[2]) + frecs
        out += blob
        return bytes(out)

    def roundtrips(self) -> bool:
        """True se regravar o banco sem mudanças reproduz o arquivo byte a byte."""
        return self.to_bytes() == self.original


def bank_path(root: str, bank: str) -> str | None:
    """sounds/<idioma>/<1a letra>/<2a letra>/<banco>.zsm|.zss dentro de uma pasta de jogo."""
    bank = bank.lower()
    if len(bank) < 2:
        return None
    base = os.path.join(root, "sounds")
    if not os.path.isdir(base):
        return None
    langs = sorted(os.listdir(base), key=lambda l: (l.lower() != "eng", l))
    for lang in langs:
        for ext in (".zsm", ".zss"):
            p = os.path.join(base, lang, bank[0], bank[1], bank + ext)
            if os.path.isfile(p):
                return p
    return None
