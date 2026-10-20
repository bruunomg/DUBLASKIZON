# DUBLASKIZON V87.95

## Configuração de APIs refeita
- IMPORTAR .env nas guias OpenAI, Claude e Gemini. Campos mostram as variáveis equivalentes do arquivo. Suporta OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, CODEX_MODEL/OPENAI_CODEX_MODEL, LUNA_TRANSLATION_MODEL, SOL_REVIEW_MODEL, ANTHROPIC_* e GEMINI_*/GOOGLE_API_KEY. Valores vazios não apagam a configuração existente durante a importação. O arquivo de origem não é alterado.
- Exemplos de IDs nos campos OpenAI/GPT e Codex, identificados como exemplos sem garantia de acesso. CONSULTAR MODELOS obtém os nomes disponíveis na conta e preenche as listas; não gera texto.
- TESTAR ESTE MODELO consulta o recurso do modelo selecionado sem enviar áudio ou texto de tradução. O teste de consulta não comprova saldo ou compatibilidade completa de geração.
- RESTAURAR URL PADRÃO e orientação para não usar o site de cadastro no campo URL base.
- Chave secreta, nome/ID da chave e nome do modelo são explicados separadamente. Valores semelhantes a chaves/identificadores no campo de modelo são bloqueados antes de iniciar o áudio nos provedores oficiais. Chaves não são incluídas nas mensagens de erro.
- ATIVAR CHAVE informa que a chave foi salva localmente e ainda precisa ser verificada. Um modelo inválido é limpo ao ativar, com aviso; SALVAR E ATIVAR exige corrigir campos preenchidos inválidos.
- Mensagens HTTP distinguem autenticação recusada (401), permissão (403), recurso/modelo/endereço não encontrado (404) e limite/cota (429). TXT anterior preservado.
- Arquivo CONFIGURACAO_APIS.env.exemplo incluído sem chave real. Não importa nem testa credenciais automaticamente.

Validação: 131 testes automatizados passaram. Importação, listagem e teste de modelo, erros HTTP, bloqueio antes da transcrição e preservação dos demais fluxos. Respostas de API simuladas; nenhuma chave real do usuário lida/testada e nenhuma chamada paga realizada. Executável e ZIP auditados.

Como usar: abra CADASTRAR CHAVE, importe seu .env ou cole a chave secreta, clique CONSULTAR MODELOS, selecione o modelo, clique TESTAR ESTE MODELO e SALVAR E ATIVAR. Uma chave inválida/sem acesso precisa ser corrigida no provedor; a atualização não pode criar acesso à conta.

Fontes de implementação e exemplos:
- https://developers.openai.com/api/reference/overview
- https://developers.openai.com/api/docs/guides/error-codes
- https://developers.openai.com/api/docs/models/gpt-4.1-mini
- https://developers.openai.com/api/docs/models/gpt-5-codex
