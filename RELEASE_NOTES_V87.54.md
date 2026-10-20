# DUBLASKIZON V87.54

Recuperação de acréscimos isolados no OmniVoice: quando a conferência detecta todas as palavras do TXT e palavras extras, solicita tempos por palavra ao reconhecedor. Só remove intervalos identificados como inserções que não sobreponham palavras solicitadas, estejam dentro do áudio e tenham tempos válidos. Depois transcreve o áudio corrigido novamente e só aceita a correção se o texto estiver completo sem acréscimos. Não corta por substituições, palavras ausentes ou tempos ambíguos; nesses casos continua as tentativas de geração.

Mantém o fluxo da V87.53: quando não conseguir confirmar, salva o melhor áudio válido marcado para revisão. Portanto, esta recuperação reduz acréscimos detectáveis e isoláveis, mas não garante eliminá-los em todos os casos.

60 testes de conferência, geração reutilizada e revisão aprovados, incluindo remoção de inserção, reconferência e rejeição de tempos sobrepostos. Sem teste auditivo ou nova geração do áudio real do projeto. Pacote contém código-fonte e scripts, sem executável compilado nem modelos.
