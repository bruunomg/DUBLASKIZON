# Dublaskizon V86.83

Na aba **Separar áudio igual por frequência idêntica**, cada ação possui agora seu próprio bloco visual de configuração na mesma cor do botão.

- **Primeira passagem:** MFCC e tolerância de duração configuráveis.
- **Segunda passagem:** MFCC independente; a duração não restringe esta passagem.
- **Filtrar repetidos ou diferentes:** novo nome do filtro que conserva o candidato mais próximo de cada OGG.
- **Filtrar resultado final:** compara somente `WAV INGLES` com os OGG pelo MFCC mínimo configurado.

O filtro final pede confirmação antes de excluir. Quando um WAV inglês fica abaixo do MFCC mínimo, remove também o arquivo de mesmo nome em `WAV PT-BR`. Se um arquivo não puder ser analisado, ele é preservado e a falha aparece no registro.

Validação: compilação do módulo e cinco testes automatizados passaram, incluindo primeira e segunda passagem, colisão de nomes, filtro de repetidos, verificação final e remoção pareada EN/PT.
