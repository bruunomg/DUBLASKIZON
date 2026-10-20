# DUBLASKIZON V87.56

- Alinhamento aproveita espaço vazio antes de um bloco de fala quando isso evita acelerá-lo. Continua usando pausas posteriores e respeitando os blocos já encaixados, a duração total e o limite de velocidade. Não desloca a fala para trás se ela já cabe naturalmente. Isso reduz a compressão desnecessária causada por grandes pausas iniciais; não garante sincronização palavra por palavra.
- DUBLAR PARTE DO ÁUDIO ORIGINAL fica ao lado de DUBLAR PARTE DO TXT na janela Ouvir Cena.
- A nova janela abre o editor de ondas existente sobre uma cópia do original guardada em revisoes/partes_txt/<identidade>/rascunhos_audio. A onda inferior é o RECORTE DO ORIGINAL — EDITÁVEL; a superior mantém o original para comparação. Os controles de divisão, recorte, remoção de silêncio, volume, duração, desfazer e refazer continuam disponíveis.
- Edite o texto da parte e clique SALVAR E DUBLAR RECORTE. A geração usa uma cópia fixa do recorte salvo, não o original completo nem a voz modelo cadastrada. O recorte e a parte dublada são publicados juntos em revisoes/partes_txt/<identidade>/parte_NNNN, com original.wav, parte.wav, texto.txt e info.json.
- A coluna lateral se chama PARTES DO TXT E DOS ÁUDIOS ORIGINAIS DUBLADOS. Partes de áudio original aparecem com botão roxo e abrem o recorte correspondente junto do resultado.
- Nenhuma dessas ações substitui WAV ORIGINAIS, o TXT principal ou a dublagem da cena principal.

Validação: 165 testes de lógica aprovados, 6 testes do player e 1 teste nativo da nova janela. O teste da janela editou e salvou uma cópia real e confirmou que o original ficou intacto. Geração da parte validada com motor simulado; sem nova síntese no projeto do usuário nesta atualização.

Executável e fontes incluídos; modelos e dependências de inferência permanecem externos.
