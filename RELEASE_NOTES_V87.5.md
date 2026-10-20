# Dublaskizon V87.5

A aba Texto para Fala agora usa referências emocionais com OmniVoice/F5 por
padrão. Os botões de expressão inserem `[alegre]`, `[sussurro]`, `[triste]` etc.
no cursor. A geração divide o texto em trechos, seleciona a referência de cada
emoção e une o resultado com 150 ms de silêncio entre trechos. Os marcadores
antigos `[[EXPRESSAO:...]]` também funcionam nesse modo.

Selecionar um áudio numa das três listas ativa Original, Do sistema ou Escolhido
por mim. Um novo botão CONFIGURAR REAÇÕES DA VOZ SELECIONADA associa gravações de
cada emoção àquela voz e salva o perfil no projeto. Os perfis são separados por
voz e modo. Sem uma referência emocional existente, o trecho usa o áudio neutro
selecionado e informa o fallback em Processos e mensagens. O software não promete
uma emoção que não esteja presente nas referências fornecidas.

A lista Do sistema aceita também arquivos de referência pelo botão ADICIONAR
ÁUDIO DO SISTEMA. Ao escolher uma voz descritiva do sistema, o motor gera uma
referência neutra fixa antes dos trechos, evitando gerar uma voz nova em cada
parte. Esse caminho depende de o motor suportar geração sem referência; para
motores que só clonam, selecione um arquivo de referência nessa lista.

As pastas de saída, nomes, hierarquia, metadados, histórico e Ouvir cena foram
preservados. A síntese executa fora da thread da interface; o progresso de cada
trecho e o relatório do motor aparecem no quadro de mensagens. Cancelar interrompe
o subprocesso e impede novos trechos. Temporários são removidos também nas falhas;
um áudio parcial não substitui o resultado final. FFmpeg normaliza os formatos
quando está disponível, sem alterar velocidade ou tom. Fish permanece como opção
alternativa com seu fluxo anterior, sem ser necessário para a nova fórmula.

O módulo emotional_speech foi incluído nos scripts de compilação Windows/Linux,
no spec e na auditoria do EXE. Os modelos de IA continuam fora do executável.
Não exige reinstalar as dependências existentes.

Validação: 73 testes automatizados passaram, incluindo referências distintas
por trecho, fallback, voz do sistema fixa, proteção de saída, limpeza, parser e
compilação. Teste Tk real no ScrollableFrame do aplicativo verificou seleção de
voz, inserção de tags, janela de reações e dimensões dos controles. Não foi feita
avaliação auditiva de emoções com um personagem real nesta versão.

Entrega: pacote de fontes completo com scripts de compilação; não inclui um novo
EXE compilado.
