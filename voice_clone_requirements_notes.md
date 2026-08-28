# Requisitos verificados para pré-processamento de clonagem

## ElevenLabs

Fonte oficial: https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning

A documentação indica que o Instant Voice Cloning recomenda aproximadamente 1–2 minutos de áudio claro e o Professional Voice Cloning recomenda 30–180 minutos de áudio bom. A recomendação de formato é MP3 a 192 kbps ou superior na visão geral. A qualidade da gravação é mais importante que o codec; devem ser evitados ruído, reverberação, artefatos, múltiplos falantes e silêncios longos.

Fonte oficial específica do Instant: https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning/instant-voice-cloning

A página específica recomenda pelo menos 1 minuto, evitar mais de 3 minutos, usar aproximadamente 1–2 minutos de áudio claro, e informa que MP3 a partir de 128 kbps é aconselhado. Também recomenda volume entre -23 dB e -18 dB RMS com true peak de -3 dB. A ferramenta poderá manter a saída WAV sem compressão ou MP3 de alta qualidade, mas a documentação não confirma um teto de 400 MB como requisito oficial de voz; portanto 400 MB será tratado como limite conservador interno do aplicativo.

## OmniVoice

Fonte pública do projeto: https://github.com/k2-fsa/OmniVoice

A busca pública indica uso de referência curta, aproximadamente 3–10 segundos no projeto OmniVoice. A página pública omnivoice.app indica 3–25 segundos. Como há diferenças entre implementações/produtos, o modo será parametrizado com alvo padrão de 5–20 segundos e máximo configurável de 25 segundos, com aviso no aplicativo.

## Decisões de implementação

O aplicativo terá três modos: OmniVoice (5–20 s, máximo 25 s), ElevenLabs Instant (60–180 s, alvo recomendado 60–120 s) e ElevenLabs Professional (blocos configuráveis de 30–45 min, acumulando 30–180 min). Cortes serão preferencialmente feitos em silêncio próximo às bordas; quando não houver silêncio, será usado corte exato com aviso. A normalização peak será para -1 dBFS, com a ressalva de que isso não garante o RMS recomendado pelo ElevenLabs; a interface exibirá metadados e avisos para revisão. Os limites internos de tamanho serão 400 MB para Instant e 450 MB por bloco Professional, abaixo do teto solicitado pelo usuário, sem afirmar que sejam limites oficiais da plataforma.


Fonte oficial do Professional Voice Cloning: https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning/professional-voice-cloning

A documentação atual recomenda pelo menos uma hora de áudio para melhores resultados e idealmente próximo de três horas. Ela recomenda áudio limpo, sem ruído, eco, música ou múltiplas pessoas, e pré-processamento para remover pausas longas e vícios quando apropriado. A orientação de volume é -23 dB a -18 dB RMS com true peak de -3 dB. A implementação manterá o intervalo solicitado de blocos de 30–45 minutos e o acumulado de 30–180 minutos, mas exibirá aviso de qualidade quando o total ficar abaixo de uma hora, pois a documentação atual recomenda pelo menos uma hora para melhores resultados.

Fonte pública do OmniVoice: https://github.com/k2-fsa/OmniVoice

O repositório público descreve o OmniVoice como um modelo TTS multilíngue instalável via PyPI/GitHub, mas não estabelece no README um limite universal do VoiceStudio. A ferramenta manterá os limites conservadores solicitados pelo usuário, com segmento de 5–20 segundos e máximo de 25 segundos, claramente identificados como configuração da ferramenta.
