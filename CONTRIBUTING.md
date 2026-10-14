# Contribuindo com o Dublaskizon

Obrigado pelo interesse no Dublaskizon. Este documento descreve um fluxo seguro para propor mudanças sem misturar dados reais de projetos de dublagem com o código-fonte.

## Antes de começar

Crie uma cópia de segurança do projeto original. Trabalhe em um clone ou em uma branch separada e mantenha a branch principal protegida. Não use uma pasta que contenha os áudios, textos, modelos em cache, configurações pessoais ou saídas do seu projeto real.

Instale as dependências de desenvolvimento com:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

FFmpeg, FFprobe, FFplay, SoX, OmniVoice e Audacity são dependências externas. Um colaborador não precisa receber credenciais, tokens, modelos em cache ou arquivos privados para trabalhar na interface e nos testes.

## Fluxo recomendado

Leia `README.md`, `LEIA-ME_BUILD_DUBLASKIZON.md` e `PRD_DUBLASKIZON.md` antes de alterar o comportamento. Faça mudanças pequenas e específicas, preserve as chaves relativas e não introduza varreduras recursivas desnecessárias em fluxos interativos.

Crie uma branch descritiva:

```bash
git switch -c feat/minha-mudanca
```

Mantenha operações de arquivo seguras. Substituições de áudio devem usar temporários e backup quando aplicável. A ferramenta WEM deve operar somente sobre o conjunto carregado e sempre manter prévia, detecção de conflito e possibilidade de rollback.

## Testes obrigatórios

Antes de abrir um pull request, execute:

```bash
python3 -m py_compile *.py
for test_file in test_*.py; do
  xvfb-run -a python3 "$test_file" || exit 1
done
```

No Windows, execute os testes com um ambiente Tkinter funcional. Inclua uma regressão para qualquer correção de player, tema, conversão, revisão ou operação de arquivo. Não use áudios reais: gere fixtures curtas e temporárias dentro dos testes.

## Pull request

O pull request deve explicar o problema, a solução, os arquivos alterados, os testes executados e eventuais dependências externas. Se houver mudança de interface, inclua uma captura sem dados pessoais ou descreva claramente a alteração.

Não inclua no commit:

- arquivos de projeto com áudio ou texto real;
- `Dublaskizon_interface.json`, `voz_config.json`, `revisao_config.json` ou `revisao_estado.json`;
- tokens, senhas, chaves de API ou arquivos `.env`;
- caches de modelos, diretórios `ferramentas_audio`, `dublado`, `revisoes` ou saídas de conversão;
- builds locais, pastas `dist`/`build`, caches Python ou ZIPs.

Revise o staged diff antes de publicar:

```bash
git status --short
git diff --cached
```

## Política de compatibilidade

Novas funcionalidades devem manter o suporte a subpastas, chaves relativas, navegação, temas claro/médio/escuro, idiomas existentes, logs globais e operação sem bloqueio da interface. Não altere o contrato de nomes e pastas sem atualizar o PRD, o README e os testes correspondentes.
