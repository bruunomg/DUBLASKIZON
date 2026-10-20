# DUBLASKIZON V87.59

Correção dos scripts de compilação e auditoria. O verificador agora reconhece módulos de extensão nativos, incluindo audioop.pyd e audioop.cp312-win_amd64.pyd, além do pacote audioop das versões mais recentes do Python. Mantém a rejeição de dependências realmente ausentes e bibliotecas pesadas indevidamente incorporadas.

Os dois BATs verificam a importação de audioop, pydub e numpy e uma operação PCM antes de gerar o EXE. pydub é carregado da mesma pasta build_vendor utilizada pela compilação. Testes cobrem nomes de extensão, ausência real e rejeição de bibliotecas pesadas.

Esta atualização corrige a compilação da V87.58. O EXE pronto está incluído no ZIP; não é necessário recompilá-lo para usar.
