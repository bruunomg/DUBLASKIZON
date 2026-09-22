# Compactar / converter vídeos — versão 11

1. Abra a aba COMPACTAR / CONVERTER VÍDEOS (linha abaixo das abas principais).
2. Arraste arquivos/pastas para a lista ou use ADICIONAR VÍDEOS / ADICIONAR PASTA.
3. Escolha formato, qualidade e pasta de saída.
4. Use CONVERTER VÍDEO PARA FICAR MAIS LEVE. O relatório informa os MB antes/depois.
5. Use ABRIR PASTA DE SAÍDA para acessar os resultados. Os originais não são substituídos.

Entradas comuns: MP4, MKV, AVI, MOV, WebM, M4V, MPEG, WMV, FLV, TS, MTS, M2TS, VOB, OGV, 3GP e MXF.
Também é possível selecionar outros arquivos em Todos os arquivos. A aceitação depende dos decodificadores do FFmpeg instalado; entradas sem vídeo são recusadas.
Saídas: MP4/H.265, MKV/H.265, MP4/H.264, MOV/H.264, WebM/VP9 e MKV/FFV1 sem perdas.

O perfil padrão reproduz os parâmetros do script enviado: H.265, CRF 28, preset medium e áudio AAC 128k.
Esse perfil é COM PERDAS. Não reduz a resolução nem impõe outra taxa de quadros, mas não garante qualidade idêntica.
CRF 20 e 16 privilegiam qualidade e podem produzir arquivos maiores.
FFV1 + FLAC é a opção sem perdas de conteúdo decodificado; não garante redução de tamanho.
Vídeo e faixas de áudio são convertidos. Legendas e anexos não são incluídos nesta ferramenta.
Nomes repetidos recebem sufixos. Cancelar remove a saída parcial, mantendo os arquivos já concluídos.

## Visualizar — player integrado v11

Selecione um vídeo e clique VISUALIZAR VÍDEO, ou dê duplo clique.
A própria janela contém a tela do vídeo, os controles e a linha do tempo.
PLAY reproduz ou continua; PAUSE pausa. FECHAR encerra a janela e o processo de reprodução.
ANTERIOR e PRÓXIMO navegam pela lista carregada quando a janela foi aberta.
A linha mostra a posição atual e o tempo total. Clique ou arraste para buscar:
quadros do vídeo são atualizados durante o arraste. Ao soltar, a reprodução continua
se estava tocando; se estava pausada, permanece no quadro escolhido.
A resposta da busca depende da velocidade de decodificação do arquivo/computador.
A janela acompanha o tema do aplicativo e pode ser redimensionada/maximizada.
Atalhos com foco nos controles: Espaço alterna Play/Pause; setas buscam 5 segundos.
A integração da tela utiliza os recursos nativos do Windows com FFplay, sem instalar outro player.

Se faltarem FFmpeg, FFprobe ou FFplay, use PREPARAR FERRAMENTAS (o mesmo instalador portátil já existente no aplicativo).
A prévia não corta o vídeo convertido: a conversão sempre usa o arquivo inteiro.

Referência oficial do player: https://ffmpeg.org/ffplay.html
Referência oficial de codecs: https://ffmpeg.org/ffmpeg-codecs.html

Validação: seis perfis convertidos com FFmpeg real; dimensões e taxa de quadros conferidas;
quadros FFV1 comparados por hashes; entrada sem áudio, arquivo inválido, nomes repetidos,
cancelamento, limpeza de temporários e preservação dos originais testados.
A v11 também foi testada com extração real de quadros em diferentes tempos, limites da linha do tempo, busca durante pausa/reprodução, navegação e carregamento das APIs do Windows.
A integração visual completa com FFplay/Tkinter não pôde ser executada no ambiente de desenvolvimento.
