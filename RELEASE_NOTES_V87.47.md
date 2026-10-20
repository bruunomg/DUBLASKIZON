# V87.47

- Clonagem + Dublagem limita a conferência a duas tentativas por trecho, sem recuperação recursiva; qualidade de síntese mantida, falas não confirmadas ficam REVISAR. Menor esforço de recuperação automática é a contrapartida do limite.
- Conferência transcreve em janelas de até 26 segundos para evitar a falha de Whisper em áudios acima de 30 segundos.
- Fechamento explícito dos arquivos exportados pelo alinhamento antes de substituir/remover, corrigindo fonte de bloqueio de arquivo no Windows.
- Fila e posição salvas separadamente; Iniciar continua fila interrompida e Retomar conserva seleção anterior, inclusive após reiniciar. Cena interrompida é tentada novamente.
- Estados recuperados de histórico e relatórios. WAV anterior sem comprovação aparece EXISTENTE; erros antigos sem registro não podem ser inferidos.
- 66 testes passaram. Não medido o desempenho real da fila de 51 mil áudios, nem reproduzido todo o caso no computador do usuário.
- Código e scripts, sem EXE compilado.
