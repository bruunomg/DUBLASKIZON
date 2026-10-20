# DUBLASKIZON V86.77

Foi acrescentada a opção **MANTER VOZ NATURAL DO ÁUDIO ORIGINAL** ao lado de **Idioma da voz** na aba Clonagem + Dublagem.

Quando ativada, ela compara cinco regiões do espectro do original e do áudio sintetizado. O Dublaskizon aplica uma equalização limitada a ±4,5 dB e somente ativa filtros passa-altas ou passa-baixas quando encontra uma limitação forte compatível com voz de rádio, capacete ou robô. A fala original não é misturada no resultado.

O processamento ocorre em segundo plano e reutiliza o FFmpeg do aplicativo. Uma falha nessa etapa não perde a dublagem: o áudio gerado é mantido e o aviso aparece no histórico. A preferência é salva em `dublagem_vozes.json` e as traduções da nova opção foram incluídas em português, inglês, russo e espanhol.

Validação: compilação dos módulos modificados, dois testes espectrais, testes de idioma e sete testes dos controles de geração passaram.
