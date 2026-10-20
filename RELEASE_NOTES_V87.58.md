# DUBLASKIZON V87.58

- Remover silêncios do meio e Organizar ondas agora usam o mesmo detector complementar de pausas com baixo ruído. A proteção anterior aceitava apenas amostras exatamente zero, fazendo pausas com ruído contarem como fala.
- Análise em janelas de 10 ms exige contraste entre fala e piso de ruído; mantém margem de 40 ms em cada lado e só encurta pausas longas. Fala baixa, ordem dos trechos e entradas estéreo com canais de fase oposta são protegidas. Sons uniformes muito baixos permanecem intactos em casos incertos.
- Remover silêncios do meio mantém os silêncios externos e separadores de 60 ms. Organizar ondas também usa a detecção nova mesmo sem clicar antes em remover.
- No editor do recorte original, reprodução em laranja com rótulo INICIAR PARTE DO RECORTE; partes dubladas mantêm o verde.
- Undo e áudio original preservados. O limite de velocidade continua impedindo aceleração excessiva quando a fala, sem pausas removíveis, realmente não cabe. Detecção automática não garante classificação perfeita de fala/ruído.

Validação: testes para pausas com ruído sob um intervalo VAD contínuo, palavras baixas, conservação do original, sequência dos trechos e interface nativa. Teste real de remoção seguido de organização no projeto: 5,79 s → 4,98 s após remoção → 5,79 s alinhado, sem alterar os arquivos originais.
