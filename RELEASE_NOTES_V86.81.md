# Dublaskizon V86.81

Corrige o executável de 2,35 GB produzido pela V86.80.

O analisador MFCC agora roda no ambiente Python isolado da janela **Requisitos**. O EXE envia os áudios a um processo persistente e recebe somente as assinaturas numéricas, sem incorporar `librosa`, SciPy, Numba, Torch, Transformers, Gradio, CUDA ou ROCm.

Os scripts de compilação limpam o cache anterior e bloqueiam o resultado quando o executável ultrapassa 120 MB. Isso impede que uma instalação Python carregada de bibliotecas científicas volte a gerar silenciosamente um pacote de vários gigabytes.

Para usar **SEPARAR ÁUDIO IGUAL POR FREQUÊNCIA IDÊNTICA**, abra **Requisitos**, mantenha **Incluir análise MFCC** selecionado e execute **1. INSTALAR / REPARAR**. **DESINSTALAR TUDO** remove esse ambiente e suas dependências.
