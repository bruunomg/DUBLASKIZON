# DUBLASKIZON V88.10

- Corrigida a validação de referências em idiomas que não exigem espaços entre palavras. A regra anterior podia contar uma frase chinesa inteira como uma palavra e rejeitá-la como pouca fala. Agora considera densidade e variedade de caracteres nesses sistemas de escrita, mantendo os critérios existentes para palavras separadas por espaços.
- A seleção de frase também reconhece pontuação chinesa/japonesa.
- Nas tentativas alternativas de referência, usa o canal de maior energia em vez da média que podia cancelar voz em canais de fase oposta. O arquivo original não é modificado.
- Quando a fala não pode ser validada, o erro explica as possibilidades de fala baixa, reconhecimento insuficiente ou música/ruído. Não declara que o arquivo é necessariamente ruído.
- A ausência inicial do cache de referência não aparece mais encadeada como causa principal dessa recusa. Caches válidos existentes continuam reaproveitados.

Diagnóstico do arquivo informado: SW_01_CN_5_1_MIX.wav tem aproximadamente 71,04 segundos, 24 kHz e um canal. O nome 5_1 não corresponde ao número de canais desse WAV. O erro do log ocorreu durante preparação da referência, antes da síntese terminar; o aviso de pydub/FFmpeg não é a exceção final mostrada.

Validação: 70 testes passaram, incluindo referência longa chinesa, canais em oposição, preservação do original e filtros contra resultados esparsos/repetitivos. O reconhecimento foi simulado nos testes; o WAV do usuário não foi redublado nesta validação. Uma gravação sem referência reconhecível ainda requer recorte com voz ou outro áudio de referência.
