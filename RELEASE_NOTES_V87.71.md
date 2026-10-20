# DUBLASKIZON V87.71

Proteções de recursos para áudio longo: ondas calculadas em blocos com audioop, sem listas Python por amostra nem cópias float64 de toda a faixa para desenhar o fundo. Teste PCM estéreo de três minutos mantém no máximo 5600 picos e menos de 4 MB de memória auxiliar.

Textos a partir de 120 palavras ou duração explícita a partir de 45 segundos alternam síntese e conferência no trabalhador em memória, reduzindo a disputa de VRAM e o risco de uso da memória gráfica compartilhada. Os parâmetros de qualidade e a conferência de palavras permanecem os existentes. A marcação de memória é restaurada após o pedido.

Reserva mínima do cache passa a 1 GB para preservar a interface gráfica; abaixo de 768 MB livres a liberação ociosa é imediata, enquanto quedas passageiras acima desse patamar continuam com tolerância. Pré-carga e cache continuam disponíveis. Ajustes salvos de tempo/revisão são preservados na migração da reserva.

Clonagem + dublagem: margens verticais agora acompanham a escala, controles adicionais deixam a coluna do botão Iniciar e usam duas colunas, lista/log usam o espaço restante e a área da aba acompanha a altura da janela. Teste em 1600x780 a 25%: altura mínima 687, sem rolagem externa e com botões visíveis. Em telas menores, rolagem permanece se necessária para não esconder controles. Log visual limitado às linhas recentes; histórico central continua recebendo as mensagens.

O aviso CreateDIBSection é uma falha de alocação gráfica do Windows. A imagem isolada não permite atribuir uma causa única nem garantir que todo fechamento por recursos/driver seja eliminado. Esta versão trata pressões e custos concretos encontrados no código, preservando os áudios e o fluxo existente.
