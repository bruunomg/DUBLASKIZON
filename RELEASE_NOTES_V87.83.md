# DUBLASKIZON V87.83

Janela Transcrever → traduzir → dublar reorganizada:

- Seção 1: mecanismo de transcrição, um único campo de modelo, idioma original e CPU/CUDA. large-v3 faz parte da lista de modelos do Whisper. O botão separado de selecionar perfil foi removido.
- Cada mecanismo mantém seu modelo escolhido. Alternar entre Faster-Whisper e OpenAI Whisper atualiza o campo de modelo sem mostrar uma segunda seleção inativa.
- Seção 2: tradutor com nomes claros, idioma da tradução e configuração de chave. Argos, TranslateGemma e Qwen são locais; Luna e Sol usam a API configurada.
- Luna e Sol só podem ser selecionados com uma chave disponível. A janela permite salvar/ativar ou desativar a chave, protegida pelo Windows. Disponibilidade do modelo e cobrança dependem do provedor.
- Luna/Sol são aplicados ao fluxo de transcrever, traduzir e dublar, incluindo a geração de texto para revisão/redublagem. A transcrição permanece local. Nenhuma chave é gravada nos arquivos do projeto.
- PREPARAR DEPENDÊNCIAS prepara o transcritor e, quando aplicável, o tradutor local; a seleção Luna/Sol não tenta baixar um modelo Ollama.
- A aba Transcrever e traduzir acompanha a seleção feita nessa janela, incluindo Sol como tradutor.

Validação: 71 testes, incluindo seleção única do large-v3, ativação por chave, roteamento Luna/Sol e preservação dos textos. Chamadas API simuladas nos testes; nenhum consumo de API pago para validação.
