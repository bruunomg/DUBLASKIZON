# DUBLASKIZON V87.20

## Ouvir Cena acompanha a seleção e descobre novas dublagens

Clonagem + Dublagem, Revisão e Dublagem Personalizada sincronizam a seleção
da lista com a janela Ouvir Cena quando ela já está aberta. ANTERIOR/PRÓXIMO
continua sincronizando a lista no outro sentido, com proteção contra ciclos
de callbacks. A seleção não abre uma janela fechada nem inicia reprodução
sozinha. A confirmação de edição pendente continua na navegação.

Cada avanço ou retorno consulta novamente o par da cena escolhida. Um
resultado anterior “ainda sem dublado” não fica preso no cache quando o
WAV é criado. Os controles e as formas de onda carregam a nova saída sem
precisar fechar e reabrir a janela. As atualizações de cena já existentes
ao finalizar uma geração continuam funcionando.

A resolução permanece sob demanda por cena, sem varrer todas as pastas
ou carregar os WAVs de uma lista inteira. Os índices de navegação e as
chaves completas das cenas preservam a hierarquia e a distinção entre
áudios normais e personalizados. Síntese e conferência não foram alteradas.

## Validação

- 146 testes automatizados da suíte principal passaram.
- 3 testes novos com janelas Tk reais passaram: dublagem criada após a
  primeira visita em normal/personalizado, seleção na mesma janela sem
  loop e ausência de abertura automática quando a janela está fechada.
- Testes de atualização após redublagem e playlist de 3.000 itens passaram;
  a abertura desta playlist levou cerca de 0,154 s no teste local.
- Verificações adicionais de destinos de redublagem, pastas, personalização
  e controles de revisão passaram.
- Um teste antigo de posição dos botões na janela com endereço longo falhou
  da mesma forma na V87.19 e na V87.20. A falha já existia antes desta mudança;
  os testes novos de navegação e carregamento passaram.

ZIP com fonte e scripts de compilação; não contém EXEs pré-compilados.
