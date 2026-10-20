# DUBLASKIZON V87.76

- Diagnóstico da execução: síntese de 1.47–1.70s com conferência CPU de 28–29s por trecho. A conferência era o gargalo.
- Áudios longos podem conferir na GPU quando há ao menos 3 GiB livres e GPU com pelo menos 7 GiB. CPU permanece para falta de memória e recuperação nativa. Referências curtas e proteção de duração mantidas.
- Revisão também protege referências em cenas normais, além das personalizadas; uma falha nativa recebe uma tentativa com reconhecimento CPU.
- Saída de processos observados e geração de partes/recortes encaminhada em tempo real para Comandos e Processos e mensagens da Clonagem + Dublagem. Inclui início, conferência, tentativas, erro e conclusão.
- Encaminhamento por filas sem modificar widgets em threads de trabalho e sem ciclo de retransmissão. Até 200 eventos por atualização e 1500 linhas recentes nas áreas de registro; progresso repetitivo de carregamento reduzido para proteger a interface.
- 98 testes aprovados antes do empacotamento. O ganho real de desempenho depende da memória disponível; não foi executada outra síntese simultânea à tarefa ativa do usuário.
