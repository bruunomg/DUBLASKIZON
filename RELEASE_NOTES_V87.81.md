# DUBLASKIZON V87.81

Atualização da aba Transcrever e traduzir:

- Somente os TXTs finalizados ficam em TRANSCRIÇÕES E TRADUÇÕES/TRANSCRIÇÕES e TRANSCRIÇÕES E TRADUÇÕES/TRADUÇÕES, preservando as subpastas. Pastas adicionadas/arrastadas mantêm também seu nome. Colisões entre entradas diferentes recebem uma subpasta identificadora.
- Revisão bem-sucedida passa a ser a tradução final. Metadados, rascunhos e candidatos de revisão ficam em revisoes/transcricoes_traducoes. Uma falha na revisão preserva a tradução já finalizada.
- Lista e área de texto ampliadas, arrastar pastas/arquivos, remover selecionados e limpar janela sem apagar arquivos do disco.
- Textos editáveis; SALVAR atualiza o TXT final da guia, EXPORTAR TXT permite escolher outro destino. Entradas originais não são sobrescritas por esse fluxo.
- Seletor de tradutor ampliado. FERRAMENTAS LOCAIS / BAIXAR fica à esquerda, junto do tema. O perfil WHISPER LARGE-V3 está dentro das ferramentas locais.
- Barras separadas para transcrição e tradução/revisão, determinadas por etapas concluídas e sem animação contínua. Durante carregamento ou chamadas indivisíveis, a barra aguarda novos dados reais.
- Pesquisa do tema em fontes Wikipedia pt/en, com URLs e data, armazenada no projeto. Ao traduzir/revisar um tema sem pesquisa, o aplicativo tenta buscar referências e continua com o contexto configurado se a rede falhar. Não envia áudios nem transcrições à pesquisa; envia somente o título.
- PESQUISAR TEMA NA INTERNET permite conferir/editar as fontes. IA LOCAL: ANALISAR FONTES usa o modelo Ollama preparado e só apresenta propostas de termos com palavras e citações presentes no documento indicado. O usuário confere e aplica as propostas ao glossário. Fontes podem não conter a localização desejada e não garantem terminologia oficial.

Validação: testes locais dos fluxos de arquivos, interface, progresso, pesquisa e integração; IA e rede simuladas nos testes de pesquisa. Não foi baixado nem executado um novo modelo grande para medir qualidade semântica.

API de pesquisa utilizada: https://www.mediawiki.org/wiki/API:Search
