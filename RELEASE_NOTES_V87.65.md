# DUBLASKIZON V87.65

## Regulagens da conferência — Clonagem + Dublagem

Painel compacto CONFIGURAR CONFERÊNCIA / REDUBLAGEM logo abaixo de INICIAR DUBLAGEM. Os controles que já existiam continuam abaixo dele; a estrutura das colunas, listas e barras não foi reorganizada.

A janela permite escolher tentativas por trecho (1–5), passos iniciais (0 = automático do motor, ou 16–96), acréscimo de passos por tentativa (0–32), palavras na divisão inicial (8–35), tentativas para recuperar hesitações (1–5) e a tentativa adicional em trechos menores. Frases curtas podem ser agrupadas para preservar contexto.

Padrões preservados: 2 tentativas por trecho, passos automáticos do motor (normalmente 32), acréscimo de 16 passos, divisão inicial de 20 palavras, 3 tentativas para hesitações e recuperação adicional por subdivisão desativada nesta fila. Restaurar padrão repõe esses valores; Salvar grava por projeto em Dublaskizon_conferencia_fala.json, preservando campos anteriores.

As regulagens são aplicadas ao comando da fila OmniVoice. Revisão manual e outros motores mantêm seus parâmetros anteriores. A conferência das palavras continua ativa: não há redução da exigência de correspondência para declarar um trecho completo. Resultados incertos continuam para revisão, sem garantia de perfeição. Mais tentativas/passos e recuperação adicional podem aumentar o tempo. Alterações passam a valer para os próximos áudios, sem interromper a cena atual.

Validação: 98 testes de lógica, incluindo padrões, persistência, rejeição de valores inválidos, aplicação das tentativas/passos ao motor e isolamento dos demais caminhos. Interface nativa conferida com painel abaixo de Iniciar dublagem e botões inferiores visíveis em 1600x850; salvar e restaurar padrão verificados na janela de configuração.
