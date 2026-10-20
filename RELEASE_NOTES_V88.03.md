# DUBLASKIZON V88.03

- Com tema ativo, a execução pesquisa contexto e terminologia a partir dos transcritos usando a mesma IA configurada em Tema/jogo/glossário. Transcrever e traduzir passa a usar etapas: transcrição do lote, pesquisa contextual, tradução e revisão conforme configurada.
- Traduzir e revisar pesquisam os textos disponíveis antes de executar. Transcrever pesquisa ao terminar, alimentando o tema para as próximas etapas. SEM TEMA ignora a pesquisa.
- Regras manuais existentes do glossário têm prioridade. Contexto, termos novos, vocabulário e evidências são salvos no tema do projeto. O botão do tema pisca ao concluir e para ao abrir a janela.
- PAUSAR / RETOMAR espera terminar e salvar a etapa atual. RETOMAR DE ONDE PAROU restaura o último lote salvo após reabrir o projeto, incluindo configurações, hierarquia, resultados e etapas concluídas. Credenciais continuam sendo carregadas do armazenamento protegido, não do checkpoint.
- O checkpoint é salvo em revisoes/transcricao-traducao-pendente.json. Se fechar no meio de uma etapa, essa etapa incompleta será refeita. Arquivos removidos ou modificados impedem retomada automática para evitar reutilizar resultados incompatíveis.

Limites: a pesquisa analisa vocabulário recorrente e até oito trechos distribuídos pelo lote; não envia todo lote ilimitadamente à IA. Usa resumos web e extratos enciclopédicos, sem garantir localização oficial. Pode gerar cobrança na API configurada. Falha de pesquisa preserva o tema anterior e registra aviso. A pesquisa já concluída é reutilizada na retomada se o corpus não mudou.

Validação: testes de pesquisa contextual, preservação de glossário manual, sinalização visual, pausa e retomada após recriar a interface, além dos fluxos existentes de transcrição/tradução.
