"""Visualização de .igb pelo Insight do Alchemy (só abre o modelo; não carrega dados do jogo).

Testado com C:\\Alchemy\\ArtistPack\\insight\\DX9\\insight.exe: abre mannequins e modelos antigos;
skins e HUDs em versões mais novas do formato ele mostra "Insight: viewing nothing" - é ignorado e avisado.
O Insight não entende caminho com espaço, então o arquivo é copiado para uma pasta temporária sem espaços.
"""
from __future__ import annotations

import ctypes
import os
import re
import shutil
import struct
import subprocess
import tempfile

DEFAULT_INSIGHT = r"C:\Alchemy\ArtistPack\insight\DX9\insight.exe"


def find_insight(saved: str = "") -> str:
    cands = [saved, os.environ.get("MUA_INSIGHT", ""), DEFAULT_INSIGHT]
    root = os.environ.get("IG_ROOT")
    if root:
        cands += [os.path.join(root, "ArtistPack", "insight", "DX9", "insight.exe"),
                  os.path.join(root, "ArtistPack", "insight", "insight.exe")]
    return next((c for c in cands if c and os.path.isfile(c)), "")


def igb_version(path: str) -> int | None:
    """Versão do formato IGB (u32 em 0x2C, depois da marca 0xFADA). Mannequins costumam ser 4; skins 6-8."""
    try:
        with open(path, "rb") as f:
            h = f.read(0x30)
        if len(h) >= 0x30 and struct.unpack_from("<I", h, 0x28)[0] == 0xFADA:
            return struct.unpack_from("<I", h, 0x2C)[0] & 0xFFFF
    except OSError:
        pass
    return None


def _temp_dir() -> str:
    base = tempfile.gettempdir()
    if " " in base:  # perfil com espaço no nome: usa a raiz do disco do Windows
        base = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "Temp")
    d = os.path.join(base, "mua_insight")
    os.makedirs(d, exist_ok=True)
    return d


def _window_title(pid: int) -> str | None:
    """Título da janela principal do processo (para saber se o Insight carregou o arquivo)."""
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return None
    found: list[str] = []
    proto = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, _):
        p = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value:
                found.append(buf.value)
        return True

    user32.EnumWindows(proto(cb), 0)
    return found[0] if found else None


class Viewer:
    """Abre arquivos no Insight. check(callback) informa depois se ele conseguiu carregar."""

    def __init__(self, exe: str = ""):
        self.exe = find_insight(exe)
        self.procs: list[subprocess.Popen] = []

    @property
    def available(self) -> bool:
        return bool(self.exe)

    def open(self, path: str) -> subprocess.Popen:
        if not self.exe:
            raise FileNotFoundError("Insight não encontrado (escolha o insight.exe nas configurações do visualizador)")
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(path))
        tmp = os.path.join(_temp_dir(), f"{len(self.procs):02d}_{safe}")
        shutil.copy2(path, tmp)
        p = subprocess.Popen([self.exe, tmp], cwd=os.path.dirname(self.exe))
        self.procs.append(p)
        return p

    @staticmethod
    def status(p: subprocess.Popen) -> str:
        """'ok', 'vazio' (abriu mas não carregou), 'fechou' (erro) ou 'esperando'."""
        if p.poll() is not None:
            return "fechou"
        t = _window_title(p.pid)
        if t is None:
            return "esperando"
        return "vazio" if "viewing nothing" in t.lower() else "ok"

    def close_all(self):
        for p in self.procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        self.procs = []


# ----------------------------------------------------------------- o que dá para ver de um personagem
def character_assets(root: str, num: str, skins: list[str], name: str = "") -> list[tuple[str, str]]:
    """(rótulo, caminho) dos .igb do personagem que existem na pasta do jogo."""
    out: list[tuple[str, str]] = []

    def add(label, *rel):
        p = os.path.join(root, *rel)
        if os.path.isfile(p):
            out.append((label, p))

    for s in skins:
        add(f"Skin {s}", "actors", f"{s}.igb")
        add(f"HUD {s}", "hud", f"hud_head_{s}.igb")
    if num:
        add("Mannequin", "ui", "models", "mannequin", f"{num}01.igb")
        for i in ("01", "02", "03"):
            add(f"Loading {num}{i}", "textures", "loading", f"{num}{i}.igb")
        add("Retrato de conversa", "ui", "hud", "characters", f"{num}01.igb")
    if name:
        add("Ícones dos poderes", "textures", "ui", f"{name}_icons.igb")
    return out


# ----------------------------------------------------------------- hex-edit da skin
APPEARANCE = b"igActor01Appearance"


def patch_skin_name(data: bytes, skin: str) -> tuple[bytes, int]:
    """Troca o nome 'igActor01Appearance' pelo número da skin (mesmo tamanho, completado com zeros),
    como o guia faz no XVI32 / SkinEdit. Só mexe no texto exato seguido de \\0. Devolve (dados, trocas)."""
    new = skin.encode("ascii")
    if len(new) > len(APPEARANCE):
        return data, 0
    rep = new + b"\0" * (len(APPEARANCE) - len(new))
    buf = bytearray(data)
    n = 0
    i = buf.find(APPEARANCE)
    while i >= 0:
        end = i + len(APPEARANCE)
        before = buf[i - 1] if i else 0
        if end < len(buf) and buf[end] == 0 and not (chr(before).isalnum() or before == ord("_")):
            buf[i:end] = rep
            n += 1
        i = buf.find(APPEARANCE, end)
    return bytes(buf), n
