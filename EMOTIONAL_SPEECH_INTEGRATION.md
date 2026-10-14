# Sistema dinâmico de tags emocionais

Implementação reutilizável em `emotional_speech.py`, integrada ao botão DUBLAR
da aba Texto para Fala a partir da V87.5. Configure as gravações emocionais em
CONFIGURAR REAÇÕES DA VOZ SELECIONADA. O exemplo `example_emotional_speech.py` usa os comandos e o
ambiente já gerenciados pelo Dublaskizon; não instala dependências adicionais.

## Como funciona

```python
from emotional_speech import parse_emotion_tags, VoiceProfile

segments = parse_emotion_tags("Olá. [alegre] Tudo bem? [sussurro] Segredo nosso.")
# [{"emocao": "neutro", "texto_limpo": "Olá."},
#  {"emocao": "alegre", "texto_limpo": "Tudo bem?"},
#  {"emocao": "sussurro", "texto_limpo": "Segredo nosso."}]

profile = VoiceProfile({
    "neutro": "vozes/andre/neutro.wav",
    "alegre": "vozes/andre/alegre.wav",
    "sussurro": "vozes/andre/sussurro.wav",
}, name="André")
```

Cada referência deve conter a voz do mesmo personagem, realmente falando com
a emoção correspondente. A emoção é conduzida pela referência; a tag é removida
antes da síntese. A fidelidade depende do modelo e das gravações e não é garantida
somente pelo parser. Nenhum efeito artificial de tom ou velocidade é aplicado.

Uma tag vale até a próxima tag. Texto sem tag usa `neutro`. Nomes ignoram maiúsculas
e acentos. Emoções desconhecidas, referências ausentes e referências vazias usam
o WAV neutro. O neutro é obrigatório. Marcadores antigos como
`[[EXPRESSAO:sussurro]]` também são aceitos. Colchetes são reservados às tags;
escreva indicações que devam ser faladas entre parênteses.

## Gerar com o motor configurado

```python
import batch_tab
from example_emotional_speech import generate_with_dublaskizon

result = generate_with_dublaskizon(
    "[alegre] Olá! [sussurro] Vem cá, não conte a ninguém.",
    profile,
    "saida/andre.wav",
    model=batch_tab.MODEL,
    language="Portuguese",
    pause_ms=150,
)
print(result.output_path)
# result.references informa a referência usada e os fallbacks por trecho.
```

Execute em um worker, fora da thread do Tk. O exemplo inclui tratamento de erro
e envio por Queue. Consuma essa fila com `root.after` para atualizar as barras,
mostrar o fallback neutro e exibir erros sem fechar o programa.

O adaptador envia `--text`, `--ref_audio` e `--output` aos comandos F5/OmniVoice
existentes. O idioma deve ser suportado pelo modelo: o F5 Russian do Dublaskizon
não deve ser escolhido para português. Quando o motor precisa da transcrição da
referência, seu backend deve reconhecê-la ou fornecê-la a partir do áudio de cada
emoção. Não use o texto novo como transcrição da referência.

## Integrar outro backend Python

Implemente o protocolo abaixo e passe a instância a
`generate_expressive_speech(text, profile, engine, output_path)`:

```python
class MyEngine:
    def synthesize(self, text, ref_audio_path, output_path):
        # Chamar seu backend com o texto limpo e a referência selecionada.
        # Salvar um WAV completo em output_path; levantar erro em caso de falha.
        ...
```

O protocolo não exige importar Torch, OmniVoice ou F5 na interface.

## Saída e segurança dos arquivos

- Os WAVs são unidos na ordem do texto, com 150 ms de silêncio entre trechos por
  padrão, sem silêncio adicional no início ou no fim. A pausa é configurável.
- WAVs PCM com o mesmo formato são concatenados sem recodificar as amostras.
- Para WAVs float ou formatos diferentes, use `FFmpegNormalizer`, que converte
  todos para PCM 24-bit, 24 kHz, mono por padrão; taxa e canais são configuráveis.
  O exemplo o ativa quando encontra o FFmpeg da ferramenta.
- Falha de qualquer trecho interrompe a operação; nenhum resultado parcial
  substitui o arquivo final. A saída existente é preservada.
- Temporários são limpos ao concluir ou falhar. Referências não são sobrescritas.
- Não há verificação automática por ASR: ela não bloqueia frases curtas e
  sussurradas por falsos negativos. A geração de todas as palavras e a qualidade
  emocional devem ser avaliadas ouvindo a saída do motor real.

## Testes

```text
python -m unittest test_emotional_speech
```

Os testes usam WAVs sintéticos e um motor simulado para conferir seleção das
referências, tags, fallback, pausas, erro por trecho, formatos, áudio truncado,
proteção da saída e limpeza. Eles não avaliam a emoção produzida por um modelo.

O Dublaskizon V87.5 já inclui o módulo nos manifests de compilação e na auditoria
do executável. Para outras integrações com importação dinâmica, acrescente
`--hidden-import emotional_speech` ao PyInstaller. Não embarque modelos ou
runtimes de IA no EXE.
