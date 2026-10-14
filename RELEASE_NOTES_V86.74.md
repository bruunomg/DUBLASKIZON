# DUBLASKIZON V86.74

## Principal atualização

- Motor F5-TTS PT-BR com Microsoft DirectML para Radeon RX 560, RX 570, RX 580 e RX 590.
- Detecção automática dessas placas e seleção automática do modelo `firstpixel/F5-TTS-pt-br`.
- Ambiente isolado com Python 3.12, `torch-directml 0.2.5.dev240914`, PyTorch/Torchaudio 2.4.1 e TorchCodec 0.0.3.
- Teste real de geração WAV em português na janela REQUISITOS quando existe áudio de referência no projeto.
- Fallback automático para CPU quando um operador DirectML não é aceito pela placa.
- Integração na Clonagem + Dublagem, Dublagem Personalizada, Revisão, Ouvir Cena e Dublar Parte do TXT.

## Instalação na RX 500

Na janela REQUISITOS, deixe Processamento em Automático. Confirme o perfil F5-TTS PT-BR DirectML e execute, em ordem: 1. INSTALAR / REPARAR; 2. BAIXAR MODELOS; 3. TESTAR MODELO.

## Validação

40 testes automatizados aprovados. A aceleração DirectML precisa ser confirmada pelo TESTAR MODELO no computador de destino; se falhar, a geração continua por CPU.
