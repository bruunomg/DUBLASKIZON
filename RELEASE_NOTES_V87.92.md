# DUBLASKIZON V87.92

- Duplo clique em Transcrever e traduzir respeita OUVIR: FFPLAY / WINDOWS. Áudio usa Ouvir cena; vídeo usa o visualizador integrado no modo FFplay. Windows abre o aplicativo padrão. Arquivo original preservado.
- Transcrição desta execução agora fica na própria aba com mecanismo, modelo, idioma original e processamento CPU/GPU. O perfil Whisper-WebUI / large-v3 continua instalado localmente, sem Pinokio.
- Tradutor desta execução fica logo abaixo, com o idioma de saída. As escolhas sincronizam com Ferramentas locais / baixar.
- Tradutores OpenAI / ChatGPT, OpenAI / Codex, Claude e Gemini adicionados às APIs Luna/Sol e tradutores locais. Cada opção exige chave e modelo compatível da conta. As opções OpenAI usam Responses, com IDs de modelo separados; não usam o login do aplicativo.
- Revisão semântica também oferece Gemini. Configuração compartilhada de tradução/revisão em guias OpenAI, Claude e Gemini: campos protegidos, consulta de modelos, obter chave e ativar.
- Ferramentas locais / baixar oferece todos os provedores, libera APIs com chave/modelo e prepara somente os modelos locais necessários.
- As validações de índice, tags, respostas incompletas e apresentação explicativa continuam antes de publicar o TXT. Credenciais ficam protegidas pelo Windows fora do projeto e do ZIP.

Validação: 112 testes automatizados passaram e teste da aplicação completa confirmou a alternância global do player. APIs testadas com respostas simuladas; nenhuma chamada de tradução/revisão paga foi realizada. O acesso real depende da chave, saldo e modelos aceitos pela conta.

Referências de implementação:
- https://developers.openai.com/api/docs/guides/text
- https://platform.claude.com/docs/en/api/messages/create
- https://ai.google.dev/gemini-api/docs/text-generation
