# Dublaskizon V86.86

- Nova **Etapa 1** com árvore de pastas e suporte a arrastar e soltar.
- O botão da Etapa 1 cria uma pasta com o nome de cada áudio e move o próprio arquivo para dentro.
- A comparação existente passa a ser identificada como **Etapa 2**.
- Nova **Etapa 3**, também com árvore e pasta arrastada de forma independente.
- A Etapa 3 encontra `WAV PT-BR`, relaciona os WAV ao OGG por nome ou ordem, renomeia pelo OGG e move dois níveis acima.
- Depois de uma devolução completa, a pasta da cena é removida.
- Se o destino já existir, faltar OGG, faltar correspondência ou ocorrer erro, a pasta da cena é preservada.
- Nenhum `.bat` externo ou caminho fixo é necessário.

Validação: treze testes automatizados passaram, incluindo organização recursiva, devolução completa, remoção da pasta concluída e proteção contra sobrescrita.
