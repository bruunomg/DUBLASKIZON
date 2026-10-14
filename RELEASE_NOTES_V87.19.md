# DUBLASKIZON V87.19

## Salvar áudio disponível quando a conferência não confirmar

A divergência do Whisper deixa de impedir a disponibilização de uma
amostra utilizável. O OmniVoice gerenciado continua gerando, transcrevendo,
tentando novamente e recuperando trechos menores. Depois das tentativas,
a melhor amostra válida pode ser salva para revisão, em vez de abortar
somente porque o reconhecimento não confirmou todas as palavras.

“Disponível” e “confirmado” são estados diferentes. Uma saída para revisão
não comprova que o texto está inteiro ou com a pronúncia correta. Confira
antes de aprovar. O relatório preserva texto pedido, texto reconhecido,
palavras em dúvida e referências das amostras.

Clonagem + Dublagem e Dublagem Personalizada mostram REVISAR em vez de OK
para as saídas não confirmadas. A redublagem na Revisão/Ouvir Cena salva
a nova saída e informa a necessidade de revisão no registro de processos.
O estado é guardado num JSON .conferencia.json ao lado do WAV publicado.
A nova geração confirmada substitui esse estado. Backups anteriores
continuam sendo feitos pelos fluxos existentes de redublagem.

A conferência não foi desativada, e a fila rápida, proteção de finais,
contexto de frases curtas e modo de pouca VRAM das versões anteriores
permanecem. Outros motores conservam o comportamento anterior.

Falha de instalação, memória, cancelamento, arquivo inválido ou motor que
retorna somente silêncio/áudio vazio ainda pode impedir geração. Não é
possível garantir um áudio utilizável em qualquer erro de execução.
Nessas situações, a saída anterior continua preservada.

## Casos reais verificados

O reconhecimento escreveu “Mathias” como “Matias” e “Reichsmark” como
“Hikes Mark”. Esses desacordos causavam o bloqueio. Na nova versão, ambas
as cenas foram geradas e salvas para REVISAR usando a mesma voz-modelo
MON_021_TrishkaSERIA.wav, sem sobrescrever os arquivos do projeto:

- DiggingGravesC01L01: 35,81 s incluindo carregamento; disponível para revisão.
- DiggingGravesC02L02: 12,36 s com modelos reutilizados; disponível para revisão.

Teste na RTX 5060 local com modo de pouca VRAM, não na RTX 4050 do amigo.
146 testes passaram. Cobertura inclui melhor candidato, relatório,
estados de disponibilidade/confirmação, recuperação vazia com amostra
válida anterior e proibição de publicar áudio inteiramente vazio.
Verificações adicionais de destinos, pastas e redublagem também passaram.

Os TXTs não foram alterados. Os áudios antigos não são corrigidos
automaticamente: reduble as cenas desejadas. Este pacote contém fonte
e scripts de compilação, sem EXEs pré-compilados.
