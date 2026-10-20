# V87.28 — correção de pausas no editor

- REMOVER SILÊNCIOS DO MEIO na linha da onda dublada: remove pausas longas detectadas por Silero VAD (fallback por energia), mantendo a ordem, margens da fala e separadores de 60 ms. Preserva extremidades para o botão específico.
- ORGANIZAR ONDAS mantém a velocidade natural dos blocos curtos; preenche o espaço restante com silêncio, sem desacelerar a fala para ocupar todo o intervalo original.
- Erros do alinhamento no editor exibem o número do bloco, duração da fala compactada, espaço disponível e aceleração necessária versus limite. Edição permanece intacta.
- Operações em segundo plano, reversíveis com DESFAZER, publicadas apenas com SALVAR. Divisões são recalculadas após remover silêncios internos.
- Testes sintéticos de preservação de fala, pausa curta, extremidades e PCM de entrada. Não houve teste auditivo do áudio mostrado nas imagens.
