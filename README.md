# Dublaskizon

O **Dublaskizon** é uma aplicação desktop em Python/Tkinter para organizar, preparar, gerar, revisar, redublar e converter áudios de projetos de dublagem. O foco é manter a relação entre áudio original, texto, dublagem, revisões e traduções alternativas mesmo em projetos com milhares de arquivos distribuídos em subpastas.

> Este repositório contém o código-fonte e os testes. Modelos de voz, áudios, textos de projeto, credenciais e binários externos não devem ser commitados.

## Funcionalidades

A aplicação possui sete áreas integradas: **CLONAGEM + DUBLAGEM**, **REVISÃO**, **CONVERTER DURAÇÃO**, **CONVERTER FORMATOS**, **FILTRO RENOMEAR .WEM**, **REDIMENSIONAR ÁUDIO PARA CLONAR** e **COMANDOS**.

A área de dublagem organiza filas, modelos, modos de geração, perfis de voz, referência de áudio, pronúncia do R, progresso, cancelamento e logs. A Revisão permite ouvir cenas, editar textos, aprovar, rejeitar, redublar, escolher outro áudio original, consultar histórico e abrir pares no Audacity.

A janela **OUVIR CENA** possui player FFplay, navegação, formas de onda original/dublado, duração e metadados, comparação proporcional entre faixas, marca vertical de final e busca por clique: clicar na onda inicia o áudio no ponto correspondente quando o FFplay interno está selecionado. A janela também preserva o editor compacto de texto português, menus contextuais, ações de revisão e barras de clonagem/dublagem.

Os conversores trabalham com formatos de áudio comuns e mantêm a hierarquia relativa. O filtro WEM aceita arquivos de qualquer extensão, extrai IDs, gera prévias, trata mapas Wwise, ajusta números, renomeia com segurança e permite desfazer a última operação. A ferramenta de clonagem seleciona, une, corta, normaliza e exporta áudios para OmniVoice VoiceStudio, ElevenLabs Instant e ElevenLabs Professional.

## Requisitos

Para executar a versão-fonte, use Windows com Python 3.12 ou mais recente, que é a versão recomendada pelos scripts de compilação e pelo fluxo OmniVoice. O aplicativo utiliza Tkinter, que precisa estar disponível na instalação do Python. O suporte a arrastar-e-soltar usa `tkinterdnd2` quando instalado.

FFmpeg, FFprobe e FFplay são necessários para conversão, leitura de metadados e reprodução interna. SoX pode ser usado pela conversão de duração. O OmniVoice e o modelo escolhido são dependências do fluxo de síntese, enquanto o Audacity é opcional para revisão em duas faixas.

| Dependência | Obrigatoriedade | Uso |
|---|---|---|
| Python + Tkinter | Obrigatória para executar a fonte | Interface desktop |
| `tkinterdnd2` | Opcional | Arrastar-e-soltar |
| `pydub` | Recomendada | Processamento auxiliar de áudio |
| `ffmpeg-python` | Recomendada | Integração Python com FFmpeg |
| `numpy` e `scipy` | Recomendadas para preparação de clonagem | Análise e processamento |
| FFmpeg/FFprobe/FFplay | Necessários para recursos de áudio | Conversão, metadados e reprodução |
| SoX | Opcional | Ajuste de duração com melhor precisão em alguns fluxos |
| OmniVoice | Necessária para síntese OmniVoice | Geração de voz |
| Audacity | Opcional | Revisão e comparação de faixas |

## Instalação para desenvolvimento

Clone o repositório e crie um ambiente virtual. No Windows PowerShell:

```powershell
git clone <URL-DO-SEU-REPOSITORIO>
cd Dublaskizon
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Se a instalação do `tkinterdnd2` não for desejada, o aplicativo continua podendo funcionar sem arrastar-e-soltar, desde que as outras dependências necessárias ao fluxo escolhido estejam disponíveis.

Os binários FFmpeg/FFprobe/FFplay e SoX não são distribuídos por este repositório. Instale-os no `PATH` ou use o botão **BAIXAR / PREPARAR FERRAMENTAS** dentro do aplicativo, quando permitido pelo ambiente. O OmniVoice deve ser instalado no mesmo Python que será usado na execução ou disponibilizado conforme a configuração do ambiente.

## Executar a aplicação

A partir da raiz do projeto:

```powershell
python Dublaskizon.py
```

O programa pode ser iniciado depois de selecionar uma pasta de projeto pela interface. O aplicativo não deve receber, no repositório, áudios ou textos reais do usuário.

## Estrutura esperada de um projeto de dublagem

O Dublaskizon usa uma chave relativa formada pela subpasta e pelo nome-base, sem extensão. Por exemplo, `CAP01/cena.wav` corresponde a `CAP01/cena.txt` e resulta em `CAP01/cena.wav` na pasta `dublado`. Isso permite repetir nomes-base em capítulos diferentes sem colisão.

```text
PROJETO_DUBLAGEM/
├── Dublaskizon.exe                 # gerado localmente; não versionar
├── WAV ORIGINAIS/
├── TXT TEXTO PORTUGUES/
├── TXT TEXTO ORIGINAL/
├── TXT TEXTO do WAV TRANSCRITO e TRADUZIDO/
├── OUTRAS TRADUÇÕES/
├── dublado/
├── revisoes/
└── REDIMENSIONAR ÁUDIO PARA CLONAR/
```

A criação da estrutura é explícita pela interface. Configurações locais, caches de modelos, arquivos de projeto e saídas estão no `.gitignore` para reduzir o risco de publicação acidental.

## Compilar o executável no Windows

A compilação precisa ser feita no Windows, pois o PyInstaller gera o executável para o ambiente em que é executado. Com Python ativo, execute:

```powershell
.\build_exe.bat
```

O resultado será criado em `dist\Dublaskizon.exe`. Para um executável portátil que incorpora Python e bibliotecas, use:

```powershell
.\build_exe_portatil_sem_python.bat
```

FFmpeg, FFprobe, FFplay, SoX, OmniVoice, modelos e Audacity continuam sendo dependências externas. Consulte `LEIA-ME_BUILD_DUBLASKIZON.md` para o procedimento detalhado e as limitações de distribuição.

## Preparação de áudio para clonagem via CLI

A ferramenta de preparação também pode ser executada pela linha de comando:

```powershell
python main.py --input arquivo.mp3 --target omnivoice
python main.py --input voz_01.wav voz_02.flac --target eleven_instant --format mp3 --bitrate 256k
python main.py --input pasta\gravacao.wav --target eleven_pro --block-minutes 30 --json
```

As saídas são organizadas em `REDIMENSIONAR ÁUDIO PARA CLONAR\omnivoice`, `elevenlabs_instant` e `elevenlabs_pro`. Os limites de duração e tamanho são parâmetros conservadores de preparação e não substituem a validação da plataforma de destino.

## Testes

Os testes são scripts independentes. Em um ambiente Linux de CI com display virtual, execute:

```bash
python3 -m py_compile *.py
for test_file in test_*.py; do
  xvfb-run -a python3 "$test_file" || exit 1
done
```

No Windows, execute os testes individualmente com Python e forneça um ambiente Tkinter funcional. A suíte cobre descoberta recursiva, hierarquia, temas, atalhos, conversores, WEM, preparação de clonagem, player, ondas, seek por clique, atualização pós-redublagem e organização da lista de Revisão.

## Privacidade e segurança antes do commit

Não publique arquivos `Dublaskizon_interface.json`, `voz_config.json`, `revisao_config.json`, `revisao_estado.json`, tokens, chaves de API, caches do Hugging Face, áudios, TXT, mapas reais, logs com caminhos pessoais ou pastas de saída. O `.gitignore` já exclui os principais padrões, mas a revisão manual continua obrigatória antes do primeiro `git push`.

Confira o conteúdo que será enviado:

```bash
git status --short
git diff --cached --stat
git diff --cached
```

Se houver um segredo publicado por engano, remova-o do histórico do Git e revogue-o no serviço correspondente; apagar somente o arquivo no commit mais recente não é suficiente.

## Documentação

| Arquivo | Conteúdo |
|---|---|
| `PRD_DUBLASKIZON.md` | Requisitos do produto, fluxos, arquitetura, critérios e roadmap |
| `LEIA-ME_BUILD_DUBLASKIZON.md` | Uso detalhado, estrutura do projeto e build |
| `voice_clone_requirements_notes.md` | Notas da ferramenta de preparação para clonagem |
| `Dublaskizon_TUTORIAL.pdf` | Manual visual incorporado ao build |
| `CONTRIBUTING.md` | Fluxo recomendado para contribuições e pull requests |

## Licença

Nenhuma licença de código aberto foi definida neste pacote. Antes de tornar o repositório público ou aceitar contribuições externas, escolha uma licença adequada e adicione o arquivo `LICENSE`. Sem uma licença explícita, os direitos autorais permanecem com o titular do código.

## Edição direta na janela OUVIR CENA

A janela **OUVIR CENA** possui o modo **EDITAR** para ajustes rápidos sem abrir o Audacity. Clique em **EDITAR** e arraste sobre uma forma de onda para selecionar um trecho. Em **ORIGINAL**, a faixa é somente leitura: use **COPIAR** ou **Ctrl+C** para colocar o trecho no buffer de áudio. Na forma **DUBLADO**, clique em um ponto para indicar a inserção ou arraste para selecionar uma área de substituição; use **COLAR** ou **Ctrl+V** para inserir o trecho copiado. **CORTAR** remove somente a seleção da faixa DUBLADO, como medida de segurança para preservar o original.

O comando **SALVAR** escreve o WAV dublado editado por meio de arquivo temporário e substituição atômica. Antes da troca, uma cópia é arquivada em `revisoes/<subpasta>/<cena>_edit_vNN.wav`. O player para ao entrar no modo EDITAR, as formas de onda e os metadados são recalculados em memória, e alterações pendentes são protegidas ao navegar para outra cena ou sair do modo. A edição direta exige WAV PCM legível com características compatíveis para copiar e colar; arquivos em outros formatos continuam disponíveis para reprodução e conversão pelos fluxos próprios.

Os atalhos **Ctrl+C** e **Ctrl+V** no Canvas das ondas atuam sobre o buffer de áudio. No editor de texto português, os mesmos atalhos continuam sendo os atalhos padrão de texto, sem conflito com a edição da faixa.


### RECORTAR, DELETE e atalhos

No modo **EDITAR**, **RECORTAR** e **Ctrl+X** fazem duas ações: copiam o trecho selecionado para o buffer e removem esse trecho da faixa **DUBLADO**. Isso permite colar o conteúdo posteriormente com **COLAR** ou **Ctrl+V**. Já **DELETE** e a tecla **Delete** somente removem o trecho selecionado do **DUBLADO**; o áudio removido não substitui o conteúdo do buffer de colagem. Em ambos os casos, a alteração fica apenas em memória até o usuário clicar em **SALVAR**.

A faixa **ORIGINAL** continua protegida: não pode ser cortada nem apagada. Ela serve como fonte para **COPIAR**, permitindo transferir partes para o DUBLADO. O botão **SALVAR** cria backup do dublado anterior em `revisoes` antes de confirmar a substituição.


### Reprodução e salvamento durante a edição

Enquanto o modo **EDITAR** estiver ativo, pressione **Espaço** com a janela OUVIR CENA em foco para alternar entre reproduzir e pausar a faixa editada. O áudio dublado é materializado em uma cópia WAV temporária validada antes de ser enviado ao FFplay; por isso, depois de colar um trecho do ORIGINAL no DUBLADO, a reprodução já usa a edição atual em memória, mesmo antes de SALVAR. Ao pausar, o próximo Espaço retoma a partir do tempo pausado.

O botão **SALVAR** interrompe a reprodução antes de gravar, escreve um novo cabeçalho e todos os frames em arquivo temporário, confere canais, largura de amostra, frequência e quantidade de frames, e somente então substitui o WAV dublado carregado. O arquivo anterior é arquivado em `revisoes` antes da substituição.

Além da tecla **Delete**, a tecla **Backspace** e o botão **DELETE** removem a seleção do DUBLADO sem alterar o buffer copiado. **RECORTAR** e **Ctrl+X** continuam copiando e removendo a seleção para que ela possa ser colada posteriormente.

Os botões **DESFAZER** e **REFAZER** ficam à esquerda de **SALVAR**. No modo EDITAR, **Ctrl+Z** desfaz a última alteração de frames e **Ctrl+Y** refaz uma alteração desfeita. O histórico vale para a cena atual, é limpo quando uma nova alteração é feita e é reiniciado após um salvamento bem-sucedido.

A reprodução agora interrompe qualquer preview antigo antes de recriar a cópia temporária. Depois de copiar um trecho do ORIGINAL e colá-lo no DUBLADO, o início por botão ou por Espaço reproduz os frames atuais em memória, com validação do cabeçalho e da quantidade de frames, em vez de tocar a versão antiga do arquivo no disco.

A janela OUVIR CENA usa o controle nativo de maximizar/restaurar da barra de título do Windows, junto dos controles nativos de minimizar e **X FECHAR**. Ao maximizar, o painel de texto absorve o espaço vertical disponível e os controles inferiores permanecem acima da barra de tarefas. Ao restaurar, a geometria normal da janela volta pelo próprio Windows.
