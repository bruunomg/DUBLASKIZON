# DUBLASKIZON V87.75

- Referências longas são varridas em blocos de até oito segundos para localizar atividade sonora após o silêncio inicial. Silero VAD identifica o início da fala quando disponível; sem ele há detecção por energia com validação posterior da transcrição.
- A janela de referência e a busca de alternativas partem da atividade/fala detectada, em vez do início silencioso ou de posições arbitrárias do arquivo.
- Usa o canal mais forte, evitando cancelamento de voz em canais com fase oposta.
- O original não é editado, recortado nem deslocado. Cache v4 evita reutilizar seleções anteriores.
- Mantidas as proteções de duração V87.74, conferência de palavras e layout.
- Verificados cinco arquivos reais da pasta indicada: primeira atividade em 8.4s, 6.8s, 0s, 5.9s e 20.7s. Isso é atividade sonora, não uma confirmação de fala.
