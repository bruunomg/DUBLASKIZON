# Compilar e executar no Linux

O arquivo comparável a um `.exe` portátil é `Dublaskizon-x86_64.AppImage`. Ele precisa ser compilado **dentro do Linux**; PyInstaller não gera um binário Linux a partir do Windows.

Em Ubuntu 24.04/26.04 ou distribuição equivalente, instale os componentes de compilação:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk ffmpeg sox curl
bash build_linux.sh
```

O resultado fica em `dist/Dublaskizon-x86_64.AppImage`. Para executar:

```bash
chmod +x dist/Dublaskizon-x86_64.AppImage
./dist/Dublaskizon-x86_64.AppImage
```

Se a distribuição não tiver FUSE 2, execute de forma portátil com:

```bash
./dist/Dublaskizon-x86_64.AppImage --appimage-extract-and-run
```

Também é gerado `dist/Dublaskizon_Linux/Dublaskizon_Linux`, acompanhado das bibliotecas. O AppImage é mais simples para distribuição.

FFmpeg, FFplay e SoX devem ser instalados pelo gerenciador da distribuição. No Linux, o visualizador abre a reprodução em FFplay; a prévia, a busca, anterior e próximo continuam na janela do Dublaskizon. Os instaladores automáticos Windows de Python/CUDA/ROCm não são executados no Linux. A janela REQUISITOS faz um diagnóstico específico do Linux. Para síntese local no Linux, prepare o ambiente OmniVoice/ROCm/CUDA conforme a documentação oficial da plataforma ou configure `OMNIVOICE_INFER` para o executável correspondente.

O script grava todo o processo em `build-linux.log`. Se a compilação falhar no computador de destino, esse arquivo contém a linha e a mensagem necessárias para diagnosticar o ambiente.

AppImage não é universal entre arquiteturas: este script gera `x86_64`. Para outra arquitetura, compile nessa arquitetura e use uma versão compatível do appimagetool.
