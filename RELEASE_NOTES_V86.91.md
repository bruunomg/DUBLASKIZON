# Dublaskizon V86.91

- Comparação integral entre V86.78 e V86.90, inclusive do conteúdo interno dos EXEs.
- O V86.90 foi confirmado com todos os 26 módulos do aplicativo.
- A redução entre os portáteis é de somente 121.100 bytes (0,116 MB), sem módulo perdido.
- `Dublaskizon.spec` sincronizado com os scripts de build.
- `personalized_dubbing_tab` e `main` adicionados explicitamente ao compilador alternativo.
- `tkinterdnd2` passa a ser coletado integralmente nos dois builds.
- Novo `verify_frozen_build.py` executado automaticamente após cada compilação.
- O auditor rejeita EXE com módulo ausente, biblioteca pesada incorporada ou tamanho superior a 120 MB.

Validação: o portátil V86.90 existente passou na auditoria interna; 79 testes automatizados passaram e um teste dependente de plataforma foi ignorado.

O novo build não pôde ser executado neste ambiente porque a instalação local do Python 3.13 está com o Tcl/Tk incompleto (`init.tcl`). Isso afeta o computador compilador, não o EXE V86.90 já produzido nem o código-fonte.
