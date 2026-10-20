# DUBLASKIZON V87.80

- Whisper-WebUI identificado pelo Pinokio em execução; a configuração exposta mostrou Model large-v3. Novo botão WHISPER LARGE-V3 seleciona o modelo no transcritor nativo, sem exigir o Pinokio aberto. Download/preparação continua pelas ferramentas locais do Dublaskizon.
- Janela TEMA / JOGO / GLOSSÁRIO com perfis Geral, Moss 1 VR, Moss Book 2 VR, Filme, Documentário e Personalizado. Nome, tipo, instruções, glossário, vocabulário da transcrição e modelo local são editáveis.
- Moss inclui a preferência Cristal indicada pelo usuário; isso não é uma afirmação de localização oficial. Regras aplicam variantes somente quando o termo de origem ocorre, sem mexer em tags ou placeholders. Documentário e Filme não recebem essas substituições.
- Whisper recebe somente dicas de vocabulário original; a transcrição não é reescrita pela terminologia traduzida. Tradução e revisão recebem o contexto completo.
- Configuração salva por projeto em revisoes/translation-context.json; não passa para os padrões globais de outro projeto. Transcrição/tradução existente do projeto também lê o contexto quando não há configuração explícita diferente.
- Tradução contextual local via Qwen/Ollama e nova revisão local com comparação original/tradução. Sol por API continua disponível. Revisões são candidatos separados, não aprovação automática de fidelidade.
- PREPARAR IA LOCAL baixa o modelo escolhido pelo usuário via Ollama. Qwen 7B e 3B são opções; requer Ollama disponível. Nenhum novo modelo foi baixado nesta atualização.
- Revisão local em fluxo cancelável, com limites de tempo/saída, validação de índices e tags, até quatro threads CPU e descarregamento do modelo ao terminar. Cache de síntese liberado antes desta etapa.
- Testes de contexto Moss/Documentário, isolamento entre projetos, janela de perfis, revisão sem chave, dicas de vocabulário e regressões. Inferência Qwen validada com respostas simuladas; modelo local não foi carregado para teste real.
