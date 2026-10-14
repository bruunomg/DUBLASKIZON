# DUBLASKIZON V87.13

Melhorada a recuperação de falas incompletas no OmniVoice gerenciado.
As opções e os locais de saída da V87.12 permanecem os mesmos.

- Novas tentativas sem duração fixa usam ritmo um pouco mais lento, além
  do aumento de passos, para reduzir a perda de palavras.
- Se três tentativas não confirmarem uma frase de pelo menos oito palavras,
  o programa tenta recuperá-la em duas partes menores. Cada parte continua
  sujeita à conferência. Há limite de profundidade e tentativas; não existe
  repetição infinita. O texto solicitado não é reescrito nem encurtado.
- Reconhece diferenças de espaços em palavras compostas quando a sequência
  de letras é exatamente a mesma, como “casamata” e “casa mata”. Não aceita
  omissões como “deve sendo transportada” em vez de “deve ter mais água
  pesada sendo transportada”.
- Após recuperar as partes, concatena-as. Sem duração fixa, a pausa entre
  partes de recuperação é de 60 ms. Com duração fixa, reparte a duração
  entre as partes e não adiciona essa pausa.
- Se ainda não confirmar, preserva o áudio final anterior e mantém a
  amostra e o relatório em `revisoes/_conferencia_fala`. Na Revisão/Ouvir
  Cena aparece um aviso de conferência com mensagem legível, em vez de
  um diálogo com toda a pilha de erro. O relatório completo continua no
  registro de processos; falhas de outros tipos mantêm seu tratamento.

## Validação

116 testes automatizados passaram, incluindo recuperação simulada da frase
reportada, falha em um trecho menor sem publicar resultado parcial, espaços
em palavras compostas e limites das tentativas. As verificações de integração
de destino da redublagem, Revisão, Personalizada e seleção de pastas passaram.

Teste real com OmniVoice BR-PT v1.5, o WAV original e o TXT da cena Battlefield:
“deve ter mais agua pesada sendo transportada para a casamata.”
A primeira tentativa foi reconhecida sem “para a casamata”; a segunda foi
reconhecida inteira, com “Casa Mata” na transcrição, e a saída foi salva.
Nenhum WAV ou TXT do projeto do usuário foi substituído durante esse teste.

O reconhecimento pode errar. Esta atualização aumenta as possibilidades de
recuperação, mas não garante geração perfeita ou ausência de falhas futuras.
Os motores diferentes do OmniVoice gerenciado continuam fora deste recurso.

Este ZIP contém fontes e scripts de compilação, sem EXE pré-compilado.
