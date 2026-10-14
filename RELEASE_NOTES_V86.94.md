# Dublaskizon V86.94

## Texto para Fala com emoções
- Motor Fish Audio S1-mini como opção separada do OmniVoice BR-PT.
- Comandos oficiais de alegria, tristeza, risada, sussurro, suspiro, surpresa, dúvida e descontentamento inseridos no cursor.
- A referência precisa do texto exato do áudio; aceita TXT de mesmo nome ou o campo editável.
- No modo DO SISTEMA, Fish usa voz automática sem referência; os perfis de desenho de voz continuam exclusivos do OmniVoice.
- Saídas, hierarquia, janela Ouvir Cena e arquivos anteriores preservados. Cancelamento e limite de tempo da geração.

## Instalar
1. Abra REQUISITOS e selecione fishaudio/s1-mini. Execute 1. INSTALAR / REPARAR.
2. Clique em AUTORIZAR ACESSO OFICIAL e aceite os termos na sua conta Hugging Face. Execute 2. BAIXAR MODELOS e informe um token de leitura com acesso ao modelo, ou use seu login já existente. O token não é registrado no relatório e o arquivo temporário é removido ao terminar.
3. Execute 3. TESTAR MODELO. Depois escolha Fish em TEXTO PARA FALA, selecione referência, informe a transcrição exata dela e gere uma fala com as expressões.

Fish tem licença CC-BY-NC-SA-4.0 (uso não comercial). Português e comandos de emoção são declarados pelo modelo oficial: https://huggingface.co/fishaudio/s1-mini

O instalador automático Fish desta versão é para Windows. O ambiente Fish usa Python 3.12 e fica separado de OmniVoice, F5 e DirectML. NVIDIA usa CUDA 12.8; outros perfis usam CPU para Fish. Não há promessa de aceleração AMD para esse motor. DESINSTALAR TUDO remove seu runtime e seus modelos gerenciados.

A instalação conserva o código oficial S1 na revisão ef1af2079182ca38623c54b2dd4b934204e9dfd0, que corrige a API do codec S1. Bibliotecas pesadas e pesos são externos ao EXE.

Pacote com fontes e scripts de compilação; não contém EXE compilado. Testes automatizados e sintaxe verificados. Não foi feita síntese real com o modelo gated, nem teste de instalação completa em outro PC. A intensidade e a qualidade das emoções devem ser conferidas ouvindo o resultado.
