# DUBLASKIZON V87.86

- ABRIR PASTA DE SAÍDA movido para o canto inferior direito, junto às barras de transcrição e tradução/revisão.
- A lista principal mostra o nome exato do tradutor, como Argos, TranslateGemma ou Qwen, em vez de uma seleção genérica Local. Sua escolha é sincronizada ao abrir/aplicar FERRAMENTAS LOCAIS / BAIXAR.
- A preparação/configuração e a lista da aba representam o mesmo tradutor: não executam dois tradutores em sequência. A revisão opcional continua sendo uma etapa separada.
- O log da etapa de tradução de texto já transcrito agora identifica essa operação corretamente, sem repetir a mensagem Transcrevendo áudio original.

Esclarecimento do perfil: Whisper-WebUI / Whisper large-v3 — perfil local fixa Faster-Whisper + large-v3. Para outros modelos, escolha os mecanismos faster-whisper ou openai-whisper. PREPARAR DEPENDÊNCIAS verifica/baixa arquivos locais necessários; não instala a interface web do Pinokio.

Validação: 74 testes, incluindo sincronização do tradutor e posicionamento do botão. Nenhuma mudança na política de qualidade ou nas tentativas de dublagem.
