# Dublaskizon V86.92

- Nova aba **TEXTO PARA FALA**, independente das filas de dublagem.
- Três referências: áudio original, perfil de voz do sistema ou voz-modelo adicionada pelo usuário.
- Carregamento recursivo de `WAV ORIGINAIS` e biblioteca persistente em `MODELOS DE VOZ PERSONALIZADOS`.
- Texto editável, reprodução do resultado, cancelamento e saída em `TEXTO PARA FALA`.
- Grade de expressões com emojis. Os marcadores nunca são falados; somente atributos aceitos pelo OmniVoice são enviados ao motor.
- Nova opção em **REQUISITOS**, logo abaixo da análise MFCC, para instalar e validar `datasets<4`, `soundfile` e `librosa` no ambiente isolado.
- Os três passos de Requisitos continuam responsáveis por instalar as bibliotecas, baixar o OmniVoice e testar o conjunto. **DESINSTALAR TUDO** remove o ambiente e essas dependências.
- Manifestos do PyInstaller e verificador do EXE atualizados para incluir `text_to_speech_tab` sem incorporar bibliotecas pesadas ao executável.

Validação: compilação sintática aprovada e 5 testes focados passaram. A abertura visual não pôde ser automatizada neste computador porque o Tcl/Tk da instalação Python usada para compilar continua inválido; o código preserva o runtime externo e o tamanho leve do EXE.
