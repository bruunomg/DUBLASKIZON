# DUBLASKIZON V88.09

- Corrigido Aplicar na configuração de transcrição/tradução: agora ativa a tradução automática e inclui na fila os áudios sem TXT. Antes podia salvar a configuração mantendo a opção desligada e a fila limitada aos pares já existentes. O estado de ativação agora também é salvo.
- A preparação dos textos considera as cenas elegíveis antes dos filtros de síntese: pode verificar TXTs mesmo quando não houver dublagem pendente após esses filtros.
- Processos e mensagens mostra a ativação, o tema escolhido, contagens da varredura, cada transcrição concluída e cada tradução pronta. Logs da aba Transcrever e traduzir continuam espelhados na Clonagem e em Comandos.
- Quando todos os TXTs estiverem preenchidos, o log informa explicitamente que não foi necessário transcrever/traduzir. Cadastrar tema não força substituição de textos existentes.
- As quatro barras de progresso ficam compactas no alto, sem acompanhar a altura do painel de opções. Pausar, Parar após cena, Cancelar e os controles da mesma linha ficam abaixo das barras.
- O log agora tem mais altura e rolagem vertical própria, limitado à coluna esquerda, sem ocupar a área dos controles à direita. Todos os controles existentes foram mantidos.

Validação: testes de ativação por Aplicar, inclusão de áudios sem TXT, razões de não processamento, preparação, posicionamento e encaixe a 25%, roteamento de logs e inicialização completa.
