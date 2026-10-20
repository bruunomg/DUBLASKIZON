# DUBLASKIZON V87.63

- RECUPERAR DUBLADO ANTERIOR e VOLTAR AO DUBLADO MAIS ATUAL reposicionados no canto direito da linha de ORGANIZAR ONDAS.
- DURAÇÃO EXATA DO ORIGINAL junto aos controles de duração: comprime pelo mesmo conversor dos botões -/+ quando necessário; se menor, conserva a fala e adiciona silêncio apenas ao final. Trabalha na edição, com DESFAZER e SALVAR.
- MOVER ORIGINAL + DUBLADO + TXT PARA LIXEIRA DO PROJETO junto ao título das ondas. Move arquivos do mesmo identificador e caminho relativo nas pastas de áudio original, dublado, dublados personalizados e TXT, mantendo hierarquia e nomes. Outras cenas permanecem intactas; movimentação não faz varredura recursiva do projeto.
- Confirmar ao mover ativado inicialmente, com Sim/Não. Preferência pode ser desativada e fica salva por projeto. Edições de áudio/TXT pendentes ou dublagem em andamento bloqueiam a movimentação.
- lixeira do projeto mantém os caminhos relativos; se já houver um arquivo, o novo movimento fica em movimentos anteriores/<identificador>, sem sobrescrever. Registros de origem/destino ficam em _registros. Falha de movimento provoca devolução aos locais originais; falha de devolução informa os arquivos que permaneceram preservados na lixeira.
- Recortes temporários não movem a cena inteira: botão de lixeira fica desativado nas janelas de partes.

Validação: testes de isolamento de cenas, hierarquia, colisão, devolução após falha, compressão pelo mesmo conversor e preenchimento com silêncio. Interface nativa testada em janelas largas/estreitas e confirmação cancelada/desativada. 13 testes de lógica e 9 de interface passaram. O conversor requer as mesmas ferramentas FFmpeg/SoX já utilizadas nos controles -/+.
