# DUBLASKIZON V87.51

- Alinhamento: silêncio digital isolado não é considerado bloco de fala. Preserva amostras de voz fraca e utiliza o espaço livre após cada bloco antes de acelerar a fala, mantendo os pontos de início do original.
- Manter voz natural do áudio original: opção abaixo de Pular por demora e disponível no Ouvir Cena. Usa o tratamento de voz original já existente no aplicativo.
- Ouvir Cena: opções distribuídas em duas linhas. Abrir Audacity após redublar e Pedido de alterar pronúncia do R iniciam desativados.
- Revisão: REDUBLAR TODOS REJEITADOS [REFAZER] processa os rejeitados em sequência, preserva versões anteriores e marca os concluídos como [AVALIAR], em amarelo. Falhas não são marcadas como concluídas.

Validação: 150 testes de lógica e 6 testes da janela Ouvir Cena aprovados. Não foi feita validação auditiva dos arquivos reais do usuário nem teste na GPU do amigo.

O pacote contém código-fonte e scripts; não contém um novo executável compilado nem os modelos.
