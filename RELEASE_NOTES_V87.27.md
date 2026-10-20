# V87.27 — Silero VAD

- Silero VAD 6.2.3 detecta intervalos de fala na CPU para o alinhamento por blocos e ORGANIZAR ONDAS. Usa tensores a 16 kHz, margens de 40 ms e modelo JIT incluído no pacote oficial.
- Instalação pelo botão 1 dos Requisitos: verifica e reutiliza o pacote pronto; instala só Silero com --no-deps, sem atualizar PyTorch/torchaudio. Permanece dentro do ambiente gerenciado, removido por Desinstalar tudo.
- Sem Silero disponível, há aviso e fallback por energia. A integração não sincroniza palavras nem elimina diferenças de ritmo entre traduções.
- No editor, ultrapassar o limite vira aviso na área de estado, sem janela de erro. Edição anterior permanece intacta.
- 157 testes de regressão passaram. Detecção real com modelo oficial validada em amostra existente: mesmos intervalos nos dois inputs e posições dentro da duração. Não foi feita avaliação auditiva de um novo alinhamento.
- EXE permanece sem Torch ou modelo Silero embutidos. O pacote é instalado no runtime separado.
