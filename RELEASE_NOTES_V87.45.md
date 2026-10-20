# V87.45

- Clonagem + Dublagem: RETOMAR PENDENTES pula saídas WAV existentes com mais de 44 bytes e inclui novamente cenas sem saída, inclusive após interrupção.
- IGNORAR ÁUDIOS COM ERROS REGISTRADOS exclui erros do histórico salvo das novas execuções. Desative para tentar novamente; histórico anterior à implementação não é recuperado automaticamente.
- DUBLAR SOMENTE SELECIONADOS utiliza seleção múltipla com Ctrl e Shift; respeita a política existente de sobrescrita.
- Histórico por projeto em revisoes/_controle_lote/clonagem.jsonl, gravado incrementalmente, sem reescrever toda a fila por cena.
- 20 testes passaram. Interface com 51 mil arquivos e GPU do usuário não testadas nesta atualização.
- Código e scripts, sem EXE compilado. Reinicie a aplicação atualizada para carregar os controles.
