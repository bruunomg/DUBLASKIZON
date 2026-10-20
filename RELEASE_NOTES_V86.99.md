# Dublaskizon V86.99

Corrige o reconhecimento da falta de autorização Hugging Face no download Fish. O processo informa um diagnóstico curto em vez de páginas de traceback. O botão 2 passa a reconhecer a falha mesmo quando o executor reporta somente um código de saída genérico, permitindo solicitar a autenticação na tentativa seguinte. Erros de conexão não são classificados como falta de autorização.

No relatório enviado, o ambiente Fish foi reutilizado e validado com CUDA; o bloqueio restante é HTTP 401 do modelo oficial gated. É necessário entrar em https://huggingface.co/fishaudio/s1-mini e aceitar os termos, criar um token de leitura na mesma conta em https://huggingface.co/settings/tokens e informá-lo somente no campo de autenticação do Dublaskizon. Login apenas no navegador não autentica o download do programa. Não reinstale nem desinstale tudo.

36 testes passaram. Sem nova geração real de fala. Fontes e scripts de compilação; sem EXE compilado.
