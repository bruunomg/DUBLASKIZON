# DUBLASKIZON V88.11

- OUVIR CENA: opções AUDACITY Music Separation e AUDACITY Noise Suppression junto ao título do ORIGINAL. As duas opções iniciam desativadas.
- O tratamento cria cópias em revisoes/audacity_openvino, sem substituir o original. A supressão é aplicada somente à voz separada, preservando também a voz sem supressão e o instrumental.
- Novas ondas sample-instrumental, sample-vocals e sample-vocals Suppression, com reprodução, indicação de tempo, zoom e controles individuais/conjuntos para mostrar ou esconder.
- Barras de clonagem e dublagem empilhadas, progresso por etapas do Audacity e cancelamento do tratamento. A área das ondas tem rolagem própria quando necessário para preservar os botões e o editor de texto.
- Confirmações de redublagem e dublagem de partes permitem escolher original/referência habitual (Sim), instrumental, voz separada ou voz com supressão. Não cancela a ação.
- Para recortes, a faixa escolhida é copiada para o editor e somente o recorte salvo é usado na geração.
- Requer Audacity com OpenVINO e respectivos modelos instalados no Windows. O aplicativo prepara sua própria cópia de execução no primeiro uso. Salve e feche o Audacity antes de usar o tratamento: a automação nunca utiliza seu projeto aberto.
- O motor inicia isoladamente em segundo plano; sua inicialização pode levar cerca de 20 segundos antes dos efeitos. O tratamento roda fora da interface e possui limite de tempo e cancelamento. Desativar as opções mantém disponíveis os arquivos já tratados e a escolha da referência habitual.

Validação: execução real dos dois efeitos em trecho de 4,45 s, exportação das três faixas com duração correta e verificação SHA-256 do original; testes de proteção dos arquivos, cancelamento, referências, visibilidade, editores e regressão da revisão.
