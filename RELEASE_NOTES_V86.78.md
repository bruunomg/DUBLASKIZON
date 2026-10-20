# DUBLASKIZON V86.78

Foi adicionado o botão vermelho **DESINSTALAR TUDO** à janela de requisitos.

- Calcula o tamanho sem bloquear a interface.
- Mostra o total em GB antes de pedir confirmação.
- Remove o runtime isolado do Dublaskizon, `ferramentas_audio` e somente os caches dos modelos conhecidos usados pela aba Requisitos.
- Não segue atalhos, links simbólicos ou junções para fora das pastas gerenciadas.
- Preserva projetos, WAVs, TXT, dublagens, outros modelos e programas instalados externamente.
- Impede a remoção durante dublagem, revisão ou conversão.
- Mostra os GB realmente removidos e lista itens que permaneceram bloqueados.

Validação: compilação dos módulos, 23 testes da instalação de requisitos, dois testes específicos da desinstalação e o teste do progresso de downloads passaram. O teste de link simbólico é ignorado automaticamente quando o Windows não concede permissão para criá-lo.
