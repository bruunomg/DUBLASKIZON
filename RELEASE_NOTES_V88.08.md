# DUBLASKIZON V88.08

## Preparar os textos antes da síntese

- Na janela Transcrever → traduzir → dublar, à esquerda de APLICAR, a opção TRANSCREVER E TRADUZIR TUDO ANTES DE DUBLAR começa ativada. A mesma opção fica abaixo de TRANSCREVER E TRADUZIR QUANDO FALTAR TXT na aba Clonagem + dublagem. A configuração é sincronizada e salva.
- Com a tradução automática ativada, faz uma varredura dos áudios da fila. Somente TXTs ausentes ou vazios são preparados; textos existentes não são substituídos. Primeiro transcreve todos os pendentes, depois pesquisa o tema se escolhido, depois traduz. Só então começa a síntese das cenas prontas.
- Desativar a opção mantém o fluxo anterior por cena. Ela depende de TRANSCREVER E TRADUZIR QUANDO FALTAR TXT estar ativado.
- Ao iniciar uma fila com tradução automática, o aviso de tema oferece Sim para abrir a janela de tema da aba Transcrever e traduzir, Não para continuar sem tema e Cancelar para não iniciar. O tema é opcional. A pesquisa usa a IA configurada, pode cobrar API e alimenta contexto, glossário e vocabulário antes da tradução.
- Resultados de preparação ficam em revisoes/preparacao_textos, identificados pelo áudio e pelas configurações. Resultados compatíveis são reaproveitados em nova execução. Etapas ainda não concluídas podem ser refeitas. Cenas com erro de preparação são registradas, preservadas e não iniciam síntese sem texto.
- Transcrições preparadas são reaproveitadas na tradução, inclusive por tradutores locais, sem repetir o reconhecimento de fala.
- As preferências do transcritor/modelo/idioma continuam sendo as selecionadas. A preparação não altera o modelo de voz e não corrige falhas de conexão durante o download de modelos.

Mantidos alinhamento, acabamento, revisão, preservação dos originais e controles existentes. Pequenos espaços vazios foram reduzidos para acomodar a opção sem esconder botões na escala de 25%.
