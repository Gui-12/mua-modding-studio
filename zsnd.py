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

    # ---- edição (editor de áudio) ----------------------------------------------------
    def sample_of(self, sound_index: int) -> int:
        return struct.unpack_from("<H", self.sounds[sound_index][1], 0)[0]

    def file_of(self, sound_index: int) -> int:
        return struct.unpack_from("<H", self.samples[self.sample_of(sound_index)][1], 0)[0]

    def rate(self, sound_index: int) -> int:
        r = struct.unpack_from("<I", self.samples[self.sample_of(sound_index)][1], 4)[0]
        return r if 4000 <= r <= 96000 else 22050

    def fmt(self, sound_index: int) -> int:
        return self.files[self.file_of(sound_index)][1]

    def pcm(self, sound_index: int) -> list[int]:
        data = self.audio(sound_index)
        if self.fmt(sound_index) == FMT_ADPCM:
            return adpcm_decode(data)
        n = len(data) // 2
        return list(struct.unpack(f"<{n}h", data[:n * 2]))

    def duration(self, sound_index: int) -> float:
        data = self.audio(sound_index)
        n = len(data) * 2 if self.fmt(sound_index) == FMT_ADPCM else len(data) // 2
        return n / self.rate(sound_index)

    def wav_bytes(self, sound_index: int) -> bytes:
        return make_wav(self.pcm(sound_index), self.rate(sound_index))

    def add_pcm(self, new_hash: int, samples: list[int], rate: int, filename: str):
        """Som novo a partir de áudio PCM 16 bits mono (codificado em ADPCM, como os do jogo)."""
        if self.sounds:
            srec, mrec = bytearray(self.sounds[0][1]), bytearray(self.samples[self.sample_of(0)][1])
        else:
            srec = bytearray(bytes.fromhex("000000107f001f00007f007f") + b"\0" * 12)
            mrec = bytearray(b"\0" * SAMPLE_REC)
        name = os.path.basename(filename).encode("latin-1", "replace")[:63]
        self.files.append([self._free(pjw_hash(os.path.basename(filename)), self.files), FMT_ADPCM, name, adpcm_encode(samples), b""])
        struct.pack_into("<H", mrec, 0, len(self.files) - 1)
        struct.pack_into("<I", mrec, 4, int(rate))
        self.samples.append([self._free(pjw_hash(filename + "#s"), self.samples), mrec])
        if len(self.samples) - 1 > 0xFFFF:
            raise ZsndError("banco cheio (mais de 65535 samples)")
        struct.pack_into("<H", srec, 0, len(self.samples) - 1)
        self.sounds.append([new_hash, srec])

    def rebuilt(self, keep: list[int]) -> "Bank":
        """Banco novo só com os sons em 'keep' (na ordem dada); samples e áudio sem uso saem junto."""
        b = Bank.empty(self.path)
        b.original, b.size_field = self.original, self.size_field
        cache: dict = {}
        for i in keep:
            b.add_from(self, i, self.sounds[i][0], cache)
        return b

    def sort_tables(self):
        """Tabelas de hash em ordem crescente (o jogo procura os sons por busca binária)."""
        self.orders = [sorted(range(len(t)), key=lambda i, t=t: t[i][0]) for t in (self.sounds, self.samples, self.files)]


FMT_ADPCM = 106  # IMA ADPCM sem cabeçalho, 4 bits, nibble baixo primeiro, começando em 0 (conferido contra o wav exportado pelo zsmeditor)
_STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
         130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060,
         1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484,
         7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767]
_IDX = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8]


def _ima_step(n: int, p: int, i: int) -> tuple[int, int]:
    s = _STEP[i]
    d = s >> 3
    if n & 1:
        d += s >> 2
    if n & 2:
        d += s >> 1
    if n & 4:
        d += s
    p = p - d if n & 8 else p + d
    return max(-32768, min(32767, p)), max(0, min(88, i + _IDX[n]))


def adpcm_decode(data: bytes) -> list[int]:
    out, p, i = [], 0, 0
    for byte in data:
        for n in (byte & 15, byte >> 4):
            p, i = _ima_step(n, p, i)
            out.append(p)
    return out


def adpcm_encode(samples: list[int]) -> bytes:
    out, p, i = bytearray(), 0, 0
    nibbles = []
    for x in samples:
        diff = x - p
        n = 8 if diff < 0 else 0
        diff = abs(diff)
        s = _STEP[i]
        if diff >= s:
            n |= 4
            diff -= s
        if diff >= s >> 1:
            n |= 2
            diff -= s >> 1
        if diff >= s >> 2:
            n |= 1
        p, i = _ima_step(n, p, i)  # acompanha o decodificador para não acumular erro
        nibbles.append(n)
    if len(nibbles) % 2:
        nibbles.append(0)
    for a, b in zip(nibbles[0::2], nibbles[1::2]):
        out.append(a | (b << 4))
    return bytes(out)


def make_wav(samples: list[int], rate: int) -> bytes:
    data = struct.pack(f"<{len(samples)}h", *samples)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


def read_wav(path: str) -> tuple[list[int], int, str]:
    """Lê um .wav PCM (8/16 bits, mono ou estéreo) e devolve (amostras 16 bits mono, taxa, aviso)."""
    import wave
    with wave.open(path, "rb") as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 2:
        vals = list(struct.unpack(f"<{len(raw) // 2}h", raw[:len(raw) // 2 * 2]))
    elif width == 1:
        vals = [(b - 128) << 8 for b in raw]
    else:
        raise ZsndError(f"o wav tem {width * 8} bits; use 16 bits (ou 8)")
    note = []
    if ch > 1:
        vals = [sum(vals[k:k + ch]) // ch for k in range(0, len(vals) - ch + 1, ch)]
        note.append(f"{ch} canais misturados em mono")
    if rate != 22050:
        note.append(f"taxa {rate} Hz (o jogo usa quase sempre 22050)")
    return vals, rate, "; ".join(note)


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
