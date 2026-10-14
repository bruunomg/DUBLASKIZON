# DUBLASKIZON V87.10

Adicionado Qwen3-TTS 1.7B como motor opcional em Texto para Fala,
Clonagem + Dublagem, Revisão e Dublagem Personalizada. OmniVoice continua
como padrão. Os motores anteriores e seus ambientes são preservados.

## Instalação

1. Em REQUISITOS, selecione `Qwen/Qwen3-TTS-12Hz-1.7B-Base`.
2. Execute 1. INSTALAR / REPARAR, 2. BAIXAR MODELOS e 3. TESTAR MODELO.
3. Para dublagem, selecione Qwen em Ferramenta / modelo na aba Clonagem +
   Dublagem e use Voice Cloning. Revisão e Personalizada usam essa seleção.
4. Em Texto para Fala, selecione Qwen no MOTOR. O áudio original ou modelo
   escolhido será usado como referência; Ryan e Vivian são vozes próprias
   disponíveis em DO SISTEMA.

O ambiente é instalado em `%LOCALAPPDATA%\Dublaskizon\runtime\qwen`.
Base, CustomVoice, tokenizer e Whisper ocupam aproximadamente 10,7 GB de
modelos, além de Python/dependências. Downloads existentes são reutilizados.
O botão DESINSTALAR TUDO de Requisitos inclui esse ambiente gerenciado.

NVIDIA usa CUDA 12.8. Neste adaptador Qwen, AMD/DirectML utiliza CPU;
não foi adicionada nem comprovada aceleração AMD para Qwen. Os outros
motores AMD continuam disponíveis como antes.

## Novas referências emocionais

PREPARAR NOVAS REAÇÕES (QWEN) instala o motor, baixa os modelos oficiais
e gera amostras masculina/feminina em português: calmo, animado, medo,
grito e choro. As novas opções aparecem somente quando suas amostras
existem e correspondem ao manifesto verificado. OUVIR EXPRESSÕES permite
escutar cada referência sem inserir tags. A grade contém duas linhas com
botões uniformes quando todas as 11 expressões estão disponíveis.

CustomVoice aceita instruções de interpretação para suas vozes próprias.
Base clona uma referência e não recebe instruções livres de emoção. Para
vozes escolhidas pelo usuário, o sistema continua usando referências
emocionais adaptadas com Seed-VC, blocos de texto e concatenação. Grito e
choro representam instruções de interpretação da fala: a intensidade e
a fidelidade à voz dependem do modelo e das referências. Ouça as amostras
e o resultado; não há garantia de interpretação perfeita.

A transcrição da referência é automática quando não informada, com cache
por conteúdo. O texto novo nunca é usado como transcrição da referência.
Textos longos são divididos, os blocos têm pequenas pausas e o WAV final
é gravado de forma atômica. Falhas do motor são exibidas sem fechar a aplicação.

## Verificação

Testes automatizados do adaptador e regressões de instalação, referências,
geração, temas e manifesto de compilação. Conferência real do layout a 25%.
Instalação, download, carregamento Base/CustomVoice e geração de dez amostras
testados nesta RTX 5060 de 8 GB. Clonagem em português com transcrição
automática produziu um WAV de 2,40 s. Consulta após download: zero bytes faltantes.

Este ZIP contém o código e os scripts de compilação atualizados. Não inclui
um novo EXE compilado nem os modelos pesados. Compile o executável com os
scripts incluídos, ou execute a ferramenta a partir do código.

Documentação oficial: https://github.com/QwenLM/Qwen3-TTS
