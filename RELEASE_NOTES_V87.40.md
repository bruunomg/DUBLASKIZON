# V87.40

- Texto para Fala reutiliza o processo, modelo OmniVoice e referências entre trechos da mesma geração, reduzindo recarregamentos.
- Antes de executar conversão de timbre, libera o processo de síntese para evitar disputa por VRAM; encerra o processo ao terminar, falhar ou cancelar.
- Parâmetros de qualidade e conferência das palavras preservados. Outros motores continuam com seu executor original.
- Alteração restrita ao Texto para Fala. 49 testes de geração expressiva, interface e reutilização passaram.
- Desempenho na RTX 4050 do usuário não medido; conversão de timbre continua tendo custo próprio.
- Código e scripts, sem executável compilado.
