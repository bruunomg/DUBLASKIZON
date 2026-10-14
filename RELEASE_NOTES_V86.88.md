# Dublaskizon V86.88

- Etapa 1 com preenchimento azul-claro.
- Etapa 2 com preenchimento verde-claro.
- Etapa 3 com preenchimento amarelo.
- **CANCELAR** e **ABRIR RESULTADO** foram movidos para baixo da janela de processos.
- Botões `?` foram adicionados acima dos controles de pasta das etapas 1, 2 e 3.
- Os balões explicam qual pasta deve ser arrastada em cada janela.
- A posição dos balões respeita as quatro bordas da tela e muda de lado quando necessário.

Validação: compilação do módulo e quatorze testes funcionais/de tema passaram. O teste que abre uma janela Tk real não pôde rodar no Python isolado porque essa instalação local está sem `init.tcl`; nenhum erro de código foi encontrado.
