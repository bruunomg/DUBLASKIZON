# DUBLASKIZON V87.15

Corrigida a lentidão introduzida pelo pós-processamento obrigatório na
Dublagem Personalizada, inclusive na redublagem de personalizados pela
Revisão e pela janela Ouvir Cena.

Antes, mesmo com o alinhamento desligado, `match_original_expression`
alterava a velocidade para forçar a duração do original. Uma fala curta
gerada com voz-modelo podia ficar muito lenta se o WAV original era longo.
O fluxo de Dublar parte do TXT não executava esse pós-processamento.

Agora, com ALINHAR RITMO E DURAÇÃO AO ORIGINAL desligado, a saída gerada
é preservada integralmente, sem alterar velocidade, duração ou aplicar
o envelope de pausas/intensidade do original. A síntese continua usando
a voz-modelo selecionada e a conferência de texto das versões anteriores.

O alinhamento opcional continua funcionando quando ativado, respeitando
o limite de alteração configurado. Para manter a duração natural, deixe
essa opção desligada. A descrição da aba e o status foram ajustados;
o manifesto registra se houve alinhamento ou preservação do ritmo natural.

Áudios antigos já esticados não são modificados automaticamente: reduble
com o alinhamento desligado. Projetos, vozes-modelo e TXTs são preservados.

124 testes automatizados passaram. Os testes novos simulam a síntese
e usam WAVs reais: original de 4 segundos e geração de 1 segundo.
O lote personalizado e a redublagem pela Revisão preservam todos os bytes
da geração, mantêm os originais e conservam o backup da versão anterior.
Outro teste confirma que o alinhamento explicitamente ativado é chamado.
Não foi feita uma nova avaliação acústica do motor nesta alteração.

O ZIP contém fontes e scripts de compilação; não contém EXE pré-compilado.
