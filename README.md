# MUA Modding Studio

### The All-in-One Modding IDE for Marvel: Ultimate Alliance (2006)

An integrated modding environment designed to simplify, accelerate, and centralize the creation of mods and boosters for **Marvel: Ultimate Alliance (2006)**.

**English** | [Português](#portugues)

---

<a id="english"></a>

# 🇺🇸 English

## Overview

**MUA Modding Studio** is an integrated development environment (IDE) designed to make creating, editing, and managing mods and boosters for *Marvel: Ultimate Alliance (2006)* easier and more accessible.

The goal is to bring together all the essential tools needed for game modification into a single application, providing a more organized and efficient workflow.

With MUA Modding Studio, you can transfer powers between characters, assign abilities to NPCs, copy fightmoves, edit character configurations, manage animations, and experiment with new gameplay possibilities.

Instead of switching between multiple utilities and manually editing different game files, you can perform many of these tasks directly within one environment.

## ✨ Key Features

### 1. Advanced Power Transfer

One of the main highlights of MUA Modding Studio is its ability to transfer much more than just a power's code.

When copying or adding powers to another character, the tool can also transfer the associated assets and configurations.

**A complete power transfer can include:**

- **Power Code:** The ability definition and its configuration.
- **Animations:** Associated animation files and references.
- **Sounds:** Sound effects linked to the ability.
- **Visual Effects:** Particle effects and other visual elements used by the power.
- **Associated Talents:** The corresponding talent definitions, preserving the relationship between powers and talents.

This makes transferring abilities between characters significantly easier while helping preserve their original behavior and presentation.

### 2. Talent Management

Manage and customize character talents with dedicated tools.

- **Power + Talent Copy:** Copy a power together with its associated talent.
- **Talent Values Reordering:** Reorganize talent values to make editing and balancing easier.
- **Simplified Balancing:** Improve the workflow for adjusting character attributes and power progression.

The ability to reorganize talent values is particularly useful when working with complex character configurations and balancing multiple characters.

### 3. Fightmove Management

Transfer and reuse fightmoves between characters.

- **Copy Fightmoves:** Transfer fightmoves from one character to another.
- **Combat Customization:** Experiment with different combinations of combat moves and character configurations.
- **Animation Reuse:** Simplify the process of reusing existing character animations and movesets.

### 4. Built-in Animation Mixer

MUA Modding Studio includes the **Animation Mixer**, bringing animation-related functionality directly into the application.

This allows you to access animation-mixing tools without constantly switching between separate utilities.

### 5. Herostat & NPC Stat Editors

The application supports editing both major character configuration files:

- **Herostat Editor:** Modify configurations and properties for playable characters.
- **NPC Stat Editor:** Edit configurations and properties for NPCs.

Having both editors in the same environment makes character customization and mod development more convenient.

### 6. NPC Power Assignment

Customize NPCs by assigning them powers and abilities from other characters.

This opens up additional possibilities for creating unique enemies, allies, and custom NPC configurations.

---

## 🧪 Experimental Features

### Hero-to-NPC Power Conversion

An experimental feature allows you to adapt powers originally designed for playable heroes so they can be used by NPCs.

The objective is to make it possible to reuse playable-character abilities in NPC configurations, expanding the possibilities for character and gameplay customization.

**Current testing status:**

- Tested by transferring powers from **Sinestro** to **Super-Skrull**.
- Initial results were successful, with the transferred powers working as expected in the tested scenario.

<sub>Experimental feature — compatibility and behavior may vary depending on the character and ability.</sub>

**Important: NPC Limitations**

NPCs have their own technical limitations and do not necessarily support every feature available to playable characters.

Some abilities may require additional adjustments, and certain animations, effects, or behaviors may not work correctly when transferred.

This functionality is experimental and should be considered a work in progress.

---

## 🛠️ Requirements & Dependencies

Before using MUA Modding Studio, make sure the following dependencies are installed and properly configured.

| Dependency | Purpose |
|---|---|
| **Python** | Required to run the application. |
| **Tkinter** | Required for the graphical interface. Usually included with standard Python installations. |
| **Alchemy** | Required to open, view, and edit `.igb` files used by Marvel: Ultimate Alliance. |

### Important Notes

- Make sure Python is installed and accessible from your system.
- Verify that your Python installation includes Tkinter support.
- Install and configure the appropriate **Alchemy version** compatible with the MUA modding tools.
- The MUA modding utilities are already included with the application.
- Alchemy is an external dependency and must be installed separately.

**Note:** Use the Alchemy version compatible with the tools included in your setup. The exact tested version should be specified in the project documentation.

---

## 🚀 Installation & Setup

Getting started is simple. No complicated installation process is required.

### Installation Steps

1. Open your *Marvel: Ultimate Alliance (2006)* installation directory.
2. Create a folder named `tools` in the game's root directory.
3. Place the MUA Modding Studio files inside the newly created `tools` folder.
4. Make sure Python, Tkinter, and the required Alchemy version are installed.
5. Run the provided `.bat` file.
6. The application will launch and be ready to use.

**That's it!**

All the MUA modding utilities required by the application are already included in the package. You only need to configure the external dependencies mentioned above.

### Expected Folder Structure

```text
Marvel Ultimate Alliance/
│
├── Marvel.exe
├── data/
├── packages/
│
└── tools/
    └── MUA Modding Studio/
        ├── [Application Files]
        ├── [Included MUA Tools]
        └── [Launch .bat]
```

*Folder structure is illustrative. Actual filenames and organization may vary.*

---

## 🎯 Project Goals

MUA Modding Studio aims to make Marvel: Ultimate Alliance modding more accessible by bringing essential utilities and workflows together in one integrated environment.

The project focuses on:

- Reducing repetitive manual file editing.
- Simplifying power and talent transfers.
- Making character customization easier.
- Improving the workflow for animation and fightmove editing.
- Expanding possibilities for NPC customization.
- Making mod and booster development more organized and accessible.

**Less time dealing with repetitive file editing. More time creating, experimenting, and improving the game.**

---

## ⚠️ Disclaimer

MUA Modding Studio is an independent community project created for modding and customization purposes.

It is not affiliated with, endorsed by, or officially supported by Marvel, Activision, or the original developers of *Marvel: Ultimate Alliance*.

All trademarks and game-related assets belong to their respective owners.

---

<a id="portugues"></a>

# 🇧🇷 Português

## Visão Geral

O **MUA Modding Studio** é uma IDE (Ambiente Integrado de Desenvolvimento) criada para facilitar a criação, edição e gerenciamento de mods e boosters para *Marvel: Ultimate Alliance (2006)*.

A proposta é reunir todas as ferramentas essenciais para modificação do jogo em uma única aplicação, proporcionando um fluxo de trabalho mais organizado, prático e eficiente.

Com o MUA Modding Studio, você pode transferir poderes entre personagens, atribuir habilidades a NPCs, copiar fightmoves, editar configurações de personagens, gerenciar animações e experimentar novas possibilidades de gameplay.

Em vez de alternar entre diversos utilitários e editar manualmente diferentes arquivos do jogo, você pode realizar várias dessas tarefas diretamente em um único ambiente.

## ✨ Principais Funcionalidades

### 1. Transferência Avançada de Poderes

Um dos grandes diferenciais do MUA Modding Studio é a capacidade de transferir muito mais do que apenas o código de um poder.

Ao copiar ou adicionar poderes a outro personagem, a ferramenta também pode transferir os recursos e configurações associados à habilidade.

**Uma transferência completa pode incluir:**

- **Código do Poder:** Definição e configuração da habilidade.
- **Animações:** Arquivos e referências de animações associados ao poder.
- **Sons:** Efeitos sonoros vinculados à habilidade.
- **Efeitos Visuais:** Partículas e demais elementos visuais utilizados pelo poder.
- **Talentos Associados:** Definições dos talentos correspondentes, preservando a relação entre poderes e talentos.

Isso torna a transferência de habilidades entre personagens muito mais prática, ajudando a preservar seu comportamento e apresentação originais.

### 2. Gerenciamento de Talentos

Gerencie e personalize os talentos dos personagens por meio de ferramentas dedicadas.

- **Cópia de Poder + Talento:** Copie um poder juntamente com seu talento associado.
- **Reordenação de Talent Values:** Reorganize os valores dos talentos para facilitar a edição e o balanceamento.
- **Balanceamento Simplificado:** Facilite os ajustes de atributos dos personagens e da progressão dos poderes.

A possibilidade de reorganizar os talent values é especialmente útil ao trabalhar com configurações complexas e balancear diferentes personagens.

### 3. Gerenciamento de Fightmoves

Transfira e reutilize fightmoves entre personagens.

- **Copiar Fightmoves:** Transfira fightmoves de um personagem para outro.
- **Personalização de Combate:** Experimente diferentes combinações de movimentos e configurações de combate.
- **Reutilização de Animações:** Simplifique o reaproveitamento de animações e conjuntos de movimentos existentes.

### 4. Animation Mixer Integrado

O MUA Modding Studio também conta com o **Animation Mixer**, disponibilizando funcionalidades relacionadas à combinação de animações diretamente na aplicação.

Assim, você pode acessar essa ferramenta sem precisar alternar constantemente entre diferentes utilitários.

### 5. Editores de Herostat e NPC Stat

A aplicação permite editar os dois principais arquivos de configuração de personagens:

- **Herostat Editor:** Modificação das configurações e propriedades dos personagens jogáveis.
- **NPC Stat Editor:** Edição das configurações e propriedades dos NPCs.

Ter os dois editores disponíveis no mesmo ambiente facilita a personalização de personagens e o desenvolvimento de mods.

### 6. Atribuição de Poderes a NPCs

Personalize NPCs atribuindo poderes e habilidades de outros personagens.

Isso abre novas possibilidades para criar inimigos, aliados e configurações personalizadas de NPCs.

---

## 🧪 Funcionalidades Experimentais

### Conversão de Poderes de Heróis para NPCs

Uma funcionalidade experimental permite adaptar poderes originalmente desenvolvidos para heróis jogáveis para que possam ser utilizados por NPCs.

O objetivo é possibilitar o reaproveitamento de habilidades de personagens jogáveis em configurações de NPCs, ampliando as possibilidades de personalização de personagens e gameplay.

**Status atual dos testes:**

- Teste realizado transferindo poderes do **Sinestro** para o **Super-Skrull**.
- Os resultados iniciais foram positivos, com os poderes transferidos funcionando conforme esperado no cenário testado.

**Importante: Limitações dos NPCs**

NPCs possuem limitações técnicas próprias e não necessariamente suportam todos os recursos disponíveis para personagens jogáveis.

Algumas habilidades podem exigir ajustes adicionais, e determinadas animações, efeitos ou comportamentos podem não funcionar corretamente após a transferência.

Essa funcionalidade ainda é experimental e deve ser considerada um recurso em desenvolvimento.

---

## 🛠️ Requisitos e Dependências

Antes de utilizar o MUA Modding Studio, certifique-se de que as seguintes dependências estejam instaladas e configuradas corretamente.

| Dependência | Finalidade |
|---|---|
| **Python** | Necessário para executar a aplicação. |
| **Tkinter** | Necessário para a interface gráfica. Geralmente já acompanha as instalações padrão do Python. |
| **Alchemy** | Necessário para abrir, visualizar e editar arquivos `.igb` utilizados pelo Marvel: Ultimate Alliance. |

### Observações Importantes

- Certifique-se de que o Python esteja instalado e acessível pelo sistema.
- Verifique se sua instalação do Python possui suporte ao Tkinter.
- Instale e configure a **versão adequada do Alchemy**, compatível com as ferramentas de modding do MUA.
- Os utilitários de modificação do MUA já estão incluídos na aplicação.
- O Alchemy é uma dependência externa e precisa ser instalado separadamente.

**Observação:** Utilize a versão do Alchemy compatível com as ferramentas incluídas na sua configuração. A versão exata testada deverá ser informada na documentação do projeto.

---

## 🚀 Instalação e Configuração

Começar a utilizar é simples. Não é necessário realizar uma instalação complexa.

### Passo a Passo

1. Acesse a pasta raiz de instalação do *Marvel: Ultimate Alliance (2006)*.
2. Crie uma pasta chamada `tools` dentro do diretório principal do jogo.
3. Coloque os arquivos do MUA Modding Studio dentro da pasta `tools`.
4. Certifique-se de que Python, Tkinter e a versão necessária do Alchemy estejam instalados.
5. Execute o arquivo `.bat` disponibilizado.
6. A aplicação será iniciada e estará pronta para utilização.

**Pronto!**

Todas as ferramentas de modificação do MUA necessárias para a aplicação já estão incluídas no pacote. Você só precisa configurar as dependências externas mencionadas anteriormente.

### Estrutura Esperada de Pastas

```text
Marvel Ultimate Alliance/
│
├── Marvel.exe
├── data/
├── packages/
│
└── tools/
    └── MUA Modding Studio/
        ├── [Arquivos da Aplicação]
        ├── [Ferramentas MUA Incluídas]
        └── [Arquivo .bat para Inicialização]
```

*Estrutura ilustrativa. Os nomes e a organização reais dos arquivos podem variar.*

---

## 🎯 Objetivos do Projeto

O MUA Modding Studio tem como objetivo tornar o modding de Marvel: Ultimate Alliance mais acessível, reunindo ferramentas e fluxos de trabalho essenciais em um único ambiente integrado.

O projeto busca:

- Reduzir edições manuais repetitivas.
- Simplificar a transferência de poderes e talentos.
- Facilitar a personalização de personagens.
- Melhorar o fluxo de trabalho para edição de animações e fightmoves.
- Ampliar as possibilidades de personalização de NPCs.
- Tornar a criação de mods e boosters mais organizada e acessível.

**Menos tempo com edições manuais repetitivas. Mais tempo criando, experimentando e aprimorando o jogo.**

---

## ⚠️ Aviso Legal

O MUA Modding Studio é um projeto independente da comunidade, desenvolvido para fins de modificação e personalização do jogo.

Não possui vínculo, associação, aprovação ou suporte oficial da Marvel, Activision ou dos desenvolvedores originais de *Marvel: Ultimate Alliance*.

Todas as marcas registradas e os recursos relacionados ao jogo pertencem aos seus respectivos proprietários.

---

*Created for the Marvel: Ultimate Alliance modding community.*
