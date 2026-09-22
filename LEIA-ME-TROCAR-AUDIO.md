# Versão 13 — abas e troca de áudio

Todas as abas ficam em uma única linha, no topo, com altura e largura uniformes.
Se a janela não comportar a linha inteira, use a barra de rolagem horizontal abaixo das abas.
A ordem final é: REDIMENSIONAR ÁUDIO → COMPACTAR / CONVERTER VÍDEOS → TROCAR AUDIO DO VÍDEO → COMANDOS.

TROCAR AUDIO DO VÍDEO possui três painéis:
- Áudios dublados: arrastar/adicionar, ouvir por botão ou duplo clique.
- Vídeos originais: arrastar/adicionar e visualizar no player integrado.
- Áudios originais extraídos: lista os WAVs dos vídeos carregados; botão Ouvir e duplo clique.

ABRIR PASTA DE DESTINO DOS VÍDEOS DUBLADOS abre a pasta do vídeo selecionado (ou do primeiro carregado).
A dublagem é aplicada nos próprios vídeos carregados, como nos BAT originais.
EXTRAIR ÁUDIOS ORIGINAIS WAV exporta as faixas antes de aplicar dublagem, sem modificar os vídeos.
APLICAR DUBLAGEM também extrai o backup automaticamente, caso ainda não exista.
A repetição da aplicação não sobrescreve os WAVs originais.

## Backups WAV

O backup agora contém apenas áudio WAV PCM 16-bit e um manifesto pequeno, não uma cópia completa do vídeo.
Todas as faixas de áudio são extraídas. Vídeos sem áudio são registrados para que a reversão volte a deixá-los sem áudio.
Cada vídeo tem sua subpasta, e faixas adicionais têm subpastas próprias. Nenhuma dessas pastas acumula mais de 100 arquivos.
O nome do WAV corresponde ao nome do vídeo. As subpastas com identificadores evitam misturar cenas de mesmo nome em locais diferentes.
O WAV sem compressão pode ainda ser grande, mas não contém a imagem do vídeo.

REVERTER DUBLAGEM reinsere as faixas originais. A imagem continua sem recodificação.
Isso não restaura o arquivo inteiro byte por byte: o áudio pode ser recodificado para um codec aceito pelo contêiner, por exemplo AAC no MP4.
Para reverter, mantenha os vídeos nos mesmos caminhos e selecione a mesma pasta de backup.
Backups danificados são recusados antes de modificar o vídeo.

## Backups antigos BIN

Ao extrair/aplicar/reverter, a ferramenta reconhece os backups BIN da versão 12 na pasta de backup selecionada.
Ela confere a integridade do BIN, extrai os áudios dele (não da versão já dublada), verifica os WAVs e grava o novo manifesto.
Somente depois dessa validação o BIN antigo é removido para liberar espaço. O manifesto antigo passa a apontar para o novo.
Backups WAV dos BAT antigos não são importados automaticamente.

## GitHub / organização

O pacote possui no máximo 100 arquivos diretamente em cada pasta; a contagem é verificada ao empacotar.
Caches Python/pytest foram removidos do ZIP. O .gitignore exclui backups e arquivos de mídia gerados para não incluí-los por engano no repositório.
O limite pedido é aplicado por pasta, não ao total de arquivos de todas as subpastas.

Testes reais: extração WAV comparada ao áudio original decodificado, preservação dos quadros de vídeo,
reaplicação, reversão de várias faixas, migração de BIN, rejeição de backup corrompido e vídeo sem áudio.
Interface completa não validada visualmente neste ambiente.
