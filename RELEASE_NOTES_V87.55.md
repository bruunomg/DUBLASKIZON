# DUBLASKIZON V87.55

Correção testada na cena real falas mp4/V008__moha_igc_eog, OmniVoice BR-PT v1.5:

- Clonagem normal e Revisão também preparam uma referência curta com frase completa, usando o mesmo áudio do personagem. Anteriormente só a Dublagem Personalizada recebia essa proteção.
- Frases com menos de seis palavras são agrupadas com contexto adjacente, sem alterar o texto, até 40 palavras. Mantém pausas explícitas no caminho personalizado.
- Recuperação não divide um candidato válido em fragmentos de menos de quatro palavras: estes fragmentos estavam produzindo falas estranhas neste caso real. A recuperação de áudio vazio permanece disponível.
- Conferência e recuperação de palavras extras continuam disponíveis; áudio válido ainda é salvo para revisão quando não é possível confirmar tudo.

Teste real: referência original de 54,59 s; referência preparada de 4,75 s da mesma gravação. Arquivo regenerado com 24,94 s. Whisper Medium independente detectou Change sete vezes no áudio antigo e nenhuma no novo. Transcreveu o nome, a data e as frases do novo arquivo; há divergências em grafias e termos do TXT que ainda pedem revisão. Não representa garantia de ausência de acréscimos em todo áudio futuro.

O novo áudio foi salvo no projeto com versão anterior preservada em V008__moha_igc_eog_v05.wav. Ouvir Cena foi recarregado sem fechar o aplicativo.

Validação: 164 testes aprovados; executável compilado e auditado (34 módulos exigidos presentes, bibliotecas pesadas externas ausentes, 29,63 MiB). Modelos não incluídos. O aplicativo já aberto continua usando a versão anterior do código até reiniciar com o novo executável.
