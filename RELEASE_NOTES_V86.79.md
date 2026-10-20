# Dublaskizon V86.79

Esta versão acrescenta a aba **SEPARAR ÁUDIO IGUAL POR FREQUÊNCIA IDÊNTICA**.

## Funcionamento

1. Arraste a pasta dos WAVs em inglês para a janela 1.
2. Arraste a pasta equivalente dos WAVs em português para a janela 2.
3. Arraste a árvore dos OGGs para a janela 3.
4. Execute a primeira passagem. Ela combina MFCC com duração para reduzir correspondências incorretas.
5. Se ainda houver WAVs, execute a segunda passagem. Ela compara somente os arquivos restantes e não exige duração semelhante.

Os resultados são organizados nas pastas `WAV INGLES` e `WAV PT-BR`, criadas junto do OGG correspondente. Arquivos existentes não são substituídos: o programa acrescenta um número ao novo nome.

As árvores carregam subpastas sob demanda, e o processamento de áudio fica em uma thread separada para não congelar a interface.

## Compilação corrigida

Os scripts de build incluem o suporte MFCC por importação dirigida, sem coletar todos os submódulos do ambiente Python. Também preservam o cache incremental do PyInstaller e não atualizam pacotes que já satisfazem os requisitos. Isso evita varrer e incorporar bibliotecas de IA que não pertencem a essa ferramenta.
