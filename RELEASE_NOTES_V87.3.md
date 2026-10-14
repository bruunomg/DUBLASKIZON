# Dublaskizon V87.3

Correção do Texto para Fala Fish com áudio modelo: o caminho antigo não identificava o locutor na sequência da referência e do texto novo. O formato de prompt agora identifica ambos como locutor 0, conforme a implementação do Space oficial fishaudio/s1-mini. O teste que antes retornava apenas “Whispering” passou a gerar a frase pedida, com conferência aproximada do final da fala.

Cada geração recebe uma nova semente aleatória, registrada pelo próprio Fish no histórico, evitando repetir sempre as mesmas duas tentativas malsucedidas a cada clique. Cada parte pode ter até quatro tentativas, interrompidas assim que a conferência aceita o resultado. Resultados não confirmados continuam sem substituir o arquivo final por fala parcial.

Novas expressões oficiais em MAIS EXPRESSÕES — Fish: grito, grito forte, choro, choro intenso, raiva, medo, animado, voz suave, nervoso, calmo, sarcástico e ofegante. Escolha e clique INSERIR para adicionar o marcador no cursor. Choro, choro intenso e ofegante são sons separados; para fala triste use também TRISTE. Esses comandos adicionais exigem Fish; o programa não os descarta silenciosamente ao gerar com OmniVoice.

A caixa de erro mostra o diagnóstico final em português e indica PROCESSOS E MENSAGENS, onde permanece o relatório completo. A aba Texto para Fala ganhou rolagem para manter DUBLAR e os processos acessíveis em telas menores. Modelos e dependências existentes continuam reutilizados; este ajuste não exige reinstalação ou novo download dos pesos Fish.

Validação: 50 testes automatizados passaram. Sintaxe dos fontes e script interno verificada. Interface Tk, controles e aplicação do tema conferidos em janela invisível de 1280×800. Testes reais com as referências ULY_003_Sarrano e BAC_078_Trishka do projeto geraram WAV usando o protocolo corrigido. Frases curtas tiveram reconhecimento inconclusivo, indicado por aviso. A verificação é aproximada e não comprova a pronúncia exata. Não foi feita avaliação auditiva da intensidade das emoções ou da fidelidade de voz; o modelo ainda pode falhar com determinadas referências e textos. Falhas reais são informadas, sem garantir geração perfeita em todos os casos.

O teste real adicional com os comandos de grito e choro também gerou e salvou um WAV. A transcrição da fala obteve 86% de correspondência aproximada; a intensidade do grito e o som do choro ainda exigem conferência auditiva.

Fontes oficiais consultados:
- https://huggingface.co/fishaudio/s1-mini — lista de emoções S1 e tons.
- https://huggingface.co/spaces/fishaudio/s1-mini/blob/main/fish_speech/models/text2semantic/inference.py — ContentSequence e identificação do locutor.

Pacote de fontes e scripts de compilação, sem EXE compilado. Não inclui modelos nem ambientes de dependências; mantém os arquivos anteriores.
