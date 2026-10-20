# DUBLASKIZON V87.74

- Corrige a aceitação de referência longa de oito segundos reconhecida como apenas uma palavra, que podia distorcer a estimativa de duração do motor.
- Referências longas com pouca fala reconhecida buscam até três janelas curtas alternativas, preservando o original. Se nenhuma contém fala suficiente, informa o problema em vez de clonar com uma referência inválida.
- Novo cache v3 invalida referências fracas das versões anteriores sem apagar arquivos do usuário.
- Antes da síntese, estimativa automática desproporcional ao texto recebe uma duração de recuperação. Durações explicitamente solicitadas continuam respeitadas.
- Áudios gerados desproporcionais são recuperados sem desperdiçar uma conferência ASR longa. Nenhuma fala é simplesmente cortada para caber.
- Conferência de palavras, proteção de originais e layout V87.73 mantidos.
- 91 testes automatizados aprovados, incluindo recuperação antes da conferência, busca após referência This, e duração explícita longa.
