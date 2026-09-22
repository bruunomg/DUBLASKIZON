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

## Dublagem personalizada por áudio-modelo

A versão modificada inclui a aba **PERSONALIZADA**. Ela permite cadastrar vários áudios-modelo de voz, selecionar um deles e gerar apenas as cenas escolhidas em `dublados personalizados/`.

O OmniVoice atual recebe uma única referência de áudio por síntese. Por isso, não existe transferência nativa e independente de **timbre de um áudio** + **entonação/prosódia exata de outro**. A aba usa o áudio-modelo como referência de identidade/timbre e, depois da síntese, aproxima a duração, as pausas e o envelope de intensidade do áudio original. A entonação/pitch exata do original não é prometida.

Na aba **REVISÃO**, o seletor de fonte permite alternar entre **Dublados** e **Dublados personalizados**. A janela **OUVIR CENA** acompanha essa escolha; os personalizados podem ser ouvidos, editados e redublados. Para uma redublagem personalizada, o programa reutiliza automaticamente o áudio-modelo registrado no manifesto da cena.


## Organização v17
Os testes foram preservados no pacote separado DUBLASKIZON-86-testes-desenvolvimento-v52.zip. Não são necessários para executar nem compilar a ferramenta. Para executá-los, extraia esse pacote sobre a mesma pasta-pai deste projeto: os arquivos test_*.py devem ficar ao lado de Dublaskizon.py, como antes. Para revisão por outra IA, envie o pacote principal e, quando precisar dos testes, esse pacote complementar. Todos os módulos de execução, recursos e scripts de compilação mantêm seus caminhos. A separação não altera dependências de execução; compilação completa não foi executada nesta atualização.


## Dividir e mover trechos — v18
1. Abra OUVIR CENA e clique em EDITAR.
2. Clique no ponto da onda DUBLADO onde deseja dividir. Use Ctrl+I ou DIVIDIR (Ctrl+I). Repita para criar mais partes.
3. Arraste a barra verde do trecho, acima da onda. O número identifica o trecho, mesmo quando sua ordem muda. Ao cruzar outro trecho, o editor reorganiza as partes sem sobreposição e sem apagar amostras.
4. Os espaços deixados livres viram silêncio. Ao mover para além do fim, a duração pode aumentar. O áudio ORIGINAL não é alterado.
5. Ouça a prévia. DESFAZER/REFAZER também restauram as divisões e posições. SALVAR grava o WAV montado e mantém o backup do áudio anterior.
6. As divisões são registradas em revisoes/.dublaskizon_trechos.json (um arquivo por projeto, sem cópias do áudio). Leve também esse arquivo ao mover o projeto para outro computador. O WAV funciona sozinho; sem esse registro, o editor o reabre como um único trecho. Se o áudio for alterado externamente, o registro antigo é ignorado para preservar o conteúdo atual.

Recortar, excluir e colar preservam as divisões restantes. DESFAZER restaura o áudio e as divisões anteriores. Os controles de duração continuam em 1% por clique.

Validação: testes de divisão exata por amostras, mono/estéreo, PCM 8–32 bits, silêncio, troca de ordem com trechos de durações diferentes, eventos de arraste, histórico, recortar/colar, salvamento WAV e reabertura do registro de divisões. Sintaxe dos módulos e integridade dos ZIPs verificadas. A aparência não pôde ser validada neste ambiente porque o Tk instalado não inicializa; não foi gerado um novo EXE. Os dois scripts de compilação incluem o novo módulo audio_clip_timeline.


## Correção v19 — colar preservando divisões
COLAR mantém os trechos existentes separados e cria um novo trecho para o áudio colado. Ao colar dentro de um trecho, suas partes antes e depois da inserção também ficam separadas. Uma seleção é substituída normalmente, preservando as divisões que ficam fora dela. O restante da linha do tempo se desloca conforme a duração inserida, como antes. Funciona com cópias do ORIGINAL e do DUBLADO, histórico de desfazer/refazer e registro das divisões.


## Correção v20 — duração e silêncio preservam divisões
Os botões −/+ continuam ajustando o áudio inteiro em 1%, mas agora reposicionam as divisões sem unir os trechos. Cortar silêncio mantém as divisões restantes e remove apenas as extremidades detectadas; partes inteiramente contidas no silêncio removido desaparecem. Os espaços internos permanecem em silêncio. A preservação também funciona no histórico e no registro salvo das divisões. Testado com FFmpeg real, ajustes para mais/menos, corte das extremidades, histórico e reabertura dos metadados.


## Correção v21 — seleção visível e Delete
Clique na barrinha de um trecho para selecioná-lo: ela e a região correspondente da onda ficam em tom escuro. O destaque indica seleção para qualquer ação, não somente exclusão. Clique e arraste a barrinha para mover (pequenos movimentos involuntários do mouse são ignorados). Delete ou Backspace excluem o trecho selecionado; copiar/recortar/colar e seus atalhos funcionam na barrinha. Arraste sobre a onda para selecionar somente uma região. Delete e Recortar preservam os trechos fora da região removida e não unem as divisões. A exclusão continua removendo a duração selecionada e deslocando o áudio seguinte, como antes. Testados clique/arraste, seleção, exclusão total de um trecho e parcial, recorte, área de transferência e histórico; a aparência não foi validada visualmente neste ambiente.


## v22 — reproduzir a partir da seleção
No modo EDITAR, clique na onda ou selecione um trecho: Espaço inicia no ponto clicado ou no início da seleção. INICIAR DUBLADO usa esse mesmo ponto na prévia editada. Espaço novamente pausa; outro Espaço continua da pausa. Um novo clique redefine o início. Sem seleção, a reprodução começa do início. O posicionamento usa o player FFplay interno; o player externo do Windows mantém suas limitações de busca. Testados seleção de ponto/intervalo, seleção invertida, pausa/retomada, novo clique e reprodução fora do modo EDITAR.


## v23 — Dublar parte do TXT e montar a cena
1. Abra OUVIR CENA na Revisão ou na Dublagem Personalizada e clique DUBLAR PARTE DO TXT.
2. A janela abre uma cópia do texto atual. Exclua o que não deseja e deixe somente a frase da parte. Isso não altera o TXT principal.
3. DUBLAR usa a referência original da cena. Em Dublados personalizados/Dublagem Personalizada, usa o modelo registrado para a cena (ou o modelo ativo da aba personalizada). DUBLAR COM OUTRO ÁUDIO permite escolher outra referência. Se o modelo personalizado estiver ausente, escolha uma referência; não é usada silenciosamente uma voz normal.
4. A geração cria PARTE (1), PARTE (2), etc., na coluna direita, com rolagem. A numeração é independente para cada cena e para dublagem normal/personalizada. Cada resultado permanece salvo ao reabrir a ferramenta.
5. Clique numa PARTE para abrir seu áudio e TXT em outra janela. Ela já abre no modo EDITAR. Use COPIAR PARTE INTEIRA ou selecione um trecho e use COPIAR/Ctrl+C.
6. Na janela principal, ative EDITAR, clique no ponto desejado do DUBLADO e use COLAR/Ctrl+V. As divisões existentes continuam separadas; use Desfazer/Refazer e SALVAR normalmente.
7. Repita DUBLAR PARTE DO TXT para gerar outras frases. Editar/salvar o texto de uma parte só altera o TXT daquela parte.

Os resultados ficam em revisoes/partes_txt/<identificador da cena>/parte_0001, parte_0002, etc. Cada pasta contém parte.wav, texto.txt e info.json. Leve a pasta revisoes junto ao mover o projeto. As partes não substituem áudios/TXTs principais nem partes anteriores. O botão CANCELAR/FECHAR interrompe a geração daquela parte. O áudio é compatibilizado com os canais, taxa de amostragem e profundidade PCM do dublado principal para permitir colagem. As partes personalizadas usam o modelo de voz, sem esticar uma frase parcial à duração da cena original inteira.

Validação: inferência simulada verificando os parâmetros OmniVoice; testes reais de conversão PCM/float com FFmpeg, arquivos separados e imutabilidade da cena principal, numeração persistente, fontes normal/personalizada independentes, referência correta, cópia entre janelas preservando divisões, Desfazer, falha e cancelamento de subprocesso. Testes anteriores de Revisão e Dublagem Personalizada também passaram. Geração real do modelo OmniVoice, aparência da interface e compilação EXE não foram validadas neste ambiente. Os scripts de compilação incluem scene_parts.


## v24 — botões da janela Dublar parte do TXT
O editor usa layout com rodapé reservado: somente o campo de texto expande. SALVAR ALTERAÇÃO grava rascunho.txt na pasta de partes da cena, sem modificar o TXT principal; ao reabrir, o rascunho é recuperado. REDUBLAR gera uma nova parte com a referência atual; REDUBLAR COM OUTRO ÁUDIO permite escolher a referência. CARREGAR TXT PRINCIPAL repõe o texto completo na janela para preparar outra parte (clique SALVAR ALTERAÇÃO para substituir o rascunho). CANCELAR / FECHAR continua disponível durante a geração. A janela possui barra de rolagem no texto. Testes de callbacks com widgets simulados passaram; aparência em Tk real e inferência OmniVoice não foram validadas neste ambiente.


## v25 — zoom horizontal das ondas
Ctrl + roda do mouse sobre ORIGINAL, DUBLADO ou a barra de trechos amplia/reduz as duas ondas juntas. O ponto sob o mouse permanece como referência ao ampliar. O controle superior tem uma linha e uma bolinha: centro = 100%, direita amplia, esquerda reduz; faixa de 12,5% a 800%. O botão 100% restaura o tamanho normal. A barra horizontal abaixo das ondas navega pelas duas faixas e pelos trechos sincronizados. O zoom apenas altera a visualização, sem mudar duração, tom ou arquivos. Funciona também nas janelas das partes. Clique, seleção, divisão e arraste consideram o zoom e a posição da rolagem. Os picos da onda guardam mais detalhes; somente o trecho visível é desenhado. Testados sincronismo, posição sob o mouse, seleção/divisão/arraste após rolagem, limites, controle circular e preservação do PCM; aparência em janela real não validada neste ambiente.


## v26 — menu da Dublagem Personalizada e busca
Botão direito na lista personalizada: ouvir cena, abrir local do áudio original/personalizado, copiar nome e pastas. Ctrl+F abre busca não modal: pesquisa enquanto digita, conta resultados e navega por Anterior/Próximo, Enter/F3 e Shift+Enter/F3. Com foco em um botão, usa a lista visível da janela. Nas listas ignora maiúsculas e acentos; palavras podem aparecer em qualquer ordem. Busca em blocos com cancelamento da consulta anterior para manter a interface responsiva. Inclui o zoom da v25. Testes de lógica com controles simulados passaram; interface gráfica real não validada neste ambiente.


## v27 — seleção visível na busca em todas as abas
Ctrl+F destaca o resultado atual com fundo azul e texto branco mesmo com o foco na busca. Anterior/Próximo continuam selecionando e trazendo o arquivo para a área visível; as cores anteriores da linha são restauradas ao navegar. Abrange listas e tabelas de Revisão, Clonagem + Dublagem, Dublagem Personalizada, conversões, filtro, redimensionamento, compactação e troca de áudio. O seletor superior permite escolher entre as listas visíveis da aba, inclusive áudios dublados, vídeos e originais extraídos. Controles de abas ocultas são ignorados. Seleção das conversões fica independente da seleção do texto da busca. Testes com controles simulados cobrem destaque, restauração, próxima/anterior, abas ocultas, troca de lista, seleção em tabelas sem foco, cancelamento e busca incremental. Interface gráfica real não validada neste ambiente.


## v28 — volume do áudio dublado
Em OUVIR CENA, ative EDITAR e use − VOLUME / VOLUME + ao lado de DIVIDIR. Cada clique solicita −1 ou +1 dB no áudio dublado inteiro da cena atual; a seleção não limita este ajuste. Ouça com INICIAR DUBLADO e use SALVAR para gravar; DESFAZER/REFAZER funcionam normalmente. O original e outros arquivos não são alterados. Processamento vetorizado em float64/NumPy, já incluído nas dependências, sem compressão dinâmica nem codificação com perdas. Mantém taxa, canais, profundidade PCM e número de amostras. O ganho positivo fica limitado a pico de amostra de −1 dBFS; se o áudio já ultrapassa esse teto, o botão + não aumenta nem reduz o volume. A mensagem informa quanto foi aplicado. O teto evita saturação das amostras, mas não é medição de true peak; ruídos existentes também são amplificados. Há arredondamento inerente ao retorno para PCM inteiro. Não é aplicado ruído de dither. Trechos, IDs, posições e silêncios preservados. Testes passaram em PCM 8/16/24/32 bits estéreo, saturação, silêncio, isolamento do original, desfazer/refazer e regressões de duração/zoom. Interface gráfica real não validada neste ambiente. Referência conceitual de ganho: https://www.ffmpeg.org/ffmpeg-filters.html#volume


## v29 — pedido para alterar personagem
Em OUVIR CENA, marque Pedido para alterar personagem da dublagem personalizada. Ao usar REDUBLAR (ou REDUBLAR ÁUDIO PERSONALIZADO), abre ÁUDIOS MODELO DE VOZ, com lista, + ADICIONAR MODELO, REMOVER MODELO, OUVIR MODELO, PARAR, CANCELAR e USAR MODELO E CONTINUAR. Reutiliza a biblioteca e a preparação de modelos da aba personalizada; remover tira o modelo da lista, sem apagar o arquivo. A prévia toca diretamente no diálogo. Cancelar não inicia geração. A confirmação continua pelo fluxo existente de pronúncia do R e confirmação da cena. A saída continua na fonte da cena atual: personalizada fica em dublados personalizados; dublado normal continua em dublado. Na saída personalizada, o manifesto registra a referência após o WAV ter sido substituído com sucesso. A opção começa desmarcada. REDUBLAR COM OUTRO ÁUDIO conserva seu seletor existente. Testes com UI e síntese simuladas validaram diálogo, callbacks, cancelamento, referência de geração, destino personalizado e manifesto; testes anteriores de integração personalizada e destino de redublagem também passaram. OmniVoice e aparência real da janela não validados neste ambiente.


## v30 — correção dos botões de duração
Os botões DURAÇÃO usam o mesmo convert_longer da pasta maior do conversor (SoX tempo quando disponível; FFmpeg atempo como alternativa). Cada trecho dividido é processado independentemente, mantendo IDs e espaços de silêncio escalados com a duração; não recorta mais as divisões sobre uma onda inteira esticada. Cliques consecutivos usam a mesma base, evitando acumular processamento: cada clique muda 1 ponto percentual da duração-base, + aumenta duração/diminui velocidade e − diminui duração/aumenta velocidade. + seguido de − retorna exatamente à base. Faixa deste ajuste: 50% a 200%; outro tipo de edição estabelece uma nova base. DESFAZER/REFAZER preservam a base e a porcentagem. Mantém formato PCM e duração-alvo em amostras; diferenças de tamanho do processador são ajustadas somente no fim de cada trecho. Testado com FFmpeg real em áudio sintético: tom, duração, correspondência ao conversor por trecho, cliques sem processamento cumulativo, retorno exato, volume, silêncio, seleção, divisões e histórico. O áudio específico com som robótico e a interface real não foram avaliados; o processamento de tempo não garante ausência de artefatos em qualquer sinal.


## v31 — saída somente com áudios finalizados
Síntese e processamento de expressão da Revisão e Dublagem Personalizada passam a usar revisoes/_intermediarios, com nomes exclusivos e subpastas preservadas. Somente o WAV concluído é transferido para a saída. Se o Windows impedir a remoção de um intermediário, ele permanece em revisoes, sem poluir dublados personalizados. O manifesto JSON permanece na saída, pois guarda a associação dos personagens. Testes de referência, destino e integração passaram com geração simulada.


## v32 — seleção múltipla de trechos
Em OUVIR CENA / EDITAR: Ctrl+A seleciona todas as divisões do dublado; Ctrl+clique marca/desmarca trechos individuais; Shift+clique seleciona do trecho âncora ao clicado, inclusive os intermediários, nos dois sentidos. Funciona nas barras e, com modificadores, sobre os trechos na onda. Os trechos selecionados ficam escuros. Clique simples na barra seleciona apenas um e permite o arraste habitual; a seleção múltipla não implementa movimentação em grupo. Ctrl+A dentro de um campo de texto mantém a seleção do texto. Copiar concatena apenas os trechos selecionados em ordem; Delete/Recortar removem apenas eles, preservando os desmarcados; Colar substitui os selecionados e insere o conteúdo no primeiro ponto, sem apagar os intermediários desmarcados. Desfazer restaura áudio e divisões. Testes de seleção, realce, operações não contíguas, exclusão total, histórico, zoom e início de reprodução passaram com controles simulados; interface real não validada neste ambiente.


## v33 — arraste da seleção em grupo
Depois de selecionar os trechos, solte Ctrl/Shift e arraste a barra de qualquer trecho selecionado. O clique preserva a seleção; todos acompanham o deslocamento do mouse, mantendo as distâncias entre si. O primeiro trecho limita o grupo no início da faixa. Colisões deslocam os trechos não selecionados para evitar sobreposição/perda de áudio. A seleção permanece após soltar e DESFAZER/REFAZER preservam posições e PCM. Testes passaram para todos/alguns selecionados, deslocamento em ambos os sentidos, limite zero, colisões, zoom, rolagem e histórico. Interface real não validada.


## v34 — projetos com milhares de áudios
Descoberta de WAV/TXT por enumeração de diretórios, sem resolver no disco cada caminho repetidamente; mantém subpastas, preferência WAV e exclusão de arquivos internos. Dublagem Personalizada atualiza o índice em segundo plano sem chamadas Tk no worker, impede scans simultâneos e mantém a seleção; lista idêntica não é redesenhada. Revisão não recria a lista sem mudanças e atualiza apenas as linhas de status alteradas. Clonagem + Dublagem insere a lista em lote. O controlador de revisão personalizado recebe o índice já carregado. OUVIR CENA normaliza a playlist sem resolver milhares de caminhos no disco, resolvendo o par atual sob demanda. Busca FFmpeg/SoX verifica executáveis diretamente na raiz e recorre somente nas pastas de ferramentas (ferramentas_audio/tools/sox), evitando percorrer a árvore de áudios em cada aba. Tradução automática não reconfigura textos e variáveis idênticos, evitando redesenhos e callbacks repetidos. Teste local com 5000 pares: índice em aproximadamente 0,34s; playlist com 9 resoluções de caminho, somente o par atual. Testes de índices, seleção, atualização em segundo plano, ferramentas portáteis, reprodução exata nos conversores, integração personalizada e traduções passaram. Medição sintética em disco local, não garante o mesmo tempo em outros discos; interface real não validada neste ambiente.


## v35 — outras traduções em Ouvir cena
Acima do texto, SELECIONAR OUTRA TRADUÇÃO abre um TXT para a cena atual e ativa Usar no redublar. O texto aparece editável; Salvar alteração grava a alternativa com backup sem sobrescrever o principal. Desmarcar Usar no redublar ou MOSTRAR TEXTO DA TRADUÇÃO PRINCIPAL retorna ao principal. Os botões REDUBLAR, REDUBLAR COM OUTRO ÁUDIO e REDUBLAR ÁUDIO PERSONALIZADO capturam o texto exibido. Edições não salvas pedem confirmação antes de trocar de tradução. A opção da aba Revisão também se chama Usar no redublar. Seleção de TXT avulso fica vinculada à cena durante a sessão. Testes de visualização/carregamento, salvamento isolado, encaminhamento do texto, principal, integração personalizada e destinos passaram com controles/síntese simulados; interface real e OmniVoice não validados.


## v36 — pastas de OUTRAS TRADUÇÕES em Ouvir cena
A seleção avulsa de TXT foi substituída pelos mesmos diretórios usados pela Revisão. MOSTRAR TEXTO DA TRADUÇÃO PRINCIPAL fica à esquerda; as pastas ficam à direita, organizadas em linhas de até três botões. Clicar na pasta usa o seletor da Revisão e carrega o TXT correspondente à cena/subpasta, ativando Usar no redublar quando encontrado. Se faltar o TXT, mantém o principal e informa o motivo. ESCOLHER PASTA OUTRAS TRADUÇÕES permite trocar a raiz, como na Revisão. Testes de descoberta real de pastas, correspondência, fallback e retorno ao principal passaram; interface gráfica real não validada.


## v37 — botões de traduções compactos
Removido o botão Escolher pasta outras traduções de Ouvir cena. Usar no redublar fica à direita na linha da tradução principal. Pastas usam fonte/padding da Revisão, largura natural sem esticar. Principal permanece à esquerda.


## v38 — carregar pastas/personagens na Dublagem Personalizada
ADICIONAR PASTA acumula pastas dentro de WAV ORIGINAIS, incluindo subpastas. ADICIONAR TODAS DO PERSONAGEM pede o nome exato da pasta e inclui todas as ocorrências em qualquer capítulo, sem diferenciar maiúsculas/minúsculas e sem confundir nomes parecidos ou nomes dos arquivos. As escolhas se somam sem duplicar cenas. Apenas pares áudio/TXT entram na lista. MOSTRAR TODAS AS CENAS limpa o filtro. Ao alterar o filtro as cenas visíveis ficam selecionadas; revise a seleção antes de DUBLAR PERSONALIZADOS. ATUALIZAR CENAS mantém o filtro durante a sessão e inclui novos pares correspondentes. O filtro usa o índice em memória; preserva caminhos relativos e não altera arquivos nem outras abas. Testes de subpastas, nomes repetidos, duplicatas, TXT, recarga e limpeza passaram, assim como integração personalizada e projeto de 5000 pares. Interface real não validada neste ambiente.


## v39 — árvore de pastas dos personagens
ADICIONAR TODAS DO PERSONAGEM abre uma árvore somente de pastas, a partir do índice dos áudios carregados, sem listar WAVs. Expanda um capítulo, selecione a pasta do personagem e use ADICIONAR TODAS COM ESTE NOME para reunir ocorrências em qualquer capítulo. SOMENTE ESTA PASTA limita à pasta escolhida e subpastas. A informação inferior mostra a quantidade de pastas com o nome e cenas com áudio/TXT. Seleções são adicionadas ao filtro atual. Pastas vazias ou sem áudios carregados não constam da árvore. Testes simulados validaram hierarquia, ausência de arquivos, nomes repetidos, confirmação e filtros; interface real não validada.


## v40 — instalação guiada e requisitos
A janela REQUISITOS foi reorganizada em VERIFICAR, INSTALAR / REPARAR, BAIXAR MODELOS e TESTAR MODELO, com seleção CPU/NVIDIA, relatório persistente, cancelamento e preparação das ferramentas de áudio. As operações demoradas usam subprocessos e uma fila para atualizar a interface; nenhuma instalação começa ao abrir a janela.

O cache não é toda a instalação: a síntese precisa de Python, OmniVoice, PyTorch e modelos. A interface em EXE já leva seu próprio Python; o mecanismo de voz usa um ambiente separado por usuário em `%LOCALAPPDATA%/Dublaskizon/runtime`. A instalação guiada usa Python 3.13.15 x64 de python.org, confere o SHA-256 publicado pelo projeto, cria um venv novo e instala OmniVoice 0.2.1 do PyPI com PyTorch/torchaudio 2.8.0 do índice oficial (CPU ou CUDA 12.8). Não remove Python da Store, não altera o PATH global e não modifica o ambiente anterior. Só ativa o novo após pip check, carregamento da CLI e teste de tensor; CUDA precisa funcionar para ativar a opção NVIDIA. Uma instalação interrompida não substitui a anterior. Ambientes antigos/incompletos são preservados em runtime; não há limpeza automática destrutiva. O Python da Store não é intrinsecamente inferior: a separação evita conflitos de versões e aliases.

Use BAIXAR MODELOS para obter o repositório completo do modelo escolhido, o tokenizer `eustlb/higgs-audio-v2-tokenizer` e, opcionalmente, `openai/whisper-large-v3-turbo`, pelo Hugging Face oficial. Whisper vem marcado porque permite transcrever o áudio de referência. BR-PT é uma adaptação publicada pelo autor edwixx; o modelo base oficial é k2-fsa/OmniVoice. Os downloads reutilizam o cache padrão ou o configurado por HF_HOME/HF_HUB_CACHE e podem ocupar vários GB. O cache simples do VoiceStudio em `%LOCALAPPDATA%/OmniVoice/hf_cache/edwixx/omnivoice-brpt-v15` também é reconhecido para a voz principal, quando contém config.json, tokenizer.json e model.safetensors. A variante `hf/_cache` é reconhecida. Pastas encontradas não são anunciadas como modelos validados. TESTAR MODELO tenta carregar voz/tokenizer/Whisper sem baixar arquivos e informa erros de memória ou dependências; não é um teste de qualidade da fala. Não há migração nem exclusão dos caches existentes.

A geração das abas utiliza automaticamente o ambiente validado. Uma variável OMNIVOICE_INFER explicitamente configurada continua tendo prioridade. Sem ambiente gerenciado, a descoberta anterior permanece disponível. VoiceStudio não é obrigatório: o módulo omnivoice-subprocess da imagem é uma opção do próprio VoiceStudio, não outro pacote de modelo. O botão correspondente abre as releases do autor, sem Google Drive nem espelhos alternativos.

Fontes consultadas:
- Python e hash do instalador: https://www.python.org/downloads/release/python-31315/
- OmniVoice: https://github.com/k2-fsa/OmniVoice e https://pypi.org/project/omnivoice/0.2.1/
- PyTorch: https://download.pytorch.org/whl/cpu/ e https://download.pytorch.org/whl/cu128/
- Modelos: https://huggingface.co/edwixx/omnivoice-brpt-v15 e https://huggingface.co/k2-fsa/OmniVoice
- VoiceStudio opcional: https://github.com/debpalash/VoiceStudio/releases
- FFmpeg: https://ffmpeg.org/download.html (o projeto distribui fontes e indica Gyan para binários Windows; o preparador existente usa Gyan). SoX: projeto oficial no SourceForge.

Windows x64 é necessário para esta instalação automática. NVIDIA precisa de driver compatível; CPU é uma opção mais lenta. Erros de DLL podem exigir Visual C++ x64 da Microsoft: https://learn.microsoft.com/pt-br/cpp/windows/latest-supported-vc-redist . Os logs ficam em runtime/logs, e o log do instalador Python em runtime/python-install.log. Reserve pelo menos 12 GB para a preparação do ambiente, além de espaço para modelos e caches. Os downloads não vêm embutidos neste ZIP. Se usar o código-fonte, instale requirements.txt para abrir/compilar a interface; os dois BATs de compilação foram atualizados, inclusive para audioop-lts no Python 3.13.

Validação desta entrega: 13 testes automatizados do assistente (subprocessos reais para saída, cancelamento, erro e timeout; instalação/download e widgets simulados), oito scripts de regressão das funcionalidades existentes, análise sintática e integridade dos ZIPs. Não foi executada instalação completa, síntese real nem inspeção visual da janela Tk neste ambiente. O executável não foi recompilado; este pacote contém o projeto atualizado e os scripts de compilação.


## v41 — pendências, progresso e atividade nas abas
A barra de REQUISITOS agora é determinada: começa vazia, avança por download/etapas concluídas sem retroceder e volta a zero quando não há operação. Não há animação indeterminada.
Na DUBLAGEM PERSONALIZADA, os arquivos já presentes aparecem com [OK] e a seleção inicial inclui só pendentes. O processamento normal pula WAVs finais já existentes, inclusive se surgirem após selecionar o lote. REDUBLAR explícito continua permitindo refazer uma cena. O OK e a seleção são atualizados por linha ao terminar, sem reconstruir toda a lista.
A aba personalizada tem barras de voz-modelo, síntese e ritmo/pausas do original, além do total de cenas. A terceira etapa é pós-processamento do original, não uma segunda clonagem nativa do OmniVoice. Clonagem + Dublagem e Revisão agora acompanham mensagens/percentuais emitidos pelo processo; o relógio da Revisão não inventa porcentagens nem previsão de término por tempo decorrido. O OUVIR CENA recebe os mesmos dados da operação vinculada, inclusive do lote personalizado e da clonagem normal. Sem saída de progresso do motor, a etapa pode permanecer no mesmo valor até a próxima mensagem: não é uma medição de utilização da GPU. Cada cena nova inicia suas próprias barras em zero.
Abas com tarefas em andamento piscam em amarelo quando estão em segundo plano. Ao selecionar a aba ou terminar a tarefa, o estilo normal volta. Abrange as operações assíncronas de clonagem, revisão, personalizada, conversores, vídeo, troca de áudio, redimensionamento e o terminal de Comandos.
Validação: 18 testes automatizados (assistente, avanço monotônico, leitura ao vivo de subprocesso, OK/seleção, pular existentes versus redublar e sinalização de abas), oito scripts de regressão e análise sintática/CRC do pacote. Widgets e síntese OmniVoice foram simulados; subprocessos de teste foram reais. Interface Tk real e geração de voz não foram validadas neste ambiente. Projeto para compilar, sem EXE recompilado.


## v42 — rolagem e disposição das barras personalizadas
Lista de cenas com barra vertical e rolagem do mouse local, sem rolar a página junto. As barras de clonagem, dublagem e ritmo ficam lado a lado em três colunas de largura igual. O total de cenas processadas usa vinho #800020 em todos os temas. Validados sintaxe, eventos de rolagem, cinco testes de progresso/pendências e integridade do ZIP; interface real não inspecionada.


## v43 — largura inicial da Revisão e pronúncia do R personalizada
A divisória da lista de áudios da Revisão recebe uma largura inicial de 30% do painel, limitada entre 320 e 440 pixels, somente após a aba ser exibida. O usuário continua livre para arrastar a divisória; o ajuste inicial não é reaplicado depois.
DUBLAGEM PERSONALIZADA agora tem PRONÚNCIA DO R com as mesmas opções da clonagem: SEM ALTERAÇÃO, R SUAVE, R NORMAL e R FORTE. A cada inicialização começa em SEM ALTERAÇÃO, sem restaurar escolha anterior. A escolha é capturada no início do lote e usada também no controlador de redublagem personalizada do OUVIR CENA, mantendo o pedido pontual de R como opção. O TXT salvo não é modificado; aplica-se a mesma transformação textual existente antes da síntese.
Verificação: ajuste inicial e preservação da divisória, seleção do R, comando de geração com transformação do texto sem modificar o TXT, cinco testes de progresso/pendências e oito scripts de regressão. Interface e síntese reais não validadas neste ambiente. Projeto para compilar; sem EXE recompilado.


## v44 — transcrever, traduzir e dublar quando faltar TXT
Na aba Clonagem + Dublagem, ative TRANSCREVER E TRADUZIR QUANDO FALTAR TXT e configure mecanismo, modelos, tradutor, idioma original/saída e CPU/CUDA. A opção começa desligada. Ativada, inclui áudios sem TXT; textos existentes e preenchidos continuam sendo usados sem nova transcrição. O idioma escolhido aplica-se aos textos gerados automaticamente.
Em Ouvir cena, o pedido para transcrever e traduzir o original fica ao lado do pedido de personagem. Redublar e Redublar com outro áudio abrem a configuração; a transcrição usa sempre o original, enquanto o modelo de voz escolhido continua sendo usado na síntese. A tradução gerada aparece no quadro de texto após a geração; o TXT principal existente é preservado.
São oferecidos faster-whisper e openai-whisper, modelos tiny/base/small/medium/large-v2/large-v3/turbo, Argos e os mesmos perfis Ollama de Gerar DUBLASKIZON V22: translategemma-local = translategemma:4b, qwen-game-local = qwen2.5:7b.
Preparação: instale primeiro o Python gerenciado pela Verificação inicial. Na configuração nova, use PREPARAR DEPENDÊNCIAS; este ambiente é separado do OmniVoice. Para TranslateGemma ou Qwen, instale e abra o Ollama pelo botão OLLAMA OFICIAL. O serviço local deve estar disponível em localhost:11434. Modelos ausentes são baixados no primeiro uso, que precisa de internet e pode demorar. Argos baixa os pares oficiais necessários quando disponíveis. CUDA depende de hardware e bibliotecas compatíveis; CPU é o padrão. Para outros idiomas, escolha um modelo de voz compatível/multilíngue; a qualidade varia com o modelo e o áudio.
Sem fala, tradução vazia ou falha do tradutor interrompem a síntese daquela cena. O lote permite cancelar. Registros ficam em revisoes/transcricoes_traducoes; traduções alternativas ficam em OUTRAS TRADUÇÕES/AUTO_<idioma>, sem sobrescrever arquivos já preenchidos. A versão nova fica preservada no registro de revisões.
Validação: 26 testes automatizados de tradução, instalação e progresso, além de oito scripts de regressão. Serviços de reconhecimento, tradução e síntese foram simulados nos testes; não houve download de modelos, inferência real nem validação visual da interface neste ambiente. Pacote de código-fonte; nenhum EXE foi recompilado.
Fontes oficiais: https://github.com/SYSTRAN/faster-whisper ; https://github.com/openai/whisper ; https://argos-translate.readthedocs.io/en/stable/ ; https://ollama.com/library/translategemma ; https://ollama.com/library/qwen2.5 ; https://docs.ollama.com/api/generate


## v45 — Python instalado e progresso da preparação
Corrigida a preparação de transcrição/tradução: não exige mais active.json de uma instalação completa do OmniVoice. Procura o Python gerenciado, o Python base dos Requisitos, instalações oficiais usuais e registradas no Windows e o executável do PATH. Valida execução, versão 3.10–3.13, 64 bits e venv antes de criar o ambiente separado. Não altera o Python encontrado nem o ambiente de dublagem. Versões incompatíveis recebem orientação explícita.
A janela tem barra de etapas concluídas e barra do arquivo baixado com MB recebidos/total. O progresso do download usa a saída raw oficial do pip; cada arquivo inicia seu próprio percentual. Durante instalação/verificação sem bytes informados não há animação fictícia. Preparação só chega a 100% depois das verificações e ativação. Modelos continuam sendo baixados no primeiro uso; estas barras acompanham a preparação das dependências nesta janela.
28 testes automatizados passaram, incluindo instalação separada sem active.json e progresso por bytes. Instalação real de dependências e interface gráfica não executadas neste ambiente. Código-fonte, sem EXE recompilado.
Referência do progresso: https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program


## v46 — carregamento das bibliotecas CUDA no faster-whisper
O subprocesso de transcrição registra torch/lib e os diretórios bin de pacotes NVIDIA do próprio ambiente no PATH e na busca de DLLs do Windows, mantendo os handles abertos e inicializando PyTorch antes de CTranslate2. Não copia DLLs para o sistema e não precisa reinstalar Python quando as bibliotecas já estão presentes.
Se ocorrer falha de CUDA/cuBLAS/cuDNN durante carregamento ou durante iteração dos segmentos, reinicia uma vez a transcrição completa pela CPU (int8 no faster-whisper), registrando o motivo no log. Não reaproveita segmentos parciais e não faz fallback para erros não relacionados à GPU. A escolha CUDA continua preservada nas configurações; o fallback afeta apenas a transcrição da cena.
30 testes automatizados passaram. Foi verificado no ambiente instalado do usuário que cuBLAS e cuDNN carregam com a configuração corrigida e que CTranslate2 detecta uma GPU. Dublagem completa e interface gráfica não foram executadas nesta validação. Pacote de código-fonte, sem EXE recompilado.
Referência: https://github.com/SYSTRAN/faster-whisper#gpu


## v47 — Python existente nos Requisitos e início automático do Ollama
A instalação dos Requisitos procura e valida o Python 3.13 de 64 bits já instalado (pasta gerenciada, pastas oficiais usuais e Registro do Windows) antes de chamar o instalador. Assim evita o caso em que o instalador entra em manutenção, retorna sucesso e não cria o TargetDir solicitado. Cria um novo venv para as dependências; não instala pacotes no Python base. Após executar um instalador também verifica a localização real. Se não encontrar Python utilizável, apresenta erro específico com o caminho do log, sem tentar abrir um executável inexistente nem ativar ambiente incompleto.
Para TranslateGemma/Qwen, reutiliza o Ollama que já responde em localhost:11434. Se estiver fechado, localiza o executável instalado e inicia ollama serve sem terminal visível, restrito a 127.0.0.1, aguardando a API responder. Se estiver ausente, orienta a instalação oficial ou escolha de Argos. Não inicia instalação automática nem baixa modelos durante os testes. A transcrição e as configurações anteriores permanecem preservadas.
36 testes passaram, incluindo Python existente sem reinstalação, instalador que retorna sucesso sem criar Python, redescoberta da pasta e Ollama aberto/fechado/ausente. O Python 3.13.15 instalado no computador do usuário passou na verificação real de execução, 64 bits, venv e ensurepip. Instalação completa das dependências, interface gráfica e dublagem completa não foram executadas nesta validação. Código-fonte, sem EXE recompilado.
Referência Ollama: https://github.com/ollama/ollama/blob/main/docs/windows.mdx


## v48 — FFmpeg nas verificações dos Requisitos
A janela Requisitos resolve o diretório das ferramentas de áudio em todas as ações, inclusive instalação e teste do modelo, e o repassa ao ambiente dos subprocessos. FFmpeg fica acessível no PATH apenas desses processos, sem modificar o PATH do Windows. Corrige o aviso do pydub no teste quando o FFmpeg do projeto já existe.
37 testes automatizados passaram. Um teste executa um subprocesso real para verificar a resolução do executável numa pasta com espaços e a preservação do PATH do aplicativo. Os relatórios fornecidos pelo usuário confirmam instalação do ambiente, pip check sem conflitos, CUDA disponível e carregamento do modelo de voz; a geração completa de uma fala ainda não foi validada nesta etapa. Não é necessário reinstalar o ambiente ou baixar os modelos para aplicar esta correção. Código-fonte, sem EXE recompilado.


## v49 — processamento automático, downloads e tamanhos
Processamento começa em Automático: consulta a NVIDIA pelo nvidia-smi; quando disponível usa a instalação CUDA 12.8, caso contrário usa CPU. A janela mostra o nome do processador e da NVIDIA/memória detectada e permite escolher CPU AMD/Intel manualmente. A instalação ainda testa a execução real do PyTorch antes de ativar o novo ambiente. Compatibilidade do instalador: Windows x64; não há garantia de desempenho ou memória suficiente em qualquer PC.
CPU AMD Ryzen e Intel são suportadas pelo caminho CPU. GPU AMD/ROCm não foi adicionada ao instalador: os pacotes oficiais dependem da placa, sistema, versão do Python e PyTorch, e essa combinação com OmniVoice não foi validada. A janela oferece o link da matriz oficial. Não confundir o processador Ryzen com a GPU Radeon integrada. No computador do usuário foram detectados Ryzen 5 8600G/Radeon 760M e RTX 5060; automático escolheu NVIDIA.
Duas barras na Verificação inicial: etapas concluídas e download atual com bytes e MB/GB. O pip usa progresso raw após sua atualização; o Python usa Content-Length; o download dos modelos usa callbacks de bytes da API oficial Hugging Face. Uma nova transferência pode reiniciar a barra do arquivo; não existe animação fictícia. Sem tamanho total conhecido, mostra bytes recebidos e informa total desconhecido. Durante instalação sem transferência, informa que está executando/instalando. A barra geral chega a 100% apenas após conclusão.
CONSULTAR TAMANHO DOS MODELOS faz uma consulta dry-run de metadados/cache, sem baixar os modelos; requer o ambiente isolado já instalado. Mostra tamanho de cada repositório e total, quanto está no cache e quanto falta baixar. A seleção de voz e a opção Whisper determinam os repositórios consultados. Pacotes Python/OmniVoice/PyTorch têm estimativas de planejamento: CPU 1–3 GB, NVIDIA 4–7 GB, além dos modelos. Cache, versões e arquivos temporários podem alterar os valores; não são tamanhos exatos de rede nem consumo final de disco. Modelos dos tradutores e transcrição opcionais são downloads separados na primeira utilização.
40 testes automatizados passaram, incluindo reconhecimento de GPU, fallback CPU, progresso dividido em blocos de subprocesso, tamanhos desconhecidos, consulta sem download e preservação do cache. Detecção real do hardware validada. A validação visual em Tk não foi possível neste ambiente (init.tcl indisponível); a interface foi exercitada com widgets simulados. Não foi feito download de grandes modelos ou reinstalação das dependências durante esta atualização. Código-fonte, sem EXE recompilado.
Fontes oficiais: https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibility.html ; https://huggingface.co/docs/huggingface_hub/guides/download ; https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program


## v50 — transcrição/tradução, preparação reutilizável e downloads visíveis
Na Clonagem + Dublagem, a ativação da transcrição/tradução e sua configuração ficam empilhadas acima de INICIAR DUBLAGEM. Novas barras Transcrevendo e Traduzindo recebem eventos do subprocesso. Faster-whisper informa avanço dos segmentos sobre a duração; OpenAI Whisper informa frames processados; tradução Ollama informa trechos concluídos. Argos e traduções curtas podem passar de início a conclusão sem percentuais intermediários. Clonagem/referência e dublagem/síntese permanecem independentes; não se atribui avanço de clonagem antes da geração.
Na janela de configuração há um painel de processos com scroll. O modelo do mecanismo não selecionado fica desabilitado e identificado como INATIVO; o selecionado fica EM USO. Durante preparação a seleção fica bloqueada para corresponder ao serviço em execução.
PREPARAR DEPENDÊNCIAS primeiro valida o ambiente de tradução existente. Quando compatível, não reinstala Python/PyTorch e verifica/prepara somente os recursos selecionados. Faster-whisper reutiliza os arquivos locais do modelo; OpenAI Whisper verifica o checksum do arquivo; Ollama consulta os modelos instalados; Argos verifica o par de idiomas e instala apenas pacotes ausentes. Modelos ausentes agora podem ser baixados nessa preparação, com confirmação prévia e logs/progresso, em vez de esperar necessariamente a primeira dublagem. Os logs distinguem mecanismo instalado, modelo disponível, tradutor e idioma. Com Argos/origem automática, o par só pode ser verificado após detectar o idioma do áudio; isso é informado explicitamente. Ollama usa modelo multilíngue, sem pacote separado por idioma.
Na Verificação inicial, o progresso aceita pip raw e barras convencionais; informa pacotes já instalados e arquivos de cache. Reutilização aparece como disponível sem novo download. O último resultado da transferência/cache permanece visível quando a instalação termina ou passa a uma etapa sem download. Cache não é apresentado como bytes recebidos da rede. Também há progresso para o instalador Python e callbacks de modelos; etapas sem bytes informados mostram atividade textual sem inventar porcentagens.
Validação: 44 testes automatizados e oito scripts de regressão passaram. Incluem mudança de mecanismo com controles desativados, ambiente existente sem pip/venv, modelos em cache sem baixar novamente, eventos de transcrição/tradução, formatos de progresso e recursos anteriores de revisão/personalizada/conversão. Serviços e widgets foram simulados; interface real e uma nova síntese completa não foram validadas neste ambiente. Código-fonte, sem EXE recompilado.


## v50 — transcrição/tradução, preparação reutilizável e downloads visíveis
Na Clonagem + Dublagem, a ativação da transcrição/tradução e sua configuração ficam empilhadas acima de INICIAR DUBLAGEM. Novas barras Transcrevendo e Traduzindo recebem eventos do subprocesso. Faster-whisper informa avanço dos segmentos sobre a duração; OpenAI Whisper informa frames processados; tradução Ollama informa trechos concluídos. Argos e traduções curtas podem passar de início a conclusão sem percentuais intermediários. Clonagem/referência e dublagem/síntese permanecem independentes; não se atribui avanço de clonagem antes da geração.
Na janela de configuração há um painel de processos com scroll. O modelo do mecanismo não selecionado fica desabilitado e identificado como INATIVO; o selecionado fica EM USO. Durante preparação a seleção fica bloqueada para corresponder ao serviço em execução.
PREPARAR DEPENDÊNCIAS primeiro valida o ambiente de tradução existente. Quando compatível, não reinstala Python/PyTorch e verifica/prepara somente os recursos selecionados. Faster-whisper reutiliza os arquivos locais do modelo; OpenAI Whisper verifica o checksum do arquivo; Ollama consulta os modelos instalados; Argos verifica o par de idiomas e instala apenas pacotes ausentes. Modelos ausentes agora podem ser baixados nessa preparação, com confirmação prévia e logs/progresso, em vez de esperar necessariamente a primeira dublagem. Os logs distinguem mecanismo instalado, modelo disponível, tradutor e idioma. Com Argos/origem automática, o par só pode ser verificado após detectar o idioma do áudio; isso é informado explicitamente. Ollama usa modelo multilíngue, sem pacote separado por idioma.
Na Verificação inicial, o progresso aceita pip raw e barras convencionais; informa pacotes já instalados e arquivos de cache. Reutilização aparece como disponível sem novo download. O último resultado da transferência/cache permanece visível quando a instalação termina ou passa a uma etapa sem download. Cache não é apresentado como bytes recebidos da rede. Também há progresso para o instalador Python e callbacks de modelos; etapas sem bytes informados mostram atividade textual sem inventar porcentagens.
Validação: 44 testes automatizados e oito scripts de regressão passaram. Incluem mudança de mecanismo com controles desativados, ambiente existente sem pip/venv, modelos em cache sem baixar novamente, eventos de transcrição/tradução, formatos de progresso e recursos anteriores de revisão/personalizada/conversão. Serviços e widgets foram simulados; interface real e uma nova síntese completa não foram validadas neste ambiente. Código-fonte, sem EXE recompilado.


## v50 — transcrição/tradução, preparação reutilizável e downloads visíveis
Na Clonagem + Dublagem, a ativação da transcrição/tradução e sua configuração ficam empilhadas acima de INICIAR DUBLAGEM. Novas barras Transcrevendo e Traduzindo recebem eventos do subprocesso. Faster-whisper informa avanço dos segmentos sobre a duração; OpenAI Whisper informa frames processados; tradução Ollama informa trechos concluídos. Argos e traduções curtas podem passar de início a conclusão sem percentuais intermediários. Clonagem/referência e dublagem/síntese permanecem independentes; não se atribui avanço de clonagem antes da geração.
Na janela de configuração há um painel de processos com scroll. O modelo do mecanismo não selecionado fica desabilitado e identificado como INATIVO; o selecionado fica EM USO. Durante preparação a seleção fica bloqueada para corresponder ao serviço em execução.
PREPARAR DEPENDÊNCIAS primeiro valida o ambiente de tradução existente. Quando compatível, não reinstala Python/PyTorch e verifica/prepara somente os recursos selecionados. Faster-whisper reutiliza os arquivos locais do modelo; OpenAI Whisper verifica o checksum do arquivo; Ollama consulta os modelos instalados; Argos verifica o par de idiomas e instala apenas pacotes ausentes. Modelos ausentes agora podem ser baixados nessa preparação, com confirmação prévia e logs/progresso, em vez de esperar necessariamente a primeira dublagem. Os logs distinguem mecanismo instalado, modelo disponível, tradutor e idioma. Com Argos/origem automática, o par só pode ser verificado após detectar o idioma do áudio; isso é informado explicitamente. Ollama usa modelo multilíngue, sem pacote separado por idioma.
Na Verificação inicial, o progresso aceita pip raw e barras convencionais; informa pacotes já instalados e arquivos de cache. Reutilização aparece como disponível sem novo download. O último resultado da transferência/cache permanece visível quando a instalação termina ou passa a uma etapa sem download. Cache não é apresentado como bytes recebidos da rede. Também há progresso para o instalador Python e callbacks de modelos; etapas sem bytes informados mostram atividade textual sem inventar porcentagens.
Validação: 44 testes automatizados e oito scripts de regressão passaram. Incluem mudança de mecanismo com controles desativados, ambiente existente sem pip/venv, modelos em cache sem baixar novamente, eventos de transcrição/tradução, formatos de progresso e recursos anteriores de revisão/personalizada/conversão. Serviços e widgets foram simulados; interface real e uma nova síntese completa não foram validadas neste ambiente. Código-fonte, sem EXE recompilado.


## v53 — textos por mecanismo e seleção de originais
Transcrições são exportadas em TXT TEXTO ORIGINAL, com versões em subpastas por mecanismo/modelo/idioma de origem. Traduções ficam também em OUTRAS TRADUÇÕES, separadas por mecanismo, modelo, tradutor e idioma de saída. Arquivos existentes são preservados; resultados diferentes ficam em uma nova pasta com identificador de tempo. O TXT português principal continua sendo preenchido apenas quando ausente/vazio, sem sobrescrever a edição do usuário.
Na Revisão, os botões abaixo de TEXTO ORIGINAL selecionam a pasta para leitura e edição; SALVAR grava na pasta selecionada. O aviso de TXT ausente agora explica a transcrição/tradução opcional e não cria arquivos vazios. INICIAR DUBLAGEM ganhou letras maiores e mais altura/largura, mantendo os controles de configuração visíveis.
Validação: 46 testes automatizados e oito scripts de regressão. Não foi validada uma nova síntese completa nem a interface gráfica real nesta entrega. Pacote de código-fonte; não inclui EXE recompilado.


## v54 — atualizar Revisão durante a dublagem
ATUALIZAR TELA funciona durante os serviços: atualiza o índice da Revisão em segundo plano sem destruir abas, filas ou controladores ativos. A lista-base é renovada para incluir novas cenas e mantém a fonte Dublados/Dublados personalizados selecionada. A cena aberta e seus textos em edição não são recarregados. Novas pastas de textos e traduções também aparecem. Cliques repetidos durante a mesma varredura não criam trabalhos duplicados, e resultados de um projeto anterior são descartados.
Validação: 48 testes automatizados passaram, incluindo atualização concorrente normal/personalizada, prevenção de reconstrução durante serviço e preservação do editor. Serviços e interface foram simulados; não foi executada uma dublagem completa nesta validação. Entrega de código-fonte, sem EXE recompilado.


## v55 — rolagem das pastas e opções de redublagem
Revisão: OUTRAS TRADUÇÕES e TEXTO ORIGINAL possuem uma linha de pastas com barra horizontal fina. Usar no redublar fica no cabeçalho acima das pastas. Ouvir cena: pastas de traduções em uma única linha com rolagem horizontal; controles principal/usar no redublar permanecem fora da região rolável. Opções Audacity, pronúncia do R, personagem e transcrição/tradução alinhadas em duas linhas e duas colunas.
Validação: oito scripts de regressão passaram; sintaxe e integridade do ZIP verificadas. Interface real não validada nesta entrega. Código-fonte, sem EXE recompilado.


## v56 — barras compactas, controle de parada e tema da rolagem
Barras de clonagem e dublagem menores para acomodar PARAR APÓS CENA e CANCELAR empilhados na Revisão e Ouvir cena. Com redublagem individual ativa, parar após cena deixa a cena terminar; cancelar interrompe o subprocesso e preserva o áudio anterior. Fora da redublagem individual, os comandos controlam o lote da fonte selecionada (normal/personalizada), apenas se estiver ativo. Personalizada aceita parada após finalizar a cena atual.
O componente horizontal de pastas aplica o tema ao canvas, fundo e scrollbar, inclusive ao trocar temas e no player vinho. Validação: 51 testes e oito scripts de regressão; inclui cancelamento de um subprocesso de teste. Interface real e síntese completa não validadas. Código-fonte, sem EXE recompilado.


## v57 — alinhamento opcional ao original
Abaixo de INICIAR DUBLAGEM: ALINHAR RITMO E DURAÇÃO AO ORIGINAL e CONFIGURAR ALINHAMENTO. Desativado por padrão. Ajusta duração com FFmpeg atempo (preservação de tom); limite padrão de mudança de velocidade de 25%, configurável de 5 a 100%. Exceder o limite marca falha sem substituir a saída anterior. Aproximação experimental de pausas/intensidade reutiliza o mecanismo da Personalizada; não é alinhamento de palavras/fonemas nem sincronização labial. Pode atenuar sílabas; vem desativada. FFmpeg necessário; modo experimental requer NumPy/pydub. Configurações são salvas e copiadas ao iniciar o lote; alterações durante processamento valem para o próximo lote.
54 testes automatizados e oito scripts de regressão passaram, incluindo limite, cancelamento e publicação somente após validação da duração. Serviços simulados; qualidade auditiva, interface real e nova síntese completa não validadas. Código-fonte, sem EXE recompilado.


## v58 — cenas concluídas aparecem automaticamente na Revisão
Cada OK em Clonagem + Dublagem e Dublagem personalizada registra a cena na Revisão pela fila da interface, após publicação do WAV final. Atualização incremental: nenhuma varredura de pastas, apenas inserção da nova linha em ordem, sem reconstruir a lista de 5000 itens. Mantém fonte selecionada, cena atual, edição e posição da lista. Duplicatas não são inseridas. Cenas concluídas durante atualização manual são reaplicadas ao resultado da varredura. O fim do lote personalizado não muda mais a fonte da Revisão.
56 testes passaram, incluindo inserção única entre 5000 cenas, deduplicação e manutenção de seleção/fonte. Interface e síntese simuladas; não foi executado um lote real de 5000 áudios. Código-fonte, sem EXE recompilado.


## v59 — alinhamento e transcrição quando faltar texto em Ouvir cena
Novas opções desativadas por padrão: Alinhar ritmo e duração ao original e Transcrever e traduzir quando faltar TXT. Organizadas em uma terceira linha de duas colunas, junto às opções existentes. A transcrição condicional respeita o texto exibido/alternativo; não substitui texto existente. O pedido explícito de nova transcrição permanece independente. Alinhamento usa as configurações de Clonagem + Dublagem; sem provedor usa ajuste de duração com limite de 25%. Na Personalizada evita aplicar duas vezes o ajuste de expressão quando o alinhamento opcional foi solicitado.
57 testes automatizados e oito scripts de regressão passaram. Interface real e nova síntese completa não validadas. Código-fonte, sem EXE recompilado.


## v60 — duas linhas de opções e integração do player
Seis opções de Ouvir cena em duas linhas e três colunas. Configurar transcrição/tradução e Configurar alinhamento agora ocupam a mesma coluna com largura preenchida. Player do Batch usa o mesmo controlador de traduções, contexto de partes e controles da Revisão, além das ações/textos/preferências já compartilhados. O componente de janela é o mesmo AudioPlayerManager; cada aba mantém sua instância de reprodução.
Oito scripts de regressão passaram. Interface real não validada; código-fonte sem EXE recompilado.


## v61
Opções de transcrição automática e alinhamento de ritmo alinhadas pela margem esquerda. Apenas ajuste de layout; sintaxe e integridade do ZIP verificadas.


## v62 — edição, textos da cena e controles personalizados
Cortar silêncio e duração ficam após Volume + na linha DUBLADO; DIVIDIR recebe verde-limão. Desfazer/refazer/salvar/colar/copiar/delete/recortar/editar permanecem acima, seguindo a referência enviada.
Dublagem personalizada: ativação/configuração de alinhamento e de transcrição/tradução. Transcrição ativada permite listar cenas sem TXT e gera o texto antes da síntese; configurações são copiadas ao iniciar o lote. O alinhamento opcional usa as configurações próprias; desativado mantém o comportamento anterior de expressão da Personalizada.
Pastas de texto original e traduções são filtradas pelo caminho completo do TXT da cena. Pastas de capítulos/personagens não são apresentadas como versões. Redublagem com nova transcrição notifica a interface quando os textos estão prontos, mesmo antes da síntese. Mostrar texto original fica abaixo do botão de tradução principal: consulta no mesmo quadro, sem sobrescrever TXT português nem usar inglês inadvertidamente para redublar.
59 testes e oito scripts de regressão passaram. Interface real e síntese completa não validadas nesta entrega. Código-fonte, sem EXE recompilado.


## v63 — voz russa, preparação de tradução e idiomas da interface
A opção k2-fsa/OmniVoice agora aparece como OmniVoice oficial — russo e 600+ idiomas. É o modelo multilíngue oficial, com suporte a russo declarado pelos autores; não é um fine-tune russo nem uma alegação de melhor qualidade. Instalação usa a mesma rotina oficial em REQUISITOS; a interface russa inicia o assistente com o modelo oficial selecionado. Não há download duplicado quando o cache já está presente.
Novo seletor Idioma da voz no Batch, persistido por projeto. Escolher saída russa na configuração de transcrição também atualiza esse seletor. Vozes não portuguesas usam k2-fsa/OmniVoice em lugar do modelo BR-PT; sotaque português e transformação de pronúncia do R não são aplicados ao russo. Revisão, Personalizada e dublagem por partes recebem a configuração de idioma correspondente. TXT existente é considerado texto já no idioma de saída; transcrição automática continua sendo usada somente quando falta texto. O idioma visual da interface não traduz os textos do projeto.
Argos com origem automática prepara a etapa inglês → idioma de saída (inclusive russo) e verifica o resultado, reutilizando pacote instalado. Após detecção da origem pode ser necessário baixar a outra etapa. Origem explícita mantém seleção direta ou via inglês. TranslateGemma/Qwen usam modelos multilíngues, sem pacote russo separado. A escolha de idioma aceita os rótulos localizados e mantém códigos internos estáveis; comandos e prompts usam o idioma efetivamente escolhido. A seleção do modelo funciona também com nomes traduzidos.
Catálogo inglês/russo/espanhol ampliado para abas, controles personalizados, áudio/vídeo, partes, alinhamento, transcrição/tradução e requisitos. Mensagens técnicas dos programas externos permanecem no idioma fornecido por eles. Caminhos e nomes de arquivos do projeto continuam inalterados.
Fontes verificadas em 20/09/2026:
- https://huggingface.co/k2-fsa/OmniVoice
- https://github.com/k2-fsa/OmniVoice/blob/master/docs/languages.md
- https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json
- https://ollama.com/library/translategemma
Validação: 64 testes automatizados e oito scripts de regressão passaram. Incluem seleção localizada, russo no comando de síntese, preservação do português, instalação Argos simulada e reutilização sem novo download. Sem download de modelos pesados nesta validação; instalação completa em PC limpo, interface real e qualidade auditiva russa ainda não verificadas. Não se garante ausência de erros de rede/driver ou incompatibilidades externas. Código-fonte, sem EXE recompilado.


## v64 — F5-TTS Russian adicional
Novo modelo hotstone228/F5-TTS-Russian em Ferramenta / modelo e REQUISITOS. Ao selecionar no Batch, o idioma muda para Russo e o modo para Voice Cloning. Use texto russo ou configure a tradução para Russo. O modelo também suporta inglês; não usar para português ou Voice Design.
Preparação: selecione hotstone228/F5-TTS-Russian em REQUISITOS, execute 1. INSTALAR / REPARAR, 2. BAIXAR MODELOS e 3. TESTAR MODELO. Dependências F5-TTS ficam em outro ambiente, com f5-active.json separado do OmniVoice. Downloads mostram tamanhos e progresso e reutilizam o cache. Baixa somente model_last.safetensors, vocab.txt, metadados, Vocos e Whisper; não baixa o checkpoint .pt duplicado nem os gráficos de treinamento. Whisper é obrigatório neste adaptador para transcrever a voz de referência real. Síntese offline após a preparação; arquivos ausentes geram orientação para os REQUISITOS.
CPU AMD/Intel e CUDA NVIDIA são opções do instalador Windows. GPU AMD não foi adicionada. A transcrição da referência usa CPU e libera o modelo antes de carregar a síntese; os trechos de texto são gerados em sequência para reduzir a pressão na memória da GPU. O F5-TTS usa a arquitetura F5TTS_Base e o vocabulário do próprio modelo russo, sem enviar esses pesos para o OmniVoice.
A Revisão, Ouvir cena e Partes do TXT usam o gerador selecionado no Batch. A Dublagem personalizada usa esse mesmo gerador e mantém o áudio modelo escolhido; configure nela a saída Russo (ou Inglês) em CONFIGURAR TRANSCRIÇÃO / TRADUÇÃO. As saídas, revisões, backups e alinhamento existentes continuam nos respectivos fluxos.
Licença dos pesos hotstone228/F5-TTS-Russian: CC-BY-NC-SA-4.0 (uso não comercial, atribuição e compartilhamento pela mesma licença). Não significa uma declaração de que este é o melhor modelo ou de equivalência auditiva ao BR-PT. Fontes:
- https://huggingface.co/hotstone228/F5-TTS-Russian
- https://huggingface.co/hotstone228/F5-TTS-Russian/blob/main/setting.json
- https://github.com/SWivid/F5-TTS
- https://pypi.org/project/f5-tts/1.1.22/
Validação: 75 testes automatizados e oito scripts de regressão passaram. Resolução real de dependências via pip --dry-run no Python 3.13 Windows x64 passou (relatório de desenvolvimento). API conferida no wheel oficial 1.1.22. Testes de execução do adaptador usam modelos simulados: instalação completa, carregamento dos pesos, interface real e qualidade da síntese ainda não foram validados. Nenhum modelo pesado foi baixado nesta atualização. Código-fonte, sem EXE recompilado; scripts de build incluem o novo módulo.


## v65 — correção do download F5-TTS com Hub 0.36.2
Corrige TypeError: hf_hub_download() got an unexpected keyword argument 'tqdm_class'. O adaptador v64 usava um argumento indisponível no Hub fixado para F5-TTS. Agora usa a assinatura compatível e intercepta a fábrica de progresso em bytes do Hub somente dentro do subprocesso de download, mantendo cache, retomada, tamanhos e progresso para HTTP/Xet. Não altera os pacotes instalados nem o ambiente OmniVoice.
Não é necessário reinstalar Python ou F5-TTS. Na versão corrigida, abra REQUISITOS, selecione hotstone228/F5-TTS-Russian, execute 2. BAIXAR MODELOS e depois 3. TESTAR MODELO. A mensagem de modelos incompletos era consequência do download interrompido. Segundo o relatório fornecido, PyTorch/CUDA/RTX 5060 estão disponíveis e faltavam aproximadamente 1,40 GB; Whisper já estava no cache.
Validação: 75 testes automatizados passaram. O teste do download agora usa uma assinatura estrita, que rejeita argumentos inválidos. Validação adicional executada no Python F5 instalado com huggingface_hub 0.36.2: download real de README.md e vocab.txt em cache isolado de desenvolvimento, segunda execução reaproveitando cache, e teste da fábrica real de progresso com início, retomada e conclusão em bytes. Pesos grandes e síntese não foram testados nesta correção. Código-fonte, sem EXE recompilado.


## v66 — F5-TTS: DLL de TorchCodec e seleção de idioma
Corrige a falha torch_get_const_data_ptr / libtorchcodec_image.dll na transcrição da referência. Transformers 4.57 tenta importar TorchCodec mesmo recebendo um WAV; o TorchCodec mais recente instalado não corresponde ao PyTorch 2.8. O adaptador F5 agora seleciona, somente em seu subprocesso, o caminho FFmpeg/NumPy já disponível, sem carregar TorchCodec. Funciona com o ambiente F5 já instalado: não é necessário reinstalar para esta correção. Novas instalações fixam torchcodec==0.7.0, correspondente a PyTorch 2.8 na tabela oficial https://github.com/meta-pytorch/torchcodec#compatibility-with-torch-versions . A leitura de áudio deste adaptador continua independente de TorchCodec e de FFmpeg shared.
Complemento da voz agora é editável também em clonagem, com opção Russo. Russo / Russian / Russian accent são interpretados como seleção do idioma russo, não enviados como instrução de sotaque inglês ao OmniVoice. A escolha sincroniza o idioma da tradução; quando BR-PT estava selecionado, mostra o OmniVoice multilíngue efetivamente utilizado. Ao selecionar BR-PT novamente, restaura Português (Brasil) no idioma de voz e na configuração de tradução. Selecionar idioma de voz também sincroniza a tradução e o modelo multilíngue quando necessário. Textos existentes não são traduzidos automaticamente por trocar o modelo: devem estar no idioma desejado ou usar o pedido de transcrever/traduzir.
Erros da Revisão agora identificam F5-TTS Russian quando esse é o gerador, em lugar de rotular tudo como OmniVoice.
Validação: 78 testes automatizados e oito scripts de regressão passaram. TESTE REAL no ambiente F5 já instalado: referência CH01_PT_Sally_56.wav transcrita por Whisper em CPU; modelo hotstone228/F5-TTS-Russian e Vocos carregados em CUDA; geração concluída para Привет! Как дела? e WAV gravado separadamente no workspace de desenvolvimento, sem alterar áudios do projeto. Estrutura WAV validada; qualidade auditiva/pronúncia não foi avaliada. Modelos reaproveitados do cache, sem reinstalação. Pacote de código-fonte, sem EXE recompilado.
