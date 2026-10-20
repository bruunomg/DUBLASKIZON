# DUBLASKIZON V87.87

- Os três botões TRANSCREVER, TRADUZIR TEXTO e TRANSCREVER E TRADUZIR abrem uma escolha de ordem: somente a etapa solicitada, transcrever todo o lote antes de traduzir ou concluir cada arquivo antes do próximo. REVISAR TRADUÇÃO mantém a execução específica da revisão.
- No modo por etapas, múltiplas transcrições usam um único processo local e reutilizam o modelo Whisper carregado. O processo é encerrado antes da etapa de tradução, evitando manter o transcritor junto com o tradutor. Transcrição isolada em lote também reutiliza o modelo.
- Falhas comuns em um arquivo ficam registradas e não impedem os demais de continuar. Cancelamento e falha nativa do processo continuam interrompendo com aviso; TXTs já publicados permanecem salvos.
- ADICIONAR ARQUIVOS, ADICIONAR PASTA, REMOVER SELECIONADOS e LIMPAR JANELA ficam imediatamente acima de PROCESSOS.
- Durante o processamento é possível selecionar arquivos e consultar os textos já disponíveis. Os textos ficam somente para leitura até a operação terminar.
- Finalizados sem alertas recebem [OK] em branco; avisos/falhas recebem [REVISAR] em amarelo. As justificativas aparecem junto da lista e nos metadados em revisoes.
- Sinais para REVISAR incluem baixa confiança reportada pelo Whisper, possível repetição, idioma detectado incompatível com a origem configurada ou indicação do nome do arquivo, saída vazia e diferenças suspeitas em comprimento/tags. São sinais para revisão humana, não certificação de acerto ou erro semântico. OK indica etapas concluídas sem esses alertas.
- As atualizações de estado usam índices da lista e preservam a seleção, evitando percorrer todos os itens a cada resultado.

Validação: 78 testes. Em teste real com modelo small em CPU e duas execuções da mesma amostra curta já em cache, as transcrições chegaram em 5,57 s e 7,52 s desde o início (segunda amostra aproximadamente 1,95 s após a primeira); total 7,84 s. Não é previsão de desempenho para large-v3 ou para outros áudios. Nenhum modelo foi baixado para esse teste.
