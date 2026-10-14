# DUBLASKIZON V87.21

Relatórios .conferencia.json deixam de ser gravados junto dos WAVs.
O novo destino é, dentro do projeto:

revisoes/_conferencia_fala/relatorios/

Os relatórios finais preservam a pasta de origem e a hierarquia da cena,
por exemplo relatorios/dublados personalizados/capitulo/100097641.conferencia.json.
Isso evita misturar avaliações de cenas de mesmo nome ou fontes diferentes.
Relatórios de gerações intermediárias ficam em relatorios/_pendentes,
com identificadores derivados do caminho temporário, e são movidos ao
publicar a saída. Nenhum relatório novo fica nas pastas dos áudios.

A indicação REVISAR continua funcionando pelo novo endereço. Relatórios
antigos ao lado do áudio são movidos para o novo destino quando o estado
daquela cena é consultado. Não há varredura completa do projeto na abertura.
Uma nova geração confirmada limpa o estado anterior daquela saída.
Os WAVs não são alterados pelo deslocamento dos relatórios.

148 testes passaram, incluindo preservação de hierarquia, migração de
relatório antigo, isolamento dos WAVs e manutenção da indicação REVISAR.
A síntese, navegação e fila rápida não foram alteradas.

ZIP com código-fonte e scripts de compilação, sem EXEs pré-compilados.
