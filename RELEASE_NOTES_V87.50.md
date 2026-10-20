# V87.50

- Clonagem + Dublagem: PULAR POR DEMORA ativável, desligado por padrão, limite ajustável de 15 a 3600 segundos (sugestão 120).
- Limite cobre o processo de síntese/conferência, incluindo carga dos modelos. Não cobre preparação inicial dos WAVs, transcrição/tradução anterior, nem alinhamento posterior.
- Ao exceder, encerra processo de síntese, marca DEMORA, preserva saída anterior e passa à próxima cena. Modelo precisa ser recarregado após essa interrupção.
- DUBLAR PULADOS tenta registros de SEM FALA?, DEMORA e ERRO. Suspende detector de fala nessa fila, mantém limite configurado e preserva versão anterior ao publicar nova síntese.
- Abertura deixa de ler os cabeçalhos de todos os WAVs. Verificação de formato passa para o início da dublagem; varreduras de nomes das abas continuam necessárias.
- Recuperação de histórico enumera saídas existentes em vez de consultar todos os caminhos ausentes. Avisos de TXT resumidos; popup de TXT removido da aba embutida.
- 124 testes passaram. Não medida a abertura completa com 51 mil arquivos nem o layout final na resolução do usuário.
- Código e scripts, sem EXE compilado. Reinício da aplicação atualizada necessário.
