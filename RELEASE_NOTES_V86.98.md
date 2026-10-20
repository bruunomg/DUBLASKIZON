# Dublaskizon V86.98

Correções dos dois erros confirmados no relatório de 01/10:
- Verificação do Fish: usa o arquivo do módulo do codec, não fish_speech.__file__. O pacote Fish é um namespace válido e pode ter __file__ = None. Isso evita classificar uma instalação boa como defeituosa e reinstalá-la.
- Download Fish: remove tqdm_class, que hf_hub_download do Hub 0.36.2 não aceita. O progresso é integrado apenas no processo isolado do download, mantendo a API compatível.
- Arquivos íntegros em cache continuam sendo pulados. Tamanhos exibidos com a mesma unidade GB do painel.
- Relatórios não imprimem mais páginas de código interno na linha de comando; preservam mensagens e erros do processo.

Validação real realizada com o ambiente Fish instalado neste computador:
1. Verificação de importações, versões, codec e CUDA concluiu com reutilização, sem instalar pacotes ou criar outro ambiente.
2. Download de um README oficial pequeno usando huggingface_hub 0.36.2 concluiu com progresso; repetição confirmou cache e nenhum novo download do arquivo.
3. 44 testes automatizados passaram; 1 ignorado. Testes de regressão cobrem pacote namespace e downloader sem parâmetro tqdm_class. Sintaxe dos módulos verificada.

Não foi feita geração de fala real com os pesos do Fish. A autorização exigida pelo modelo no Hugging Face permanece necessária quando não houver acesso autorizado salvo.

Para atualizar: aplique/compile os fontes desta versão e tente o botão 2 novamente. Não use DESINSTALAR TUDO: o ambiente Fish já instalado será reutilizado.

Inclui as atualizações anteriores. Pacote com fontes e scripts de compilação, sem EXE compilado.
