# Dublaskizon V87.6 — banco nativo de reações

A aba Texto para Fala inclui vozes brasileiras masculina e feminina com
referências de alegria, tristeza, raiva e neutro, selecionadas do emoUERJ.
Sussurro e surpresa usam gravações alemãs do Thorsten-Voice. Autoria, licença,
arquivos originais, idioma e SHA-256 estão em emotional_voices/manifest.json e
ATTRIBUTION.txt. As gravações estão incluídas neste pacote e na configuração do
EXE; não é necessário procurar áudios para cadastrar.

## Uso

1. Selecione um áudio em Original ou Escolhido por mim, ou uma das vozes brasileiras
   nativas em Do sistema.
2. Mantenha REAÇÕES NATIVAS AUTOMÁTICAS ativado. O banco masculino/feminino escolhe
   a interpretação doadora; a voz alvo continua sendo o áudio selecionado.
3. Escreva o texto e clique nos botões para inserir [alegre], [triste], [raiva],
   [sussurro] etc. Todas as 21 expressões estão em uma grade compacta, clicável.
4. Clique em DUBLAR. Quando necessário, o programa prepara automaticamente o
   conversor e adapta a referência emocional ao timbre alvo. Também há o botão
   PREPARAR REAÇÕES NATIVAS para fazer a instalação antes da geração.

O cadastro de referências próprias permanece opcional e tem prioridade. Os
resultados continuam nas pastas por modo, com Ouvir cena e texto editável.

## O que a nova fórmula faz

Para um áudio seu, Seed-VC V1 converte o timbre da gravação emocional doadora para
a voz selecionada. OmniVoice/F5 usa essa referência adaptada para sintetizar o
novo texto em português. As referências adaptadas são reutilizadas por emoção,
conteúdo do áudio alvo e versão do conversor. Uma mudança na referência gera um
novo cache, sem substituir o áudio original.

As vozes brasileiras nativas já têm suas próprias gravações emocionais em
português e usam essas referências diretamente. Para elas, alegria/tristeza/raiva
não precisam do conversor adicional. Sussurro/surpresa ainda podem precisar dele.
Riso, suspiro e interjeição de dúvida usam tags de sons não verbais documentadas
pelo OmniVoice; F5 não recebe esses comandos exclusivos do OmniVoice.

Não há banco nativo verificado de todas as 21 expressões. Tags como grito/choro,
sem referência própria disponível, usam neutro e mostram o aviso no relatório.
Não são apresentadas como emoções efetivamente aplicadas. Animado utiliza a
referência alegre; descontente utiliza raiva, como aproximações declaradas.

Essa adaptação não garante emoção, identidade vocal ou sotaque idênticos. As
referências brasileiras priorizam português; o banco complementar alemão pode
influenciar a pronúncia, especialmente em sussurro/surpresa. A intensidade final
depende dos modelos e deve ser conferida ouvindo o resultado.

## Requisitos e armazenamento

O Seed-VC oficial usa revisão fixa, código verificado por SHA-256 e ambiente
isolado. Instala PyTorch/torchaudio compatíveis, sem alterar OmniVoice/F5/Fish.
Os botões 1/2/3 de Requisitos passam a instalar, baixar e testar esse recurso
quando Incluir reações nativas automáticas estiver marcado. Ambientes e modelos
existentes são reutilizados. Tudo fica em runtime/native-emotions e é abrangido
pelo botão DESINSTALAR TUDO, incluindo o cache de referências adaptadas.

NVIDIA usa CUDA 12.8; em computadores sem NVIDIA, o conversor adicional usa CPU.
Não foi testada aceleração AMD para Seed-VC nesta versão. Isso não altera os
modos AMD das outras ferramentas. Modelos/pacotes adicionais ocupam GB fora do
EXE; nesta máquina, a instalação do conversor ocupou cerca de 8,65 GB. O EXE leva
somente o banco pequeno de gravações e o código do aplicativo.

Exportação da referência Seed-VC corrigida para PCM 24-bit, pois o WAV float do
upstream não era aceito pelo leitor wave. Aplica redução uniforme de volume
somente quando necessária para evitar clipping na exportação. Não altera
velocidade nem tom. Temporários são limpos em sucesso/falha/cancelamento.

## Validação

80 testes automatizados passaram, incluindo banco e checksums, cache por voz,
falha do conversor, referências próprias, WAV PCM, concatenação e manifests.
Teste Tk real verificou a grade de 21 expressões, as duas vozes nativas, seleção
de áudio e janela opcional de referências.

Teste real com CUDA executou Seed-VC para adaptar uma referência alegre feminina
brasileira à voz BAC_078_Trishka, e gerou WAV com OmniVoice BR-PT. O reconhecedor
Whisper-small retornou: “Olá, André! Que bom encontrar você aqui!”. Isso confirma
o conteúdo reconhecido neste exemplo, não a qualidade emocional ou semelhança
vocal; não houve avaliação auditiva dessas características.

Fontes oficiais:
- https://zenodo.org/records/5427549 — emoUERJ, CC BY 4.0.
- https://huggingface.co/datasets/Thorsten-Voice/TV-44kHz-Full — CC0 1.0.
- https://github.com/Plachtaa/seed-vc — conversor oficial, GPL-3.0.
- https://github.com/k2-fsa/OmniVoice/blob/master/docs/voice-design.md — atributos
  de desenho de voz, que não oferecem separação independente de todas as emoções.

Entrega: fontes completos, referências nativas e scripts de compilação. Não
inclui novo EXE compilado.
