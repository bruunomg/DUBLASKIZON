# V87.30 — proteger inícios e fala baixa

- A classificação do Silero não autoriza mais descartar samples com sinal na dublagem. Compactação remove apenas intervalos longos de silêncio digital fora da fala detectada, com margens de 40 ms.
- Proteção aplicada ao Organizar ondas e Remover silêncios do meio. Ruído é mantido quando há dúvida. Remoção interna também protege canais estéreo com cancelamento na mistura mono.
- 994001710.wav verificado em modo somente leitura: todos os samples PCM não nulos da entrada compactada foram preservados, na mesma ordem. Compactação de 8,2 s para aproximadamente 7,836 s.
- Esta validação é da compactação, não uma garantia auditiva do resultado completo após mudança de tempo. Uma fala já cortada e salva precisa ser restaurada de uma versão anterior ou redublada.
- 160 testes de regressão passaram antes da proteção adicional de canais estéreo.
