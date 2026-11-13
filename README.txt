MUA STUDIO
==========
IDE desktop para editar os arquivos de personagem do Marvel Ultimate Alliance (mod DC).
Abre os binarios do jogo (.engb / .xmlb / .pkgb) direto como texto, valida a sintaxe,
compila ao salvar (sempre com backup) e automatiza o trabalho repetitivo de mod:
copiar poderes entre personagens, clonar personagens, editar herostat/npcstat, etc.

Idioma: Portugues (Brasil) e o oficial. English esta disponivel no menu "Idioma"
(vale depois de reiniciar o app).


O QUE E PRECISO PARA RODAR
--------------------------
- Windows 10/11 (usa fontes Segoe e a barra de titulo escura do Windows).
- Python 3.10 ou mais novo, COM tkinter. (Testado no Python 3.13.)
- Nenhum pacote pip. O CustomTkinter (visual) ja vem embutido em vendor/pylibs.

Instalar as dependencias:
  Duplo clique em  "Install dependencies.bat"
  Ele confere se existe Python 3.10+ com tkinter; se nao existir, instala o Python 3.13
  pelo winget. Sem winget, instale em https://www.python.org/downloads/ e marque
  "tcl/tk and IDLE" e "Add python.exe to PATH".
  Depois de instalar, abra um terminal NOVO (para o PATH atualizar).


ONDE A PASTA DEVE FICAR
-----------------------
O app deve ficar dentro da pasta do mod/jogo, assim:

  <pasta do jogo/mod>\
      data\  packages\  actors\  effects\  sounds\ ...     (arquivos do jogo/mod)
      tools\
          MUAStudio\               <- esta pasta (app.py, README.txt...)
              vendor\animation_tools\bin\   (ferramentas de animacao, ja incluidas)

- Ao abrir, ele sobe pelas pastas ate achar a que contem "data" e "packages". Se nao achar,
  pergunta qual e a pasta do jogo.
- As ferramentas de animacao (animationProducer.exe e sgOptimizer.exe) vao junto em
  vendor\animation_tools\bin\. O app usa essa copia; se ela faltar, procura em
  <jogo>\tools\*\bin.
  Elas so sao necessarias para o Mixer de animacoes e para importar animacoes
  ao copiar poderes. Sem ela o resto funciona e o app avisa quando a ferramenta faria falta.


COMO ABRIR
----------
  Duplo clique em  "Run MUA Studio.bat"   (ou em "tools\MUA Studio.bat", se existir)
  ou, no terminal:  python app.py


COMO USAR (resumo)
------------------
- Lista da esquerda: personagens do herostat e abas Criados / Avulsos / Outro jogo / Arquivos.
  Duplo clique abre o arquivo; botao direito no personagem/poder mostra as acoes.
- Editor: abre o binario como texto. Ctrl+S valida e compila. Problemas aparecem na aba
  "Problemas"; F12 ou Ctrl+clique vai para a definicao; Ctrl+F localiza; Ctrl+K edita cor.
- Copiar poder (Ctrl+T): escolhe origem, poder e destino; mostra uma previa do que sera
  gravado e so grava ao clicar em Aplicar. Pode copiar efeitos, sons e animacoes.
- Converter poder de heroi para NPC, Clonar personagem / criar novo mod, Compilar personagem
  (exporta para uma pasta), Mixer de animacoes, Editar Herostat/NPCStat: menus "Ferramentas"
  e a barra de botoes.
- Outros jogos / personagens avulsos: Arquivo > Carregar pasta de outro jogo... /
  Adicionar personagem avulso...


BACKUPS E CONFIGURACAO
----------------------
- Toda gravacao guarda o original em  backups\<sessao>\  (menu Ferramentas > Abrir pasta de backups).
- settings.json (criado ao usar): pastas extras carregadas e idioma. Pode apagar sem medo.
- criados\ e herostat_guardados\: personagens criados/retirados do herostat que o app guarda.


ARQUIVOS DO PROJETO
-------------------
app.py        janela principal e editor            theme.py    cores, fontes e widgets
extras.py     herostat/npcstat, mixer, clonar      xmlb.py     leitor/compilador do formato XMLB
project.py    leitura de personagens e pastas      transfer.py logica de copiar/converter poderes
ops.py        remover/exportar/clonar              anims.py    animacoes (animationProducer)
zsnd.py       bancos de som (ZSNDPC)               i18n.py / lang_en.py   idiomas

Para adicionar uma traducao: escreva o texto em portugues no codigo e a versao em ingles
em lang_en.py (o que nao estiver la continua em portugues).
