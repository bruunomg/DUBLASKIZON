# DUBLASKIZON V87.12

Nova opção, ativada por padrão: **CONFERIR SE A FALA CONTÉM TODO O TEXTO — OmniVoice**.
Disponível em Clonagem + Dublagem, Dublagem Personalizada, Revisão e Texto para Fala.
É compartilhada por projeto e salva em `Dublaskizon_conferencia_fala.json`.
Redublagem pela janela Ouvir Cena e geração de partes também respeitam a opção.

## Funcionamento

O adaptador do OmniVoice gerenciado divide textos longos em trechos de até
35 palavras, sem remover palavras. Usa a mesma referência durante os trechos.
Transcreve o áudio gerado com o Whisper do próprio ambiente e compara as
palavras reconhecidas com o texto enviado à síntese. Ignora pontuação,
acentos e algumas contrações equivalentes; tags de sons não verbais não
são contadas como palavras faladas.

Se houver divergência, tenta gerar o trecho novamente, até três tentativas,
com mais passos de geração. Trechos confirmados são concatenados com uma
pausa de 100 ms. Quando uma duração total é explicitamente solicitada ao
motor, ela é repartida entre os trechos sem acrescentar essas pausas.

Se não confirmar um trecho, não publica a sequência parcial como áudio
final. Guarda a última amostra e o relatório do trecho em
`revisoes/_conferencia_fala`, mostrando o caminho no erro. A saída final
anterior e os TXTs originais permanecem intactos. Os processos e o status
mostram o reconhecimento e as novas tentativas.

## Limites

É uma conferência automática, não garantia de áudio perfeito. O Whisper
pode reconhecer incorretamente uma fala correta, especialmente nomes,
interjeições e siglas. Esses casos também seguem para conferência. Pode-se
ouvir a amostra e desativar a opção antes de gerar novamente.

O recurso acrescenta tempo de processamento e utiliza o modelo Whisper
que o OmniVoice já emprega para reconhecer referências. Na ausência do
modelo, o carregador do OmniVoice pode precisar baixá-lo. Se o reconhecimento
falhar, a saída final anterior é preservada.

Esta conferência se aplica ao OmniVoice iniciado pelo ambiente gerenciado
(`python -u -c`). Qwen, F5 e instalações externas via executável/configuração
OMNIVOICE_INFER continuam com seus fluxos anteriores e não recebem esta
conferência nesta versão. Não foi implementado glossário ou conversão de
números nesta atualização.

## Validação

- 112 testes automatizados, incluindo omissão no fim/meio, palavras repetidas,
  palavra cortada, limite de tentativas, aprovação após nova tentativa,
  evidência para revisão e preservação de todos os trechos de texto longo.
- Verificações de integração da Revisão, Personalizada, descoberta inicial,
  destino da redublagem e geração/cancelamento de partes.
- Teste real com OmniVoice BR-PT v1.5 e a referência do projeto Deadpool:
  a frase iniciada em “Que merda? Estou preso...” foi reconhecida inteira
  e salva após a conferência.
- Interface Texto para Fala em escala de 25%: controles e grade visíveis
  sem rolagem externa na área testada de 1900 × 850.

O pacote contém fontes e scripts de compilação; não contém EXE compilado.
Os manifestos incluem o novo módulo e mantêm as bibliotecas dos motores
fora do executável. As versões anteriores do ZIP foram preservadas.
