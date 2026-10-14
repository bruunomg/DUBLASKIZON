# DUBLASKIZON V87.57

## Interface do recorte

- Onda e barras do recorte original em laranja, mantendo a dublagem gerada em verde.
- SALVAR E DUBLAR RECORTE em laranja.
- Reprodução de partes identificada como INICIAR PARTE DO DUBLADO.
- Indicadores de clonagem e dublagem no editor do recorte, atualizados a partir das mensagens reais do processo. Cancelamento e tratamento de falhas mantidos.

## Recuperação de fala no OmniVoice

- Detecta sequências de três ou mais palavras idênticas em português. Gera a palavra em uma frase auxiliar com tempo suficiente, localiza o trecho por transcrição com tempos, exclui o texto auxiliar e monta exatamente a quantidade solicitada usando até duas tomadas independentes. Mantém a voz da referência escolhida. Intensidade, duração e pausas variam conforme o envelope de fala do original, com limites conservadores e alteração de tempo sem alterar o tom. Não transfere a entonação exata nem garante interpretação idêntica ao original.
- Frases curtas junto das repetições também podem ser recuperadas com contexto auxiliar e isolamento de um trecho contendo todas as palavras solicitadas.
- Estimativas de duração muito curtas para falas incompletas acionam nova tentativa com mais tempo. Em resultados empatados, prioriza candidatos que preservem início e fim do texto.
- A transcrição de referências de até 10 s tem limite de 128 tokens para conter reconhecimento que se prolongava indevidamente em referências com hesitações.
- Recuperação compartilhada entre geração de partes e os caminhos OmniVoice das abas principais. Outros motores não foram alterados.
- Os resultados reconstruídos ficam para revisão: o reconhecedor pode exagerar ou omitir a contagem em fala muito repetitiva. Falhas reais do motor continuam preservando arquivos anteriores.

## Verificação real

Cena CS28_E02_0010_N_DEC_0120AA, recorte de 3,59 s e texto com 14 repetições de eu. O teste pelo botão da versão anterior gerou fala reconhecida como Ai! Ai!. A recuperação final identificou eu na frase auxiliar e montou 14 unidades. Whisper Medium independente passou a reconhecer eu no recorte, mas exagerou a contagem; não foi tratado como confirmação automática perfeita.

Na cena inteira, a frase Mas, quando tento me lembrar foi encontrada completa no áudio com contexto auxiliar, isolada e unida às 14 repetições. Arquivos corrigidos salvos em parte_0003/parte.wav e dublado/CS28_E02_0010_N_DEC_0120AA.wav. Parte anterior preservada em parte_antes_V87.57.wav; original e TXT principal preservados. A parte 3 foi reaberta no aplicativo.

173 testes de lógica e 7 testes nativos de interface aprovados. Executável compilado e auditado; modelos e bibliotecas de inferência permanecem externos. O aplicativo aberto usa o código anterior até reiniciar com o novo executável.

## Organizar ondas e distribuição

- pydub incluído no executável, junto com audioop e numpy; auditoria do pacote agora exige essas dependências. Não requer reinstalar os modelos.
- Quando um bloco não precisa mudar de velocidade, preserva seu PCM em vez de passá-lo pelo atempo, evitando alteração e falha de duração em falas curtas.
- Teste real de Organizar ondas com pydub e Silero executado: PCM válido, duração original preservada. Limites de aceleração continuam protegendo a edição.
- Scripts de inferência grandes são guardados em revisoes/_conferencia_fala/_scripts para evitar o limite de caracteres de comandos do Windows.
- Novo recorte com variação conferido por Whisper Medium independente: reconheceu eu, mas exagerou a contagem. Montagem preserva 14 unidades; revisão humana continua necessária. Versão anterior preservada em parte_antes_prosodia_V87.57.wav.
