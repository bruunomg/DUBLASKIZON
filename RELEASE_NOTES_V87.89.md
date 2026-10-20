# DUBLASKIZON V87.89

Revisão semântica de tradução e provedores de API:

- REVISÃO SEMÂNTICA / APIs permite configurar chaves protegidas pelo Windows, URLs e identificadores de modelos para OpenAI/ChatGPT, OpenAI/Codex e Claude. Os campos de modelo ficam em branco até o usuário definir um ID disponível para sua conta; consultar modelos usa GET, sem gerar texto pago.
- A seleção Avaliar/revisar tradução inclui os novos provedores, além de Sol e Ollama local. OpenAI usa Responses; Claude usa Messages. Não utiliza login ou créditos da interface dos aplicativos ChatGPT/Codex/Claude.
- A revisão pede um parecer explícito sobre sentido, ordens/imperativos, expressões idiomáticas, naturalidade, negações, contexto e intensidade de palavrões. O parecer contém precisa revisar, motivos e tradução corrigida completa.
- Uma tradução sem parecer semântico fica REVISAR. Um parecer que proponha mudanças ou indique problema também fica REVISAR, mesmo após publicar a sugestão, para conferência humana. Transcrições isoladas continuam usando os alertas de transcrição.
- O texto anterior, a sugestão e o parecer ficam preservados no relatório de revisoes. Falha, resposta incompleta, tags alteradas ou parecer inválido preservam a tradução anterior e sinalizam REVISAR.
- Salvar uma edição invalida o parecer anterior e pede nova avaliação, evitando reutilizar aprovação de outro texto.
- Saídas com apresentações como "translates to" recebem alerta geral, independentemente do revisor. Não foi criada uma substituição fixa para uma frase alemã específica.

Validação: 92 testes com APIs simuladas, incluindo o exemplo fornecido, pareceres inválidos, proteção de chaves, preservação de arquivos, invalidação do parecer após edição e configuração dos provedores. Não houve chamada paga para comprovar qualidade dos modelos. Revisor semântico também pode errar: OK significa ausência de alertas e parecer favorável, não garantia absoluta.

Documentação oficial:
- https://developers.openai.com/api/docs/guides/text
- https://developers.openai.com/api/docs/guides/migrate-to-responses
- https://platform.claude.com/docs/en/api/messages/create
