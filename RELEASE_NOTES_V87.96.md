# DUBLASKIZON V87.96

- Observações do arquivo selecionado movidas para painel à direita de PROCESSOS, com rolagem própria, largura inicial próxima à lista de arquivos e divisória redimensionável. Áudios/vídeos selecionados mostram seu parecer/alertas, sem comprimir a lista.
- EXPORTAR .env em cada guia de API: exporta os parâmetros preenchidos e as variáveis próprias de OpenAI/GPT/Codex, Claude ou Gemini. A chave secreta é exportada vazia; credenciais continuam protegidas no Windows.
- Campos editáveis BATCH_SIZE (1–32), MAX_BATCHES (0 = sem limite), MAX_RETRIES (0–3), REQUEST_TIMEOUT (10–600 s) nas configurações compartilhadas das APIs. Importação/exportação compatível com esses parâmetros do exemplo fornecido.
- Tamanho/limite de lotes aplicado à tradução por API. Limite insuficiente interrompe antes de enviar qualquer lote, evitando resultado parcial. Tempo limite e repetição limitada de erros transitórios aplicados à geração por OpenAI/Claude/Gemini. Padrão sem repetição; 401/403/404 não são repetidos. Revisão usa o mesmo tempo limite/tentativas.
- Parâmetros de lote são controles do Dublaskizon; cada provedor mantém sua autenticação e formato nativo de chamada. Consultas de modelos continuam sem gerar tradução.

Validação: 135 testes automatizados passaram. Inclui observação longa sem reduzir lista, troca áudio/vídeo, exportação/importação sem segredo, tamanho/limite de lotes e tempo/repetição da chamada simulada. Nenhuma chamada paga realizada. Arquivo .env do usuário não foi alterado ou copiado para o pacote.

Fontes: https://developers.openai.com/api/reference/overview ; https://platform.claude.com/docs/en/api/messages/create ; https://ai.google.dev/gemini-api/docs/text-generation
