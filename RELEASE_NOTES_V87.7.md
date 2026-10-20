# Dublaskizon V87.7 — Texto para Fala compacto

O título TEXTO PARA FALA, o motor e REQUISITOS ficam na mesma linha.
As ações de carregar WAV ORIGINAIS, adicionar áudio original e adicionar voz
modelo ficam junto aos títulos das três listas, nas posições solicitadas.
Adicionar áudio original continua alimentando a lista de originais, mesmo com
seu botão localizado no cabeçalho de Vozes do sistema.

As 21 expressões ficam em três linhas de sete botões, com altura e largura
uniformes. A distribuição de pixels pode variar um pixel entre colunas.
Espaçamentos, alturas iniciais das listas, texto e relatório foram compactados.
As listas e o relatório mantêm suas barras de rolagem próprias.
Abrir pasta de saída permanece disponível no painel dos resultados.

Nenhuma mudança nos motores, referências emocionais, instalação, cache ou
geração de áudio. As funções das outras abas não foram alteradas.

Validação: 80 testes automatizados passaram. Teste com Tk real e a mesma
função de escala do aplicativo confirmou todos os botões visíveis, cabeçalhos
sem sobreposição, inserção de tag e acesso ao relatório, em uma janela
1900 × 1000, escala 25%, reservando 150 pixels para cabeçalho/abas.
Nessa condição, não foi necessária rolagem externa. Telas menores ainda podem
precisar dela; o programa mantém acesso a todos os controles.

Entrega: fontes completos, banco nativo de referências e scripts de compilação.
Não inclui novo EXE compilado. Para compilar o portátil no Windows, execute
build_exe_portatil_sem_python.bat. O resultado fica em dist.
Para instalar os modelos emocionais, use PREPARAR REAÇÕES NATIVAS na aba
Texto para Fala. Uma instalação válida existente é reutilizada.
