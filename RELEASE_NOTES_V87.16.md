# DUBLASKIZON V87.16

## Fila OmniVoice mais rápida

Clonagem + Dublagem e Dublagem Personalizada reutilizam um processo isolado
OmniVoice durante cada fila. O modelo de síntese e o Whisper de conferência
não precisam ser carregados do disco novamente para cada cena. Referências
já preparadas também são reutilizadas, com cache limitado a quatro itens;
se o arquivo de referência mudar, ele será preparado novamente.

O processo é encerrado ao terminar, cancelar ou sair por exceção da fila.
Uma falha de cena não impede o processamento das seguintes. A troca de
modelo descarta o anterior. Outros motores continuam com o fluxo anterior.
A Revisão e Dublar parte do TXT mantêm seus processos independentes.

## GPUs com pouca memória

Em CUDA com até 7 GiB de memória total, o Whisper e o OmniVoice alternam
entre RAM e GPU: a síntese roda na GPU; durante a transcrição/conferência,
a síntese vai temporariamente para RAM e o mesmo Whisper roda na GPU.
Isso evita manter os dois modelos grandes na GPU ao mesmo tempo.
A detecção é automática; nenhum novo download é necessário.

Não foram reduzidos passos de geração, trocados modelos, aplicadas novas
quantizações ou desativada a conferência de palavras. Os parâmetros de
qualidade, a proteção da referência e o ritmo natural da V87.15 continuam.
As transferências consomem tempo e RAM, mas reduzem pressão sobre a VRAM.
Duas sínteses simultâneas ainda disputam a memória e capacidade da GPU.

## Validação

134 testes automatizados passaram, além das verificações de destino de
redublagem, configurações de pronúncia, pastas e Dublagem Personalizada.
Gerações reais locais confirmaram o texto inteiro nos casos medidos.

Teste com OmniVoice BR-PT v1.5, Whisper de conferência ativado e frase curta
“Precisamos sair daqui agora.”, na RTX 5060 de 8 GB local:

- Processo novo anterior: 22,98 s.
- Primeira cena reutilizável: 24,79 s.
- Próxima cena com modelos e referência carregados: 1,36 s.
- Fluxo com proteção de referência personalizada: 23,41 s / 2,54 s.
- Modo de pouca VRAM forçado para testar: 28,23 s / 5,48 s.
- Pico CUDA alocado: 6.487,9 MiB sem alternância / 4.551,5 MiB com alternância.

Esses tempos são exemplos locais, não medição da RTX 4050 de notebook.
Texto, referência, tentativas de recuperação, memória e potência do notebook
alteram o resultado. A primeira cena ainda carrega modelos; o ganho principal
é nas seguintes. O pico informado é memória alocada pelo PyTorch no teste,
não uma garantia de limite para todos os textos ou ocupação total do sistema.

O ZIP contém fonte e scripts de compilação; não contém EXEs pré-compilados.
As bibliotecas e modelos continuam fora do EXE, no ambiente gerenciado.
