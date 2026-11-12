"""Leitura e escrita do formato XMLB do Marvel Ultimate Alliance (.xmlb / .engb / .pkgb)
e do formato de texto usado pelos modders (.txt com chaves e ' ;').

Layout do binário (little-endian):
    u32 magic = 0x11B1
    u32 versão = 1
    elemento raiz, e cada elemento:
        u32 offset do nome
        u32 offset do próximo irmão (0xFFFFFFFF = nenhum)
        u32 offset do primeiro filho (0xFFFFFFFF = nenhum)
        u32 quantidade de atributos
        N x (u32 offset do nome, u32 offset do valor)
    tabela de strings terminadas em zero, sem repetição, na ordem de primeira aparição
"""
from __future__ import annotations

import struct

MAGIC = 0x11B1
NONE = 0xFFFFFFFF
ENC = "latin-1"  # preserva os bytes exatamente como estão no arquivo


class XmlbError(Exception):
    def __init__(self, msg: str, line: int | None = None):
        super().__init__(msg)
        self.msg = msg
        self.line = line

    def __str__(self):
        return f"linha {self.line}: {self.msg}" if self.line else self.msg


class Node:
    __slots__ = ("name", "attrs", "children", "line")

    def __init__(self, name: str, attrs=None, children=None, line: int = 0):
        self.name = name
        self.attrs: list[list[str]] = attrs if attrs is not None else []  # [[nome, valor], ...]
        self.children: list[Node] = children if children is not None else []
        self.line = line

    # ---- utilidades -----------------------------------------------------
    def get(self, key: str, default=None):
        for k, v in self.attrs:
            if k == key:
                return v
        return default

    def set(self, key: str, value: str):
        for a in self.attrs:
            if a[0] == key:
                a[1] = value
                return
        self.attrs.append([key, value])

    def find_all(self, name: str):
        return [c for c in self.children if c.name == name]

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def clone(self) -> "Node":
        return Node(self.name, [list(a) for a in self.attrs], [c.clone() for c in self.children], self.line)

    def same_as(self, other: "Node") -> bool:
        if self.name != other.name or len(self.children) != len(other.children):
            return False
        if [tuple(a) for a in self.attrs] != [tuple(a) for a in other.attrs]:
            return False
        return all(a.same_as(b) for a, b in zip(self.children, other.children))


# ------------------------------------------------------------------ binário
def is_xmlb(data: bytes) -> bool:
    return len(data) >= 24 and struct.unpack_from("<I", data, 0)[0] == MAGIC


def read_binary(data: bytes) -> Node:
    if not is_xmlb(data):
        raise XmlbError("não e um arquivo XMLB (magic diferente de 0x11B1)")
    size = len(data)

    def cstr(off: int) -> str:
        if off >= size:
            raise XmlbError(f"offset de string fora do arquivo: {off:#x}")
        end = data.index(b"\0", off)
        return data[off:end].decode(ENC)

    def read_chain(off: int) -> list[Node]:
        out = []
        while off != NONE:
            if off + 16 > size:
                raise XmlbError(f"offset de elemento fora do arquivo: {off:#x}")
            name, nxt, child, nattr = struct.unpack_from("<4I", data, off)
            node = Node(cstr(name))
            p = off + 16
            for _ in range(nattr):
                k, v = struct.unpack_from("<2I", data, p)
                node.attrs.append([cstr(k), cstr(v)])
                p += 8
            if child != NONE:
                node.children = read_chain(child)
            out.append(node)
            off = nxt
        return out

    roots = read_chain(8)
    return roots[0]


def write_binary(root: Node) -> bytes:
    # 1) posicao de cada elemento (pre-ordem)
    order: list[Node] = []
    offsets: dict[int, int] = {}
    pos = 8
    stack = [root]
    while stack:
        n = stack.pop()
        order.append(n)
        offsets[id(n)] = pos
        pos += 16 + 8 * len(n.attrs)
        stack.extend(reversed(n.children))
    str_base = pos

    # 2) tabela de strings
    strings: dict[str, int] = {}
    blob = bytearray()

    def soff(s: str) -> int:
        o = strings.get(s)
        if o is None:
            o = str_base + len(blob)
            strings[s] = o
            blob.extend(s.encode(ENC, "replace"))
            blob.append(0)
        return o

    next_of: dict[int, int] = {id(root): NONE}
    for n in order:
        for i, c in enumerate(n.children):
            next_of[id(c)] = offsets[id(n.children[i + 1])] if i + 1 < len(n.children) else NONE

    out = bytearray(struct.pack("<2I", MAGIC, 1))
    for n in order:
        child = offsets[id(n.children[0])] if n.children else NONE
        out += struct.pack("<4I", soff(n.name), next_of[id(n)], child, len(n.attrs))
        for k, v in n.attrs:
            out += struct.pack("<2I", soff(k), soff(v))
    out += blob
    return bytes(out)


# -------------------------------------------------------------------- texto
def format_text(root: Node) -> str:
    lines: list[str] = []

    def emit(n: Node, depth: int, is_root: bool):
        ind = "   " * depth
        lines.append(f"{ind}{'XMLB ' if is_root else ''}{n.name} {{")
        for k, v in n.attrs:
            lines.append(f"{ind}{k} = {v} ;")
        for c in n.children:
            emit(c, depth + 1, False)
        lines.append(f"{ind}}}")
        lines.append("")

    # mesmo estilo do Raven-Formats: atributos alinhados com a chave que abre
    def emit_rf(n: Node, depth: int, is_root: bool):
        ind = "   " * depth
        lines.append(f"{ind}{'XMLB ' if is_root else ''}{n.name} {{")
        for k, v in n.attrs:
            lines.append(f"{ind}{k} = {v} ;")
        for c in n.children:
            emit_rf(c, depth + 1, False)
        lines.append(f"{ind}}}")
        lines.append("")

    emit_rf(root, 0, True)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def parse_text(text: str, strict: bool = True) -> tuple[Node | None, list[XmlbError]]:
    """Le o formato de texto. Devolve (raiz, lista de problemas).
    Com strict=False tenta continuar depois de um erro para listar todos."""
    errors: list[XmlbError] = []
    root: Node | None = None
    stack: list[Node] = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    n_lines = len(lines)
    closed_root = False

    def err(msg, ln):
        errors.append(XmlbError(msg, ln))

    while i < n_lines:
        raw = lines[i]
        ln = i + 1
        s = raw.strip()
        i += 1
        if not s or s.startswith("//"):
            continue
        if s == "}":
            if not stack:
                err("'}' sobrando: não há bloco aberto", ln)
                continue
            stack.pop()
            if not stack:
                closed_root = True
            continue
        if s.endswith("{") and " = " not in s and "=" not in s:
            name = s[:-1].strip()
            if root is None:
                if name.startswith("XMLB "):
                    name = name[5:].strip()
                else:
                    err("a primeira linha deveria ser 'XMLB <nome> {'", ln)
            if not name or " " in name:
                err(f"nome de bloco inválido: '{name}'", ln)
            node = Node(name, line=ln)
            if root is None:
                root = node
            elif not stack:
                err("bloco fora da raiz (a raiz já foi fechada)", ln)
                continue
            else:
                stack[-1].children.append(node)
            stack.append(node)
            continue
        if "=" in s:
            # valores podem (raramente) ocupar varias linhas: junta até achar ';'
            start = ln
            full = s
            while not full.endswith(";") and i < n_lines:
                nxt = lines[i].strip()
                if nxt == "}" or nxt.endswith("{") or (" = " in nxt and nxt.endswith(";")):
                    break
                full += "\n" + lines[i].rstrip()
                i += 1
            key, _, val = full.partition("=")
            key = key.strip()
            val = val.strip()
            if not val.endswith(";"):
                err(f"falta ' ;' no fim de '{key}'", start)
            else:
                body = val[:-1]
                if body and not body.endswith((" ", "\t")):
                    err(f"falta o espaço antes do ';' em '{key}'", start)
                val = body.strip()
            if not key or " " in key:
                err(f"nome de propriedade inválido: '{key}'", start)
            if not stack:
                err(f"propriedade '{key}' fora de qualquer bloco", start)
                continue
            if stack[-1].children:
                # o binário guarda atributos antes dos filhos; avisar não e necessário,
                # mas a ordem relativa entre atributo e bloco se perde.
                pass
            stack[-1].attrs.append([key, val])
            continue
        err(f"linha não reconhecida: '{s[:60]}'", ln)

    if root is None:
        err("arquivo vazio ou sem bloco raiz", 1)
    for n in stack:
        err(f"bloco '{n.name}' aberto aqui nunca e fechado", n.line)
    return root, errors


# ------------------------------------------------------------- conveniencia
def load_file(path: str) -> Node:
    """Carrega binário ou texto, decidindo pelo conteudo."""
    with open(path, "rb") as f:
        data = f.read()
    if is_xmlb(data):
        return read_binary(data)
    root, errors = parse_text(data.decode(ENC))
    if errors:
        raise errors[0]
    return root


def read_text_file(path: str) -> str:
    with open(path, "rb") as f:
        return f.read().decode(ENC).replace("\r\n", "\n")


def write_text_file(path: str, text: str):
    with open(path, "wb") as f:
        f.write(text.replace("\r\n", "\n").replace("\n", "\r\n").encode(ENC, "replace"))
