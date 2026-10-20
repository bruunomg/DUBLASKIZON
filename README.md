# DUBLASKIZON V88.25

Atualização completa para Windows, com código-fonte e dois executáveis prontos.

- [Baixar o pacote completo e os executáveis](https://github.com/bruunomg/DUBLASKIZON/releases/tag/V88.25)
- [Tutorial em vídeo — playlist](https://www.youtube.com/playlist?list=PLK1xVaaFN88s)

## Começar

1. Baixe `DUBLASKIZON-V88.25.zip` no release e extraia a pasta `DUBLASKIZON V88.25`.
2. Abra `Dublaskizon V88.25.exe` ou `Dublaskizon_Portatil V88.25.exe`. Os dois executáveis contêm a mesma versão do aplicativo.
3. Em **REQUISITOS**, prepare os motores e ferramentas que pretende usar. Os modelos e ferramentas externos não estão incorporados ao EXE.
4. Selecione seu projeto e acompanhe o tutorial da playlist.

FFmpeg, FFprobe, FFplay e SoX são preparados em `%LOCALAPPDATA%/Dublaskizon/runtime/ferramentas_audio`, para reutilização entre projetos. As abas também reconhecem cópias locais. Ao preparar as ferramentas, cópias existentes podem ser reaproveitadas sem serem movidas.

## Recursos

- Clonagem e dublagem em lote, referências de voz, alinhamento, conferência de fala e logs de progresso.
- Revisão de cenas, aprovação/rejeição, redublagem, versões anteriores e lixeira do projeto.
- **Ouvir cena — Editor Simples e Editor Avançado**, com texto editável, navegação, recortes e geração de partes do TXT ou do áudio original.
- Integração com Audacity/OpenVINO para separação instrumental/vocal e supressão de ruído, preservando o original.
- Edição e mistura de som de fundo do original no dublado.
- Transcrição, tradução e revisão semântica, com mecanismos locais e provedores por API configuráveis.
- Tema, contexto, glossário, pesquisa de terminologia e indicação de origem dos termos.
- Texto para fala, ferramentas de conversão de áudio/vídeo e organização de projetos.
- Motor na memória com controle sincronizado e desinstalação seletiva dos componentes instalados.

## Últimas melhorias

- Escolha entre original, `ORIGINAL- sample-instrumental`, `ORIGINAL- sample-vocals` e `ORIGINAL- sample-vocals Suppression` ao dublar parte do áudio original, nos dois editores.
- O recorte abre à frente do Ouvir cena e recebe o foco. A edição usa uma cópia privada da faixa escolhida.
- Ferramentas de áudio compartilhadas entre projetos e tema atualizado da desinstalação por componentes.

Consulte também as notas `RELEASE_NOTES_V88.*.md` do pacote.

## Executar pelo código-fonte

Use Python com Tkinter e prepare as dependências do aplicativo. Para gerar os executáveis, consulte `Dublaskizon.spec`, `Dublaskizon_Portatil.spec` e `verify_frozen_build.py`. A versão fica em `app_version.py`.

Os projetos, áudios, modelos e chaves pessoais não fazem parte desta publicação. As APIs exigem configuração da chave e acesso ao modelo no respectivo provedor; assinatura de aplicativos não configura uma chave de API.

## Validação

Os dois executáveis foram auditados: 64 módulos exigidos presentes e bibliotecas externas pesadas ausentes. O ZIP foi conferido quanto à integridade e à pasta principal única. Os testes recentes verificaram seleção das quatro faixas, preservação dos áudios, troca de editores, foco da janela de recorte e reutilização das ferramentas entre projetos. A qualidade final de voz e tradução deve ser conferida no contexto do projeto.

Esta atualização é publicada na branch e no release **V88.25**; as versões anteriores e a branch `main` são preservadas.
