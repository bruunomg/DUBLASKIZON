# DUBLASKIZON V87.94

- Ações separadas: CADASTRAR CHAVE abre a configuração; LINK ADQUIRIR CHAVE DA API abre o portal do provedor.
- ATIVAR CHAVE visível por provedor em Revisão semântica / APIs. Permite salvar a chave protegida antes de escolher o modelo; informe/consulte o modelo e salve para liberar a tradução/revisão.
- Ferramentas locais / baixar oferece ATIVAR CHAVE e acesso ao cadastro. Luna/Sol mantêm SALVAR E ATIVAR na sua configuração.
- Ferramentas locais / baixar movido para a esquerda de Revisão semântica / APIs.
- Tema / jogo / glossário em verde-água, ampliado à esquerda até a linha de transcrição. Tema: título do tema em destaque ao lado do título da aba.
- Confirmar tema na linha dos quatro botões de processamento, ativado por padrão. A preferência é salva por projeto em revisoes/transcription-ui.json. Responder Não interrompe o início da execução, sem processar ou publicar arquivos.
- Processamento do tradutor na própria linha: CPU ou GPU (auto) para Ollama, CPU para Argos, API — remoto para serviços externos. CPU envia num_gpu=0 ao Ollama; GPU auto mantém a seleção dinâmica conforme o hardware disponível. A opção é independente do processamento do transcritor e persiste nas configurações.

Como cadastrar: clique em CADASTRAR CHAVE, cole a chave no campo protegido do provedor e clique em ATIVAR CHAVE. Consulte ou informe um ID de modelo compatível e salve. O link abre apenas o portal de aquisição; ele não cadastra a chave no Dublaskizon.

Validação: 119 testes automatizados passaram, incluindo cancelamento das quatro ações, preferência persistente, ativação de chave sem modelo, posição dos controles e payload CPU/GPU do tradutor local. APIs simuladas, sem chamadas pagas. Executável e ZIP auditados.

Referência de seleção dinâmica GPU: https://github.com/ollama/ollama/blob/main/api/types.go
