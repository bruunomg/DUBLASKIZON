# DUBLASKIZON V87.11

Correção de referências com palavras cortadas no OmniVoice da Dublagem
Personalizada e na redublagem dos personalizados pela Revisão/Ouvir Cena.

O programa identifica uma frase completa de 3 a 10 segundos na voz-modelo,
mantém uma pequena pausa após ela e fornece sua transcrição real ao motor.
Isso evita usar o final incompleto de referências longas como continuação
da próxima fala. Não remove palavras do texto solicitado nem modifica
o áudio-modelo original. O reconhecimento automático pode errar; quando
não encontra um trecho seguro, preserva a referência e registra um aviso.

O trecho preparado é reutilizado por conteúdo do arquivo, em
`%LOCALAPPDATA%\Dublaskizon\runtime\voice-references-v1`.
Uma referência alterada produz uma nova entrada de cache. O cache permanece
dentro do ambiente gerenciado que o botão DESINSTALAR TUDO remove.
Não são instaladas novas dependências ou modelos para esta correção.
Outros motores e as dublagens comuns não recebem este tratamento.

As falas já geradas precisam ser redubladas; não há alteração automática
das saídas existentes. Em Processos e mensagens aparece a transcrição
do trecho de referência preparado ou reutilizado.

Este ZIP contém fontes e scripts de compilação, sem EXE pré-compilado.
Os manifestos de compilação e o auditor incluem o novo módulo, mantendo
as bibliotecas dos motores fora do executável.

Validação: 100 testes automatizados e verificações de integração da Revisão
e Dublagem Personalizada; reprodução de duas falas do projeto Deadpool
com a referência de 15 segundos que terminava em “sonho” cortado.
