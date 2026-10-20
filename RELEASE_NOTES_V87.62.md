# DUBLASKIZON V87.62

Otimizações no caminho gerenciado do OmniVoice, compartilhado por clonagem, revisão, dublagem personalizada, texto para fala e partes.

- Referências sem uma frase completa de 3–10 s agora guardam também a transcrição usada com o áudio inteiro. A referência permanece intacta e a transcrição é reutilizada pelo conteúdo SHA-256 do arquivo; alterar o áudio invalida o cache. Falhas ao gravar esse cache não interrompem a dublagem.
- Conferência de frases curtas usa um orçamento de reconhecimento proporcional ao texto esperado, com margem, em vez de deixar o Whisper seguir por centenas de tokens desnecessários. Síntese, número de passos, velocidade e tentativas de recuperação preservados. A verificação de palavras continua ativa.
- GPUs CUDA de pouca memória agrupam as chamadas consecutivas de conferência, tempos e reconferência: um único ciclo de transferência de pesos por grupo. Mesmos modelos e precisão; liberação/restauração em finally também nas falhas.
- Cache danificado de referência é refeito em vez de bloquear a geração.

Validação: 127 testes de regressão, incluindo mudança do áudio de referência, preservação do original, texto incompleto e retorno seguro à GPU após erro. Teste com OmniVoice BR-PT v1.5 e fala contínua: texto Precisamos sair daqui antes que eles voltem confirmado integralmente; geração e conferência em 5,76 s no computador de teste. Uma preparação de referência sem recorte levou 13,28 s pelo caminho anterior e 0,002 s com transcrição já reutilizada; essa comparação mede somente a preparação, não a dublagem inteira. Reconhecimento de referências com hesitações pode divergir; no teste de referência repetitiva, uma fala não confirmada continuou marcada para revisão. Nenhuma amostra de teste substituiu áudios do projeto.

O ganho varia por referência, duração, GPU e tentativas necessárias. A primeira carga dos modelos e a primeira preparação ainda têm custo; falas difíceis mantêm as recuperações e a indicação de revisão.
