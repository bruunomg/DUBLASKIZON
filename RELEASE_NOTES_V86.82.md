# Dublaskizon V86.82

Os três passos da janela **Requisitos** agora têm um monitor anti-travamento.

O monitor acompanha avanço real em bytes, saída do instalador e uso de CPU. Depois de 30 segundos sem atividade útil, a segunda barra informa a situação e exibe uma contagem até a retomada. Se a paralisação chegar a quatro minutos, ou se um arquivo grande avançar menos de 1 MB nesse período, o processo é encerrado e reiniciado automaticamente.

São feitas até três tentativas. Pip, Hugging Face e Xet reutilizam os arquivos e blocos já presentes no cache, então a retomada não apaga os gigabytes concluídos. Se as três tentativas falharem, a operação termina com erro e registra qual arquivo permaneceu parado.
