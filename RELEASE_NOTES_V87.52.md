# DUBLASKIZON V87.52

- Conferência OmniVoice: detecta inserções no início, meio e fim, anteriormente ignoradas mesmo quando todas as palavras solicitadas estavam presentes. Refaz os trechos e prioriza tentativas sem acréscimos. Se os acréscimos detectados persistirem, conserva a amostra no diretório de conferência e preserva a saída anterior, sem publicar essa tentativa como final.
- Reconhecimento de voz pode errar ou omitir palavras: a verificação não é garantia de fidelidade absoluta. Divergências de grafia sem inserção continuam seguindo o fluxo de revisão já existente.
- Revisão: ordenação Avaliar primeiro, incluindo cenas adicionadas durante o processamento.
- Todas as listas e árvores da aplicação principal permitem seleção estendida com Ctrl e Shift. O rodapé mostra a quantidade selecionada na lista em uso. A seleção múltipla na Revisão não é mais reduzida a uma única cena pelo carregamento dos detalhes.

Validação: 154 testes de lógica e 2 testes nativos da interface aprovados. O relatório existente de V008__moha_igc_eog foi inspecionado; não houve nova síntese nem alteração do áudio do projeto.

Distribuição: código-fonte e scripts; não inclui novo executável compilado ou modelos.
