# V87.42

- Redublagem de áudio personalizado na janela Ouvir Cena deixa de esperar indefinidamente pelo motor: interrompe após 10 minutos sem novas mensagens ou 30 minutos no total.
- Interrupção e cancelamento encerram o subprocesso, preservam o áudio anterior e seguem o fluxo de falha que libera a interface.
- Redublagem personalizada também usa a preservação de pausas em reticências introduzida na V87.41.
- Limites aplicados somente quando o destino é áudio personalizado. Não confirma a causa do travamento no computador do usuário.
- Oito testes passaram e o teste de destino da redublagem foi validado.
- Código e scripts, sem EXE compilado.
