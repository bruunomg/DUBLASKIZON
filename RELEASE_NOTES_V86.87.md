# Dublaskizon V86.87

- Quinta ação adicionada à Etapa 2, com quadro rosa e botão vermelho.
- Os cinco controles superiores e inferiores têm largura uniforme.
- O botão **5ª — SALVAR ÁUDIOS SEM PARES** abre a seleção da pasta de destino.
- Arquivos sem par são copiados sem perder a hierarquia de subpastas.
- Cenas que possuem simultaneamente `WAV INGLES` e `WAV PT-BR` ficam fora dessa cópia.
- Depois da cópia, uma confirmação oferece a limpeza opcional da origem.
- A limpeza nunca remove cenas que possuam as duas pastas.
- Arquivos sem par são removidos e diretórios vazios são apagados.
- Destinos dentro da própria origem são recusados para impedir cópia recursiva.

Validação: quatorze testes automatizados passaram, incluindo cópia hierárquica, proteção da cena completa e remoção de diretórios vazios.
