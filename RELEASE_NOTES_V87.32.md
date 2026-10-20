# V87.32 — voz selecionada nas expressões próprias

- Referências próprias fornecem a expressão: são convertidas por Seed-VC usando a voz selecionada como destino antes de alimentar o motor de síntese.
- A referência neutra permanece o modelo escolhido, inclusive se houver um neutro cadastrado nas referências próprias.
- Conversor ausente é preparado pelo fluxo existente de reações nativas. Conversão indisponível interrompe com erro; não usa a voz da expressão diretamente como substituição.
- A prévia OUVIR EXPRESSÕES continua reproduzindo a referência cadastrada; não é prévia da conversão final.
- Cache inclui conteúdo do doador, voz destino e emoção. Conversão de timbre aproxima identidade; não garante identidade perfeita nem preservação exata da emoção.
- Verificação do encaminhamento para conversão e síntese com mocks; não houve geração nem avaliação auditiva real nesta correção.
