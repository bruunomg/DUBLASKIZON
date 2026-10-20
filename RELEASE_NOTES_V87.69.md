# DUBLASKIZON V87.69

Motor na memória imediatamente à direita de Atualizar tela, com regulagens salvas: prazo de inatividade (0 sem prazo), quantidade de redublagens para reconhecer sequência fora da Revisão, proteção enquanto Revisão/Ouvir cena estiver aberta e reserva de RAM. Revisão aberta ou Ouvir cena reconhece o trabalho imediatamente. A segurança por pouca RAM continua válida e a razão da liberação fica visível.

Estado confirmado pelo processo de inferência: síntese e conferência separadas, PID real, GPU alocada/reservada pelo PyTorch. PRONTO exige síntese e conferência carregadas; síntese pronta sem conferência indica carga parcial. Durante troca de modelo, o trabalhador comunica que está descarregado/carregando. Desativar durante uma fala informa que a liberação ocorrerá ao finalizar.

Transcrição/tradução libera o cache ocioso da síntese antes de preparar seus próprios modelos. Geração manual e preparação são serializadas para não sobrepor modelos na mesma memória. Ao voltar à síntese pode ser necessário recarregar; não é informado como pronto enquanto estiver descarregado. As últimas escolhas da janela Transcrever → traduzir → dublar são salvas em runtime/translation-last-settings.json e reaplicadas na abertura, inclusive ao trocar de projeto.

Revisão mostra totais acima de Ouvir cena/Ouvir todos: Padrão total, sem avaliação, Avaliar, Aprovadas e Rejeitadas. Contagens respeitam a fonte normal/personalizada e são calculadas no processamento da lista existente, sem nova varredura do projeto.

Regulagens de cache em runtime/review-memory-settings.json. A opção de ativar continua desligada em cada nova abertura. Modelos residentes ocupam RAM/VRAM; tempo e uso dependem do hardware. As mudanças não reduzem parâmetros da síntese/conferência nem prometem eliminar qualquer falha de modelo/driver/tradutor.
