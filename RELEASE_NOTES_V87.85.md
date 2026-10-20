# DUBLASKIZON V87.85

- Adicionado diretamente em Mecanismo de transcrição: Whisper-WebUI / Whisper large-v3 — perfil local.
- O perfil seleciona Faster-Whisper + large-v3 no ambiente do Dublaskizon. O modelo fica fixado nesse perfil, evitando escolhas contraditórias. Não incorpora a interface Gradio do Whisper-WebUI nem exige Pinokio aberto.
- PREPARAR DEPENDÊNCIAS utiliza o instalador local já existente para verificar/baixar os arquivos necessários. O perfil não afirma que os pesos estejam presentes antes da preparação.
- As escolhas faster-whisper e openai-whisper e seus modelos continuam disponíveis. Alternar para o perfil não apaga as escolhas em edição dos outros mecanismos.
- O perfil aplicado é salvo e reconhecido ao reabrir a configuração.

Validação: 73 testes; seleção na janela Tk, parâmetros do perfil e compatibilidade dos tradutores. Os pesos grandes não estão incluídos no ZIP.
