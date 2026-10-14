# DUBLASKIZON V87.18

## Preservação do final das palavras

A síntese conferida do OmniVoice não aplica mais o recorte automático de
silêncios na saída. Finais fracos, respirações e pausas são preservados.
O fade das bordas passa de 100 ms para 5 ms, mantendo o preenchimento de
silêncio nas bordas. Não há mudança da velocidade padrão ou redução dos
passos de geração. A fila reutilizável e o modo de pouca VRAM continuam.

## Frases curtas e contexto de idioma

Uma frase final de até duas palavras, como “Prepare-se.”, é agrupada com
a frase anterior quando o total cabe no limite de 20 palavras. Isso evita
sintetizar um comando muito curto sem seu contexto em português. A
conferência considera o bloco inteiro e tenta recuperar palavras omitidas.
Não foram introduzidas instruções de sotaque que o OmniVoice não suporta;
a instrução existente portuguese accent permanece válida.

141 testes automatizados passaram, incluindo preservação dos parâmetros
de velocidade, desativação de recorte, fade curto e contexto da frase final.
As duas cenas informadas foram geradas novamente com a mesma voz-modelo
MON_021_TrishkaSERIA.wav, em uma pasta de teste, sem sobrescrever o projeto.

Reconhecimento de palavras não comprova uma terminação fonética perfeita
nem ausência de sotaque. As novas amostras precisam ser ouvidas, sobretudo
“agora” e “Prepare-se”. A referência e as limitações do motor ainda podem
influenciar a pronúncia. Não há garantia absoluta de sotaque ou prosódia.

Áudios antigos permanecem como estavam; reduble para aplicar as mudanças.
ZIP com fonte e scripts de compilação, sem EXEs pré-compilados.
