# Dublaskizon V86.90

- Corrigido o erro `got an unexpected keyword argument 'metadata_errors'` no faster-whisper.
- Ambientes existentes com PyAV 19 recebem compatibilidade imediata durante a transcrição.
- O botão **Preparar dependências** detecta PyAV 19 e instala automaticamente `av<19` no ambiente isolado.
- Novos ambientes já são criados com a restrição `av<19`.
- A alteração afeta somente o ambiente isolado de transcrição do Dublaskizon.

Validação: 33 testes passaram, cobrindo transcrição, tradução, fallback GPU/CPU, redublagem, separação de frequências e tema.
