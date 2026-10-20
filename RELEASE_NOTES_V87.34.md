# V87.34

- Reações da voz voltou a uma coluna, mantendo os controles lado a lado em cada linha. Janela ampliada verticalmente, com Salvar fixo no rodapé; rolagem permanece para telas pequenas.
- Captura verifica e prepara sounddevice no ambiente gerenciado quando ausente, sem reinstalar motores ou modelos de voz.
- ATUALIZAR MIC refaz enumeração de entradas. Nomes incluem a interface Windows (MME, DirectSound, WASAPI ou WDM-KS), permitindo selecionar USB ou headset reconhecido pelo driver.
- Enumeração real verificou Microfone (FIFINE Microphone), entradas de headset e Realtek neste PC. Nenhuma gravação foi feita.
- Teste simulado cobre inclusão de USB e headset e exclusão de saídas sem entrada.
