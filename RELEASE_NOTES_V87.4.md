# Dublaskizon V87.4

Layout do Texto para Fala corrigido: removido o Canvas interno que duplicava a rolagem já existente na aplicação e deixava a aba com altura comprimida. A aba voltou a usar o ScrollableFrame principal. DUBLAR e PROCESSOS E MENSAGENS continuam acessíveis, inclusive com escala de tela de 55%. As listas de áudio usam um estilo de tema próprio para corrigir o fundo branco.

Geração Fish dividida também nas pausas curtas da pontuação. “ei! André! vem aqui” passa a gerar “ei! André!” e “vem aqui” em partes sucessivas, mantendo o comando de expressão em ambas quando houver. Isso evita exigir que o modelo complete todas as frases curtas em uma única geração.

Conferência automática: após até quatro tentativas, um resultado com correspondência aproximada de pelo menos 65% e reconhecimento do final pode ser guardado PARA CONFERIR. Ele recebe aviso no histórico, status e identificação [CONFERIR] na lista, persistida no JSON junto ao WAV. Não é apresentado como fala integralmente confirmada. Resultados que não reconhecem o fim da frase continuam recusados nessa condição. O caso relatado de 75% com “venga aqui” é tratado como dúvida para revisão, sem esconder a possível alteração de pronúncia.

Validação: 54 testes passaram, incluindo o caso de reconhecimento de 75%, a recusa de geração que omite o final e a identificação persistente [CONFERIR]. Sintaxe dos fontes e do script interno verificada. Teste de interface Tk dentro do ScrollableFrame real do Dublaskizon, com escala de 55%, confirmou dimensões dos controles, rolagem e tema. A frase exata “ei! André! vem aqui”, usando a referência BAC_078_Trishka do projeto, gerou e salvou WAV no teste real com CUDA. O reconhecedor retornou “Ei! Andre!” e “Vem aqui!”, 100% de correspondência aproximada após uma nova tentativa na primeira parte. Não houve avaliação auditiva de emoções nem garantia de pronúncia perfeita.

As expressões adicionais da V87.3 foram preservadas. Não exige reinstalar modelos ou dependências. Pacote de fontes e scripts de compilação, sem EXE compilado.
