# DUBLASKIZON V87.79

- Nova aba TRANSCREVER E TRADUZIR imediatamente à direita de TEXTO PARA FALA, integrada a navegação, tema, escala, atividade, troca de projeto e fechamento.
- Transcrição de áudio/vídeo com Faster-Whisper ou Whisper já gerenciados pelo Dublaskizon. Configuração e downloads pelas ferramentas locais existentes. Não requer Pinokio aberto.
- Transcrever, traduzir TXT/texto editável, transcrever e traduzir, e revisar tradução com Sol; seleção múltipla, pasta, cancelamento e exportação TXT da guia selecionada.
- Tradutores locais existentes (Argos, TranslateGemma e Qwen via Ollama) e conexão API configurável para Luna e Sol. Modelos iniciais reproduzem os identificadores da ferramenta indicada, mas dependem do provedor: podem ser alterados e verificados por GET sem gerar tradução.
- Campo mascarado e importação .env; chave protegida por DPAPI no perfil Windows, nunca em projeto, registros ou pacote. Nenhuma chave do diretório indicado foi copiada.
- API em lotes de até oito linhas, índices completos, validação de tags/placeholders, preservação de transcrição, tradução e revisão em arquivos distintos e arquivos parciais separados em caso de interrupção.
- Saídas em TRANSCRIÇÕES E TRADUÇÕES/sessao_<id>, com arquivos existentes preservados. Registros também em Comandos e Processos e mensagens.
- Uso real do Faster-Whisper small em CPU com cache já instalado: reconheceu Precisamos sair daqui antes que eles voltem. em 4.6 segundos, sem download ou alteração de áudios do usuário.
- API validada por respostas simuladas; não foram feitas chamadas pagas com a chave do usuário. Pinokio estava inacessível durante a identificação do app anterior.
