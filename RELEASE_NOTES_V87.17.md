# DUBLASKIZON V87.17

## Texto inteiro no OmniVoice gerenciado

A conferência passa a ser automática e obrigatória nos comandos gerenciados
OmniVoice. Configurações antigas com enabled=false não a desativam mais.
O antigo checkbox foi substituído por informação da conferência automática.
Outros motores e executáveis externos conservam seus fluxos anteriores.

Os textos são divididos em frases, com blocos de até 20 palavras. Cada bloco
é gerado, transcrito e comparado com o texto solicitado. Apenas o bloco
que falhou é repetido, sem gerar de novo os anteriores já confirmados.
As tentativas e a recuperação em blocos menores permanecem limitadas.

O processo reutilizável exige uma confirmação nova de conclusão para cada
cena: uma confirmação anterior não libera a próxima. Se faltar confirmação,
a cena falha e o arquivo anterior é preservado. Uma primeira frase pronta
não é publicada sozinha se a segunda não passar na conferência.

A reutilização de OmniVoice, Whisper e referências da V87.16 permanece,
assim como a alternância entre RAM/GPU em CUDA com pouca memória.

## Alinhamento opcional

Removido o corte forçado do final no alinhamento por duração. O ajuste de
pausas/intensidade preserva todas as amostras sintetizadas e não silencia
palavras que coincidam com pausas diferentes no áudio original. O limite
de alteração de velocidade e a validação de duração continuam funcionando.

## Validação

139 testes automatizados passaram, incluindo falha da segunda frase sem
publicar a primeira, repetição somente do trecho incompleto, configuração
antiga desligada, confirmação independente entre cenas, preservação do
final e audibilidade no alinhamento opcional.

Teste real local com OmniVoice BR-PT v1.5, modo de pouca memória e duas
cenas consecutivas com o texto:
“Estão colocando a água pesada nos caminhões. Não posso deixar nenhum
caminhão sair daqui!”

Ambas foram confirmadas completas e salvas. A primeira levou 36,71 s,
incluindo carregamento e recuperação; a seguinte 16,30 s, também com
recuperação. O pico CUDA alocado ficou em aproximadamente 4.551 MiB.
Medição feita na RTX 5060 local; não é benchmark do notebook RTX 4050.
A frase, referência e quantidade de repetições alteram esses tempos.

O reconhecimento pode errar: confirmação automática não é garantia
absoluta de pronúncia ou audição perfeita. Uma falha persistente mantém
a cena pendente para revisão, com amostra e relatório, preservando a
saída anterior. Áudios incompletos de versões antigas precisam ser
redublados; os arquivos existentes não são alterados automaticamente.

O ZIP contém fonte e scripts de compilação; não contém EXEs compilados.
