# Dublaskizon V87.2

Texto para Fala: quadro PROCESSOS E MENSAGENS abaixo do botão DUBLAR, com rolagem, etapas do motor, comandos de expressão enviados, conferência da fala, novas tentativas e erros. O histórico é limitado para não crescer indefinidamente.

Fish: os comandos inseridos pelos botões são convertidos para marcadores do motor. Suspiro e risada são gerados como trechos separados; o estilo, como sussurro, continua nas palavras seguintes até outro comando de estilo. Textos maiores são divididos e o estilo é repetido em cada trecho. O áudio final reúne os trechos na ordem do texto, com pequenas pausas. CUDA utiliza BF16 quando suportado e FP16 nos demais casos.

A fala gerada é conferida com Whisper base em CPU/int8, reutilizando o cache. Isso também pode baixar esse modelo no primeiro uso sem uma referência. A conferência usa correspondência aproximada de palavras e verifica o final da frase; quando não confirma a fala, tenta novamente uma vez. Falhas após essas tentativas não substituem o resultado por um áudio parcial. Há um limite maior de geração por trecho.

Limitações: reconhecimento automático não comprova que todas as palavras foram faladas exatamente. Interjeições curtas e sussurros são especialmente difíceis de reconhecer. Quando a conferência curta é inconclusiva, o histórico e o status avisam para ouvir o trecho. A intensidade das emoções e a semelhança da voz dependem do Fish e da referência; esta atualização não garante emoções ou fala perfeita.

Validação: 47 testes automatizados passaram; sintaxe dos fontes e dos scripts internos verificada; criação da interface Tk e atualização do histórico verificadas em janela oculta. Os dois exemplos enviados pelo usuário geraram arquivos WAV em teste real com Fish/CUDA, usando voz do sistema, sem referência. A primeira interjeição de “ei! André!” não foi confirmada pelo reconhecedor; essa situação recebe aviso de conferência inconclusiva. Não foi feita avaliação auditiva dessas emoções nem teste com a gravação de referência do usuário.

Pacote de fontes e scripts de compilação, sem EXE compilado. Mantém os arquivos existentes da V87.1; não inclui modelos nem ambientes de dependências.
