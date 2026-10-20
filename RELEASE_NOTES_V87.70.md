# DUBLASKIZON V87.70

MOTOR NA MEMÓRIA à esquerda de ATUALIZAR TELA. Perfil pronto padrão: sem prazo de inatividade, retenção desde a primeira fala, revisão protegida e reserva de RAM de 512 MB. Regulagens antigas migram uma vez para este perfil; alterações salvas nesta versão continuam sendo respeitadas.

Ativar prepara o modelo OmniVoice selecionado e a conferência já instalados, em segundo plano e sem gerar áudios. Pré-carga usa somente arquivos em cache. Indicador PREPARANDO durante a carga, PRONTO somente após a confirmação dos componentes reais. A redublagem espera a preparação e reutiliza o mesmo processo. Não ocupa memória artificialmente para preencher o gráfico do Gerenciador.

Removido o piso oculto de 10% da RAM para este cache. Queda passageira abaixo da reserva tem tolerância de 30 segundos; menos de 256 MB livres ou pressão persistente libera o motor. Temporários de cada pedido são descartados sem descarregar os modelos e as referências em cache. Desligar e preparar transcrição/tradução continuam liberando o cache quando necessário. A voz de referência é preparada quando escolhida/usada.

Testes cobrem pré-carga sem gerar fala, reutilização do PID, migração das regulagens, pressão de RAM, cancelamento e compatibilidade com tradução. Arquivo principal do pacote acompanha a versão real.
