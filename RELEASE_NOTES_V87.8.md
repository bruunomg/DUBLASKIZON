# Dublaskizon V87.8 — cores, prévias e abas visíveis

- Originais em azul, vozes do sistema em laranja e escolhidas por mim em roxo,
  incluindo cabeçalhos, fundos das listas e botões de seleção do modo.
- Masculina/feminina com fonte maior e controle mais largo.
- PREPARAR REAÇÕES NATIVAS alterna verde/amarelo enquanto a aba estiver visível
  e o ambiente/modelos não estiverem preparados. Para ao iniciar uma tarefa,
  sair da aba ou concluir a preparação. Não inicia download sozinho.
- OUVIR EXPRESSÕES fica abaixo de Ofegante. Desativado, os botões inserem tags
  como antes. Ativado, tocam a referência nativa disponível, sem escrever texto.
  A prévia é a voz do banco, não a síntese na voz escolhida. Expressões sem
  gravação disponível mostram um aviso e não tocam uma emoção diferente.
  No Windows, reprodução WAV assíncrona; demais casos usam o reprodutor padrão.
- Fish removido do seletor de Texto para Fala e de modelos, autenticação,
  instalação e downloads da janela Requisitos. Instalações antigas não são
  apagadas automaticamente. O desinstalador existente continua abrangendo o
  runtime gerenciado, se solicitado pelo usuário.
- Resultados mostram o nome do arquivo, mantendo seu endereço nos dados da
  linha para Ouvir cena, edição e seleção. Avisos [CONFERIR] são preservados.
- As 12 abas dividem a largura da janela em uma linha uniforme. Seus títulos
  podem quebrar dentro do botão, sem criar uma segunda linha de abas. Não
  dependem mais de rolagem horizontal para acessar a última aba.

Validação: 83 testes passaram. Tk real verificou layout a 25%, cores, controle
de piscar, tags e ausência de Fish no seletor. As 12 abas couberam em 1900,
1366 e 1000 pixels, com alturas uniformes. Não foi feito novo teste de síntese
emocional, pois os motores e a fórmula de geração permaneceram iguais.

Este pacote contém fontes, referências nativas e scripts de compilação;
não inclui um novo EXE compilado. Execute build_exe_portatil_sem_python.bat
para gerar o portátil em dist. Modelos válidos já instalados são reutilizados.
