# Dublaskizon V86.80

## Análise MFCC nos Requisitos

A opção **Incluir análise MFCC** aparece ativada logo abaixo de **Incluir Whisper**. Quando selecionada durante a instalação ou reparo, instala `librosa` e `soundfile` no ambiente isolado do Dublaskizon. Como esse ambiente fica no runtime gerenciado, o botão **DESINSTALAR TUDO** calcula e remove também esses componentes.

## Filtro do resultado final

O botão **FILTRAR RESULTADO FINAL** examina as pastas `WAV INGLES` da janela 3. Para cada OGG, calcula novamente a similaridade MFCC, mantém o WAV inglês mais próximo e preserva o WAV de mesmo nome em `WAV PT-BR`. Os outros resultados são excluídos após uma confirmação explícita e cada decisão aparece no registro.

## Tema

Fundos, painéis, textos, entradas, registro, árvores, seleção e botões da nova aba passam a usar a paleta ativa do Dublaskizon.
