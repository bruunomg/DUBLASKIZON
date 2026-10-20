# V87.26

- ORGANIZAR ONDAS na janela Ouvir cena, à esquerda de DESFAZER, disponível no modo EDITAR com original e dublado.
- Alinhamento de blocos em segundo plano usando uma cópia da edição. Original e WAV dublado ficam intactos até SALVAR; DESFAZER restaura a edição anterior.
- Divisões anteriores são recalculadas ao organizar as ondas. Limite de alteração de 100%; resultados inviáveis mantêm a edição anterior com mensagem.
- Recarrega a faixa editável após redublar se não há alterações pendentes. WAV incompatível com wave usa decodificação alternativa via pydub na onda e no editor.
- 155 testes de regressão e 3 testes nativos da janela passaram. Não houve validação auditiva do áudio citado.
