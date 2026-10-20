# Transcrever e traduzir

1. Abra a aba ao lado de Texto para Fala.
2. Em FERRAMENTAS LOCAIS / BAIXAR, escolha Faster-Whisper ou Whisper, modelo, CPU/GPU e tradutor local. O download usa as ferramentas existentes do Dublaskizon.
3. Adicione áudio/vídeo ou TXT. Ctrl/Shift selecionam vários itens; sem seleção, usa todos os itens carregados. Também é possível escrever um texto sem adicionar arquivo.
4. Use TRANSCREVER para áudio/vídeo, TRADUZIR TEXTO para transcrições/TXTs, ou TRANSCREVER E TRADUZIR para as duas etapas. No tradutor local, TXT precisa de idioma de origem informado; uma transcrição já informa o idioma.
5. Para Luna/Sol, abra CHAVE / LUNA / SOL. Informe URL e identificadores aceitos pelo provedor, digite a chave ou importe seu .env e salve. A chave fica protegida no perfil Windows. A consulta VERIFICAR MODELOS não envia texto para tradução.
6. Luna traduz e Sol revisa. A opção Revisar tradução com Sol pode executar a revisão após a tradução; REVISAR COM SOL também permite revisar uma tradução que você colar na guia TRADUÇÃO. As chamadas usam sua chave e podem gerar cobrança do provedor.
7. Os TXTs finais ficam em TRANSCRIÇÕES E TRADUÇÕES/TRANSCRIÇÕES e TRANSCRIÇÕES E TRADUÇÕES/TRADUÇÕES, mantendo as subpastas adicionadas. A revisão concluída torna-se a tradução final. Relatórios e rascunhos ficam em revisoes/transcricoes_traducoes. SALVAR grava as edições no TXT final exibido; EXPORTAR TXT permite escolher outro arquivo. Originais não são alterados. LIMPAR JANELA e REMOVER SELECIONADOS retiram itens da interface sem apagar arquivos do disco. Pode arrastar pastas ou arquivos para a lista.
8. CANCELAR encerra a ferramenta local ou interrompe os próximos lotes API. Uma chamada API já enviada pode levar até o tempo limite para responder. Arquivos parciais têm parcial no nome; não são tratados como tradução final.

Os identificadores gpt-6-luna / gpt-6.1-sol foram mantidos conforme a ferramenta fornecida. Não são uma garantia de disponibilidade na API oficial: use o identificador e o endpoint que seu provedor realmente oferece. A integração segue o formato Chat Completions: https://developers.openai.com/api/reference/resources/chat

O Whisper-WebUI do Pinokio foi identificado com large-v3 selecionado. A aba nativa usa Faster-Whisper e Whisper em ambiente próprio, sem depender da janela do Pinokio.


## Tema e glossário

Abra TEMA / JOGO / GLOSSÁRIO. Escolha Moss 1 VR, Moss Book 2 VR, Filme, Documentário ou Personalizado e informe o título e as instruções. Os perfis Moss trazem a preferência Cristal pedida pelo usuário; revise e adapte essas regras ao contexto do seu projeto.

Formato: `glass => Cristal | vidro, vidraça`. O termo preferido orienta a IA. As variantes após a barra são corrigidas na tradução quando a origem aparece no texto; não substitui substrings nem tags. Defina regras no idioma de saída. A transcrição continua fiel ao idioma falado; o campo vocabulário fornece pistas ao Whisper sem traduzir a fala.

SALVAR E USAR IA LOCAL seleciona Qwen/Ollama para tradução e revisão. PREPARAR IA LOCAL baixa o modelo escolhido. Se o Ollama não estiver instalado, use FERRAMENTAS LOCAIS / BAIXAR e o botão OLLAMA OFICIAL. Qwen 7B exige mais recursos; 3B é uma opção menor, com possível diferença de qualidade. A revisão compara a tradução ao original e atualiza o TXT final da pasta TRADUÇÕES; o candidato e metadados ficam em revisoes/transcricoes_traducoes. Não é uma garantia de correção: revise termos ambíguos e informações factuais.

Argos aplica o glossário, mas não raciocina sobre o tema como um LLM. Para contexto mais amplo use IA local, TranslateGemma/Qwen local ou Luna. O nome de um jogo sozinho não garante terminologia correta; acrescente os nomes e regras que importam. O perfil fica no projeto atual, sem contaminar outro projeto.

Dentro de FERRAMENTAS LOCAIS / BAIXAR, escolha o mecanismo de transcrição e selecione large-v3 em Modelo de transcrição. Não há mais botão separado de perfil. O app Whisper-WebUI foi identificado em execução pelo Pinokio, com large-v3 selecionado, mas os ambientes continuam independentes. Prepare o modelo nas ferramentas locais se ele ainda não estiver no cache do Dublaskizon.

Referências primárias: https://ollama.com/library/qwen2.5:7b-instruct e https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py


## Pesquisa e progresso (V87.81)

Informe o título em TEMA / JOGO / GLOSSÁRIO. PESQUISAR TEMA NA INTERNET consulta artigos Wikipedia em português e inglês e exibe URLs, data e trechos. Confira se são da obra/edição correta. IA LOCAL: ANALISAR FONTES usa o Ollama preparado para propor pares de termos com evidência literal; propostas sem evidência são descartadas. Revise as propostas e use APLICAR FONTES AO CONTEXTO e SALVAR TEMA. Nenhum exemplo de outra obra é inserido automaticamente.

Ao traduzir/revisar um tema que ainda não tem pesquisa, busca referências automaticamente e as guarda no perfil do projeto. A IA recebe essas referências como dados, junto das regras do usuário. A pesquisa envia somente o título à Wikipedia, não o áudio ou a transcrição. Se a rede falhar, registra o aviso e usa o contexto já configurado. Um tema sem evidência de terminologia específica não recebe uma tradução oficial inventada. Argos continua usando regras explícitas, sem raciocínio contextual.

As barras de transcrição e tradução/revisão avançam conforme os trechos/lotes terminam. Durante carregamento do modelo ou uma chamada ainda sem retorno, ficam paradas no progresso confirmado; não existe animação contínua. Preparação de modelos mantém mensagens de download próprias.

Pesquisa: https://www.mediawiki.org/wiki/API:Search


## Edição e painéis (V87.82)

Os textos são editáveis quando o processamento termina. SALVAR EDIÇÃO no cabeçalho de cada texto grava no TXT final daquela transcrição, tradução ou revisão, sem pedir outro destino. O botão geral salva a guia visível; no modo dividido, salva o último painel focado. EXPORTAR TXT continua permitindo escolher outro arquivo.

Ative TRÊS PAINÉIS VERTICAIS no canto direito da área de textos para ver transcrição, tradução e revisão simultaneamente. Arraste as divisórias horizontais entre os painéis para ajustar suas alturas. Desative para voltar às abas. O texto editado é mantido durante a troca de visualização.

Também é possível arrastar a divisória acima de PROCESSOS para dar mais altura aos textos ou ao log. ABRIR PASTA DE SAÍDA abre a pasta principal dos resultados. O seletor de tradutor ocupa uma linha própria e os títulos das barras ficam acima delas.


## Escolher transcritor e tradutor (V87.83)

Na janela Transcrever → traduzir → dublar, a seção 1 escolhe o mecanismo que ouve o áudio (Faster-Whisper ou OpenAI Whisper) e seu modelo (incluindo large-v3). Só aparece um campo de modelo, referente ao mecanismo escolhido. large-v3 é um modelo de transcrição, não um tradutor de texto para português.

A seção 2 escolhe quem traduz: Argos local, TranslateGemma ou Qwen via Ollama local, Luna ou Sol via API. CONFIGURAR CHAVE / LUNA / SOL permite ativar ou desativar a chave e definir URL e identificadores do provedor. Sem chave, Luna/Sol ficam indicados como bloqueados e fora das escolhas disponíveis. Com chave, podem ser selecionados normalmente. A presença da chave não comprova acesso a cada modelo; a chamada depende do provedor.

APLICAR grava a escolha. A dublagem usa o motor/voz definidos na respectiva aba. Quando o fluxo precisa transcrever/traduzir antes de dublar ou redublar, utiliza o tradutor aplicado nesta configuração. A opção Sol pode traduzir diretamente; a revisão separada continua disponível na aba Transcrever e traduzir. As chamadas API enviam o texto ao provedor e podem gerar cobrança. PREPARAR DEPENDÊNCIAS não baixa modelos Luna/Sol.


## Whisper large-v3 independente do Pinokio (V87.84)

Na janela Transcrever → traduzir → dublar, escolha Faster-Whisper ou OpenAI Whisper e selecione **Whisper large-v3** no campo Modelo de transcrição. PREPARAR DEPENDÊNCIAS verifica o ambiente e baixa os arquivos ausentes para o próprio Dublaskizon. Não é necessário abrir ou instalar Pinokio para usar esses mecanismos. Os demais modelos continuam na lista, e cada mecanismo mantém a própria seleção.

Uma instalação feita no Whisper-WebUI do Pinokio não é automaticamente a instalação do Dublaskizon; a preparação local confirma o que está disponível para o mecanismo escolhido. Este ZIP contém o aplicativo, não os pesos grandes do modelo.

Os textos editáveis começam mais largos e altos. As divisórias entre lista/textos, textos/log e entre os três painéis continuam móveis e não retornam à posição inicial depois que você as ajusta.


## Perfil no mecanismo (V87.85)

Agora o campo Mecanismo de transcrição também contém **Whisper-WebUI / Whisper large-v3 — perfil local**. Ele define Faster-Whisper + large-v3 no próprio Dublaskizon; o modelo fica fixado enquanto esse perfil estiver selecionado. Clique em PREPARAR DEPENDÊNCIAS e depois APLICAR. Não precisa do Pinokio aberto. Este é um perfil do transcritor local, não uma incorporação da interface web do Whisper-WebUI.

As opções faster-whisper e openai-whisper continuam na lista para escolher outros modelos. O processamento, os tradutores e o destino dos TXTs seguem as demais configurações da janela.


## Seletores e pasta de saída (V87.86)

A aba exibe o nome exato do tradutor desta execução. FERRAMENTAS LOCAIS / BAIXAR configura e prepara as mesmas opções; não é um segundo tradutor. Alterar na aba e abrir as ferramentas mantém a escolha sincronizada. Aplicar outro tradutor nas ferramentas atualiza a lista da aba.

ABRIR PASTA DE SAÍDA fica no canto inferior direito, ao lado das barras. A mensagem Traduzindo texto já transcrito identifica a etapa que usa a transcrição pronta; não está executando uma segunda transcrição do áudio.

O perfil de mecanismo Whisper-WebUI / Whisper large-v3 fixa large-v3 por ser um atalho de configuração. Os mecanismos faster-whisper e openai-whisper permitem escolher os demais modelos. PREPARAR DEPENDÊNCIAS prepara os arquivos locais escolhidos, sem instalar a interface web do Pinokio. Arquivos válidos já presentes são reaproveitados.


## Ordem, consulta durante o lote e estados (V87.87)

Ao clicar em TRANSCREVER, TRADUZIR TEXTO ou TRANSCREVER E TRADUZIR, escolha a ordem. Somente transcrever/traduzir executa a etapa indicada. Transcrever todo o lote primeiro mantém um único transcritor carregado para os arquivos e só inicia a tradução depois que ele é liberado. Por arquivo conclui transcrição, tradução e eventual revisão daquele arquivo antes do próximo. A revisão opcional permanece conforme configurada.

Separar as etapas pode reduzir carregamentos repetidos, principalmente em lotes de áudios curtos. Na transcrição por etapas o modelo é reutilizado; a tradução e a revisão seguem seus motores e custos próprios. Não se executam Whisper e tradutor simultaneamente neste modo.

A lista continua clicável durante o processamento. Selecione um áudio/vídeo para consultar sua transcrição, tradução ou revisão já salva. Os textos permanecem somente para leitura durante o trabalho e voltam a aceitar edição depois. A seleção de consulta não muda o conjunto de arquivos que já entrou no lote.

[OK] em branco indica etapas concluídas sem alertas; desde V87.89, traduções também precisam de parecer semântico favorável, sem alterações propostas. [REVISAR] em amarelo indica falha ou sinais como baixa confiança do Whisper, repetição, idioma incompatível com o configurado ou sugerido pelo nome do arquivo, texto vazio ou diferenças suspeitas em tags/comprimento. O motivo aparece junto da lista. Isso não substitui conferir áudio e texto e não garante qualidade semântica.

Os quatro botões de adicionar/remover/limpar arquivos ficam acima de PROCESSOS. Durante a execução, mudanças na composição da lista ficam bloqueadas; consultar os itens continua permitido.


## Processos, contadores e originais (V87.88)

PROCESSOS começa maior e pode ser ajustado pela divisória acima. Nas barras, arquivo 2/100 indica o segundo item do lote; processados 1/100 indica que um item terminou a tentativa e faltam 99 são os ainda não resolvidos naquela etapa. Falhas e pulados aparecem separadamente; processado não significa necessariamente resultado aprovado. A quantidade total considera os arquivos escolhidos para aquela execução. Durante a revisão opcional, a contagem da tradução só termina aquele item ao finalizar também a revisão.

CARREGAR WAV ORIGINAIS busca os áudios/vídeos nas subpastas de WAV ORIGINAIS do projeto atual. Ignora TXTs, preserva as subpastas e não duplica itens já carregados. Se a pasta não existir no projeto, exibe um aviso.

Tradutor desta execução é o seletor de quem traduzirá os textos. FERRAMENTAS LOCAIS / BAIXAR configura e prepara esses mesmos tradutores. Escolher e aplicar TranslateGemma nessa janela atualiza a aba para TranslateGemma; não são dois tradutores executando em sequência. Revisar tradução, se ativado, executa a revisão como etapa adicional.


## Avaliação semântica e APIs (V87.89)

Abra REVISÃO SEMÂNTICA / APIs. Configure a chave OpenAI e os IDs dos modelos para as opções OpenAI/ChatGPT e OpenAI/Codex; configure a chave Anthropic e o ID do modelo Claude para Claude. Os IDs devem existir na sua conta e aceitar a API correspondente. MODELOS OPENAI e MODELOS CLAUDE consultam uma lista de IDs, que pode ser parcial. Não há modelo pago escolhido automaticamente. Chaves são mascaradas e protegidas pelo Windows, fora do projeto, e não vão para o pacote.

Ative Avaliar/revisar tradução e escolha o revisor. OpenAI/ChatGPT e OpenAI/Codex usam a API Responses com o modelo configurado. Claude usa a API Messages. Essas integrações exigem chave de API; não aproveitam o login da interface do aplicativo. As chamadas enviam origem, tradução e contexto ao provedor e podem gerar cobrança. Sol usa sua configuração de chave existente. Ollama local continua disponível sem API paga, desde que preparado.

O revisor compara sentido, naturalidade, expressões idiomáticas, ordens, negações e intensidade dos palavrões. Retorna um parecer explícito e sugestão completa. Traduções sem parecer ficam REVISAR, assim como pareceres com problemas ou correções. Uma sugestão publicada continua REVISAR para você conferir, com versão anterior e motivos no relatório. Parecer favorável sem mudanças pode resultar em OK, se não houver outros alertas. Isso não é garantia de que a IA acertou.

Falhas/incompletude de API, ausência de chave, tags ou linhas alteradas e parecer inválido não descartam a tradução já finalizada. Ao salvar uma edição, o parecer anterior é invalidado e o estado volta a REVISAR. A revisão semântica adiciona uma chamada ao processamento; não acontece se a opção estiver desativada.

APIs oficiais: https://developers.openai.com/api/docs/guides/text e https://platform.claude.com/docs/en/api/messages/create


## V87.90 — menu e validação
Clique com o botão direito em um arquivo da lista para abrir original/TXT, copiar caminhos, configurar ferramentas e processar a seleção. A ação VERIFICAR / LIMPAR APRESENTAÇÃO DA TRADUÇÃO carrega os TXT finalizados da hierarquia atual e remove somente apresentação reconhecida com origem correspondente. A versão anterior fica em revisoes/limpeza_traducao. Respostas ambíguas ficam REVISAR sem substituir o TXT válido. A conferência semântica continua necessária.


## V87.91 — reprodução
Dê dois cliques no áudio ou vídeo da lista para abrir o player padrão do Windows, inclusive enquanto a fila está processando. A pausa, navegação e volume ficam no player aberto.


## V87.92 — mecanismos e APIs na mesma aba
A primeira linha reúne transcritor, modelo, idioma de origem e CPU/GPU. A linha seguinte reúne tradutor e idioma de saída. Ferramentas locais / baixar aplica essas mesmas escolhas; no modo desta aba, a janela explica somente transcrição e tradução.

REVISÃO SEMÂNTICA / APIs configura as chaves e os modelos de OpenAI/GPT, Codex, Claude e Gemini por guias. Os modelos OpenAI precisam aceitar Responses. Claude usa Messages e Gemini usa generateContent. Esses provedores podem traduzir e revisar. Luna/Sol continuam com sua configuração própria. Consulte os modelos ou digite um ID compatível. A lista pode ser parcial; chave configurada não garante acesso ou saldo no provedor. A assinatura do aplicativo não substitui a chave da API.

Duplo clique respeita o botão global OUVIR: FFPLAY / WINDOWS. No primeiro modo abre o player de áudio ou visualizador de vídeo do Dublaskizon; no segundo abre o aplicativo padrão do Windows.


## V87.93 — textos e navegação do Ouvir cena
No player de áudio da aba, Anterior/Próximo acompanha a seleção e a rolagem da lista. O painel TEXTOS — EDITÁVEIS mostra os mesmos textos de Transcrição, Tradução e Revisão. Edite em uma das janelas e use SALVAR EDIÇÃO na guia desejada para gravar no TXT correspondente. Trocar de áudio preserva as edições pendentes; durante o processamento os textos ficam para consulta.

O seletor de tradutor deixou de expandir pela largura inteira da aba, mantendo os nomes completos e o idioma de saída ao lado. CADASTRAR CHAVE abre o portal oficial para configurar as APIs; não envia a chave nem cria conta automaticamente. OpenAI/GPT e Codex compartilham o portal OpenAI, assim como os aliases Luna/Sol desta configuração.


## V87.94 — ativar chave, tema e processamento
CADASTRAR CHAVE abre a configuração para colar a chave. LINK ADQUIRIR CHAVE DA API abre o site do provedor. ATIVAR CHAVE salva a chave protegida neste Windows, inclusive antes da escolha do modelo. Selecione/consulte o modelo e salve para liberar o uso. Ferramentas locais / baixar oferece acesso à mesma ativação.

O tema salvo é mostrado em destaque no topo. Confirmar tema, na linha dos botões Transcrever/Traduzir/Transcrever e traduzir/Revisar, controla o aviso Sim/Não antes de iniciar. A preferência fica salva por projeto. Não cancela o início sem alterar os resultados existentes.

O processamento do tradutor é independente do transcritor. Qwen/TranslateGemma locais permitem CPU ou GPU automática do Ollama; Argos usa CPU. APIs processam remotamente e mostram API — remoto, sem prometer usar a GPU do computador.


## V87.95 — configurar pela mesma estrutura do .env
A janela de APIs mostra as variáveis correspondentes de cada campo e oferece IMPORTAR .env. OPENAI_API_KEY é a chave secreta completa; OPENAI_MODEL e CODEX_MODEL contêm nomes de modelos. Nome/ID da chave não é modelo. Os aliases LUNA_TRANSLATION_MODEL e SOL_REVIEW_MODEL também são reconhecidos. Importe seu arquivo, consulte os modelos da conta, selecione um ID e use TESTAR ESTE MODELO antes de salvar. O arquivo de origem não é alterado e valores vazios não apagam campos existentes durante a importação.

Os exemplos gpt-4.1-mini e gpt-5-codex ilustram o formato; não garantem acesso e não são escolhidos automaticamente. CONSULTAR MODELOS faz consultas autenticadas. TESTAR ESTE MODELO usa consulta GET do recurso do modelo, sem geração; não prova saldo ou suporte completo à chamada de geração. ATIVAR CHAVE salva localmente, sem alegar que o provedor já aceitou a credencial.

Use CONFIGURACAO_APIS.env.exemplo apenas como referência; ele não contém chave real. Os erros da API explicam se a falha é autenticação, permissão ou endereço/modelo. O programa não pode liberar uma chave recusada pelo provedor, mas impede valores de chave/identificadores evidentes no campo de modelo antes de iniciar o áudio.


## V87.96 — observações e exportação .env
O parecer de cada áudio/vídeo fica em OBSERVAÇÕES DO ARQUIVO SELECIONADO, à direita de Processos, com rolagem própria e divisória ajustável. Selecione outro arquivo para consultar os alertas correspondentes.

Nas guias de APIs, preencha os campos e use EXPORTAR .env. O arquivo exporta parâmetros do provedor selecionado, nunca o valor secreto da chave. IMPORTAR .env também reconhece BATCH_SIZE, MAX_BATCHES, MAX_RETRIES e REQUEST_TIMEOUT. Esses controles pertencem ao Dublaskizon, não são nomes de parâmetros enviados diretamente a todos os provedores. MAX_BATCHES=0 não limita os lotes; se um limite explícito for insuficiente, nenhum lote daquele texto será enviado. Tentativas podem repetir solicitações de geração em erro transitório; o padrão é 0.


## V87.97 — pesquisa contextual por API
Em Tema / jogo / glossário, escolha IA para pesquisar o tema. OpenAI/GPT, Codex, Claude, Gemini, Luna e Sol usam as chaves/modelos cadastrados. PESQUISAR TEMA NA INTERNET coleta referências Wikipedia PT/EN e solicita análise à IA selecionada. Isso não equivale a navegação irrestrita de cada modelo. A API recebe tema, instruções e fontes e pode gerar cobrança.

Confira as guias Contexto, Glossário, Vocabulário original e Evidências. Termos proposed são adaptações sugeridas, não localização oficial. Aplicar contexto e glossário acrescenta a proposta aos campos existentes; SALVAR TEMA grava o contexto que orienta as próximas transcrições, traduções e revisões. O relatório fica em revisoes/pesquisa_tema. A transcrição não deve inventar palavras a partir do tema.


## V87.98 — escolha da IA e pesquisa web ampliada
IA LOCAL e IA POR API são opções exclusivas. Os botões Cadastrar/Ativar, Pesquisar e Cancelar ficam ao lado das duas linhas. Contexto, glossário e vocabulário têm rolagem própria.

A pesquisa reúne resumos atribuídos de resultados web, URLs e extratos Wikipedia PT/EN. Os resumos não equivalem à leitura da página integral nem comprovam localização oficial. A IA deve distinguir sentidos e edições; propostas devem ser conferidas antes de aplicar. A mesma validação de citações atende a análise local e as APIs.


## V87.99 — editores de tema e exportação TXT
Arraste as divisórias entre Contexto, Glossário e Vocabulário para ajustar a altura; o glossário começa com a maior área. Preparar IA local fica ao lado do modelo e não salva nem fecha o tema. Ao fechar com alterações, escolha Sim para salvar ou Não para descartar as mudanças da janela.

Exportar TXT cria uma cópia do texto atual da guia selecionada. Selecione Transcrição, Tradução ou Revisão antes de exportar. O botão informa guia vazia e erro de gravação, sem interromper a ferramenta.


## V87.100 — profundidade dos resultados da pesquisa
A pesquisa agora percorre seis categorias e analisa as fontes em conjuntos, consolidando os resultados. Se houver poucos termos ou lacunas, executa uma rodada complementar. Pode realizar até cinco análises da IA escolhida, com maior custo/tempo de API. Os comentários do glossário explicam o sentido e o uso contextual. Regras conflitantes são excluídas e mostradas como observação. Não são inventados termos para atingir uma quantidade mínima.


## V88.01 — controle do tema

SEM TEMA preserva o cadastro e ignora contexto, glossário e referências durante a execução. O título fica laranja. Com tema ativo, fica verde-água. Na janela do tema, RESETAR TEMA SALVO limpa o cadastro após confirmação; EXPORTAR TEMA PRESENTE salva os campos em JSON sem credenciais; IMPORTAR TEMA preenche os campos para conferir e salvar.


## V88.02 — terminologia por obra e adaptação
A análise propõe consultas específicas para as lacunas encontradas, priorizando termos das falas, objetos e inimigos e distinguindo a obra de suas adaptações. Termos marcados como outra adaptação ou não confirmados são excluídos. Nenhuma equivalência específica de jogo foi fixada. A coleta continua baseada em resumos web e extratos enciclopédicos; revise propostas e incertezas antes de aplicar.


## V88.03 — pesquisa durante o fluxo e retomada
Com tema cadastrado e ativo, transcrever e traduzir executa transcrição do lote, pesquisa dos termos dos transcritos e tradução com o tema atualizado. Transcrever alimenta o tema ao concluir; tradução e revisão pesquisam antes de executar. O botão do tema pisca para conferência. A pesquisa considera vocabulário recorrente e trechos distribuídos, preserva regras manuais e pode cobrar a API configurada. SEM TEMA desativa a pesquisa.

PAUSAR espera a etapa em andamento terminar e salvar; o botão muda para RETOMAR. Após fechar, abra o mesmo projeto e use RETOMAR DE ONDE PAROU. A etapa não salva pode ser refeita. Alterações nos arquivos de entrada bloqueiam retomada incompatível. O último lote fica em revisoes/transcricao-traducao-pendente.json; uma nova execução substitui o checkpoint do último lote.


## V88.04 — origem das regras e propostas automáticas
O glossário informa USUÁRIO para regras novas ou alteradas manualmente, IA para propostas contextuais e FONTE quando os termos constam da citação, com URL e evidência. Regras antigas sem rastreamento ficam com origem anterior não registrada. A IA pode preencher automaticamente propostas de alta confiança com trechos literais dos transcritos; isso não comprova tradução oficial. A busca filtra melhor o título e tenta ler páginas públicas, preservando resumos quando não consegue. Consulte TESTE_TEMA_LIMPO_V88.04.json para a execução real em tema limpo, sem o termo esperado na entrada.


## V88.05 — filtro visual do glossário
Linhas com => ficam verdes. Ative SOMENTE LINHAS COM => ao lado do título do glossário para ocultar as explicações. Desative para mostrar tudo novamente. O filtro não apaga conteúdo: salvar e exportar preservam o texto completo.


## V88.06 — adicionar regra
Abaixo do título do glossário, preencha Texto e Referência / tradução preferida e clique ADICIONAR. A linha texto => referência entra como regra do USUÁRIO em verde. Salve o tema para persistir no projeto. A ferramenta avisa se a origem já existe, preservando a regra anterior.


## V88.07 — acabamento de dublagem
Na Clonagem + dublagem, abaixo de Configurar alinhamento, ative corte de silêncio das extremidades e/ou volume máximo seguro. São aplicados às novas saídas ao terminar a síntese e o alinhamento. O corte pode reduzir a duração final. Na Revisão, os botões TODOS aplicam aos dublados existentes da lista completa da modalidade atual, com backup e progresso. O limite de aumento de volume é -1 dBFS de pico, igual ao editor de cena. PARAR AJUSTES termina após o arquivo atual.


## V88.08 — preparar todos os textos antes de dublar
Ative TRANSCREVER E TRADUZIR QUANDO FALTAR TXT. A opção TUDO ANTES DE DUBLAR, inicialmente ligada e também disponível à esquerda de Aplicar na configuração, verifica TXTs ausentes/vazios da fila e prepara as transcrições, pesquisa opcional do tema e traduções antes de iniciar a síntese. Textos preenchidos são preservados. No aviso de tema, Sim abre o tema da aba Transcrever e traduzir; Não executa sem tema; Cancelar não inicia. A pesquisa usa a IA configurada e pode gerar cobrança. Resultados compatíveis são reaproveitados a partir de revisoes/preparacao_textos. Desligar a opção usa o fluxo por cena.


## V88.09 — acionamento e log da preparação
Aplicar na configuração também ativa a transcrição/tradução automática e inclui os áudios sem TXT. A varredura informa quantos textos foram preservados e quantos precisam ser preparados. Quando todos estiverem preenchidos, o log explica que não há transcrição/tradução necessária; definir tema não sobrescreve textos existentes. O log da Clonagem foi ampliado verticalmente e limitado à esquerda dos controles; as barras e a linha de Pausar ficam acima.


## V88.10 — referências em chinês
A validação da referência de clonagem considera caracteres em idiomas sem separação obrigatória por espaços, em vez de tratar frases inteiras como uma palavra. Tentativas alternativas não fazem média de canais que possa cancelar voz. A recusa indica que não foi possível validar fala suficiente, sem afirmar que o arquivo inteiro é ruído. A ausência esperada do cache não aparece como causa principal. Originais são preservados.
