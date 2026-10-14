# Dublaskizon V86.93

- Botão ABRIR PASTA DE SAÍDA na aba Texto para Fala e no painel de resultados.
- Áudios provenientes de WAV ORIGINAIS preservam nome e subpastas em TEXTO PARA FALA/WAV ORIGINAIS TEXTO para FALA.
- Referências adicionadas separadamente geram em ÁUDIO ORIGINAL TEXTO para FALA; vozes pessoais em VOZ MODELO TEXTO para FALA; perfis do sistema em DO SISTEMA TEXTO para FALA.
- Gerações adicionais recebem sufixo numérico, preservando resultados anteriores.
- Painel de áudios gerados à direita do editor, filtrado pelo modo selecionado e atualizado após geração.
- Duplo clique e OUVIR CENA usam o visualizador de ondas existente, com navegação, edição de áudio e texto da geração, e a referência correta.
- Risadas usam [laughter]; suspiros [sigh]; surpresa [surprise-oh]; dúvida [question-oh]; descontentamento [dissatisfaction-hnn]. Tags ficam na posição em que foram inseridas no texto.
- Removida a falsa associação de tristeza/alegria à altura da voz. Esses estados dependem da referência emocional. Sussurro continua sendo um atributo global de estilo.
- Somente gerações concluídas entram na lista; arquivos temporários são removidos ao falhar/cancelar.

Fontes verificadas: https://github.com/k2-fsa/OmniVoice (tags não verbais), https://github.com/k2-fsa/OmniVoice/releases (última release 0.2.1), https://huggingface.co/edwixx/omnivoice-brpt-v15/tree/main (mesma revisão publicada). Nenhuma atualização confirmada promete controle consistente de emoção por frase.

Validação: oito testes passaram (hierarquia, proteção contra sobrescrita, categorias, tags e manifestos); compilação sintática aprovada. Síntese real e inspeção visual não foram realizadas neste ambiente, cujo Tcl/Tk local está inválido. O ZIP entrega os fontes e os compiladores, sem EXE novo.
