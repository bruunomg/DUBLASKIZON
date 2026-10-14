# Dublaskizon — compilação do executável

O aplicativo unificado possui sete áreas superiores, nesta ordem: **CLONAGEM + DUBLAGEM**, **REVISÃO**, **CONVERTER DURAÇÃO**, **CONVERTER FORMATOS**, **FILTRO RENOMEAR .WEM**, **REDIMENSIONAR ÁUDIO PARA CLONAR** e **COMANDOS** por último.
 A compilação do arquivo `.exe` precisa ser feita no Windows, pois o PyInstaller gera executáveis para o sistema operacional em que é executado.

## 1. O que precisa estar instalado no Windows

Use o mesmo Python em que o OmniVoice funciona. No PowerShell, confirme:

```powershell
python --version
python -m pip show omnivoice
python -m omnivoice.cli.infer --help
```

Se o OmniVoice ainda não estiver instalado nesse Python, instale-o antes de usar o executável:

```powershell
python -m pip install omnivoice
```

O modelo `edwixx/omnivoice-brpt-v15` não é colocado dentro do EXE. Ele continua no cache do Hugging Face e pode ser baixado na primeira execução, caso ainda não esteja disponível.

## 2. Gerar `Dublaskizon.exe`

Mantenha estes arquivos juntos dentro da pasta `unified_build`:

```text
Dublaskizon.py
batch_tab.py
review_tab.py
duration_converter_tab.py
format_converter_tab.py
wem_filter_tab.py
voice_clone_tab.py
audio_clone_preprocessor.py
main.py
audio_player.py
i18n.py
requirements_voice_clone.txt
INSTALAR_DEPENDENCIAS_CLONAGEM.bat
Dublaskizon_TUTORIAL.pdf
Dublaskizon.ico
build_exe.bat
build_exe_portatil_sem_python.bat
```

Dê duplo clique em `build_exe.bat` para usar o build tradicional. O script instalará o PyInstaller e criará:

```text
unified_build/dist/Dublaskizon.exe
```

### Build portátil sem Python no computador de destino

O arquivo `build_exe_portatil_sem_python.bat` é uma segunda opção e não altera o `build_exe.bat` original. Ele também precisa de Python somente no computador que fará a compilação, pois o PyInstaller é executado durante o build. O resultado, `dist/Dublaskizon_Portatil.exe`, incorpora o interpretador Python e as bibliotecas do aplicativo; portanto, o Windows de destino pode executar o EXE sem Python instalado. FFmpeg, FFprobe, FFplay e SoX permanecem fora do EXE para não aumentar desnecessariamente o pacote e continuam sendo obtidos pelo botão **BAIXAR / PREPARAR FERRAMENTAS**.

## 3. Instalar o aplicativo em um projeto

Copie apenas `Dublaskizon.exe` para a pasta raiz de cada projeto. O EXE deve ficar no mesmo nível das pastas abaixo:

```text
PROJETO_DUBLAGEM/
├── Dublaskizon.exe
├── WAV ORIGINAIS/
├── TXT TEXTO PORTUGUES/
├── TXT TEXTO ORIGINAL/
├── TXT TEXTO do WAV TRANSCRITO e TRADUZIDO/
├── OUTRAS TRADUÇÕES/
├── dublado/
├── revisoes/
└── REDIMENSIONAR ÁUDIO PARA CLONAR/
```

Ao abrir o EXE ou selecionar uma pasta, o aplicativo não cria pastas automaticamente. Se a estrutura ainda não existir, use explicitamente **GERAR AS PASTAS DO PROJETO AQUI** para criá-la no local escolhido. A opção **SELECIONAR ESTA PASTA** apenas abre a pasta existente sem criar diretórios; **USAR PASTA DO EXE** continua criando a estrutura somente quando esse comando é acionado. O pareamento é feito pela **mesma pasta relativa e pelo mesmo nome-base**, não apenas pelo nome isolado: `WAV ORIGINAIS/CAP01/cena.wav` corresponde a `TXT TEXTO PORTUGUES/CAP01/cena.txt`, e resulta em `dublado/CAP01/cena.wav`. Assim, `CAP01/cena.wav` e `CAP02/cena.wav` não colidem.

## 4. Uso

Abra `Dublaskizon.exe`. No topo, o seletor **IDIOMA** permite escolher **Português**, **English**, **Русский** ou **Español**. A troca localiza abas, botões, textos fixos, comboboxes, janelas, caixas de diálogo e dicas; os caminhos, nomes de arquivos, modelos e conteúdo dos TXT permanecem intactos. **Português** é o idioma original e pode ser escolhido novamente a qualquer momento. O botão **ATUALIZAR TELA** reconstrói as abas sem fechar o programa e tenta manter a aba ativa; use-o quando quiser recarregar listas e controles. Na aba **CLONAGEM + DUBLAGEM**, escolha o modelo e o modo, confira a fila e clique em **INICIAR DUBLAGEM**. O modo **Voice Cloning** usa o WAV original de cada cena como referência. O botão **REDUBLAR ÁUDIO SELECIONADO** força a geração somente da cena escolhida; se já existir um dublado, o arquivo anterior também é arquivado em `revisoes/<subpasta>/<cena>_vNN.wav` somente depois que o novo áudio for gerado com sucesso. O campo **Ferramenta / modelo** mantém os modelos recomendados e também descobre automaticamente repositórios `models--...` existentes nos caches do Hugging Face. Use **ATUALIZAR** depois de instalar ou baixar outro modelo. O seletor **Pronúncia do R** oferece **SEM ALTERAÇÃO**, **R SUAVE**, **R NORMAL** e **R FORTE**. Em **R SUAVE**, a ferramenta reduz apenas `rr` entre vogais quando possível; em **R FORTE**, transforma `r` simples entre vogais em `rr`; **R NORMAL** preserva o texto. O app não envia frases livres no parâmetro `--instruct`, porque o OmniVoice valida esse parâmetro contra uma lista fechada e rejeitaria orientações como “R suave”. Como a referência de voz e o próprio modelo também influenciam o sotaque, confira o resultado em **OUVIR CENA** antes de processar a fila inteira. A aba **REVISÃO** é acessada pelo botão superior colorido, sem abrir uma segunda janela.

Na aba **REVISÃO**, selecione uma cena, edite e salve o texto em português quando necessário, abra o par no Audacity e use **Aprovar**, **Rejeitar** ou **Refazer cena**. A lista mostra a chave relativa, como `CAP01/cena`, para desambiguar capítulos com nomes repetidos. Textos originais, transcritos/traduzidos e revisões são salvos na mesma subpasta relativa; por exemplo, versões de `CAP01/cena` ficam em `revisoes/CAP01/cena_vNN.wav`. O painel **OUTRAS TRADUÇÕES** lê automaticamente a pasta principal do projeto e suas subpastas de idiomas. As subpastas aparecem como botões acima da janelinha; clique em um botão para ativar aquela pasta e carregar o TXT com a mesma hierarquia e o mesmo nome-base da cena. Marque **Usar na REFAZER CENA** para usar essa tradução alternativa na nova síntese. A opção **Refazer cena** executa a nova síntese dentro do aplicativo já aberto e salva o novo WAV em `dublado/<subpasta>/<cena>.wav`, substituindo o dublado atual somente depois de a geração terminar com sucesso. Quando já existe um dublado, a versão substituída é copiada para `revisoes/<subpasta>/<cena>_vNN.wav`; se a geração falhar ou for cancelada, o dublado anterior permanece intacto e nenhum backup incompleto é mantido. O histórico da cena continua registrando a operação em `revisoes`. A seção também possui **Abrir Audacity após redublar**, que abre automaticamente o par original + dublagem ao finalizar, e **Pedido de alterar pronúncia do R**. Quando este último está ativo, cada clique em **REDUBLAR** ou **REDUBLAR COM OUTRO ÁUDIO** pergunta se o R deve ser alterado e permite escolher **SEM ALTERAÇÃO**, **R SUAVE**, **R NORMAL** ou **R FORTE** somente para aquela execução; cancelar ou responder não mantém a pronúncia fixa escolhida na aba **CLONAGEM + DUBLAGEM**. A escolha pontual não altera a preferência fixa do Batch e é descartada ao cancelar a seleção de outro áudio. Durante a operação, as barras **CLONANDO REFERÊNCIA** e **DUBLANDO CENA** também são espelhadas no progresso da cena da aba **CLONAGEM + DUBLAGEM**. O painel **PROCESSOS E MENSAGENS** do Batch também recebe, em tempo real, o conteúdo de **HISTÓRICO DA CENA** e de **REFAZENDO A CENA**, com a cena e a seção identificadas em cada linha. O histórico inicial da cena selecionada é sincronizado ao abrir/reconstruir as abas; as novas linhas de referência, texto, pronúncia, fases, conclusão, erro e preservação em `revisoes` são adicionadas durante a redublagem.

As duas abas repetem os controles **SELECIONAR PROJETO**, **USAR PASTA DO EXE** e **TUTORIAL PDF**. Também possuem um atalho inferior **OUTRAS TRADUÇÕES**, que abre a pasta principal; suas subpastas podem ser ativadas pelos botões exibidos acima do texto alternativo. **SELECIONAR PROJETO** abre um diálogo próprio com os botões **GERAR AS PASTAS DO PROJETO AQUI** e **SELECIONAR ESTA PASTA**. O primeiro cria a estrutura completa no local indicado e o segundo confirma o caminho escolhido e abre o projeto nele sem criar diretórios. **USAR PASTA DO EXE** também garante a criação da estrutura completa no diretório do executável, mas somente quando clicado explicitamente.
 O botão **TUTORIAL PDF** abre o manual visual incorporado ao aplicativo.

A aba **CONVERTER DURAÇÃO** ajusta o tempo dos áudios dublados ao WAV original, sendo indicada para cutscenes com duração exata. Os dois painéis se chamam simplesmente **ÁUDIOS ORIGINAIS** e **ÁUDIOS DUBLADOS**. Use **ABRIR PASTA** ou **ADICIONAR ÁUDIOS**; com `tkinterdnd2` instalado também é possível arrastar arquivos ou pastas para as listas. Nos carregamentos do projeto, os pares são encontrados pela mesma **chave relativa de subpasta + nome-base**; arquivos marcados com `convertidos` são priorizados como dublados, enquanto os WAVs sem essa marcação são tratados como originais. Os resultados separados ou unificados preservam essa chave, incluindo as subpastas dentro de cada categoria. Os botões laranja carregam as pastas do projeto a partir da **REVISÃO** ou da **CLONAGEM + DUBLAGEM**.

A aba **CONVERTER FORMATOS** é independente da conversão de duração. Ela aceita vários formatos de áudio em uma única lista, permite escolher formatos WAV PCM, AIFF, FLAC, MP3 e OGG, converte usando FFmpeg sem alterar intencionalmente a duração, salva em **AUDIO FORMATOS CONVERTIDOS** por padrão e possui **ESCOLHER**, **ABRIR PASTA**, progresso, log e cancelamento. Também aceita arrastar arquivos ou uma pasta recursivamente e tem os mesmos controles de ouvir áudio. Ao carregar do projeto, os botões laranja **CARREGAR DA ABA REVISÃO** e **CARREGAR DA CLONAGEM + DUBLAGEM** usam os caminhos reais de `WAV ORIGINAIS` e `dublado`; a saída mantém a subpasta relativa e não cria a pasta `revisoes`.

A opção **Remover silêncio inicial/final** e o botão `?` ficam agrupados e separados do botão **CONVERTER AUDIOS** por aproximadamente 1 cm. Ao ativar a opção, os silêncios do início e do final são cortados antes do ajuste de duração. Atenção: essa ferramenta também pode remover uma pequena parte da fala no começo e no fim; confira os áudios após a conversão. O botão `?` exibe essa explicação ao passar o mouse.

Quando alguma ferramenta necessária não estiver instalada, o botão **BAIXAR / PREPARAR FERRAMENTAS** pisca por aproximadamente dois segundos. Na aba **CONVERTER DURAÇÃO**, o alerta aparece ao clicar em **CONVERTER AUDIOS**; na aba **CONVERTER FORMATOS**, aparece ao abrir a aba ou ao clicar em **CONVERTER FORMATOS**. O alerta para assim que o botão de preparação é clicado.

Escolha entre **Separar por duração** ou **Salvar tudo na mesma pasta**. Na opção separada, os resultados ficam em `AUDIO CONVERTIDO ..MAIOR.. DURAÇÃO`, `AUDIO CONVERTIDO ..MENOR.. DURAÇÃO` e `AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO`. Na opção única, todos ficam em `AUDIO CONVERTIDO`. A rama maior usa SoX quando disponível ou fallback FFmpeg, a menor recebe silêncio no final e a igual somente é convertida para o formato escolhido. Há formatos WAV PCM 16-bit a 48 kHz mono/estéreo, PCM 24/32-bit, AIFF, FLAC, MP3 e OGG; os formatos WAV PCM a 48 kHz são adequados para importação na Unreal Engine.

Use **BAIXAR / PREPARAR FERRAMENTAS** para localizar as instalações existentes ou baixar, no Windows, FFmpeg/FFprobe/FFplay e SoX para a pasta portátil `ferramentas_audio` ao lado do EXE. Durante cada download, uma barra mostra o percentual e a quantidade aproximada de megabytes; depois, o painel informa que os arquivos foram preparados. O botão não baixa novamente uma ferramenta já encontrada e mostra, por exemplo, `SoX já está disponível; download ignorado.` É necessário ter internet e permissão de gravação na pasta do aplicativo. Se o botão não puder baixar, o erro fica registrado no painel de processos; também é possível instalar as ferramentas manualmente e colocá-las no PATH. O botão **?**, ao lado de **BAIXAR / PREPARAR FERRAMENTAS** nas duas abas de conversão, explica: **FFmpeg** converte e processa áudio/vídeo; **FFprobe** consulta duração, frequência e canais; **FFplay** reproduz os áudios; e **SoX** executa operações de áudio, incluindo ajustes de tempo. A caixa de ajuda aparece acima do ponteiro do mouse, sempre que houver espaço; caso contrário, aparece abaixo.

A aba **COMANDOS** permite escolher ou digitar comandos de diagnóstico, como `python --version`, `python -m omnivoice.cli.infer --help`, `python -m pip show omnivoice` e `where omnivoice-infer`. Clique em **EXECUTAR** para acompanhar a saída no painel interno, sem abrir outra janela do terminal. Os atalhos globais **Ctrl+A** e **Ctrl+F** funcionam nas abas e janelas auxiliares: Ctrl+A seleciona todo o conteúdo do campo, texto, lista ou tabela em foco; Ctrl+F abre a busca e seleciona a primeira ocorrência encontrada no widget ativo.

As listas de áudio agora possuem um reprodutor simples: clique em **▶ OUVIR CENA** ou **▶ OUVIR**, dê duplo clique em uma cena/arquivo ou use **▶ OUVIR TODOS** para carregar os itens. A janela mostra o nome e o caminho real do arquivo carregado e exige o clique em **▶ INICIAR** para começar a reprodução; depois, use **PARAR**, **◀ ANTERIOR**, **PRÓXIMO ▶** ou **X FECHAR**. Ao navegar com **ANTERIOR** ou **PRÓXIMO**, a cena correspondente também fica selecionada na lista de **CENAS/PROCESSOS** ou **DUBLADOS**. Os botões anterior e próximo percorrem a mesma lista real usada para abrir a janela e carregam o próximo arquivo sem iniciar automaticamente. O reprodutor funciona nas cenas/processos de **CLONAGEM + DUBLAGEM**, na lista de cenas da **REVISÃO**, nos painéis **ÁUDIOS ORIGINAIS** e **ÁUDIOS DUBLADOS** da conversão de duração e na nova conversão de formatos. Nas listas **CENAS/PROCESSOS** e **DUBLADOS**, cada item exibe somente o nome do áudio, enquanto os caminhos reais permanecem internos para evitar ambiguidades. A divisória vertical entre a lista e o painel de conteúdo é arrastável: mova a borda para a direita para ampliar a lista. Clique com o botão direito sobre uma linha para abrir o menu contextual. Ele oferece **ABRIR LOCAL DO ÁUDIO DUBLADO**, **ABRIR LOCAL DO ÁUDIO ORIGINAL**, **COPIAR NOME DO ÁUDIO**, **COPIAR LOCAL DO ÁUDIO DUBLADO** e **COPIAR LOCAL DO ÁUDIO ORIGINAL**. As duas primeiras ações abrem uma única janela diretamente na pasta do arquivo real correspondente, respeitando a subpasta da cena; **COPIAR NOME DO ÁUDIO** copia somente o nome do arquivo; e as duas opções **COPIAR LOCAL** copiam somente o caminho da pasta, sem o nome do arquivo. O mesmo menu completo está disponível nas listas de **CLONAGEM + DUBLAGEM**, **REVISÃO**, **CONVERTER DURAÇÃO** e **CONVERTER FORMATOS**. Caminhos inválidos não são usados como fallback. O botão superior direito **OUVIR: FFPLAY** alterna entre o FFplay interno e **OUVIR: WINDOWS**, que usa o reprodutor padrão do sistema Windows. A preferência fica salva para as próximas sessões e é aplicada às abas Batch, Revisão, Conversor de Duração, Conversor de Formatos e Redimensionar para Clonar. Ao abrir uma cena individual, somente o caminho selecionado é validado e os vizinhos são resolvidos sob demanda durante ANTERIOR/PRÓXIMO; isso evita percorrer milhares de arquivos antes de mostrar a janela. Ele usa exatamente os caminhos dos arquivos carregados nas listas e valida novamente a existência do arquivo no clique em **INICIAR**. Procura `ffplay` no PATH e na pasta portátil `ferramentas_audio`, mantendo o terminal oculto. O botão **PARAR** encerra o processo FFplay. Quando a janela é aberta pela aba **REVISÃO** ou pela aba **CLONAGEM + DUBLAGEM**, ela também exibe **Abrir ORIGINAL + DUBLAGEM no Audacity**, **Aprovar**, **Rejeitar**, **REDUBLAR** e **REDUBLAR COM OUTRO ÁUDIO**. Os dois últimos usam o controle **Pedido de alterar pronúncia do R** da Revisão e perguntam o ajuste apenas para a execução atual; o controle **Abrir Audacity após redublar** também fica disponível dentro da janela. Esses comandos atuam sempre sobre a cena atualmente mostrada e sincronizada na lista da aba Revisão. A mesma janela também exibe, em botões cinza organizados em duas linhas para manter os textos completos visíveis, os comandos **ABRIR LOCAL DO ÁUDIO DUBLADO**, **ABRIR LOCAL DO ÁUDIO ORIGINAL**, **COPIAR NOME DO ÁUDIO**, **COPIAR LOCAL DO ÁUDIO DUBLADO** e **COPIAR LOCAL DO ÁUDIO ORIGINAL**, aplicados ao item atualmente navegado. Ao clicar em **Rejeitar**, a caixa **Rejeitar cena** é aberta na frente de **OUVIR CENA** e permanece modal somente em relação a essa janela; a janela principal não a cobre, e o foco retorna para OUVIR CENA depois que o motivo é confirmado ou cancelado. A reprodução desta aba usa exclusivamente FFplay; se ele não estiver disponível ou falhar, nenhum reprodutor externo será aberto. Nesse caso, clique em **BAIXAR / PREPARAR FERRAMENTAS**.

Os títulos das abas aparecem como botões contrastantes: azul para **CLONAGEM + DUBLAGEM**, lilás para **REVISÃO**, laranja para **CONVERTER DURAÇÃO**, verde-água para **CONVERTER FORMATOS** e âmbar para **COMANDOS**, que fica por último. Mensagens como pares não encontrados, nenhuma cena selecionada, contadores de originais/dublados/pares, lista vazia, pasta de saída e conversão aguardando acompanham o idioma escolhido.
 O botão **ALTERNAR APARÊNCIA** muda imediatamente todas as abas e a área de comandos entre tema claro e escuro; a preferência é salva. A aba **CLONAR + DUBLAR** também atualiza os rótulos, listas, campos de texto e mensagens que receberam cores claras no tema escuro, evitando que letras brancas permaneçam sobre fundo claro ao retornar. A aba **COMANDOS** faz a mesma correção para rótulos que poderiam permanecer escuros no tema escuro.

O botão superior **? AJUDA** ativa ou desativa a ajuda contextual global. Quando ativo, os principais botões, campos, listas e áreas recebem pequenos marcadores **?**; passe o mouse sobre cada marcador para abrir uma explicação sem bloquear a interface. O painel central da ajuda possui **ABRIR PASSO A PASSO DA ABA ATUAL**, que abre uma janela auxiliar não modal com instruções numeradas da aba selecionada. Ao trocar de aba, essa janela acompanha a nova aba. **DESATIVAR AJUDA** remove os marcadores, fecha tooltips e retorna o botão superior a **? AJUDA**. O recurso acompanha idioma, tema, escala e reconstrução da interface, sem alterar IDs, nomes de arquivos ou dados do usuário.
 No canto direito da mesma faixa está o controle **ESCALA DA TELA**, compartilhado por toda a interface, com os botões **−** e **+**. Cada clique reduz ou amplia a interface em 5%, de **25% a 200%**, imediatamente e sem fechar o programa; o botão percentual retorna a 100%. Em níveis baixos, o layout compacta principalmente espaços para preservar a fonte legível; em níveis altos, fontes e janela crescem progressivamente. O valor é salvo automaticamente em `Dublaskizon_interface.json` e restaurado na próxima abertura. O caminho exibido ao lado de **Projeto:** pode ser selecionado e copiado. Durante a clonagem, o processo do OmniVoice é executado em segundo plano, sem abrir uma janela do CMD na frente da tela; as mensagens continuam disponíveis no painel de processos. Cada área possui rolagem apenas quando o conteúdo não cabe.

Na seção de ações da revisão, **Abrir ORIGINAL + DUBLAGEM no Audacity** aparece em amarelo, **Aprovar** em azul, **Rejeitar** em vermelho e **REFAZER CENA** em verde. Os quatro painéis de texto ficam organizados em duas linhas niveladas por uma única divisória vertical central: na linha superior ficam **Texto em português — editável** e **OUTRAS TRADUÇÕES**; na linha inferior ficam **TEXTO ORIGINAL — editável** e **TEXTO do WAV TRANSCRITO e TRADUZIDO — editável**. No painel de outras traduções, a opção de regeneração e o arquivo carregado ficam no topo, antes da caixa de texto. Cada painel começa travado quando aplicável; use **DESTRAVAR** para editar, **SALVAR** para gravar e **TRAVAR** para bloquear novamente. Os painéis possuem rolagem própria e permitem selecionar/copiar o texto.

O **Histórico da cena** também é dividido por uma divisória vertical arrastável. À esquerda ficam o histórico e as versões preservadas; à direita ficam as barras **CLONANDO REFERÊNCIA** e **DUBLANDO CENA**, além do painel de processamento. Na mesma faixa inferior dos botões das pastas aparecem os relógios de **Refazer decorrido** e **Restante**. A rolagem geral só aparece quando o conteúdo não cabe na janela.

> O EXE é portátil em relação à pasta do projeto, mas o Python/OmniVoice, o cache do modelo e o Audacity continuam sendo dependências instaladas no computador.

## 5. Idiomas e atualização da tela

A localização é feita por uma tabela interna em `i18n.py`; não depende de internet nem de serviços de tradução. Os quatro idiomas são selecionados no topo e a preferência fica salva em `Dublaskizon_interface.json`, junto com aparência e escala. Ao trocar de idioma, os controles já existentes são redesenhados em tempo real, e as novas janelas usam o idioma atual. O botão **ATUALIZAR TELA** pode ser usado para reconstruir o conteúdo das abas; ele não deve ser acionado enquanto uma dublagem ou conversão estiver em andamento.

## 6. Se o OmniVoice não for localizado pelo EXE

O aplicativo tenta localizar `omnivoice-infer.exe` no PATH e nos diretórios usuais do Python para Windows. Se a instalação usar um caminho incomum, defina a variável de ambiente `OMNIVOICE_INFER` apontando para o executável do OmniVoice antes de abrir o EXE, ou reinstale o pacote com:

```powershell
python -m pip install --upgrade omnivoice
```

A compilação não inclui modelos, WAVs, TXTs, projetos nem Audacity. FFmpeg, FFprobe, FFplay e SoX podem ser instalados pelo botão da aba conversora, permanecendo em `ferramentas_audio` fora do EXE; o suporte de arrastar-e-soltar é instalado pelo `build_exe.bat` com `tkinterdnd2`.
 O tutorial PDF é incorporado ao EXE pelo parâmetro `--add-data` e o `Dublaskizon.ico` é usado como ícone pelo parâmetro `--icon`. Depois de receber uma atualização dos arquivos `.py`, do `i18n.py`, do PDF, do `.ico` ou do `.bat`, é necessário executar `build_exe.bat` novamente e substituir o EXE antigo pelo novo `dist\\Dublaskizon.exe`.


## REDIMENSIONAR ÁUDIO PARA CLONAR

A aba **REDIMENSIONAR ÁUDIO PARA CLONAR** prepara um ou vários arquivos de áudio para referência ou treinamento de voz. Ela aceita MP3, WAV, FLAC, M4A, OGG e AAC; permite adicionar arquivos, escolher uma pasta ou arrastar arquivos para a tabela com carregamento imediato e leitura de metadados em segundo plano; exibe duração, tamanho, formato, taxa de amostragem e canais; mostra barras de duração e tamanho do arquivo selecionado; procura limites de corte em pausas; normaliza o pico para -1 dBFS quando habilitado; e salva os resultados dentro da pasta principal `REDIMENSIONAR ÁUDIO PARA CLONAR`.

O modo **OmniVoice VoiceStudio** seleciona um trecho curto entre 5 e 20 segundos, com máximo configurado de 25 segundos. O modo **ElevenLabs Instant** trabalha com alvo de 60 a 180 segundos, com recomendação prática de aproximadamente 1 a 2 minutos de áudio limpo. O modo **ElevenLabs Professional** junta os arquivos e divide o resultado em blocos configuráveis de 30 a 45 minutos, limitado a até 180 minutos de total processado. As saídas ficam em `REDIMENSIONAR ÁUDIO PARA CLONAR/omnivoice/`, `REDIMENSIONAR ÁUDIO PARA CLONAR/elevenlabs_instant/` e `REDIMENSIONAR ÁUDIO PARA CLONAR/elevenlabs_pro/`.

A documentação atual do ElevenLabs recomenda áudio limpo, consistente, sem ruído, eco, música ou múltiplos falantes. Para Instant, recomenda cerca de 1–2 minutos e evitar mais de 3 minutos; para Professional, recomenda pelo menos uma hora e idealmente próximo de três horas. A ferramenta usa limites conservadores internos de 400 MB para Instant e 450 MB por bloco Professional. Esses limites internos não substituem a validação da plataforma no momento do upload.

### CLI

Com FFmpeg e FFprobe disponíveis no PATH, é possível usar a CLI:

```text
python main.py --input arquivo.mp3 --target omnivoice
python main.py --input voz_01.wav voz_02.flac --target eleven_instant --format mp3 --bitrate 256k
python main.py --input pasta/gravacao.wav --target eleven_pro --block-minutes 30 --json
```

O script `INSTALAR_DEPENDENCIAS_CLONAGEM.bat` instala `pydub`, `ffmpeg-python`, `numpy` e `scipy` e verifica FFmpeg/FFprobe. Os scripts de build também incluem os módulos da nova ferramenta, mas os binários FFmpeg/FFprobe continuam sendo requisitos externos do computador.

## Histórico global na aba COMANDOS

A aba **COMANDOS** possui agora a área **HISTÓRICO GLOBAL DOS PROCESSOS**. Ela recebe, em tempo real e com horário, os eventos dos principais processos executados pelo aplicativo, identificados pela origem: **CLONAGEM + DUBLAGEM**, **REVISÃO**, **CONVERTER DURAÇÃO**, **CONVERTER FORMATOS**, **FILTRO RENOMEAR .WEM** e **REDIMENSIONAR PARA CLONAR**. O histórico inclui início, andamento textual, conclusão, cancelamento, erros, preparação de FFmpeg/FFprobe/FFplay, conversões, redublagens, aprovações/rejeições, salvamento de textos, reprodução e operações relevantes de arquivos.

O painel **Saída do terminal** continua separado e mostra os comandos executados manualmente pela própria aba **COMANDOS**. O botão **LIMPAR** limpa os dois painéis da aba e descarta os eventos ainda não exibidos, sem apagar arquivos ou históricos do projeto. Os logs locais das demais abas continuam disponíveis e a centralização não bloqueia as filas de trabalho nem a interface.

## Texto editável na janela OUVIR CENA

A janela **OUVIR CENA** também exibe o título do áudio atual e o painel **TEXTO EM PORTUGUÊS — EDITÁVEL**. O TXT correspondente à chave relativa da cena é carregado automaticamente ao abrir a janela e atualizado ao usar **ANTERIOR** ou **PRÓXIMO**. O botão **Salvar alteração** grava o texto no TXT português da mesma forma que a aba **REVISÃO**; quando o texto anterior foi alterado, sua versão é preservada no versionamento textual de `revisoes`. Depois de salvar, use **REDUBLAR** ou **REDUBLAR COM OUTRO ÁUDIO** para a nova síntese usar o conteúdo atualizado.

Na caixa de ações da aba **REVISÃO**, **Abrir Audacity após redublar** fica diretamente acima de **REDUBLAR**, e **Pedido de alterar pronúncia do R** fica diretamente acima de **REDUBLAR COM OUTRO ÁUDIO**. As duas preferências continuam independentes e o pedido pontual do R não modifica a pronúncia fixa da aba **CLONAGEM + DUBLAGEM**.

## Formas de onda na janela OUVIR CENA

A janela **OUVIR CENA** agora apresenta duas formas de onda empilhadas: **ORIGINAL** acima e **DUBLADO** abaixo. Cada faixa é acompanhada por duração no formato `MM:SS.cc`, frequência de amostragem e quantidade de canais, distinguindo `mono` de áudio multicanal. A forma de onda é calculada somente para a cena atualmente aberta ou para a cena exibida após **ANTERIOR**/**PRÓXIMO**; a playlist inteira não é revarrida, o que mantém a abertura eficiente mesmo em projetos com milhares de itens.

A leitura usa a biblioteca padrão do Python para WAV PCM de 8, 16, 24 ou 32 bits e reduz os dados a um máximo de 700 picos visuais. Arquivos inexistentes, WAVs ilegíveis e formatos que não sejam WAV permanecem disponíveis para as outras ações do aplicativo, mas mostram **Onda não disponível para este áudio** na faixa correspondente; nenhuma conversão automática ou chamada externa é feita apenas para desenhar a onda. Ao redimensionar a janela, o Canvas é redesenhado para acompanhar a largura disponível. Os fundos, textos, campos e linhas-guia das duas faixas acompanham imediatamente os temas claro, médio e escuro.

## Tema do diálogo pontual de pronúncia do R

O diálogo **Escolha a pronúncia do R para esta redublagem** é modal em relação à janela de origem, restaura o foco ao pai ao terminar e usa a paleta do tema atual em todos os elementos: superfície, texto, campo de seleção, lista suspensa e botões **OK** e **CANCELAR**. Assim, o tema médio ou escuro não volta a exibir um retângulo branco. A escolha continua restrita à execução pontual e a transformação ortográfica segura entre vogais; nenhuma frase livre é anexada ao parâmetro `--instruct` do OmniVoice.

## Progresso da reprodução e painel lateral em OUVIR CENA

Durante a reprodução interna com **FFplay**, a janela **OUVIR CENA** exibe uma barra colorida na base de cada forma de onda e um marcador vertical que avançam conforme o tempo reproduzido. Ao clicar em **PARAR**, o marcador é zerado; ao concluir, ele permanece no final da faixa. O modo **OUVIR: WINDOWS** continua delegando a reprodução ao aplicativo padrão do sistema e, por isso, não fornece posição interna para animar o marcador.

Quando a cena possui integração com a Revisão, uma faixa compacta acima de **FORMAS DE ONDA E COMPRIMENTO** reserva o lado direito para **HISTÓRICO DA CENA**, **REFAZENDO A CENA**, as barras **CLONANDO REFERÊNCIA** e **DUBLANDO CENA**, a fase atual e o log do refazimento. As duas ondas ficam abaixo, ocupando a largura disponível, e o painel superior é atualizado sem bloquear a reprodução nem deixar timers ativos ao fechar.

Quando os dois áudios existem e têm durações diferentes, o áudio mais longo ocupa toda a largura útil da sua faixa e o áudio menor ocupa somente a fração proporcional correspondente. Assim, o final visual das duas formas de onda permite comparar diretamente seus comprimentos; a duração numérica completa continua visível nos metadados de cada faixa. A largura proporcional é recalculada ao abrir outra cena, usar **ANTERIOR**/**PRÓXIMO** ou redimensionar a janela.

## Atualização automática após dublagem ou redublagem

Se **OUVIR CENA** já estiver aberta quando a dublagem ou redublagem terminar, o aplicativo agora revalida o par da cena atual sem exigir que a janela seja fechada. O botão **INICIAR DUBLADO** é habilitado assim que o novo arquivo passa a existir, os caminhos exibidos são atualizados e as formas de onda recalculam duração, frequência, canais e largura proporcional imediatamente. O mesmo aviso é enviado ao player aberto por **CLONAGEM + DUBLAGEM** quando a operação é concluída pela Revisão.

O diálogo **Escolha a pronúncia do R para esta redublagem** calcula o próprio tamanho e é posicionado no centro da tela antes de receber o foco. Na janela **OUVIR CENA**, a faixa de **REVISÃO DA CENA** foi compactada e permanece no alto, alinhada à direita, sem espaço vazio acima; os controles inferiores são mantidos dentro da geometria inicial para aparecerem completos na abertura.

## Janela OUVIR CENA compactada e cores das ondas

O bloco textual de status com nome, caminhos de arquivo e mensagens de processo não ocupa mais espaço na janela **OUVIR CENA**; essas informações continuam disponíveis nos logs e no estado interno do player. Com isso, **REVISÃO DA CENA** e os controles abaixo sobem para perto do topo, mantendo a área de texto, ações e botões visíveis desde a abertura.

Em **FORMAS DE ONDA E COMPRIMENTO**, a faixa **ORIGINAL — INICIAR ORIGINAL** usa a mesma cor temática roxa do botão de início original, enquanto **DUBLADO — INICIAR DUBLADO** usa a mesma cor temática verde do botão de início dublado. O marcador de reprodução e a barra de avanço acompanham a cor da respectiva faixa e continuam sendo recalculados após dublagem, redublagem, navegação ou troca de tema.

## Janela OUVIR CENA: barras compactas e fim das ondas

A janela **OUVIR CENA** não exibe mais o título, o histórico ou o log visual de **REVISÃO DA CENA**. Permanecem somente as barras **CLONANDO REFERÊNCIA** e **DUBLANDO CENA**, posicionadas na faixa de controles junto aos botões de reprodução e imediatamente antes de **PARAR**. Elas continuam recebendo os percentuais da Revisão e do processamento em lote sem ocupar a área principal de visualização.

Cada forma de onda agora possui uma barra vertical colorida de término, com pequenas marcas superior e inferior, indicando exatamente até onde o áudio daquela faixa existe. No caso de durações diferentes, o marcador do áudio menor aparece antes do marcador do áudio maior, de acordo com a escala proporcional. A cor da barra de final, do marcador e do avanço segue a cor do botão correspondente: roxa para **INICIAR ORIGINAL** e verde para **INICIAR DUBLADO**.

## Controles e marcador final das formas de onda

O botão **PARAR** agora fica imediatamente à direita do conjunto de botões **INICIAR ORIGINAL** e **INICIAR DUBLADO**. As barras **CLONANDO REFERÊNCIA** e **DUBLANDO CENA**, quando disponíveis pela integração com a Revisão, permanecem compactas na mesma faixa de controles.

A linha horizontal central foi removida das formas de onda. Em repouso, cada áudio exibe somente uma barra vertical grossa no seu ponto final, com a cor correspondente ao botão de reprodução: roxo para o original e verde para o dublado. Durante a reprodução pelo FFplay, o marcador temporário de avanço aparece sobre a faixa e desaparece ao parar ou concluir, deixando novamente apenas a barra de final.

## Área de texto em português compacta

A área **TEXTO EM PORTUGUÊS — EDITÁVEL** da janela **OUVIR CENA** agora utiliza uma altura compacta de quatro linhas visuais, mantendo a edição, a barra de rolagem, o status do TXT e o botão **SALVAR ALTERAÇÃO**. A redução libera espaço para as formas de onda e os controles sem alterar o conteúdo salvo ou o fluxo de redublagem.

## Janela OUVIR CENA sem espaço vazio

A janela **OUVIR CENA** agora calcula sua altura de acordo com o conteúdo efetivamente exibido. A área compacta de **TEXTO EM PORTUGUÊS — EDITÁVEL**, as formas de onda, os controles de revisão e os botões inferiores são empilhados sem um espaço vazio intermediário, mantendo a edição, a rolagem, o salvamento e a navegação.

## Destaque visual da janela OUVIR CENA

A janela **OUVIR CENA** passou a ter uma borda externa amarela fixa, independente do tema claro, médio ou escuro. O conteúdo interno continua usando a superfície e as cores do tema ativo, enquanto a borda cria uma separação visual clara em relação às abas principais.

## Busca por clique nas formas de onda e organização da Revisão

Na janela **OUVIR CENA**, clique diretamente na forma de onda **ORIGINAL** ou **DUBLADO** para iniciar o áudio no ponto correspondente. O clique é convertido proporcionalmente para segundos, respeitando a largura real da faixa quando as durações são diferentes. O FFplay interno recebe o ponto inicial e o marcador de reprodução começa no mesmo local; no modo **OUVIR: WINDOWS**, a busca por clique informa que é necessário usar FFplay, porque o reprodutor externo não fornece controle de posição ao aplicativo.

Na aba **REVISÃO**, a lista **DUBLADOS** possui o controle **Organizar DUBLADOS**, com as opções **Padrão**, **Aprovadas primeiro**, **Rejeitadas primeiro** e **Aprovadas e rejeitadas primeiro**. A ordenação usa os estados persistidos da cena, mantém a ordem alfabética dentro de cada grupo e preserva a cena atualmente selecionada quando a organização é alterada ou quando uma aprovação/rejeição atualiza a lista.

## Histórico e reprodução na edição de áudio

Na janela **OUVIR CENA**, os botões **DESFAZER** e **REFAZER** ficam à esquerda de **SALVAR**. Com uma forma de onda em foco, **Ctrl+Z** desfaz a última alteração de áudio e **Ctrl+Y** refaz uma alteração desfeita. O histórico inclui colagens, cortes e exclusões do DUBLADO, sem permitir qualquer alteração no ORIGINAL. Uma nova alteração descarta o caminho de refazer; depois de SALVAR, o estado atual passa a ser a nova base.

Após copiar um trecho de **ORIGINAL** e colá-lo em **DUBLADO**, a reprodução por botão ou por **Espaço** usa os frames atuais em memória. O processo FFplay anterior é interrompido antes de o aplicativo gerar um WAV temporário novo, e o arquivo é validado quanto a cabeçalho e quantidade de frames antes da reprodução. Isso impede que o player volte a tocar o dublado antigo que está gravado no disco.

A janela OUVIR CENA usa o controle nativo de maximizar/restaurar da barra de título do Windows, junto dos controles nativos de minimizar e **X FECHAR**. A Toplevel permanece redimensionável. Ao maximizar, o painel de texto absorve o espaço vertical livre e os controles inferiores continuam acima da barra de tarefas; ao restaurar, o próprio Windows recupera a geometria normal.
