# V87.48

- Tempos separados de síntese, conferência e duração gerada nos logs do motor.
- Conferência de lote com limite de 256 tokens por janela de até 26 segundos, reduzindo reconhecimento degenerado excessivamente longo. Mantém tentativas limitadas e REVISAR quando não confirmado.
- Log de publicação usa REVISAR quando o relatório exige revisão, em vez de OK indiscriminado.
- Falha específica na validação de duração do alinhamento no lote preserva síntese não alinhada e marca REVISAR. Cancelamento e demais erros continuam tratados como falha.
- Fila/retomada preservadas. Não modifica os áudios originais.
- Inspeção do computador: GPU RTX 5060 com 7702/8151 MiB e 99% de uso; outro servidor de voz ativo. Sem atribuição de memória por processo disponível.
- Código e scripts, sem EXE compilado. Processo aberto não foi interrompido nem alterado.
