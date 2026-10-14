# V87.23 — alinhamento por blocos de fala

- CONFIGURAR ALINHAMENTO oferece Alinhar blocos de fala e pausas automaticamente: detecta atividade por energia, associa blocos em ordem, agrupa pausas extras e reposiciona a fala nos intervalos do original.
- Ajuste de tempo por FFmpeg preserva o tom; pequenos arredondamentos de duração são corrigidos usando todo o bloco, sem cortar sua cauda.
- Duração final igual ao original na saída mono 24 kHz. A opção desativada continua ajustando somente a duração total.
- Limite de velocidade também se aplica aos blocos. Mudanças excessivas ou blocos inválidos preservam o áudio anterior e pedem revisão.
- Este alinhamento aproxima fala e silêncio, não sincroniza palavras de uma tradução nem torna ondas de vozes diferentes idênticas. Música e ruído podem prejudicar a detecção por energia.
- Preservados o modelo residente, a conferência textual e o ritmo natural quando o alinhamento está desligado.
- 151 testes passaram, incluindo testes com sinais sintéticos e FFmpeg simulado. Esta atualização não foi validada auditivamente com cenas reais.
