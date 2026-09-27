# Segurança

O Dublaskizon trabalha com projetos que podem conter áudios, textos, caminhos locais, modelos e configurações privadas. Não publique esses dados no repositório.

## Não enviar

Nunca faça commit de tokens, senhas, chaves de API, arquivos `.env`, configurações locais, caches de modelos, arquivos de áudio, TXT de projeto, logs com caminhos pessoais ou diretórios de saída. O `.gitignore` contém os principais padrões, mas revise manualmente o staged diff antes do push.

## Relatar um problema

Para relatar uma vulnerabilidade real, não publique detalhes exploráveis em uma issue aberta. Combine com o mantenedor do repositório um canal privado antes de enviar logs, arquivos ou passos de reprodução. Remova ou substitua qualquer credencial antes do compartilhamento.

## Se uma credencial for exposta

Revogue ou substitua a credencial imediatamente no serviço correspondente. Depois remova o segredo do histórico do Git; apagar o arquivo apenas no commit mais recente não elimina a exposição histórica.
