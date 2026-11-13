"""Conhecimento do Criador de Personagem: FAQ e dicas de cada etapa.

Base: o guia "Creating a Character from Scratch" do fórum MarvelMods (tópico 10705, lições 1-6)
e o que o MUA Studio aprendeu mexendo neste mod. Textos em pt-BR (idioma oficial do MUA Studio).
"""
from __future__ import annotations

GUIDE_URL = "https://marvelmods.com/forum/index.php/topic,10705.0.html"
NPC_GUIDE_URL = "https://marvelmods.com/forum/index.php/topic,11707.0.html"

# (categoria, pergunta, resposta)
FAQ: list[tuple[str, str, str]] = [
    # ------------------------------------------------------------------ começo
    ("Começo", "O que é preciso para um personagem existir no jogo?",
     "Um personagem jogável é a soma de:\n"
     "  • uma entrada no data/herostat.engb (nome, número, skins, atributos, talentos iniciais);\n"
     "  • skins em actors/<número da skin>.igb;\n"
     "  • sets de animação em actors/<número>_<nome>.igb (menu) e <número>_<nome>_4_combat.igb (combate);\n"
     "  • pacotes packages/generated/characters/<nome>_<skin>.pkgb e <nome>_<skin>_nc.pkgb (um par por skin);\n"
     "  • talentos data/talents/<nome>.engb e powerstyle data/powerstyles/ps_<nome>.engb;\n"
     "  • opcionais: HUD (hud/hud_head_<skin>.igb), mannequin, telas de loading, ícones, efeitos e sons.\n\n"
     "O assistente cria tudo isso a partir de um personagem-base e depois troca o que você escolher."),
    ("Começo", "Por que o assistente pede um personagem-base?",
     "É o mesmo caminho do guia: ninguém escreve talentos e powerstyle do zero. Copia-se de um personagem com "
     "animações parecidas (ex.: o guia usa o Beast para o Puck) e troca-se o nome. O MUA Studio já faz a cópia "
     "renomeando tudo (talentos, powerstyle, pacotes, efeitos, banco de som, sets de animação). Depois você "
     "troca poderes com 'Copiar poder', mistura animações no 'Mixer' e edita sons no 'Editor de áudio'."),
    ("Começo", "Devo trabalhar direto na pasta do jogo?",
     "O guia recomenda uma pasta de projeto separada. O MUA Studio grava na pasta do jogo, mas: não sobrescreve "
     "nada sem confirmar, guarda backup de tudo em tools/MUAStudio/backups e anota cada arquivo criado "
     "(criados/<nome>.arquivos.json) para poder excluir o personagem depois. Para entregar o mod pronto, use "
     "'Compilar personagem (salvar numa pasta)'."),
    ("Começo", "Quais ferramentas externas o guia cita?",
     "Quick Batch / XMLBCUI (compilar .xmlb/.engb/.pkgb) - o MUA Studio já faz isso sozinho.\n"
     "Alchemy 5 (Insight para ver .igb, mixer de animações, SkinEdit) - o mixer e o visualizador estão aqui.\n"
     "ZSM Editor / ZSND (sons) - o Editor de áudio do MUA Studio lê e grava os bancos.\n"
     "XVI32 (hex-edit de skins) - a etapa Skins pode gravar o número dentro da skin.\n"
     "SkinnerUI, GIMP (HUD, ícones, loading), WavePad (converter sons), Color Converter (cores de efeitos)."),

    # ------------------------------------------------------------------ número
    ("Número", "Como escolho o número do personagem?",
     "Vai de 0 a 255. As skins são o número + 2 dígitos (personagem 47 -> skin 4701, 4702...; personagem 243 -> "
     "24301...). Antes de lançar um mod público, confira as planilhas CCC (Marvel / Non-Marvel) do fórum e "
     "registre o número. Para uso próprio basta não repetir um número do seu herostat - o assistente mostra os usados."),
    ("Número", "Posso dividir o número com outro personagem?",
     "Pode, se as skins não se repetirem (ex.: Heimdall usa 24305-24308, Puck usa 24309-24313). Mas os dois "
     "dividem o mesmo mannequin (<número>01.igb) e as mesmas telas de loading. Avise no LEIAME do mod."),

    # ------------------------------------------------------------------ skins
    ("Skins", "Quantas skins posso ter e como elas aparecem no herostat?",
     "Até 6. 'skin' tem o número completo da primeira; skin_02..skin_06 têm só os 2 últimos dígitos, e "
     "skin_01_name..skin_06_name os nomes mostrados no menu. As roupas 5 e 6 não têm passivos próprios."),
    ("Skins", "O que é o hex-edit da skin e preciso fazer?",
     "Dentro do .igb a skin guarda o nome do 'appearance' (ex.: igActor01Appearance). O jogo usa isso nos Androides do "
     "Arcade (Murderworld) e em quem muda de forma: sem o número gravado eles aparecem brancos. O guia troca o texto "
     "por <número da skin> no XVI32 ou com o SkinEdit. A etapa Skins faz isso numa cópia (o original não é tocado) "
     "quando encontra o texto; se não encontrar, a skin é copiada como está."),
    ("Skins", "A skin aparece sem textura / branca.",
     "1) o nome do arquivo não bate com 'actorskin' do pacote; 2) a skin veio de outro personagem e tem o número antigo "
     "gravado dentro - refaça com o hex-edit ligado; 3) faltam as texturas externas (.igt / textures) que a skin usa."),
    ("Skins", "Algumas skins têm partes que somem ou aparecem só no menu.",
     "São os blocos opcionais do herostat: BoltOn (bolt, model, slot - armas, capas presas a um osso), "
     "Multipart (hideskin, showskin, nonmenuonly) e StatEffect (efeito ligado a um osso, menuonly/zoneonly). "
     "Edite no editor de herostat depois de criar."),

    # ------------------------------------------------------------------ pacotes
    ("Pacotes", "Por que existem dois pacotes por skin (_nc)?",
     "O <nome>_<skin>.pkgb é o de combate. O _nc (non-combat) é usado nos hubs (Stark Tower etc.) e é menor. "
     "Os dois precisam existir para cada skin."),
    ("Pacotes", "Uma das skins ficou sem poderes.",
     "Os pacotes de todas as skins devem ser IGUAIS, mudando só 'actorskin' e o 'model' do HUD (hud_head_<skin>). "
     "Se um pacote ficou diferente (outro powerstyle, outro talents, outro set de animação), aquela skin perde coisas. "
     "O assistente gera todos a partir do mesmo modelo."),
    ("Pacotes", "Compilei e o jogo não leu o arquivo.",
     "Extensão errada: pacotes são .pkgb, talentos/powerstyles/herostat são .engb (nunca .xmlb). O MUA Studio já grava "
     "com a extensão certa e confere que o binário é legível antes de salvar."),

    # ------------------------------------------------------------------ herostat
    ("Herostat", "Quais campos do herostat importam?",
     "name (interno, liga com talentos - não mude depois), charactername (exibido), characteranims, powerstyle "
     "(igual ao do pacote), skin/skin_0N, sounddir, team (hero/enemy), playable (true), level (1), ailevel (1), "
     "scriptlevel (3), menulocation, autospend, body/strength/mind, scale_factor e moveset1 para quem voa."),
    ("Herostat", "Quanto devo dar de body, strength e mind?",
     "A soma fica perto de 22-24 para heróis normais; mais que isso só para chefes. mind abaixo de ~4 deixa o "
     "personagem sem energia. O guia corrigiu um Puck de strength 11 / mind 3 para strength 7 / mind 6."),
    ("Herostat", "O que é autospend?",
     "Como os pontos de atributo são gastos sozinhos ao subir de nível: bruiser, bruiser_light, support ou support_heavy."),
    ("Herostat", "O personagem ficou pequeno/grande demais.",
     "scale_factor = 1 é o tamanho normal. O Puck usa 0.75-0.8, o Juggernaut 1.5."),
    ("Herostat", "Quais talentos iniciais são obrigatórios?",
     "<prefixo>_p1 (o primeiro poder, já liberado), fightstyle_default (ou um próprio), block e melee_moves. "
     "flight, might, healing_factor, leadership, <nome>_resist só se o personagem tiver aquilo. "
     "As linhas de XMen / Brotherhood / grab copiadas de outro personagem podem sair."),
    ("Herostat", "O personagem não aparece na seleção.",
     "Ele está só na aba Criados até ir para o herostat do jogo: abra Editar Herostat e use 'Adicionar' ou "
     "'Substituir por'. Verifique também menulocation: 1-25 no jogo normal, 40-50 com o 36 Roster Hack, e "
     "não pode repetir a posição de outro personagem."),
    ("Herostat", "O jogo fecha ao carregar o herostat.",
     "Erro de sintaxe (chave ou ; faltando) quando editado à mão. O editor do MUA Studio mostra os erros antes de "
     "compilar; para o herostat do jogo há backup em tools/MUAStudio/backups."),

    # ------------------------------------------------------------------ animações
    ("Animações", "Qual a diferença entre o set de menu e o de combate?",
     "<número>_<nome>.igb é usado na seleção / tela do time (idle, walk, run, menu_action, menu_idle, menu_goodbye). "
     "<número>_<nome>_4_combat.igb tem os golpes: power_1..power_20 (+ _loop / _end), attack_light1-3, "
     "attack_popup1, attack_trip2, attack_stun1/2, attack_heavy1, attack_knockback1/2, blocking, ground_attack1/2 "
     "e fly_idle/fly_slow/fly_fast para quem voa."),
    ("Animações", "Como misturo animações de vários personagens?",
     "Use o Mixer de animações do MUA Studio: escolha os sets, marque as animações e grave. Se duas animações "
     "tiverem o mesmo nome (ex.: power_1 de dois sets), uma precisa ser renomeada para outro nome que o jogo "
     "conheça - o mixer avisa. O nome do set precisa bater com o do pacote (actoranimdb)."),
    ("Animações", "Na seleção o idle fica em câmera lenta.",
     "O set de menu veio de um personagem com idle lento (o guia cita o Thing). Troque o set de menu por outro, "
     "com o mesmo nome <número>_<nome>.igb."),
    ("Animações", "As animações não tocam.",
     "O nome em actoranimdb (pacote) ou characteranims (herostat) não bate com o arquivo em actors/. "
     "Lembre: o arquivo tem .igb, o pacote não."),

    # ------------------------------------------------------------------ HUD / menu
    ("HUD e menu", "Onde ficam HUD, mannequin e telas de loading?",
     "HUD (cabeça no canto da tela): hud/hud_head_<skin>.igb, um por skin, citado no pacote como HUD/hud_head_<skin>.\n"
     "Mannequin (boneco do menu da S.H.I.E.L.D.): ui/models/mannequin/<número>01.igb - o nome PRECISA ser número+01.\n"
     "Telas de loading: textures/loading/<número>01..03.igb.\n"
     "Retrato de conversa: ui/hud/characters/<número>01.igb.\n"
     "Ícones dos poderes: textures/ui/<nome>_icons.igb (citado no pacote)."),
    ("HUD e menu", "O mannequin não aparece.",
     "O arquivo precisa ser ui/models/mannequin/<número>01.igb (ex.: 24301.igb). Se você dividir o número com "
     "outro personagem, aparece o mannequin dele."),
    ("HUD e menu", "Como vejo uma skin, HUD ou mannequin sem abrir o jogo?",
     "Aba Visualizar: escolha o arquivo e clique Abrir no Insight (Alchemy). Ele mostra o modelo, não carrega "
     "dados do jogo. Alguns .igb (versões mais novas do formato, comuns em skins e HUDs) o Insight antigo não abre "
     "e mostra 'viewing nothing' - é limitação dele, o arquivo pode estar certo."),

    # ------------------------------------------------------------------ poderes / sons
    ("Poderes", "Como troco os poderes que vieram do personagem-base?",
     "Depois de criar: 'Copiar poder para outro personagem' traz um poder de qualquer personagem (com efeitos, "
     "animação e sons); 'Remover poder' tira; 'Organizar poderes' acerta níveis e tiers. O talento "
     "power = powerN precisa bater com o FightMove de mesmo nome."),
    ("Poderes", "Como monto os poderes sem mexer em código?",
     "Etapa Poderes do assistente (ou a aba Editar poderes para quem já existe). A lista 'Poder 1, Poder 2...' é a ordem "
     "de liberação. Para cada poder:\n"
     "  • Técnica: de quem ela vem (qualquer personagem) e qual poder. Vem com efeitos, entidades, animações e sons.\n"
     "  • Nome: nome, tipo (Melee, Projectile...) e descrição da tela de poderes.\n"
     "  • Ajuste fino: barras em % do original para dano, custo de energia, duração etc., com a prévia no nível 1 e no "
     "máximo; tipo de dano e empurrão por escolha; alcance, velocidade e tamanho do projétil, tempo de carga."),
    ("Poderes", "O que o ajuste fino muda nos arquivos?",
     "Valores por nível: os talentvalue do talento (data/talents). Tipo de dano, empurrão, alcance, quantidade, atravessar "
     "e velocidade: os gatilhos punch / radial / projectile dos FightMoves do poder (data/powerstyles). Tamanho, duração e "
     "raio de explosão do projétil: a entidade dele (data/entities). Valores que são %variáveis são ajustados pelas barras "
     "do talento. O nível de liberação não é multiplicado: ele vem da ordem da lista."),
    ("Poderes", "Quantos poderes posso ter?",
     "A organização automática cobre até 7 poderes, 3 boosts e 1 Xtreme (a tela de poderes do jogo). Com mais que isso os "
     "poderes são gravados, mas a ordem/níveis precisam ser acertados em 'Organizar poderes'."),
    ("Poderes", "O ícone do poder copiado ficou errado.",
     "O número do ícone (icon) vem do personagem de origem e passa a apontar para a folha de ícones do seu personagem "
     "(textures/ui/<nome>_icons). Troque o desenho na folha ou ajuste 'icon' no talento."),
    ("Sons", "Como funcionam os sons do personagem?",
     "sounddir = <banco>_m aponta para sounds/eng/<letra1>/<letra2>/<banco>_m.zsm (efeitos) e <banco>_v.zss (voz). "
     "O nome do banco tem no máximo 6 caracteres antes do _m. O assistente cria um banco novo copiado do "
     "personagem-base (ou divide o banco dele); depois use o Editor de áudio para trocar os sons."),

    # ------------------------------------------------------------------ teste
    ("Teste", "Como testo o personagem?",
     "1) Coloque-o no herostat do jogo (Editar Herostat > Adicionar ou Substituir por).\n"
     "2) Abra o jogo, vá a um ponto da S.H.I.E.L.D. (com o 36 Roster Hack há um logo no começo), tire o time "
     "padrão e escolha o personagem.\n"
     "3) Teste idle, correr, pular, bloquear e o combo básico; depois cada poder.\n"
     "Ver o personagem sem mannequin próprio é normal: aparece o de quem divide o número."),
    ("Teste", "Funcionou o combate mas o menu está estranho.",
     "Bom sinal: combate ok quer dizer que pacote, skin e set de combate estão certos. Menu e idle são o set de menu "
     "e o mannequin - ajuste separado."),
    ("Teste", "Quero desfazer tudo.",
     "Na aba Criados, clique com o botão direito no personagem > 'Excluir este personagem criado'. Os arquivos "
     "listados no .arquivos.json são apagados (os que outro personagem usa são mantidos)."),
]

# Dica de cada etapa do assistente (título, texto)
STEP_TIPS: dict[str, tuple[str, str]] = {
    "base": ("Personagem-base",
             "Escolha quem empresta o esqueleto: poderes, talentos, powerstyle, animações, efeitos e sons. Prefira alguém "
             "com animações parecidas com o que você quer. Tudo será copiado com o nome novo; o original não muda."),
    "ident": ("Identidade",
              "Nome exibido é o que aparece no jogo. O nome interno vira o nome dos arquivos e não deve mudar depois. "
              "O número (0-255) é o começo dos números das skins: personagem 243 -> skins 24301, 24302..."),
    "skins": ("Skins",
              "Até 6 roupas. Para cada uma, escolha um .igb (ou deixe vazio para usar a skin do personagem-base) e "
              "um HUD opcional. Use 'Ver' para abrir no Insight. O hex-edit grava o número dentro da cópia da skin."),
    "menu": ("Menu e loading",
             "Mannequin é o boneco da S.H.I.E.L.D. (<número>01.igb). Telas de loading e retrato de conversa são opcionais: "
             "sem arquivo, ficam as do personagem-base (quando existem)."),
    "stats": ("Atributos",
              "Soma de body+strength+mind perto de 22-24. scale_factor 1 = tamanho normal. Marque 'voa' para moveset_flying."),
    "powers": ("Poderes",
               "Cada 'Poder N' pode ficar como veio do base ou aprender a técnica de outro personagem. Renomeie na aba Nome e "
               "ajuste dano, custo, tipo de dano, empurrão, alcance e projétil na aba Ajuste fino - sem mexer em código. "
               "A ordem da lista vira a ordem de liberação (níveis reorganizados sozinhos)."),
    "review": ("Revisão",
               "Confira a lista de arquivos. Nada existente é alterado (a não ser que você permita sobrescrever). "
               "O personagem vai para a aba Criados; depois use Editar Herostat para pô-lo no jogo."),
}

# Ordem sugerida depois de criar (aparece no fim)
NEXT_STEPS = [
    "Editar Herostat > Adicionar personagem (ou Substituir por) para colocá-lo no jogo",
    "Copiar poder para outro personagem: trocar os poderes herdados",
    "Mixer de animações: montar o set de combate próprio",
    "Editor de áudio: trocar falas e sons do banco novo",
    "Compilar personagem (salvar numa pasta): gerar o mod para distribuir",
]
