# Dublaskizon V87.9 — somente expressões com referência na grade

A grade de expressões agora contém seis botões: Neutro, Alegre, Triste, Raiva,
Sussurro e Surpreso. Todos têm gravação verificada para a prévia em ambas as
opções masculina/feminina. Foram retirados os botões de expressões sem prévia
nativa e os atalhos que apenas reutilizavam outra emoção.

OUVIR EXPRESSÕES continua alternando entre ouvir a referência e inserir a tag.
Sussurro/surpresa têm referências complementares em alemão; o aviso da prévia
informa isso. A síntese permanece em português. As outras quatro referências
são brasileiras. Ter referência não garante intensidade emocional ou timbre
perfeito na fala gerada: os motores e a conversão têm suas limitações.

Antes de iniciar a geração, o aplicativo verifica as tags presentes no texto
contra as referências próprias existentes, o banco nativo quando ativado e os
sons não verbais suportados pelo motor. Uma tag indisponível impede iniciar e
mostra quais tags precisam ser removidas ou configuradas. Não altera o texto
do usuário nem salva um resultado neutro como se tivesse aquela reação.

As referências próprias opcionais continuam permitindo emoções adicionais.
Riso/suspiro/dúvida por tags manuais continuam sendo aceitos somente pelo motor
OmniVoice ou quando há uma referência própria; não recebem novos botões sem
prévia gravada. O parser e o fallback da API modular não foram alterados.

Entrega com fontes, referências e scripts de compilação. Não inclui novo EXE
compilado. Use build_exe_portatil_sem_python.bat para gerar o portátil em dist.
Não é necessário reinstalar modelos para esta atualização da interface.
