# V87.25 — silêncios fora do ajuste de velocidade

- O alinhamento por blocos calcula velocidade sobre a fala detectada, retirando silêncio inicial/final e intervalos longos entre trechos agrupados. Mantém margens de 20 ms na detecção.
- O limite total não impede a tentativa por blocos: silêncio excedente não conta como fala lenta. Se um bloco excede o limite, mantém o áudio gerado com aviso, sem falha nem retorno à compressão global.
- Ative Alinhar blocos de fala e pausas automaticamente em Configurar alinhamento. Com a opção desligada, permanece o ajuste global anterior.
- Detecção por energia, não IA. Silero VAD foi pesquisado como alternativa, mas não está integrado. Ruído, sussurros e diferenças de fraseamento podem requerer revisão; associação por ordem não é alinhamento de palavras.
- 154 testes passaram. Verificação com sinais sintéticos e FFmpeg simulado; nenhuma validação auditiva real nesta versão.
