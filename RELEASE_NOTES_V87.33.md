# V87.33 — gravação de expressões próprias

- Reações da voz abre maior, com duas colunas de expressões compactas e Salvar reações reservado no rodapé. Tela pequena ainda dispõe de rolagem.
- Ícone 🎙 por expressão abre captura: enumera entradas informadas pelo Windows, mostra padrão, permite selecionar microfone interno/USB pelo nome.
- Captura selecionável de 3 a 10 segundos (inicial 6), PCM WAV mono, valida silêncio e apresenta onda após a gravação. OUViR, CONFIRMAR, ELIMINAR e REFAZER.
- Apenas CONFIRMAR copia a referência para TEXTO PARA FALA/GRAVACOES DE EXPRESSOES. SALVAR REAÇÕES cadastra a associação; expressão passa pela conversão de timbre para a voz selecionada.
- Sounddevice incluído nas dependências de Texto para Fala, instalado pelo botão 1 dos Requisitos. Sem reinstalação do ambiente se apenas esse pacote estiver ausente.
- Testes simulados verificam limite e PCM da captura; 163 testes passaram. Não houve gravação real de microfone nem avaliação auditiva. Nome de dispositivo depende do driver; não classifica USB/interno automaticamente.
