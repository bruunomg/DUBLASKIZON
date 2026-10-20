# V87.49

- Novo controle opcional na Clonagem + Dublagem: DETECTAR FALA — PULAR POSSÍVEIS EFEITOS SONOROS. Desligado por padrão, escolha salva nas preferências.
- Silero VAD executa na CPU antes de transcrição e síntese, um processo por lote; não ocupa VRAM do clonador. Usa as dependências Silero já preparadas em Requisitos.
- Sem fala detectada: cena marcada SEM FALA?, original preservado, nenhuma síntese solicitada; registro salvo para conferência.
- Para tentar um pulado: desative o filtro, selecione os arquivos e use DUBLAR SELECIONADOS.
- Falha no detector suspende o filtro com aviso e mantém o fluxo normal. Cancelamento encerra detector e fila.
- Detector pode errar com sussurros, vozes baixas, música e efeitos. Critério conservador mantém qualquer possível fala; não é prova de ausência de diálogo nem detector de WEM corrompido.
- Validação real somente leitura: cinco dos sete arquivos indicados sem fala detectada; 161344903 e 165398669 tiveram possível fala; aa modelo.wav teve fala detectada. Detector não elimina todos os efeitos sonoros.
- 121 testes passaram, incluindo protocolo, erro, cancelamento, fechamento, retomada e síntese.
- Pacote com código e scripts, sem EXE compilado. Aplicação aberta não foi interrompida.
