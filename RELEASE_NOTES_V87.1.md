# Dublaskizon V87.1

Texto para Fala Fish: selecione a gravação de referência, escreva qualquer texto novo na caixa principal, insira expressões e clique em DUBLAR. A transcrição manual da gravação não é mais obrigatória.

Quando não há transcrição informada nem TXT ao lado da gravação, o programa usa faster-whisper base para reconhecer automaticamente a fala da referência. Esse texto é usado somente para clonar a voz; a fala gerada continua sendo o texto novo escrito na caixa principal, com as expressões. Transcrições são guardadas por hash do conteúdo do áudio, evitando repetir o reconhecimento da mesma gravação e impedindo reutilizar um resultado antigo após mudar o áudio.

O campo de transcrição passa a ser opcional. Os status do processo aparecem durante reconhecimento e síntese. Na primeira transcrição, pode ser necessário baixar o modelo Whisper base; ele fica no runtime gerenciado, fora do EXE, e é removido por DESINSTALAR TUDO. Execução do reconhecedor em CPU/int8 libera a GPU para Fish. Decodificação via SoundFile/Librosa evita o conflito PyAV metadata_errors já observado. A gravação precisa conter fala reconhecível.

Sintaxe verificada e testes automatizados da transcrição/cache e preservação do texto novo passaram. Não foi feita nova geração real de fala nesta atualização. O relatório do usuário confirmou que os pesos Fish já foram baixados e carregados com CUDA.

Pacote de fontes e scripts de compilação, sem EXE compilado.
