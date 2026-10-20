# DUBLASKIZON V88.07

- Clonagem + dublagem: abaixo de CONFIGURAR ALINHAMENTO, opções independentes para cortar silêncio do início/fim e aumentar o volume ao máximo seguro em cada nova dublagem. Começam desligadas, são salvas nas preferências e capturadas ao iniciar o lote.
- O acabamento usa os mesmos processamentos de Ouvir cena: detecção de silêncio somente nas extremidades e ganho sem compressor, limitado a pico de -1 dBFS. Áudios silenciosos ou que já atingiram o limite não recebem amplificação adicional.
- Os ajustes são aplicados ao WAV temporário depois do alinhamento e da preservação de voz, antes de publicar o resultado. Cortar as extremidades pode deixar a duração menor que a do original. Falha de acabamento preserva a dublagem válida e registra aviso para revisão.
- Revisão: abaixo dos controles existentes, botões CORTAR SILÊNCIO INÍCIO/FIM — TODOS e VOLUME MÁXIMO SEGURO — TODOS. Aplicam aos arquivos dublados existentes das cenas da lista completa da modalidade ativa, com confirmação, andamento e PARAR AJUSTES após o arquivo atual. Não se restringem à seleção ou ao filtro visual.
- Os arquivos são processados um por vez em segundo plano. Cada versão alterada é preservada em revisoes e a substituição é atômica. Originais nunca são ajustados. Falhas em um arquivo são registradas e o lote continua.
- Para evitar editar conteúdo desatualizado, Ouvir cena é fechada ao terminar o lote de ajustes; pode ser reaberta com o arquivo atualizado. Edição não salva bloqueia o início dos ajustes.

Validação: 23 testes passaram, incluindo aplicação em lote, backups, limite de volume, silêncio e layout; testes existentes de volume e inicialização completa também passaram. Ambos os executáveis auditados.
