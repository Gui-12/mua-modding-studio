"""Criador de Personagem sem abrir o MUA Studio:  python -m creator [pasta do jogo]  (a partir de tools/MUAStudio)."""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import filedialog

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # tools/MUAStudio
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import theme as th  # noqa: E402
import project as pj  # noqa: E402
import anims  # noqa: E402

from creator import open_creator  # noqa: E402


class StandaloneHost:
    """O mínimo que o criador precisa do MUA Studio."""

    def __init__(self, root_dir: str):
        self.proj = pj.Project(root_dir)
        self.created = pj.CreatedProject(self.proj.root, os.path.join(HERE, "criados"))
        self.anim_tools = anims.AnimTools(self.proj)

    def all_characters(self):
        return list(self.proj.characters) + list(self.created.characters)

    def status(self, msg: str):
        print(msg)


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else HERE
    root_dir = pj.find_game_root(start)
    root = th.ctk.CTk()
    th.setup(root)
    root.withdraw()
    if not root_dir:
        root_dir = filedialog.askdirectory(title="Escolha a pasta do jogo (a que contém data e packages)")
        if not root_dir or not pj.find_game_root(root_dir):
            return
        root_dir = pj.find_game_root(root_dir)
    win = open_creator(StandaloneHost(root_dir))
    win.bind("<Destroy>", lambda e: root.after(50, root.destroy) if e.widget is win else None)
    root.mainloop()


if __name__ == "__main__":
    main()
