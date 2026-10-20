# DUBLASKIZON V86.76

Esta versão melhora a abertura e o uso simultâneo de projetos com milhares de cenas.

- A janela é mostrada antes da indexação inicial, evitando a tela branca de espera.
- Clonagem + Dublagem e Revisão compartilham o índice inicial de WAV e TXT.
- A migração de nomes antigos não percorre o projeto duas vezes.
- Listas extensas são inseridas em blocos de até 1.000 itens.
- A Revisão não executa mais uma operação de cor para cada áudio pendente.
- Áudios concluídos continuam aparecendo na Revisão de forma incremental enquanto outra aba dubla.

Validação: os módulos modificados compilam; os testes de responsividade com 5 mil pares, atualização incremental da Revisão e atualização ao vivo passaram. O índice de 5 mil pares levou aproximadamente 0,14 segundo no disco local de teste. O teste de interface Tk real não pôde abrir neste ambiente porque a instalação local do Python não contém `init.tcl`.
