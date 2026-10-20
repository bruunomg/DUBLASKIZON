# Dublaskizon V86.97

## Reutilização dos requisitos
- Botão 1 (Fish e OmniVoice): verifica versão, perfil de processamento, importação e dependências do ambiente ativo antes de instalar. Se compatível, reutiliza sem criar outro ambiente nem baixar os pacotes novamente.
- Se faltar uma dependência opcional do OmniVoice, instala somente essa dependência. Ambientes incompatíveis ou danificados são reparados em um ambiente novo; o anterior permanece ativo até a validação final.
- Fish verifica também a revisão do código oficial e o arquivo de configuração do codec.
- Botão 2 Fish: consulta a revisão atual e os tamanhos, pula arquivos já íntegros no cache, informa quanto falta baixar e baixa apenas arquivos novos/ausentes/danificados. Mudanças no repositório podem precisar de novos arquivos.
- Botão 3 Fish: testa o carregamento com acesso remoto desativado; não baixa pesos durante o teste.

O primeiro download do PyTorch Fish é separado do OmniVoice por compatibilidade das dependências. A atualização não apaga ferramentas instaladas, ambientes antigos nem áudios. Não use DESINSTALAR TUDO para aplicar esta correção.

Inclui V86.96 (autenticação automática quando houver login salvo) e V86.95 (posição da aba Texto para Fala).

Validação: 42 testes passaram, 1 ignorado; sintaxe dos módulos verificada. Não foi feita nova instalação real nem geração de fala nesta atualização. Fontes e scripts de compilação; sem EXE compilado.
