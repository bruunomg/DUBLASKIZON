# DUBLASKIZON V88.04

## Pesquisa e preenchimento do glossário

- Consultas incluem o título entre aspas; o filtro exige maior correspondência com a obra e rejeita resultados genéricos com uma palavra em comum.
- A coleta tenta ler até seis páginas públicas HTTPS por rodada, além dos resumos. Extratos lidos são distinguidos dos resumos; falha de leitura preserva a referência parcial. Redirecionamentos e destinos não públicos são recusados.
- A IA pode propor termos contextuais de alta confiança apoiados em trechos literais dos transcritos, mesmo sem uma equivalência de localização encontrada na web. Esses termos entram automaticamente no glossário como IA, nunca como tradução oficial.
- Cada entrada nova identifica origem, sentido e justificativa. FONTE inclui URL e citação; IA identifica proposta contextual. A presença dos dois termos numa citação não basta para provar localização oficial ou aplicação a todas as adaptações.
- Edições manuais novas ficam como USUÁRIO. Entradas antigas sem procedência registrada ficam como ORIGEM ANTERIOR NÃO REGISTRADA, sem atribuição inventada. Regras já cadastradas continuam tendo prioridade.

## Teste real sem tema anterior

Foi usado um perfil novo de The Walking Dead: Onslaught, com contexto, glossário, vocabulário e pesquisa vazios. Entrada: “Piece of shit! Walker's on me! Get off me! Walker's got me!”. A palavra esperada não foi enviada.

A API configurada retornou `walker => errante` e preencheu o glossário, identificando expressamente a escolha como proposta contextual da IA, não localização oficial comprovada. Entrada e saída estão em TESTE_TEMA_LIMPO_V88.04.json, sem credenciais. Não houve alteração do tema do usuário.

Este teste demonstra essa execução; não garante a mesma resposta em toda chamada, modelo ou obra. Os transcritos do teste foram fornecidos como texto, sem repetir a transcrição dos WAVs. Continuam os limites de amostragem do lote, disponibilidade de sites e custo de API. Recomenda-se conferir propostas e dúvidas ao abrir o tema.

Mantidos pausa, retomada persistente, etapas salvas e sinalização do botão do tema.
