CRIADOR DE PERSONAGEM (módulo à parte do MUA Studio)
=====================================================

Abrir:  MUA Studio > Ferramentas > "Criar personagem do zero (assistente)..."  (ou Ctrl+Shift+P e digitar "zero")
Sozinho: "Run Character Creator.bat" na pasta tools\MUAStudio  (python -m creator [pasta do jogo])

Tudo mora nesta pasta (creator\). O MUA Studio só tem uma entrada de menu e o método App.character_creator,
que importa este módulo na hora; se a pasta faltar ou der erro, o resto do MUA Studio continua normal.
Para atualizar o módulo basta trocar esta pasta.

ABAS
  Assistente   7 etapas: personagem-base > identidade > skins e HUD > menu e loading > atributos > poderes > revisão e criar
  Editar poderes  a mesma lista de poderes para um personagem que já existe (criado aqui ou do jogo)
  Visualizar   lista os .igb de um personagem (skins, HUDs, mannequin, loading, retrato, ícones) e abre no Insight
  FAQ / Guia   perguntas e respostas do guia "Creating a Character from Scratch" (MarvelMods, tópico 10705), com busca

ARQUIVOS
  __init__.py   open_creator(host) e VERSION
  __main__.py   modo sozinho (StandaloneHost: proj, created, anim_tools, all_characters)
  wizard.py     janela (usa theme.py e os helpers de extras.py; não importa app.py)
  builder.py    monta o plano: usa ops.clone_plan como esqueleto e aplica skins/HUD/mannequin/loading/atributos
  viewer.py     Insight (copia o .igb para uma pasta sem espaços), versão do IGB, hex-edit da skin
  knowledge.py  FAQ e dicas das etapas (para acrescentar perguntas, edite a lista FAQ)
  powers.py     poderes: PowerSlot (de quem, qual talento, nome, ajustes), leitura (PowerData) e gravação (apply:
                remove os que saíram, copia os de outros personagens com transfer.build_plan, aplica nome/ajuste fino
                no talento, powerstyle e entidades, e reorganiza ordem/níveis com ops.organize_plan)
  powers_ui.py  painel "Poder 1..N" + abas Técnica / Nome / Ajuste fino (barras em % do original, escolhas por magnitude)

PODERES - O QUE A INTERFACE MEXE
  Talento (data/talents): descname, descshort, description e os talentvalue (exceto o nível de liberação)
  Powerstyle (data/powerstyles): nos gatilhos punch/radial/projectile dos moves do poder: damagetype, knockback,
    maxrange, speed, count, pierce; e charge_time do gatilho charge. Valores que são %variáveis ficam com o talento.
  Entidades (data/entities): scale, lifetime e exploderadius das entidades lançadas pelo poder.
  settings.json caminho do insight.exe e última pasta usada (criado sozinho)

O QUE A CRIAÇÃO GRAVA
  Igual ao "Clonar personagem" (talentos, powerstyle, entidades, efeitos, sets de animação, banco de som, ícones)
  + um par de pacotes <nome>_<skin>.pkgb/_nc.pkgb por skin, todos iguais tirando actorskin e o HUD
  + actors/<skin>.igb (com hex-edit se a skin tiver o nome padrão igActor01Appearance)
  + hud/hud_head_<skin>.igb, ui/models/mannequin/<n>01.igb, textures/loading/<n>01-03.igb, ui/hud/characters/<n>01.igb
  O herostat vai para criados\<nome>.txt (aba Criados) e a lista de arquivos para criados\<nome>.arquivos.json,
  então "Excluir este personagem criado" desfaz tudo.

INSIGHT
  Padrão: C:\Alchemy\ArtistPack\insight\DX9\insight.exe (ou %IG_ROOT%). Ele abre IGB v4 (mannequins, alguns HUDs);
  as skins v8 ele costuma mostrar "viewing nothing" - o criador detecta pelo título da janela e só avisa.
