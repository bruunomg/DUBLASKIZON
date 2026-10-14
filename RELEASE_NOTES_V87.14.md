# DUBLASKIZON V87.14

Corrigido um defeito da conferência que interrompia a recuperação quando
o OmniVoice retornava um trecho vazio. Esse caso seguia diretamente para
erro, antes das novas tentativas e da recuperação em partes menores.

## Mudanças

- Retornos vazios, ausentes, silenciosos ou com amostras inválidas entram
  nas tentativas de recuperação. Áudio vazio não é enviado ao Whisper.
- Se necessário, a recuperação em partes menores também é aplicada a
  esses retornos, respeitando os limites de tentativas e profundidade.
- Frases de seis ou mais palavras podem ser divididas para recuperação.
  O corte procura evitar terminar a primeira parte em artigo ou preposição.
  Não remove palavras do texto.
- Se nenhuma tentativa produzir áudio utilizável, grava um relatório JSON
  e apresenta o aviso de revisão. Não tenta salvar uma variável de áudio
  inexistente, nem cria um WAV falso, nem sobrescreve a saída anterior.
- Quando existe áudio utilizável mas não confirmado, mantém a amostra
  para ouvir e o relatório, como nas versões anteriores.

O ajuste fica no adaptador compartilhado do OmniVoice gerenciado. Vale para
Clonagem + Dublagem, Personalizada, Revisão/Ouvir Cena, partes de TXT e
Texto para Fala, com a conferência ativada. Não é uma regra específica
para um nome de arquivo. Outros erros, como falta de memória, não são
ocultados ou considerados sucesso.

## Verificação

121 testes automatizados passaram. Os novos testes cobrem retorno vazio
seguido de recuperação, todas as tentativas vazias, silêncio, NaN,
recuperação de frase longa após retornos vazios, corte entre palavras e
preservação de arquivos anteriores. As verificações de integração da
Revisão, Personalizada e destino da redublagem também passaram.

Foi testado o WAV original e o TXT atual de
`VO_SP_Nordlys_D_Intro_CommentDepot_C01L01`:

> Eles estão carregando a água pesada no depósito. preciso destruir o que estiver por lá!

A primeira frase foi reconhecida inteira na terceira tentativa e a
segunda na primeira. A amostra final foi salva na pasta de trabalho.
Esse teste real não retornou áudio vazio; o caminho de retorno vazio
foi exercitado por testes controlados. Nenhum arquivo do projeto do
usuário foi substituído durante a verificação.

Não há garantia de geração perfeita em qualquer frase: o motor e o
reconhecimento podem falhar. Esta atualização corrige a interrupção
prematura por retorno vazio e conserva a saída anterior em falhas.

O ZIP contém fontes e scripts de compilação, sem EXE pré-compilado.
