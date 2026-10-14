# Dublaskizon V86.84

- Corrigida a leitura de WAVs cujas pastas ou nomes possuem acentos no analisador MFCC isolado.
- O processo auxiliar agora inicia explicitamente em UTF-8, evitando que `Só VOZ` vire `SÃ³ VOZ` e produza `Error opening`.
- Primeira, segunda, terceira e quarta ações estão numeradas.
- Os quatro botões possuem dimensões iguais e mantêm as cores correspondentes aos blocos de configuração.
- Os campos de MFCC e duração ficaram maiores.
- A segunda passagem pode ser iniciada diretamente, sem executar antes a primeira.

Validação: dez testes automatizados passaram. Além do teste de regressão com caminho acentuado, um WAV real do projeto Resident Evil 4 foi analisado pelo processo isolado com 20 coeficientes MFCC e duração de 76 segundos.
