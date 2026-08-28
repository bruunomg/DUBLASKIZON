"""Tradução central da interface do Dublaskizon.

O português é a fonte dos textos internos. Caminhos, nomes de arquivos, nomes de
modelos e conteúdo dos TXT não são traduzidos; somente a interface é localizada.
"""
from __future__ import annotations

from typing import Any

LANGUAGE_LABELS = {
    "pt": "Português",
    "en": "English",
    "ru": "Русский",
    "es": "Español",
}
LANGUAGE_CODES = {label: code for code, label in LANGUAGE_LABELS.items()}
CURRENT_LANGUAGE = "pt"

# As chaves permanecem em português para que o modo original nunca seja perdido.
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Dublaskizon": {"en": "Dublaskizon", "ru": "Dublaskizon", "es": "Dublaskizon"},
    "  Apenas troca o formato; não altera a duração": {"en": "  Only changes the format; does not alter the duration", "ru": "  Только меняет формат; длительность не изменяется", "es": "  Solo cambia el formato; no modifica la duración"},
    "OmniVoice + Audacity — dublagem e revisão em um único aplicativo": {
        "en": "OmniVoice + Audacity — dubbing and review in one application",
        "ru": "OmniVoice + Audacity — дубляж и проверка в одном приложении",
        "es": "OmniVoice + Audacity — doblaje y revisión en una sola aplicación",
    },
    "CLONAGEM + DUBLAGEM": {"en": "CLONING + DUBBING", "ru": "КЛОНИРОВАНИЕ + ДУБЛЯЖ", "es": "CLONACIÓN + DOBLAJE"},
    "REVISÃO": {"en": "REVIEW", "ru": "ПРОВЕРКА", "es": "REVISIÓN"},
    "CONVERTER DURAÇÃO": {"en": "CONVERT DURATION", "ru": "КОНВЕРТИРОВАТЬ ДЛИТЕЛЬНОСТЬ", "es": "CONVERTIR DURACIÓN"},
    "CONVERTER FORMATOS": {"en": "CONVERT FORMATS", "ru": "КОНВЕРТИРОВАТЬ ФОРМАТЫ", "es": "CONVERTIR FORMATOS"},
    "COMANDOS": {"en": "COMMANDS", "ru": "КОМАНДЫ", "es": "COMANDOS"},
    "COMANDOS DO TERMINAL": {"en": "TERMINAL COMMANDS", "ru": "КОМАНДЫ ТЕРМИНАЛА", "es": "COMANDOS DEL TERMINAL"},
    "Execute diagnósticos do Python, OmniVoice e ambiente sem abrir uma janela externa.": {
        "en": "Run Python, OmniVoice, and environment diagnostics without opening an external window.",
        "ru": "Запускайте диагностику Python, OmniVoice и среды без внешнего окна.",
        "es": "Ejecute diagnósticos de Python, OmniVoice y del entorno sin abrir una ventana externa.",
    },
    "Projeto ativo": {"en": "Active project", "ru": "Активный проект", "es": "Proyecto activo"},
    "Projeto atual:": {"en": "Current project:", "ru": "Текущий проект:", "es": "Proyecto actual:"},
    "Comando": {"en": "Command", "ru": "Команда", "es": "Comando"},
    "EXECUTAR": {"en": "RUN", "ru": "ЗАПУСТИТЬ", "es": "EJECUTAR"},
    "LIMPAR": {"en": "CLEAR", "ru": "ОЧИСТИТЬ", "es": "LIMPIAR"},
    "Saída do terminal": {"en": "Terminal output", "ru": "Вывод терминала", "es": "Salida del terminal"},
    "Python": {"en": "Python", "ru": "Python", "es": "Python"},
    "OmniVoice --help": {"en": "OmniVoice --help", "ru": "OmniVoice --help", "es": "OmniVoice --help"},
    "OmniVoice instalado": {"en": "OmniVoice installed", "ru": "OmniVoice установлен", "es": "OmniVoice instalado"},
    "Localizar OmniVoice": {"en": "Locate OmniVoice", "ru": "Найти OmniVoice", "es": "Localizar OmniVoice"},
    "APARÊNCIA: CLARA": {"en": "APPEARANCE: LIGHT", "ru": "ВИД: СВЕТЛАЯ", "es": "APARIENCIA: CLARA"},
    "ALTERNAR APARÊNCIA": {"en": "TOGGLE APPEARANCE", "ru": "СМЕНИТЬ ВИД", "es": "CAMBIAR APARIENCIA"},
    "ESCALA DA TELA": {"en": "UI SCALE", "ru": "МАСШТАБ", "es": "ESCALA DE PANTALLA"},
    "ATUALIZAR TELA": {"en": "REFRESH SCREEN", "ru": "ОБНОВИТЬ ЭКРАН", "es": "ACTUALIZAR PANTALLA"},
    "IDIOMA": {"en": "LANGUAGE", "ru": "ЯЗЫК", "es": "IDIOMA"},
    "IDIOMA:": {"en": "LANGUAGE:", "ru": "ЯЗЫК:", "es": "IDIOMA:"},
    "TUTORIAL PDF": {"en": "PDF TUTORIAL", "ru": "PDF-РУКОВОДСТВО", "es": "TUTORIAL PDF"},
    "SELECIONAR PROJETO": {"en": "SELECT PROJECT", "ru": "ВЫБРАТЬ ПРОЕКТ", "es": "SELECCIONAR PROYECTO"},
    "USAR PASTA DO EXE": {"en": "USE EXE FOLDER", "ru": "ПАПКА EXE", "es": "USAR CARPETA DEL EXE"},
    "Procurar...": {"en": "Browse...", "ru": "Обзор...", "es": "Examinar..."},
    "GERAR AS PASTAS DO PROJETO AQUI": {"en": "CREATE PROJECT FOLDERS HERE", "ru": "СОЗДАТЬ ПАПКИ ПРОЕКТА ЗДЕСЬ", "es": "CREAR LAS CARPETAS DEL PROYECTO AQUÍ"},
    "SELECIONAR ESTA PASTA": {"en": "SELECT THIS FOLDER", "ru": "ВЫБРАТЬ ЭТУ ПАПКУ", "es": "SELECCIONAR ESTA CARPETA"},
    "CANCELAR": {"en": "CANCEL", "ru": "ОТМЕНА", "es": "CANCELAR"},
    "Projeto:": {"en": "Project:", "ru": "Проект:", "es": "Proyecto:"},
    "Ferramenta / modelo": {"en": "Tool / model", "ru": "Инструмент / модель", "es": "Herramienta / modelo"},
    "Modo de geração": {"en": "Generation mode", "ru": "Режим генерации", "es": "Modo de generación"},
    "Pronúncia do R": {"en": "R pronunciation", "ru": "Произношение R", "es": "Pronunciación de la R"},
    "Suaviza ou reforça o R na síntese.": {"en": "Softens or strengthens the R in synthesis.", "ru": "Смягчает или усиливает R при синтезе.", "es": "Suaviza o refuerza la R en la síntesis."},
    "R SUAVE": {"en": "SOFT R", "ru": "МЯГКАЯ R", "es": "R SUAVE"},
    "R NORMAL": {"en": "NORMAL R", "ru": "НОРМАЛЬНАЯ R", "es": "R NORMAL"},
    "R FORTE": {"en": "STRONG R", "ru": "СИЛЬНАЯ R", "es": "R FUERTE"},
    "Descrição da voz (Voice Design)": {"en": "Voice description (Voice Design)", "ru": "Описание голоса (Voice Design)", "es": "Descripción de voz (Voice Design)"},
    "No Voice Cloning, o WAV da cena é a referência.": {"en": "In Voice Cloning, the scene WAV is the reference.", "ru": "В Voice Cloning WAV сцены используется как образец.", "es": "En Voice Cloning, el WAV de la escena es la referencia."},
    "Cenas / processos": {"en": "Scenes / processes", "ru": "Сцены / процессы", "es": "Escenas / procesos"},
    "Progresso da cena": {"en": "Scene progress", "ru": "Прогресс сцены", "es": "Progreso de la escena"},
    "Clonagem / referência": {"en": "Cloning / reference", "ru": "Клонирование / образец", "es": "Clonación / referencia"},
    "Dublagem / síntese": {"en": "Dubbing / synthesis", "ru": "Дубляж / синтез", "es": "Doblaje / síntesis"},
    "Processos e mensagens": {"en": "Processes and messages", "ru": "Процессы и сообщения", "es": "Procesos y mensajes"},
    "Selecione o modelo e o modo. A fila só começa ao clicar em INICIAR DUBLAGEM.": {"en": "Select the model and mode. The queue starts only when you click START DUBBING.", "ru": "Выберите модель и режим. Очередь запускается только после нажатия НАЧАТЬ ДУБЛЯЖ.", "es": "Seleccione el modelo y el modo. La cola comienza solo al pulsar INICIAR DOBLAJE."},
    "Nenhum par de wav + txt encontrado.": {"en": "No WAV + TXT pair found.", "ru": "Пара WAV + TXT не найдена.", "es": "No se encontró ningún par WAV + TXT."},
    "Nenhuma cena selecionada": {"en": "No scene selected", "ru": "Сцена не выбрана", "es": "Ninguna escena seleccionada"},
    "Aprovar": {"en": "Approve", "ru": "Одобрить", "es": "Aprobar"},
    "Rejeitar": {"en": "Reject", "ru": "Отклонить", "es": "Rechazar"},
    "Pronto para refazer a cena": {"en": "Ready to redo the scene", "ru": "Готово к переделке сцены", "es": "Listo para rehacer la escena"},
    "Nenhuma tradução alternativa selecionada": {"en": "No alternative translation selected", "ru": "Альтернативный перевод не выбран", "es": "No se seleccionó ninguna traducción alternativa"},
    "(nenhuma pasta selecionada)": {"en": "(no folder selected)", "ru": "(папка не выбрана)", "es": "(ninguna carpeta seleccionada)"},
    "Nenhum par de áudio + TXT encontrado.": {"en": "No audio + TXT pair found.", "ru": "Пара аудио + TXT не найдена.", "es": "No se encontró ningún par de audio + TXT."},
    "Cenas (0 áudios)": {"en": "Scenes (0 audio files)", "ru": "Сцены (0 аудио)", "es": "Escenas (0 audios)"},
    "Cenas (": {"en": "Scenes (", "ru": "Сцены (", "es": "Escenas ("},
    " áudios)": {"en": " audio files)", "ru": " аудио)", "es": " audios)"},
    "Originais: ": {"en": "Original: ", "ru": "Оригиналы: ", "es": "Originales: "},
    "Dublados: ": {"en": "Dubbed: ", "ru": "Дубляж: ", "es": "Doblados: "},
    "Pares: ": {"en": "Pairs: ", "ru": "Пары: ", "es": "Pares: "},
    "Áudios: ": {"en": "Audio files: ", "ru": "Аудио: ", "es": "Audios: "},
    "ÁUDIOS PARA CONVERTER (": {"en": "AUDIO FILES TO CONVERT (", "ru": "АУДИО ДЛЯ КОНВЕРТАЦИИ (", "es": "AUDIOS PARA CONVERTIR ("},
    "▶ OUVIR CENA": {"en": "▶ LISTEN TO SCENE", "ru": "▶ СЛУШАТЬ СЦЕНУ", "es": "▶ ESCUCHAR ESCENA"},
    "▶ OUVIR TODOS": {"en": "▶ LISTEN TO ALL", "ru": "▶ СЛУШАТЬ ВСЕ", "es": "▶ ESCUCHAR TODO"},
    "▶ OUVIR": {"en": "▶ LISTEN", "ru": "▶ СЛУШАТЬ", "es": "▶ ESCUCHAR"},
    "▶ ouvir em sequência": {"en": "▶ listen in sequence", "ru": "▶ слушать по порядку", "es": "▶ escuchar en secuencia"},
    "Pausar": {"en": "Pause", "ru": "Пауза", "es": "Pausar"},
    "Parar após cena": {"en": "Stop after scene", "ru": "Остановить после сцены", "es": "Parar después de la escena"},
    "Cancelar": {"en": "Cancel", "ru": "Отмена", "es": "Cancelar"},
    "INICIAR DUBLAGEM": {"en": "START DUBBING", "ru": "НАЧАТЬ ДУБЛЯЖ", "es": "INICIAR DOBLAJE"},
    "Aguardando início — escolha a ferramenta e clique em INICIAR DUBLAGEM": {"en": "Waiting to start — choose the tool and click START DUBBING", "ru": "Ожидание запуска — выберите инструмент и нажмите НАЧАТЬ ДУБЛЯЖ", "es": "Esperando el inicio — elija la herramienta y pulse INICIAR DOBLAJE"},
    "Tempo decorrido: 00:00:00": {"en": "Elapsed time: 00:00:00", "ru": "Прошло времени: 00:00:00", "es": "Tiempo transcurrido: 00:00:00"},
    "Tempo restante estimado: --:--:--": {"en": "Estimated remaining time: --:--:--", "ru": "Оставшееся время: --:--:--", "es": "Tiempo restante estimado: --:--:--"},
    "CONVERTER DURAÇÃO DOS ÁUDIOS DUBLADOS AO ORIGINAL": {"en": "CONVERT DUBBED AUDIO DURATION TO ORIGINAL", "ru": "ПРИВЕСТИ ДЛИТЕЛЬНОСТЬ ДУБЛЯЖА К ОРИГИНАЛУ", "es": "CONVERTIR LA DURACIÓN DEL AUDIO DOBLADO AL ORIGINAL"},
    "Ajuste para cutscenes com tempo exato": {"en": "Adjust for cutscenes with exact timing", "ru": "Настройка кат-сцен с точным временем", "es": "Ajuste para escenas con tiempo exacto"},
    "ÁUDIOS ORIGINAIS": {"en": "ORIGINAL AUDIO", "ru": "ОРИГИНАЛЬНОЕ АУДИО", "es": "AUDIOS ORIGINALES"},
    "ÁUDIOS DUBLADOS": {"en": "DUBBED AUDIO", "ru": "ДУБЛИРОВАННОЕ АУДИО", "es": "AUDIOS DOBLADOS"},
    "ÁUDIOS PARA CONVERTER": {"en": "AUDIO FILES TO CONVERT", "ru": "АУДИО ДЛЯ КОНВЕРТАЦИИ", "es": "AUDIOS PARA CONVERTIR"},
    "Nenhum arquivo carregado": {"en": "No file loaded", "ru": "Файл не загружен", "es": "Ningún archivo cargado"},
    "Adicione os áudios e escolha o formato de saída.": {"en": "Add audio files and choose the output format.", "ru": "Добавьте аудио и выберите выходной формат.", "es": "Añada audios y elija el formato de salida."},
    "Arraste arquivos ou uma pasta para a lista. A conversão usa os caminhos reais carregados.": {"en": "Drag files or a folder to the list. Conversion uses the actual loaded paths.", "ru": "Перетащите файлы или папку в список. Конвертация использует реальные загруженные пути.", "es": "Arrastre archivos o una carpeta a la lista. La conversión usa las rutas reales cargadas."},
    "Conversão de formato: aguardando": {"en": "Format conversion: waiting", "ru": "Конвертация формата: ожидание", "es": "Conversión de formato: esperando"},
    "Ferramentas: não verificadas": {"en": "Tools: not checked", "ru": "Инструменты: не проверены", "es": "Herramientas: no verificadas"},
    "Adicione os áudios e escolha o formato de saída.": {"en": "Add audio files and choose the output format.", "ru": "Добавьте аудио и выберите выходной формат.", "es": "Añada audios y elija el formato de salida."},
    "Pronto": {"en": "Ready", "ru": "Готово", "es": "Listo"},
    "Áudios: 0": {"en": "Audio files: 0", "ru": "Аудио: 0", "es": "Audios: 0"},
    "Pasta de saída": {"en": "Output folder", "ru": "Папка вывода", "es": "Carpeta de salida"},
    "Pasta de saída dos áudios convertidos": {"en": "Output folder for converted audio", "ru": "Папка вывода конвертированного аудио", "es": "Carpeta de salida de los audios convertidos"},
    "Escolher pasta de áudios para converter": {"en": "Choose audio folder to convert", "ru": "Выберите папку аудио для конвертации", "es": "Elegir carpeta de audios para convertir"},
    "Selecionar áudios para converter": {"en": "Select audio files to convert", "ru": "Выберите аудио для конвертации", "es": "Seleccionar audios para convertir"},
    "Formato de saída": {"en": "Output format", "ru": "Формат вывода", "es": "Formato de salida"},
    "Opções de saída": {"en": "Output options", "ru": "Параметры вывода", "es": "Opciones de salida"},
    "Remover silêncio inicial/final": {"en": "Remove initial/final silence", "ru": "Удалять тишину в начале/конце", "es": "Eliminar silencio inicial/final"},
    "IGUAL: a pasta 'AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO' recebe os áudios cuja duração já era igual à do original; nenhum ajuste de duração foi necessário.\n\nMAIOR: a pasta 'AUDIO CONVERTIDO ..MAIOR.. DURAÇÃO' recebe os áudios dublados mais longos que o original; eles são comprimidos para ficar com a duração do original.\n\nMENOR: a pasta 'AUDIO CONVERTIDO ..MENOR.. DURAÇÃO' recebe os áudios dublados mais curtos que o original; apenas silêncio é acrescentado no final para completar o tempo faltante.": {"en": "EQUAL: the folder 'AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO' receives audio whose duration was already equal to the original; no duration adjustment was needed.\n\nLONGER: the folder 'AUDIO CONVERTIDO ..MAIOR.. DURAÇÃO' receives dubbed audio longer than the original; it is compressed to match the original duration.\n\nSHORTER: the folder 'AUDIO CONVERTIDO ..MENOR.. DURAÇÃO' receives dubbed audio shorter than the original; only silence is added at the end to complete the missing time.", "ru": "РАВНАЯ: в папку 'AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO' попадает аудио, длительность которого уже совпадала с оригиналом; корректировка не потребовалась.\n\nБОЛЬШАЯ: в папку 'AUDIO CONVERTIDO ..MAIOR.. DURAÇÃO' попадает озвученное аудио длиннее оригинала; оно сжимается до длительности оригинала.\n\nМЕНЬШАЯ: в папку 'AUDIO CONVERTIDO ..MENOR.. DURAÇÃO' попадает озвученное аудио короче оригинала; в конец добавляется только тишина для восполнения недостающего времени.", "es": "IGUAL: la carpeta 'AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO' recibe los audios cuya duración ya era igual a la original; no fue necesario ajustar la duración.\n\nMAYOR: la carpeta 'AUDIO CONVERTIDO ..MAIOR.. DURAÇÃO' recibe los audios doblados más largos que el original; se comprimen hasta igualar la duración original.\n\nMENOR: la carpeta 'AUDIO CONVERTIDO ..MENOR.. DURAÇÃO' recibe los audios doblados más cortos que el original; solo se añade silencio al final para completar el tiempo que falta."},
    "CONVERTER AUDIOS": {"en": "CONVERT AUDIO", "ru": "КОНВЕРТИРОВАТЬ АУДИО", "es": "CONVERTIR AUDIOS"},
    "CONVERTER FORMATOS DE ÁUDIO": {"en": "CONVERT AUDIO FORMATS", "ru": "КОНВЕРТИРОВАТЬ ФОРМАТЫ АУДИО", "es": "CONVERTIR FORMATOS DE AUDIO"},
    "FILTRO RENOMEAR .WEM": {"en": "RENAME FILES FILTER", "ru": "ФИЛЬТР ПЕРЕИМЕНОВАНИЯ ФАЙЛОВ", "es": "FILTRO DE RENOMBRAR ARCHIVOS"},
    "FILTRO de RENOMEAR ARQUIVOS .WEM": {"en": "FILE RENAMING FILTER", "ru": "ФИЛЬТР ПЕРЕИМЕНОВАНИЯ ФАЙЛОВ", "es": "FILTRO DE RENOMBRAR ARCHIVOS"},
    "Adicionar áudios": {"en": "Add audio", "ru": "Добавить аудио", "es": "Añadir audios"},
    "ADICIONAR ÁUDIOS": {"en": "ADD AUDIO", "ru": "ДОБАВИТЬ АУДИО", "es": "AÑADIR AUDIOS"},
    "ABRIR PASTA": {"en": "OPEN FOLDER", "ru": "ОТКРЫТЬ ПАПКУ", "es": "ABRIR CARPETA"},
    "ABRIR LOCAL DO ÁUDIO": {"en": "OPEN AUDIO LOCATION", "ru": "ОТКРЫТЬ ПАПКУ АУДИО", "es": "ABRIR UBICACIÓN DEL AUDIO"},
    "ABRIR LOCAL DO ÁUDIO DUBLADO": {"en": "OPEN DUBBED AUDIO LOCATION", "ru": "ОТКРЫТЬ ПАПКУ ДУБЛИРОВАННОГО АУДИО", "es": "ABRIR UBICACIÓN DEL AUDIO DOBLADO"},
    "ABRIR LOCAL DO ÁUDIO ORIGINAL": {"en": "OPEN ORIGINAL AUDIO LOCATION", "ru": "ОТКРЫТЬ ПАПКУ ОРИГИНАЛЬНОГО АУДИО", "es": "ABRIR UBICACIÓN DEL AUDIO ORIGINAL"},
    "COPIAR NOME DO ÁUDIO": {"en": "COPY AUDIO NAME", "ru": "КОПИРОВАТЬ ИМЯ АУДИО", "es": "COPIAR NOMBRE DEL AUDIO"},
    "COPIAR LOCAL DO ÁUDIO DUBLADO": {"en": "COPY DUBBED AUDIO LOCATION", "ru": "КОПИРОВАТЬ ПУТЬ ДУБЛИРОВАННОГО АУДИО", "es": "COPIAR UBICACIÓN DEL AUDIO DOBLADO"},
    "COPIAR LOCAL DO ÁUDIO ORIGINAL": {"en": "COPY ORIGINAL AUDIO LOCATION", "ru": "КОПИРОВАТЬ ПУТЬ ОРИГИНАЛЬНОГО АУДИО", "es": "COPIAR UBICACIÓN DEL AUDIO ORIGINAL"},
    "LOCALIZAR": {"en": "FIND", "ru": "НАЙТИ", "es": "BUSCAR"},
    "Texto para localizar:": {"en": "Text to find:", "ru": "Текст для поиска:", "es": "Texto a buscar:"},
    "OUVIR: FFPLAY": {"en": "PLAY: FFPLAY", "ru": "ВОСПРОИЗВЕДЕНИЕ: FFPLAY", "es": "REPRODUCIR: FFPLAY"},
    "OUVIR: WINDOWS": {"en": "PLAY: WINDOWS", "ru": "ВОСПРОИЗВЕДЕНИЕ: WINDOWS", "es": "REPRODUCIR: WINDOWS"},
    "ESCOLHER": {"en": "CHOOSE", "ru": "ВЫБРАТЬ", "es": "ELEGIR"},
    "ABRIR PASTA DE SAÍDA": {"en": "OPEN OUTPUT FOLDER", "ru": "ОТКРЫТЬ ПАПКУ ВЫВОДА", "es": "ABRIR CARPETA DE SALIDA"},
    "SALVAR TUDO NA MESMA PASTA": {"en": "SAVE ALL IN ONE FOLDER", "ru": "СОХРАНИТЬ В ОДНУ ПАПКУ", "es": "GUARDAR TODO EN LA MISMA CARPETA"},
    "SEPARAR POR DURAÇÃO": {"en": "SEPARATE BY DURATION", "ru": "РАЗДЕЛИТЬ ПО ДЛИТЕЛЬНОСТИ", "es": "SEPARAR POR DURACIÓN"},
    "BAIXAR / PREPARAR FERRAMENTAS": {"en": "DOWNLOAD / PREPARE TOOLS", "ru": "СКАЧАТЬ / ПОДГОТОВИТЬ ИНСТРУМЕНТЫ", "es": "DESCARGAR / PREPARAR HERRAMIENTAS"},
    "REDIMENSIONAR ÁUDIO PARA CLONAR": {"en": "RESIZE AUDIO FOR CLONING", "ru": "ПОДГОТОВИТЬ АУДИО ДЛЯ КЛОНИРОВАНИЯ", "es": "REDIMENSIONAR AUDIO PARA CLONAR"},
    "Corte, junção e normalização para clonagem de voz": {"en": "Cutting, joining and normalization for voice cloning", "ru": "Обрезка, объединение и нормализация для клонирования голоса", "es": "Corte, unión y normalización para clonación de voz"},
    "Áudios carregados — suporte a MP3, WAV, FLAC, M4A, OGG e AAC": {"en": "Loaded audio — supports MP3, WAV, FLAC, M4A, OGG and AAC", "ru": "Загруженное аудио — поддерживаются MP3, WAV, FLAC, M4A, OGG и AAC", "es": "Audios cargados — admite MP3, WAV, FLAC, M4A, OGG y AAC"},
    "Arraste arquivos para a tabela ou use ADICIONAR ÁUDIOS.": {"en": "Drag files into the table or use ADD AUDIO.", "ru": "Перетащите файлы в таблицу или используйте ДОБАВИТЬ АУДИО.", "es": "Arrastre archivos a la tabla o use AÑADIR AUDIOS."},
    "Arquivo": {"en": "File", "ru": "Файл", "es": "Archivo"},
    "Duração": {"en": "Duration", "ru": "Длительность", "es": "Duración"},
    "Tamanho": {"en": "Size", "ru": "Размер", "es": "Tamaño"},
    "Formato": {"en": "Format", "ru": "Формат", "es": "Formato"},
    "Amostragem": {"en": "Sample rate", "ru": "Частота дискретизации", "es": "Frecuencia de muestreo"},
    "Canais": {"en": "Channels", "ru": "Каналы", "es": "Canales"},
    "Caminho": {"en": "Path", "ru": "Путь", "es": "Ruta"},
    "Destino da clonagem": {"en": "Cloning target", "ru": "Цель клонирования", "es": "Destino de clonación"},
    "OmniVoice VoiceStudio": {"en": "OmniVoice VoiceStudio", "ru": "OmniVoice VoiceStudio", "es": "OmniVoice VoiceStudio"},
    "ElevenLabs Instant": {"en": "ElevenLabs Instant", "ru": "ElevenLabs Instant", "es": "ElevenLabs Instant"},
    "ElevenLabs Professional": {"en": "ElevenLabs Professional", "ru": "ElevenLabs Professional", "es": "ElevenLabs Professional"},
    "Canais": {"en": "Channels", "ru": "Каналы", "es": "Canales"},
    "1 — mono": {"en": "1 — mono", "ru": "1 — моно", "es": "1 — mono"},
    "2 — estéreo": {"en": "2 — stereo", "ru": "2 — стерео", "es": "2 — estéreo"},
    "Pasta de saída": {"en": "Output folder", "ru": "Папка вывода", "es": "Carpeta de salida"},
    "Silêncio (dB)": {"en": "Silence (dB)", "ru": "Тишина (дБ)", "es": "Silencio (dB)"},
    "Silêncio mínimo (s)": {"en": "Minimum silence (s)", "ru": "Минимальная тишина (с)", "es": "Silencio mínimo (s)"},
    "Alvo OmniVoice (s)": {"en": "OmniVoice target (s)", "ru": "Цель OmniVoice (с)", "es": "Objetivo OmniVoice (s)"},
    "Bloco Pro (min)": {"en": "Pro block (min)", "ru": "Блок Pro (мин)", "es": "Bloque Pro (min)"},
    "Normalizar pico para −1 dBFS": {"en": "Normalize peak to −1 dBFS", "ru": "Нормализовать пик до −1 dBFS", "es": "Normalizar pico a −1 dBFS"},
    "PROCESSAR ÁUDIOS": {"en": "PROCESS AUDIO", "ru": "ОБРАБОТАТЬ АУДИО", "es": "PROCESAR AUDIOS"},
    "CANCELAR PROCESSAMENTO": {"en": "CANCEL PROCESSING", "ru": "ОТМЕНИТЬ ОБРАБОТКУ", "es": "CANCELAR PROCESAMIENTO"},
    "ABRIR SAÍDA": {"en": "OPEN OUTPUT", "ru": "ОТКРЫТЬ ВЫВОД", "es": "ABRIR SALIDA"},
    "LIMPAR LISTA": {"en": "CLEAR LIST", "ru": "ОЧИСТИТЬ СПИСОК", "es": "LIMPIAR LISTA"},
    "Adicione áudios para começar.": {"en": "Add audio to begin.", "ru": "Добавьте аудио, чтобы начать.", "es": "Añada audios para comenzar."},
    "ADICIONAR ÁUDIOS": {"en": "ADD AUDIO", "ru": "ДОБАВИТЬ АУДИО", "es": "AÑADIR AUDIOS"},
    "Todos os arquivos": {"en": "All files", "ru": "Все файлы", "es": "Todos los archivos"},
    "Selecionar áudios para clonar": {"en": "Select audio for cloning", "ru": "Выберите аудио для клонирования", "es": "Seleccionar audios para clonar"},
    "Escolher pasta com áudios para clonar": {"en": "Choose folder with audio for cloning", "ru": "Выберите папку с аудио для клонирования", "es": "Elegir carpeta con audios para clonar"},
    "Escolher pasta raiz de saída": {"en": "Choose output root folder", "ru": "Выберите корневую папку вывода", "es": "Elegir carpeta raíz de salida"},
    "Arquivos:": {"en": "Files:", "ru": "Файлы:", "es": "Archivos:"},
    "Duração total:": {"en": "Total duration:", "ru": "Общая длительность:", "es": "Duración total:"},
    "Tamanho total:": {"en": "Total size:", "ru": "Общий размер:", "es": "Tamaño total:"},
    "Selecione um arquivo para ver as barras de tamanho e duração.": {"en": "Select a file to see the size and duration bars.", "ru": "Выберите файл, чтобы увидеть шкалы размера и длительности.", "es": "Seleccione un archivo para ver las barras de tamaño y duración."},
    "Selecionado:": {"en": "Selected:", "ru": "Выбрано:", "es": "Seleccionado:"},
    "Nenhum áudio compatível foi carregado.": {"en": "No compatible audio was loaded.", "ru": "Совместимое аудио не загружено.", "es": "No se cargó ningún audio compatible."},
    "áudio(s) carregado(s).": {"en": "audio file(s) loaded.", "ru": "аудиофайл(ов) загружено.", "es": "audio(s) cargado(s)."},
    "Lista limpa. Nenhum arquivo do disco foi alterado.": {"en": "List cleared. No disk file was changed.", "ru": "Список очищен. Файлы на диске не изменены.", "es": "Lista limpiada. No se modificó ningún archivo del disco."},
    "Cancelamento solicitado...": {"en": "Cancellation requested...", "ru": "Запрошена отмена...", "es": "Cancelación solicitada..."},
    "Falha no processamento.": {"en": "Processing failed.", "ru": "Ошибка обработки.", "es": "Falló el procesamiento."},
    "OmniVoice: escolhe um segmento de 5–20 s, no máximo 25 s, preferencialmente entre pausas.": {"en": "OmniVoice: selects a 5–20 s segment, up to 25 s, preferably between pauses.", "ru": "OmniVoice: выбирает сегмент 5–20 с, максимум 25 с, желательно между паузами.", "es": "OmniVoice: selecciona un segmento de 5–20 s, máximo 25 s, preferiblemente entre pausas."},
    "ElevenLabs Instant: alvo de 60–180 s; a recomendação atual é cerca de 1–2 min de áudio limpo. Limite interno de 400 MB.": {"en": "ElevenLabs Instant: 60–180 s target; the current recommendation is about 1–2 min of clean audio. Internal limit: 400 MB.", "ru": "ElevenLabs Instant: цель 60–180 с; текущая рекомендация — около 1–2 минут чистого аудио. Внутренний лимит: 400 МБ.", "es": "ElevenLabs Instant: objetivo de 60–180 s; la recomendación actual es aproximadamente 1–2 min de audio limpio. Límite interno: 400 MB."},
    "ElevenLabs Professional: junta os áudios e divide em blocos de 30–45 min, para um total de até 180 min. Limite interno de 450 MB por bloco.": {"en": "ElevenLabs Professional: joins audio and splits it into 30–45 min blocks, for a total of up to 180 min. Internal limit: 450 MB per block.", "ru": "ElevenLabs Professional: объединяет аудио и делит его на блоки 30–45 минут, всего до 180 минут. Внутренний лимит: 450 МБ на блок.", "es": "ElevenLabs Professional: une los audios y los divide en bloques de 30–45 min, hasta 180 min en total. Límite interno: 450 MB por bloque."},
    "1. Adicione ou arraste um ou mais áudios; a tabela mostra duração, tamanho, formato, amostragem e canais.": {"en": "1. Add or drag one or more audio files; the table shows duration, size, format, sample rate and channels.", "ru": "1. Добавьте или перетащите аудио; таблица показывает длительность, размер, формат, частоту и каналы.", "es": "1. Añada o arrastre uno o más audios; la tabla muestra duración, tamaño, formato, frecuencia de muestreo y canales."},
    "2. Escolha OmniVoice, ElevenLabs Instant ou ElevenLabs Professional.": {"en": "2. Choose OmniVoice, ElevenLabs Instant or ElevenLabs Professional.", "ru": "2. Выберите OmniVoice, ElevenLabs Instant или ElevenLabs Professional.", "es": "2. Elija OmniVoice, ElevenLabs Instant o ElevenLabs Professional."},
    "3. Ajuste o corte em silêncio, o formato, os canais e a normalização de pico.": {"en": "3. Adjust silence cutting, format, channels and peak normalization.", "ru": "3. Настройте обрезку по тишине, формат, каналы и нормализацию пика.", "es": "3. Ajuste el corte en silencios, el formato, los canales y la normalización del pico."},
    "4. Clique em PROCESSAR ÁUDIOS e confira as saídas na pasta organizada do destino.": {"en": "4. Click PROCESS AUDIO and check the outputs in the organized target folder.", "ru": "4. Нажмите ОБРАБОТАТЬ АУДИО и проверьте результаты в папке выбранной цели.", "es": "4. Pulse PROCESAR AUDIOS y revise los resultados en la carpeta organizada del destino."},
    "REDIMENSIONAR ÁUDIO PARA CLONAR": {"en": "RESIZE AUDIO FOR CLONING", "ru": "ПОДГОТОВИТЬ АУДИО ДЛЯ КЛОНИРОВАНИЯ", "es": "REDIMENSIONAR AUDIO PARA CLONAR"},
    "Ferramentas: não verificadas": {"en": "Tools: not checked", "ru": "Инструменты: не проверены", "es": "Herramientas: no verificadas"},
    "Áudios carregados:": {"en": "Loaded audio:", "ru": "Загружено аудио:", "es": "Audios cargados:"},
    "Cenas prontas:": {"en": "Ready scenes:", "ru": "Готовые сцены:", "es": "Escenas listas:"},
    "Progresso da cena": {"en": "Scene progress", "ru": "Прогресс сцены", "es": "Progreso de la escena"},
    "Ferramentas de áudio": {"en": "Audio tools", "ru": "Аудиоинструменты", "es": "Herramientas de audio"},
    "Converter áudios para WAV": {"en": "Convert audio to WAV", "ru": "Преобразовать аудио в WAV", "es": "Convertir audios a WAV"},
    "Ferramentas compartilhadas prontas: FFmpeg, FFprobe e FFplay.": {"en": "Shared tools ready: FFmpeg, FFprobe and FFplay.", "ru": "Общие инструменты готовы: FFmpeg, FFprobe и FFplay.", "es": "Herramientas compartidas listas: FFmpeg, FFprobe y FFplay."},
    "Ferramentas prontas para usar nesta aba.": {"en": "Tools ready to use in this tab.", "ru": "Инструменты готовы для этой вкладки.", "es": "Herramientas listas para usar en esta pestaña."},
    "Ferramentas preparadas": {"en": "Tools prepared", "ru": "Инструменты подготовлены", "es": "Herramientas preparadas"},
    "AUDIO FORMATOS CONVERTIDOS": {"en": "CONVERTED AUDIO FORMATS", "ru": "КОНВЕРТИРОВАННЫЕ ФОРМАТЫ АУДИО", "es": "FORMATOS DE AUDIO CONVERTIDOS"},
    "AUDIOS com DURAÇAO CONVERTIDAS": {"en": "AUDIO WITH CONVERTED DURATION", "ru": "АУДИО С КОНВЕРТИРОВАННОЙ ДЛИТЕЛЬНОСТЬЮ", "es": "AUDIOS CON DURACIÓN CONVERTIDA"},
    "OUVIR TODOS — FORMATOS": {"en": "LISTEN TO ALL — FORMATS", "ru": "СЛУШАТЬ ВСЕ — ФОРМАТЫ", "es": "ESCUCHAR TODO — FORMATOS"},
    "▶  INICIAR": {"en": "▶  START", "ru": "▶  НАЧАТЬ", "es": "▶  INICIAR"},
    "▶  INICIAR DUBLADO": {"en": "▶  START DUBBED", "ru": "▶  НАЧАТЬ ДУБЛЯЖ", "es": "▶  INICIAR DOBLADO"},
    "▶  INICIAR ORIGINAL": {"en": "▶  START ORIGINAL", "ru": "▶  НАЧАТЬ ОРИГИНАЛ", "es": "▶  INICIAR ORIGINAL"},
    "PARAR": {"en": "STOP", "ru": "СТОП", "es": "PARAR"},
    "◀ ANTERIOR": {"en": "◀ PREVIOUS", "ru": "◀ НАЗАД", "es": "◀ ANTERIOR"},
    "PRÓXIMO ▶": {"en": "NEXT ▶", "ru": "ДАЛЕЕ ▶", "es": "SIGUIENTE ▶"},
    "X  FECHAR": {"en": "X  CLOSE", "ru": "X  ЗАКРЫТЬ", "es": "X  CERRAR"},
    "EXPANDIR": {"en": "EXPAND", "ru": "РАЗВЕРНУТЬ", "es": "EXPANDIR"},
    "RESTAURAR": {"en": "RESTORE", "ru": "ВОССТАНОВИТЬ", "es": "RESTAURAR"},
    "OUTRAS TRADUÇÕES": {"en": "OTHER TRANSLATIONS", "ru": "ДРУГИЕ ПЕРЕВОДЫ", "es": "OTRAS TRADUCCIONES"},
    "TEXTO EM PORTUGUÊS — EDITÁVEL": {"en": "PORTUGUESE TEXT — EDITABLE", "ru": "ТЕКСТ НА ПОРТУГАЛЬСКОМ — РЕДАКТИРУЕМЫЙ", "es": "TEXTO EN PORTUGUÉS — EDITABLE"},
    "TEXTO ORIGINAL — EDITÁVEL": {"en": "ORIGINAL TEXT — EDITABLE", "ru": "ОРИГИНАЛЬНЫЙ ТЕКСТ — РЕДАКТИРУЕМЫЙ", "es": "TEXTO ORIGINAL — EDITABLE"},
    "TEXTO do WAV TRANSCRITO e TRADUZIDO — editável": {"en": "TRANSCRIBED AND TRANSLATED WAV TEXT — EDITABLE", "ru": "РАСШИФРОВАННЫЙ И ПЕРЕВЕДЁННЫЙ ТЕКСТ WAV — РЕДАКТИРУЕМЫЙ", "es": "TEXTO DEL WAV TRANSCRITO Y TRADUCIDO — EDITABLE"},
    "Salvar alteração": {"en": "Save change", "ru": "Сохранить изменение", "es": "Guardar cambio"},
    "SALVAR": {"en": "SAVE", "ru": "СОХРАНИТЬ", "es": "GUARDAR"},
    "EDITAR": {"en": "EDIT", "ru": "РЕДАКТИРОВАТЬ", "es": "EDITAR"},
    "SAIR DO EDITAR": {"en": "EXIT EDIT MODE", "ru": "ВЫЙТИ ИЗ РЕДАКТИРОВАНИЯ", "es": "SALIR DE EDICIÓN"},
    "CORTAR": {"en": "CUT", "ru": "ВЫРЕЗАТЬ", "es": "CORTAR"},
    "RECORTAR": {"en": "CUT OUT", "ru": "ВЫРЕЗАТЬ", "es": "RECORTAR"},
    "DELETE": {"en": "DELETE", "ru": "УДАЛИТЬ", "es": "ELIMINAR"},
    "COPIAR": {"en": "COPY", "ru": "КОПИРОВАТЬ", "es": "COPIAR"},
    "COLAR": {"en": "PASTE", "ru": "ВСТАВИТЬ", "es": "PEGAR"},
    "DESFAZER": {"en": "UNDO", "ru": "ОТМЕНИТЬ", "es": "DESHACER"},
    "REFAZER": {"en": "REDO", "ru": "ПОВТОРИТЬ", "es": "REHACER"},
    "Clique em EDITAR para selecionar trechos nas ondas.": {"en": "Click EDIT to select sections in the waveforms.", "ru": "Нажмите РЕДАКТИРОВАТЬ, чтобы выбрать фрагменты на формах волны.", "es": "Haga clic en EDITAR para seleccionar fragmentos en las formas de onda."},
    "Modo EDITAR ativo. Arraste sobre uma onda; ORIGINAL é somente leitura e COLAR aplica no DUBLADO.": {"en": "EDIT mode active. Drag over a waveform; ORIGINAL is read-only and PASTE applies to DUBBED.", "ru": "Режим РЕДАКТИРОВАНИЯ активен. Перетащите мышь по форме волны; ОРИГИНАЛ доступен только для чтения, а ВСТАВИТЬ применяется к ДУБЛЯЖУ.", "es": "Modo EDITAR activo. Arrastre sobre una forma de onda; ORIGINAL es de solo lectura y PEGAR se aplica a DOBLADO."},
    "DESTRAVAR": {"en": "UNLOCK", "ru": "РАЗБЛОКИРОВАТЬ", "es": "DESBLOQUEAR"},
    "TRAVAR": {"en": "LOCK", "ru": "ЗАБЛОКИРОВАТЬ", "es": "BLOQUEAR"},
    "APROVAR": {"en": "APPROVE", "ru": "ОДОБРИТЬ", "es": "APROBAR"},
    "REJEITAR": {"en": "REJECT", "ru": "ОТКЛОНИТЬ", "es": "RECHAZAR"},
    "REFAZER CENA": {"en": "REDO SCENE", "ru": "ПЕРЕДЕЛАТЬ СЦЕНУ", "es": "REHACER ESCENA"},
    "Abrir ORIGINAL + DUBLAGEM no Audacity": {"en": "Open ORIGINAL + DUBBING in Audacity", "ru": "Открыть ОРИГИНАЛ + ДУБЛЯЖ в Audacity", "es": "Abrir ORIGINAL + DOBLAJE en Audacity"},
    "HISTÓRICO DA CENA": {"en": "SCENE HISTORY", "ru": "ИСТОРИЯ СЦЕНЫ", "es": "HISTORIAL DE LA ESCENA"},
    "REVISÕES": {"en": "REVIEWS", "ru": "ПРОВЕРКИ", "es": "REVISIONES"},
    "WAV ORIGINAL": {"en": "ORIGINAL WAV", "ru": "ОРИГИНАЛЬНЫЙ WAV", "es": "WAV ORIGINAL"},
    "WAV DUBLADO": {"en": "DUBBED WAV", "ru": "WAV ДУБЛЯЖА", "es": "WAV DOBLADO"},
    "TXT PT": {"en": "PT TXT", "ru": "TXT PT", "es": "TXT PT"},
    "TXT ORIGINAL": {"en": "ORIGINAL TXT", "ru": "ОРИГИНАЛЬНЫЙ TXT", "es": "TXT ORIGINAL"},
    "TXT TRANSCRITO": {"en": "TRANSCRIBED TXT", "ru": "РАСШИФРОВАННЫЙ TXT", "es": "TXT TRANSCRITO"},
    "A pasta ainda não existe": {"en": "The folder does not exist yet", "ru": "Папка ещё не существует", "es": "La carpeta todavía no existe"},
    "Nenhuma pasta selecionada": {"en": "No folder selected", "ru": "Папка не выбрана", "es": "Ninguna carpeta seleccionada"},
    "Nenhum arquivo carregado": {"en": "No file loaded", "ru": "Файл не загружен", "es": "Ningún archivo cargado"},
    "Pronto": {"en": "Ready", "ru": "Готово", "es": "Listo"},
    "ATUALIZAR": {"en": "REFRESH", "ru": "ОБНОВИТЬ", "es": "ACTUALIZAR"},
    "Atenção": {"en": "Warning", "ru": "Внимание", "es": "Atención"},
    "Projeto": {"en": "Project", "ru": "Проект", "es": "Proyecto"},
    "Tutorial": {"en": "Tutorial", "ru": "Руководство", "es": "Tutorial"},
    "Pastas do projeto": {"en": "Project folders", "ru": "Папки проекта", "es": "Carpetas del proyecto"},
    "Dublagem em execução": {"en": "Dubbing in progress", "ru": "Дубляж выполняется", "es": "Doblaje en curso"},
    "Sair": {"en": "Exit", "ru": "Выход", "es": "Salir"},
    "Faltam ferramentas:": {"en": "Missing tools:", "ru": "Не хватает инструментов:", "es": "Faltan herramientas:"},
    "Clique em BAIXAR / PREPARAR FERRAMENTAS.": {"en": "Click DOWNLOAD / PREPARE TOOLS.", "ru": "Нажмите СКАЧАТЬ / ПОДГОТОВИТЬ ИНСТРУМЕНТЫ.", "es": "Pulse DESCARGAR / PREPARAR HERRAMIENTAS."},
    "Ferramenta / modelo": {"en": "Tool / model", "ru": "Инструмент / модель", "es": "Herramienta / modelo"},
    "Voice Cloning — usa o WAV de cada cena": {"en": "Voice Cloning — uses each scene WAV", "ru": "Voice Cloning — использует WAV каждой сцены", "es": "Voice Cloning — usa el WAV de cada escena"},
    "Voice Design — usa descrição da voz": {"en": "Voice Design — uses a voice description", "ru": "Voice Design — использует описание голоса", "es": "Voice Design — usa una descripción de voz"},
    "Auto Voice — voz automática": {"en": "Auto Voice — automatic voice", "ru": "Auto Voice — автоматический голос", "es": "Auto Voice — voz automática"},
    "Separar por duração": {"en": "Separate by duration", "ru": "Разделить по длительности", "es": "Separar por duración"},
    "Salvar tudo na mesma pasta": {"en": "Save everything in one folder", "ru": "Сохранить всё в одной папке", "es": "Guardar todo en la misma carpeta"},
    "WAV PCM 16-bit — 48 kHz — mono (Unreal)": {"en": "WAV PCM 16-bit — 48 kHz — mono (Unreal)", "ru": "WAV PCM 16 бит — 48 кГц — моно (Unreal)", "es": "WAV PCM 16-bit — 48 kHz — mono (Unreal)"},
    "WAV PCM 16-bit — 48 kHz — estéreo (Unreal)": {"en": "WAV PCM 16-bit — 48 kHz — stereo (Unreal)", "ru": "WAV PCM 16 бит — 48 кГц — стерео (Unreal)", "es": "WAV PCM 16-bit — 48 kHz — estéreo (Unreal)"},
    "WAV PCM 24-bit — 48 kHz — mono": {"en": "WAV PCM 24-bit — 48 kHz — mono", "ru": "WAV PCM 24 бит — 48 кГц — моно", "es": "WAV PCM 24-bit — 48 kHz — mono"},
    "WAV PCM 32-bit — 48 kHz — estéreo": {"en": "WAV PCM 32-bit — 48 kHz — stereo", "ru": "WAV PCM 32 бит — 48 кГц — стерео", "es": "WAV PCM 32-bit — 48 kHz — estéreo"},
    "WAV PCM 16-bit — manter frequência/canais": {"en": "WAV PCM 16-bit — keep sample rate/channels", "ru": "WAV PCM 16 бит — сохранить частоту/каналы", "es": "WAV PCM 16-bit — mantener frecuencia/canales"},
    "AIFF PCM 16-bit — 48 kHz — estéreo": {"en": "AIFF PCM 16-bit — 48 kHz — stereo", "ru": "AIFF PCM 16 бит — 48 кГц — стерео", "es": "AIFF PCM 16-bit — 48 kHz — estéreo"},
    "AIFF — 48 kHz — estéreo": {"en": "AIFF — 48 kHz — stereo", "ru": "AIFF — 48 кГц — стерео", "es": "AIFF — 48 kHz — estéreo"},
    "FLAC — 48 kHz — estéreo": {"en": "FLAC — 48 kHz — stereo", "ru": "FLAC — 48 кГц — стерео", "es": "FLAC — 48 kHz — estéreo"},
    "MP3 — 320 kbps — 48 kHz — estéreo": {"en": "MP3 — 320 kbps — 48 kHz — stereo", "ru": "MP3 — 320 кбит/с — 48 кГц — стерео", "es": "MP3 — 320 kbps — 48 kHz — stereo"},
    "MP3 — 192 kbps — 48 kHz — estéreo": {"en": "MP3 — 192 kbps — 48 kHz — stereo", "ru": "MP3 — 192 кбит/с — 48 кГц — стерео", "es": "MP3 — 192 kbps — 48 kHz — stereo"},
    "OGG Vorbis — qualidade alta": {"en": "OGG Vorbis — high quality", "ru": "OGG Vorbis — высокое качество", "es": "OGG Vorbis — alta calidad"},
    "Ferramentas de áudio": {"en": "Audio tools", "ru": "Аудиоинструменты", "es": "Herramientas de audio"},
    "CLONAR + DUBLAR": {"en": "CLONE + DUB", "ru": "КЛОНИРОВАТЬ + ДУБЛИРОВАТЬ", "es": "CLONAR + DOBLAR"},
    "REVISAR DUBLAGENS": {"en": "REVIEW DUBBING", "ru": "ПРОВЕРКА ДУБЛЯЖА", "es": "REVISAR DOBLAJES"},
    "Texto em português — editável": {"en": "Portuguese text — editable", "ru": "Текст на португальском — редактируемый", "es": "Texto en portugués — editable"},
    "TEXTO ORIGINAL — editável": {"en": "ORIGINAL TEXT — editable", "ru": "ОРИГИНАЛЬНЫЙ ТЕКСТ — редактируемый", "es": "TEXTO ORIGINAL — editable"},
    "TEXTO do WAV TRANSCRITO e TRADUZIDO — editável": {"en": "TRANSCRIBED AND TRANSLATED WAV TEXT — editable", "ru": "РАСШИФРОВАННЫЙ И ПЕРЕВЕДЁННЫЙ ТЕКСТ WAV — редактируемый", "es": "TEXTO DEL WAV TRANSCRITO Y TRADUCIDO — editable"},
    "Usar na REFAZER CENA": {"en": "Use for REDO SCENE", "ru": "Использовать для ПЕРЕДЕЛАТЬ СЦЕНУ", "es": "Usar para REHACER ESCENA"},
    "<< Anterior": {"en": "<< Previous", "ru": "<< Назад", "es": "<< Anterior"},
    "Próxima >>": {"en": "Next >>", "ru": "Далее >>", "es": "Siguiente >>"},
    "Abrir pasta do projeto": {"en": "Open project folder", "ru": "Открыть папку проекта", "es": "Abrir carpeta del proyecto"},
    "Revisão": {"en": "Review", "ru": "Проверка", "es": "Revisión"},
    "Histórico da cena": {"en": "Scene history", "ru": "История сцены", "es": "Historial de la escena"},
    "REFAZENDO A CENA": {"en": "REDOING THE SCENE", "ru": "ПЕРЕДЕЛЫВАНИЕ СЦЕНЫ", "es": "REHACIENDO LA ESCENA"},
    "CLONANDO REFERÊNCIA": {"en": "CLONING REFERENCE", "ru": "КЛОНИРОВАНИЕ ОБРАЗЦА", "es": "CLONANDO REFERENCIA"},
    "DUBLANDO CENA": {"en": "DUBBING SCENE", "ru": "ДУБЛИРОВАНИЕ СЦЕНЫ", "es": "DOBLANDO ESCENA"},
    "CARREGAR DA ABA REVISÃO": {"en": "LOAD FROM REVIEW TAB", "ru": "ЗАГРУЗИТЬ ИЗ ПРОВЕРКИ", "es": "CARGAR DESDE REVISIÓN"},
    "CARREGAR DA CLONAGEM + DUBLAGEM": {"en": "LOAD FROM CLONING + DUBBING", "ru": "ЗАГРУЗИТЬ ИЗ КЛОНИРОВАНИЯ + ДУБЛЯЖА", "es": "CARGAR DESDE CLONACIÓN + DOBLAJE"},
    "CARREGAR DA CONVERSÃO DE FORMATOS": {"en": "LOAD FROM FORMAT CONVERTER", "ru": "ЗАГРУЗИТЬ ИЗ КОНВЕРТЕРА ФОРМАТОВ", "es": "CARGAR DESDE CONVERSIÓN DE FORMATOS"},
    "Fila em execução...": {"en": "Queue running...", "ru": "Очередь выполняется...", "es": "Cola en ejecución..."},
    "Preparando referência e clonagem...": {"en": "Preparing reference and cloning...", "ru": "Подготовка образца и клонирование...", "es": "Preparando referencia y clonación..."},
    "Concluído: ": {"en": "Completed: ", "ru": "Завершено: ", "es": "Completado: "},
    "Erro em ": {"en": "Error in ", "ru": "Ошибка в ", "es": "Error en "},
    "Reproduzindo ": {"en": "Playing ", "ru": "Воспроизведение ", "es": "Reproduciendo "},
    "Reprodução concluída": {"en": "Playback complete", "ru": "Воспроизведение завершено", "es": "Reproducción terminada"},
    "Reprodução parada": {"en": "Playback stopped", "ru": "Воспроизведение остановлено", "es": "Reproducción detenida"},
    "Nenhum áudio disponível para reprodução": {"en": "No audio available for playback", "ru": "Нет аудио для воспроизведения", "es": "No hay audio disponible para reproducir"},
    "Selecione as duas pastas e clique em CONVERTER AUDIOS.": {"en": "Select both folders and click CONVERT AUDIO.", "ru": "Выберите обе папки и нажмите КОНВЕРТИРОВАТЬ АУДИО.", "es": "Seleccione ambas carpetas y pulse CONVERTIR AUDIOS."},
    "Nenhum par com o mesmo nome-base foi encontrado.": {"en": "No pair with the same base name was found.", "ru": "Пара с одинаковым именем не найдена.", "es": "No se encontró ningún par con el mismo nombre base."},
    "Conversão: aguardando": {"en": "Conversion: waiting", "ru": "Конвертация: ожидание", "es": "Conversión: esperando"},
    "Áudio carregado: ": {"en": "Audio loaded: ", "ru": "Аудио загружено: ", "es": "Audio cargado: "},
    "Cena: ": {"en": "Scene: ", "ru": "Сцена: ", "es": "Escena: "},
    "Status: ": {"en": "Status: ", "ru": "Статус: ", "es": "Estado: "},
    "Última ação: ": {"en": "Last action: ", "ru": "Последнее действие: ", "es": "Última acción: "},
    "Observação: ": {"en": "Observation: ", "ru": "Примечание: ", "es": "Observación: "},
    "\n\nVersões salvas:\n": {"en": "\n\nSaved versions:\n", "ru": "\n\nСохранённые версии:\n", "es": "\n\nVersiones guardadas:\n"},
    "- nenhuma versão arquivada ainda": {"en": "- no archived version yet", "ru": "- сохранённых версий пока нет", "es": "- aún no hay versiones archivadas"},
    "pendente": {"en": "pending", "ru": "ожидает", "es": "pendiente"},
    "aprovada": {"en": "approved", "ru": "одобрено", "es": "aprobada"},
    "rejeitada": {"en": "rejected", "ru": "отклонено", "es": "rechazada"},
    "Faltam ferramentas: ": {"en": "Missing tools: ", "ru": "Не хватает инструментов: ", "es": "Faltan herramientas: "},
    "Clique em BAIXAR / PREPARAR FERRAMENTAS.": {"en": "Click DOWNLOAD / PREPARE TOOLS.", "ru": "Нажмите СКАЧАТЬ / ПОДГОТОВИТЬ ИНСТРУМЕНТЫ.", "es": "Pulse DESCARGAR / PREPARAR HERRAMIENTAS."},
    "A conversão usa os caminhos reais carregados": {"en": "Conversion uses the actual loaded paths", "ru": "Конвертация использует реальные загруженные пути", "es": "La conversión usa las rutas reales cargadas"},
    "Carregado da aba ": {"en": "Loaded from the ", "ru": "Загружено из вкладки ", "es": "Cargado desde la pestaña "},
    "Confira os pares antes de converter.": {"en": "Check the pairs before converting.", "ru": "Проверьте пары перед конвертацией.", "es": "Compruebe los pares antes de convertir."},
    "Nenhuma pasta selecionada": {"en": "No folder selected", "ru": "Папка не выбрана", "es": "Ninguna carpeta seleccionada"},
    "Rejeitar cena": {"en": "Reject scene", "ru": "Отклонить сцену", "es": "Rechazar escena"},
    "Motivo opcional:": {"en": "Optional reason:", "ru": "Причина (необязательно):", "es": "Motivo opcional:"},
    "Abrir pasta do projeto": {"en": "Open project folder", "ru": "Открыть папку проекта", "es": "Abrir carpeta del proyecto"},
    "Falha ao abrir o par de áudios": {"en": "Failed to open the audio pair", "ru": "Не удалось открыть пару аудио", "es": "No se pudo abrir el par de audios"},
    "Aba de clonagem + dublagem selecionada.": {"en": "Cloning + dubbing tab selected.", "ru": "Выбрана вкладка клонирования + дубляжа.", "es": "Pestaña de clonación + doblaje seleccionada."},
    "REFAZER CENA concluído.": {"en": "REDO SCENE completed.", "ru": "ПЕРЕДЕЛКА СЦЕНЫ завершена.", "es": "REHACER ESCENA completado."},
    "REFAZER CENA com erro.": {"en": "REDO SCENE failed.", "ru": "ПЕРЕДЕЛКА СЦЕНЫ завершилась с ошибкой.", "es": "REHACER ESCENA con error."},
    "? AJUDA": {"en": "? HELP", "ru": "? СПРАВКА", "es": "? AYUDA"},
    "? AJUDA: ATIVA": {"en": "? HELP: ON", "ru": "? СПРАВКА: ВКЛ.", "es": "? AYUDA: ACTIVA"},
    "AJUDA CONTEXTUAL": {"en": "CONTEXTUAL HELP", "ru": "КОНТЕКСТНАЯ СПРАВКА", "es": "AYUDA CONTEXTUAL"},
    "A ajuda contextual está ativa. Passe o mouse sobre os marcadores ? para ver uma explicação.": {"en": "Contextual help is on. Hover over the ? markers to see an explanation.", "ru": "Контекстная справка включена. Наведите курсор на маркеры ?, чтобы увидеть объяснение.", "es": "La ayuda contextual está activa. Pase el ratón sobre los marcadores ? para ver una explicación."},
    "ABRIR PASSO A PASSO DA ABA ATUAL": {"en": "OPEN STEP-BY-STEP FOR CURRENT TAB", "ru": "ОТКРЫТЬ ПОШАГОВОЕ РУКОВОДСТВО ТЕКУЩЕЙ ВКЛАДКИ", "es": "ABRIR PASO A PASO DE LA PESTAÑA ACTUAL"},
    "DESATIVAR AJUDA": {"en": "DISABLE HELP", "ru": "ОТКЛЮЧИТЬ СПРАВКУ", "es": "DESACTIVAR AYUDA"},
    "Passo a passo — ": {"en": "Step by step — ", "ru": "Пошагово — ", "es": "Paso a paso — "},
    "Ajuda contextual": {"en": "Contextual help", "ru": "Контекстная справка", "es": "Ayuda contextual"},
    "Alterna entre as abas principais do aplicativo.": {"en": "Switches between the main application tabs.", "ru": "Переключает основные вкладки приложения.", "es": "Cambia entre las pestañas principales de la aplicación."},
    "Escolha o idioma da interface. Caminhos, arquivos e dados do usuário não são modificados.": {"en": "Choose the interface language. Paths, files, and user data are not modified.", "ru": "Выберите язык интерфейса. Пути, файлы и данные пользователя не изменяются.", "es": "Elija el idioma de la interfaz. Las rutas, archivos y datos del usuario no se modifican."},
    "Alterna entre os temas claro e escuro.": {"en": "Switches between light and dark themes.", "ru": "Переключает светлую и тёмную темы.", "es": "Cambia entre los temas claro y oscuro."},
    "Reconstrói a interface e recarrega as abas sem fechar o aplicativo.": {"en": "Rebuilds the interface and reloads the tabs without closing the application.", "ru": "Перестраивает интерфейс и перезагружает вкладки без закрытия приложения.", "es": "Reconstruye la interfaz y recarga las pestañas sin cerrar la aplicación."},
    "Reduz o tamanho visual da interface em 5%.": {"en": "Reduces the visual size of the interface by 5%.", "ru": "Уменьшает масштаб интерфейса на 5%.", "es": "Reduce el tamaño visual de la interfaz en un 5%."},
    "Aumenta o tamanho visual da interface em 5%.": {"en": "Increases the visual size of the interface by 5%.", "ru": "Увеличивает масштаб интерфейса на 5%.", "es": "Aumenta el tamaño visual de la interfaz en un 5%."},
    "Escolha o modelo de geração disponível para a fila.": {"en": "Choose the generation model available for the queue.", "ru": "Выберите доступную для очереди модель генерации.", "es": "Elija el modelo de generación disponible para la cola."},
    "Escolha o modo de geração: clonagem, design ou voz automática.": {"en": "Choose the generation mode: cloning, design, or automatic voice.", "ru": "Выберите режим: клонирование, дизайн или автоматический голос.", "es": "Elija el modo: clonación, diseño o voz automática."},
    "Digite a descrição usada pelo modo Voice Design.": {"en": "Enter the description used by Voice Design mode.", "ru": "Введите описание для режима Voice Design.", "es": "Escriba la descripción usada por Voice Design."},
    "Lista as cenas e os pares WAV + TXT encontrados no projeto.": {"en": "Lists the scenes and WAV + TXT pairs found in the project.", "ru": "Показывает сцены и пары WAV + TXT проекта.", "es": "Muestra las escenas y pares WAV + TXT encontrados en el proyecto."},
    "Inicia a fila de clonagem e dublagem.": {"en": "Starts the cloning and dubbing queue.", "ru": "Запускает очередь клонирования и дубляжа.", "es": "Inicia la cola de clonación y doblaje."},
    "Digite ou escolha um comando de diagnóstico.": {"en": "Enter or choose a diagnostic command.", "ru": "Введите или выберите диагностическую команду.", "es": "Escriba o elija un comando de diagnóstico."},
    "Mostra a saída dos comandos executados no projeto.": {"en": "Shows the output of commands run in the project.", "ru": "Показывает вывод команд, запущенных в проекте.", "es": "Muestra la salida de los comandos ejecutados en el proyecto."},
    "Lista as cenas disponíveis para revisão.": {"en": "Lists the scenes available for review.", "ru": "Показывает сцены, доступные для проверки.", "es": "Muestra las escenas disponibles para revisión."},
    "Edite o texto em português antes de salvar ou refazer uma cena.": {"en": "Edit the Portuguese text before saving or redoing a scene.", "ru": "Измените португальский текст перед сохранением или переделкой сцены.", "es": "Edite el texto en portugués antes de guardar o rehacer una escena."},
    "Lista os arquivos carregados para converter.": {"en": "Lists the files loaded for conversion.", "ru": "Показывает загруженные для конвертации файлы.", "es": "Muestra los archivos cargados para convertir."},
    "Lista os áudios originais carregados para comparar duração.": {"en": "Lists the original audio loaded for duration comparison.", "ru": "Показывает оригинальные аудио для сравнения длительности.", "es": "Muestra los audios originales cargados para comparar la duración."},
    "Lista os áudios dublados carregados para converter.": {"en": "Lists the dubbed audio loaded for conversion.", "ru": "Показывает дублированные аудио для конвертации.", "es": "Muestra los audios doblados cargados para convertir."},
    "Carrega os áudios reais do projeto a partir da aba Revisão.": {"en": "Loads the actual project audio from the Review tab.", "ru": "Загружает реальные аудио проекта из вкладки проверки.", "es": "Carga los audios reales del proyecto desde la pestaña Revisión."},
    "Carrega os áudios reais do projeto a partir da aba Clonagem + Dublagem.": {"en": "Loads the actual project audio from the Cloning + Dubbing tab.", "ru": "Загружает реальные аудио проекта из вкладки клонирования + дубляжа.", "es": "Carga los audios reales del proyecto desde la pestaña Clonación + Doblaje."},
    "Inicia a conversão de duração dos áudios.": {"en": "Starts audio duration conversion.", "ru": "Запускает конвертацию длительности аудио.", "es": "Inicia la conversión de duración de los audios."},
    "Inicia a conversão de duração dos áudios.": {"en": "Starts audio duration conversion.", "ru": "Запускает конвертацию длительности аудио.", "es": "Inicia la conversión de duración de los audios."},
    "Escolha o formato final do áudio.": {"en": "Choose the final audio format.", "ru": "Выберите конечный формат аудио.", "es": "Elija el formato final del audio."},
    "Escolha onde os arquivos convertidos serão gravados.": {"en": "Choose where converted files will be saved.", "ru": "Выберите место сохранения конвертированных файлов.", "es": "Elija dónde se guardarán los archivos convertidos."},
    "Inicia a conversão somente de formato, sem ajustar a duração.": {"en": "Starts format-only conversion without adjusting duration.", "ru": "Запускает только конвертацию формата без изменения длительности.", "es": "Inicia la conversión solo de formato sin ajustar la duración."},
    "Prepara FFmpeg, FFprobe, FFplay e SoX na pasta portátil.": {"en": "Prepares FFmpeg, FFprobe, FFplay, and SoX in the portable folder.", "ru": "Подготавливает FFmpeg, FFprobe, FFplay и SoX в переносимой папке.", "es": "Prepara FFmpeg, FFprobe, FFplay y SoX en la carpeta portátil."},
    "1. Selecione o modelo e o modo de geração.": {"en": "1. Select the model and generation mode.", "ru": "1. Выберите модель и режим генерации.", "es": "1. Seleccione el modelo y el modo de generación."},
    "2. Confira os pares WAV + TXT na lista de cenas.": {"en": "2. Check the WAV + TXT pairs in the scene list.", "ru": "2. Проверьте пары WAV + TXT в списке сцен.", "es": "2. Compruebe los pares WAV + TXT en la lista de escenas."},
    "3. Ajuste a descrição se estiver usando Voice Design.": {"en": "3. Adjust the description if you are using Voice Design.", "ru": "3. Измените описание, если используете Voice Design.", "es": "3. Ajuste la descripción si usa Voice Design."},
    "4. Clique em INICIAR DUBLAGEM e acompanhe o progresso.": {"en": "4. Click START DUBBING and follow the progress.", "ru": "4. Нажмите НАЧАТЬ ДУБЛЯЖ и следите за прогрессом.", "es": "4. Pulse INICIAR DOBLAJE y siga el progreso."},
    "1. Selecione uma cena na lista de revisão.": {"en": "1. Select a scene in the review list.", "ru": "1. Выберите сцену в списке проверки.", "es": "1. Seleccione una escena en la lista de revisión."},
    "2. Confira ou edite o texto em português e salve a alteração.": {"en": "2. Check or edit the Portuguese text and save the change.", "ru": "2. Проверьте или измените португальский текст и сохраните изменение.", "es": "2. Compruebe o edite el texto en portugués y guarde el cambio."},
    "3. Use Aprovar, Rejeitar ou REFAZER CENA conforme o resultado.": {"en": "3. Use Approve, Reject, or REDO SCENE according to the result.", "ru": "3. Используйте Одобрить, Отклонить или ПЕРЕДЕЛАТЬ СЦЕНУ.", "es": "3. Use Aprobar, Rechazar o REHACER ESCENA según el resultado."},
    "4. Use o player para ouvir o arquivo real carregado.": {"en": "4. Use the player to listen to the actual loaded file.", "ru": "4. Используйте проигрыватель для прослушивания реального файла.", "es": "4. Use el reproductor para escuchar el archivo real cargado."},
    "1. Carregue os áudios originais e dublados.": {"en": "1. Load the original and dubbed audio files.", "ru": "1. Загрузите оригинальные и дублированные аудио.", "es": "1. Cargue los audios originales y doblados."},
    "2. Escolha o formato e a organização da saída.": {"en": "2. Choose the format and output organization.", "ru": "2. Выберите формат и организацию вывода.", "es": "2. Elija el formato y la organización de salida."},
    "3. Ative a remoção de silêncio somente se desejar esse corte.": {"en": "3. Enable silence removal only if you want that cut.", "ru": "3. Включайте удаление тишины только при необходимости.", "es": "3. Active la eliminación de silencio solo si desea ese corte."},
    "4. Clique em CONVERTER AUDIOS e acompanhe a barra de progresso.": {"en": "4. Click CONVERT AUDIO and follow the progress bar.", "ru": "4. Нажмите КОНВЕРТИРОВАТЬ АУДИО и следите за прогрессом.", "es": "4. Pulse CONVERTIR AUDIOS y siga la barra de progreso."},
    "1. Carregue arquivos, uma pasta ou use um dos botões laranja do projeto.": {"en": "1. Load files, a folder, or use one of the orange project buttons.", "ru": "1. Загрузите файлы, папку или используйте одну из оранжевых кнопок проекта.", "es": "1. Cargue archivos, una carpeta o use uno de los botones naranjas del proyecto."},
    "2. Escolha somente o formato de saída desejado.": {"en": "2. Choose only the desired output format.", "ru": "2. Выберите нужный выходной формат.", "es": "2. Elija solo el formato de salida deseado."},
    "3. Confira a pasta de saída e clique em CONVERTER FORMATOS.": {"en": "3. Check the output folder and click CONVERT FORMATS.", "ru": "3. Проверьте папку вывода и нажмите КОНВЕРТИРОВАТЬ ФОРМАТЫ.", "es": "3. Compruebe la carpeta de salida y pulse CONVERTIR FORMATOS."},
    "4. Use INICIAR no player para ouvir um arquivo convertido.": {"en": "4. Use START in the player to listen to a converted file.", "ru": "4. Нажмите НАЧАТЬ в проигрывателе для прослушивания файла.", "es": "4. Use INICIAR en el reproductor para escuchar un archivo convertido."},
    "1. Escolha um comando pronto ou digite um comando no campo.": {"en": "1. Choose a preset command or type one in the field.", "ru": "1. Выберите готовую команду или введите её в поле.", "es": "1. Elija un comando preparado o escríbalo en el campo."},
    "2. Clique em EXECUTAR para rodar o diagnóstico no projeto.": {"en": "2. Click RUN to execute the diagnostic in the project.", "ru": "2. Нажмите ЗАПУСТИТЬ для выполнения диагностики в проекте.", "es": "2. Pulse EJECUTAR para ejecutar el diagnóstico en el proyecto."},
    "3. Leia a saída no painel e use LIMPAR quando quiser apagar o resultado.": {"en": "3. Read the output in the panel and use CLEAR when you want to remove it.", "ru": "3. Читайте вывод на панели и используйте ОЧИСТИТЬ для удаления результата.", "es": "3. Lea la salida en el panel y use LIMPIAR para borrarla."},
    "Renomeação segura e inteligente para qualquer arquivo": {"en": "Safe and intelligent renaming for any file", "ru": "Безопасное и интеллектуальное переименование любых файлов", "es": "Renombrado seguro e inteligente para cualquier archivo"},
    "Prévia automática atualizada. Os novos nomes piscam em verde; revise antes de confirmar.": {"en": "Automatic preview updated. New names flash green; review before confirming.", "ru": "Автоматический предпросмотр обновлён. Новые имена мигают зелёным; проверьте перед подтверждением.", "es": "Vista previa automática actualizada. Los nombres nuevos parpadean en verde; revise antes de confirmar."},
    "Ajuste numérico dos IDs": {"en": "Numeric ID adjustment", "ru": "Числовая корректировка ID", "es": "Ajuste numérico de IDs"},
    "Ajuste atual do ID: 0": {"en": "Current ID adjustment: 0", "ru": "Текущая корректировка ID: 0", "es": "Ajuste actual del ID: 0"},
    "Ajuste atual do ID:": {"en": "Current ID adjustment:", "ru": "Текущая корректировка ID:", "es": "Ajuste actual del ID:"},
    "VALOR PERSONALIZADO": {"en": "CUSTOM VALUE", "ru": "ПОЛЬЗОВАТЕЛЬСКОЕ ЗНАЧЕНИЕ", "es": "VALOR PERSONALIZADO"},
    "Ajuste personalizado": {"en": "Custom adjustment", "ru": "Пользовательская корректировка", "es": "Ajuste personalizado"},
    "Digite o valor do ajuste. Use número positivo para aumentar ou negativo para diminuir:": {"en": "Enter the adjustment. Use a positive number to increase or a negative number to decrease:", "ru": "Введите корректировку. Положительное число увеличивает, отрицательное уменьшает:", "es": "Introduzca el ajuste. Use un número positivo para aumentar o negativo para disminuir:"},
    "Ajuste de ID": {"en": "ID adjustment", "ru": "Корректировка ID", "es": "Ajuste de ID"},
    "aplicado somente na prévia. Nada foi renomeado.": {"en": "applied only to the preview. Nothing was renamed.", "ru": "применено только к предпросмотру. Ничего не переименовано.", "es": "aplicado solo a la vista previa. No se renombró nada."},
    "ajuste de ID": {"en": "ID adjustment", "ru": "корректировка ID", "es": "ajuste de ID"},
    "ajuste produziria ID negativo": {"en": "the adjustment would produce a negative ID", "ru": "корректировка создаст отрицательный ID", "es": "el ajuste produciría un ID negativo"},
    "+1": {"en": "+1", "ru": "+1", "es": "+1"},
    "+10": {"en": "+10", "ru": "+10", "es": "+10"},
    "−1": {"en": "−1", "ru": "−1", "es": "−1"},
    "−10": {"en": "−10", "ru": "−10", "es": "−10"},
    "ORIGINAL": {"en": "ORIGINAL", "ru": "ОРИГИНАЛ", "es": "ORIGINAL"},
    "DUBLADO": {"en": "DUBBED", "ru": "ДУБЛЯЖ", "es": "DOBLADO"},
    "FORMAS DE ONDA E COMPRIMENTO": {"en": "WAVEFORMS AND LENGTH", "ru": "ФОРМЫ ВОЛНЫ И ДЛИТЕЛЬНОСТЬ", "es": "FORMAS DE ONDA Y DURACIÓN"},
    "REVISÃO DA CENA": {"en": "SCENE REVIEW", "ru": "ПРОВЕРКА СЦЕНЫ", "es": "REVISIÓN DE LA ESCENA"},
    "PROCESSOS DE REFAZIMENTO": {"en": "REDO PROCESSES", "ru": "ПРОЦЕССЫ ПЕРЕДЕЛКИ", "es": "PROCESOS DE REHACER"},
    "Duração:": {"en": "Duration:", "ru": "Длительность:", "es": "Duración:"},
    "Duração: calculando...": {"en": "Duration: calculating...", "ru": "Длительность: вычисляется...", "es": "Duración: calculando..."},
    "Duração: indisponível": {"en": "Duration: unavailable", "ru": "Длительность: недоступна", "es": "Duración: no disponible"},
    "canais": {"en": "channels", "ru": "канала", "es": "canales"},
    "Onda não disponível para este áudio": {"en": "Waveform unavailable for this audio", "ru": "Форма волны недоступна для этого аудио", "es": "Forma de onda no disponible para este audio"},
    "Áudio sem amostras": {"en": "Audio has no samples", "ru": "В аудио нет отсчётов", "es": "El audio no tiene muestras"},
    "DUBLADOS": {"en": "DUBBED", "ru": "ДУБЛИРОВАННЫЕ", "es": "DOBLADOS"},
    "REDUBLAR": {"en": "REDUB", "ru": "ПЕРЕДЕЛАТЬ ДУБЛЯЖ", "es": "REDOBLAR"},
    "REDUBLAR COM OUTRO ÁUDIO": {"en": "REDUB WITH OTHER AUDIO", "ru": "ПЕРЕДЕЛАТЬ С ДРУГИМ АУДИО", "es": "REDOBLAR CON OTRO AUDIO"},
    "Escolher áudio para REDUBLAR COM OUTRO ÁUDIO": {"en": "Choose audio for REDUB WITH OTHER AUDIO", "ru": "Выберите аудио для ПЕРЕДЕЛАТЬ С ДРУГИМ АУДИО", "es": "Elegir audio para REDOBLAR CON OTRO AUDIO"},
    "ÁUDIOS DE REFERÊNCIA — WAV ORIGINAIS": {"en": "REFERENCE AUDIO — ORIGINAL WAV FILES", "ru": "ЭТАЛОННОЕ АУДИО — ОРИГИНАЛЬНЫЕ WAV", "es": "AUDIOS DE REFERENCIA — WAV ORIGINALES"},
    "ÁUDIOS DUBLADOS — WAV DUBLADO": {"en": "DUBBED AUDIO — DUBBED WAV FOLDER", "ru": "ОЗВУЧЕННЫЕ АУДИО — ПАПКА ОЗВУЧЕННЫХ WAV", "es": "AUDIOS DOBLADOS — CARPETA WAV DOBLADO"},
    "ÁUDIOS ORIGINAIS — WAV ORIGINAIS": {"en": "ORIGINAL AUDIO — ORIGINAL WAV FILES", "ru": "ОРИГИНАЛЬНОЕ АУДИО — ОРИГИНАЛЬНЫЕ WAV", "es": "AUDIOS ORIGINALES — WAV ORIGINALES"},
    "Nenhum WAV original encontrado — use ESCOLHER NESTE COMPUTADOR.": {"en": "No dubbed WAV found — use CHOOSE ON THIS COMPUTER.", "ru": "Озвученный WAV не найден — используйте ВЫБРАТЬ НА ЭТОМ КОМПЬЮТЕРЕ.", "es": "No se encontró WAV doblado — use ELEGIR EN ESTE ORDENADOR."},
    "Clique em um áudio para selecioná-lo. Use OUVIR CENA para escutar e confirme somente depois.": {"en": "Click an audio to select it. Use LISTEN TO SCENE to preview it, then confirm.", "ru": "Нажмите аудио, чтобы выбрать его. Используйте СЛУШАТЬ СЦЕНУ для прослушивания, затем подтвердите.", "es": "Haga clic en un audio para seleccionarlo. Use ESCUCHAR ESCENA para oírlo y confirme después."},
    "ESCOLHER NESTE COMPUTADOR": {"en": "CHOOSE ON THIS COMPUTER", "ru": "ВЫБРАТЬ НА ЭТОМ КОМПЬЮТЕРЕ", "es": "ELEGIR EN ESTE ORDENADOR"},
    "REDUBLAR COM ESSE ÁUDIO": {"en": "REDUB WITH THIS AUDIO", "ru": "ПЕРЕДЕЛАТЬ С ЭТИМ АУДИО", "es": "REDOBLAR CON ESTE AUDIO"},
    "Nenhum áudio foi encontrado em WAV ORIGINAIS. Use ESCOLHER NESTE COMPUTADOR para selecionar um arquivo externo.": {"en": "No audio was found in ORIGINAL WAV FILES. Use CHOOSE ON THIS COMPUTER to select an external file.", "ru": "В WAV ORIGINAIS аудио не найдено. Используйте ВЫБРАТЬ НА ЭТОМ КОМПЬЮТЕРЕ для внешнего файла.", "es": "No se encontró audio en WAV ORIGINALES. Use ELEGIR EN ESTE ORDENADOR para seleccionar un archivo externo."},
    "Selecione um áudio na lista ou use ESCOLHER NESTE COMPUTADOR.": {"en": "Select an audio from the list or use CHOOSE ON THIS COMPUTER.", "ru": "Выберите аудио из списка или используйте ВЫБРАТЬ НА ЭТОМ КОМПЬЮТЕРЕ.", "es": "Seleccione un audio de la lista o use ELEGIR EN ESTE ORDENADOR."},
    "Nenhum áudio selecionado": {"en": "No audio selected", "ru": "Аудио не выбрано", "es": "Ningún audio seleccionado"},
    "Selecione um áudio da lista ou escolha um arquivo neste computador.": {"en": "Select an audio from the list or choose a file on this computer.", "ru": "Выберите аудио из списка или файл на этом компьютере.", "es": "Seleccione un audio de la lista o elija un archivo en este ordenador."},
    "Selecionado:": {"en": "Selected:", "ru": "Выбрано:", "es": "Seleccionado:"},
    "Nenhum WAV original encontrado — use ESCOLHER NESTE COMPUTADOR.": {"en": "No original WAV found — use CHOOSE ON THIS COMPUTER.", "ru": "Оригинальный WAV не найден — используйте ВЫБРАТЬ НА ЭТОМ КОМПЬЮТЕРЕ.", "es": "No se encontró WAV original — use ELEGIR EN ESTE ORDENADOR."},
    "Abrir Audacity após redublar": {"en": "Open Audacity after redubbing", "ru": "Открыть Audacity после переделки дубляжа", "es": "Abrir Audacity después de redoblar"},
    "Pedido de alterar pronúncia do R": {"en": "Ask to change R pronunciation", "ru": "Запрашивать изменение произношения R", "es": "Pedir cambiar la pronunciación de la R"},
    "Alterar pronúncia do R": {"en": "Change R pronunciation", "ru": "Изменить произношение R", "es": "Cambiar la pronunciación de la R"},
    "Deseja alterar a pronúncia do R nesta redublagem?": {"en": "Change the R pronunciation for this redubbing?", "ru": "Изменить произношение R для этой переделки дубляжа?", "es": "¿Cambiar la pronunciación de la R para este redoblaje?"},
    "Escolha a pronúncia do R para esta redublagem": {"en": "Choose the R pronunciation for this redubbing", "ru": "Выберите произношение R для этой переделки дубляжа", "es": "Elija la pronunciación de la R para este redoblaje"},
    "A pronúncia do R desta vez será: ": {"en": "The R pronunciation for this run will be: ", "ru": "Произношение R для этого запуска: ", "es": "La pronunciación de la R para esta ejecución será: "},
    "FILTRO de RENOMEAR ARQUIVOS .WEM": {"en": "FILE RENAMING FILTER .WEM", "ru": "ФИЛЬТР ПЕРЕИМЕНОВАНИЯ ФАЙЛОВ .WEM", "es": "FILTRO PARA RENOMBRAR ARCHIVOS .WEM"},
    "GERAR ConversionMap.txt": {"en": "GENERATE ConversionMap.txt", "ru": "СОЗДАТЬ ConversionMap.txt", "es": "GENERAR ConversionMap.txt"},
    "GERAR PRÉVIA": {"en": "GENERATE PREVIEW", "ru": "СОЗДАТЬ ПРЕДПРОСМОТР", "es": "GENERAR VISTA PREVIA"},
    "PRÉ-VISUALIZAÇÃO": {"en": "PREVIEW", "ru": "ПРЕДПРОСМОТР", "es": "VISTA PREVIA"},
    "RENOMEAR COM SEGURANÇA": {"en": "RENAME SAFELY", "ru": "БЕЗОПАСНО ПЕРЕИМЕНОВАТЬ", "es": "RENOMBRAR CON SEGURIDAD"},
    "DESFAZER ÚLTIMA RENOMEAÇÃO": {"en": "UNDO LAST RENAME", "ru": "ОТМЕНИТЬ ПОСЛЕДНЕЕ ПЕРЕИМЕНОВАНИЕ", "es": "DESHACER ÚLTIMO CAMBIO DE NOMBRE"},
    "SALVAR RENOMEADOS": {"en": "SAVE RENAMED FILES", "ru": "СОХРАНИТЬ ПЕРЕИМЕНОВАННЫЕ", "es": "GUARDAR ARCHIVOS RENOMBRADOS"},
    "ABRIR ARQUIVOS": {"en": "OPEN FILES", "ru": "ОТКРЫТЬ ФАЙЛЫ", "es": "ABRIR ARCHIVOS"},
    "CARREGAR PROJETO": {"en": "LOAD PROJECT", "ru": "ЗАГРУЗИТЬ ПРОЕКТ", "es": "CARGAR PROYECTO"},
    "GERAR TXT IDs + NOMES": {"en": "GENERATE ID + NAME TXT", "ru": "СОЗДАТЬ TXT ID + ИМЕН", "es": "GENERAR TXT DE IDS + NOMBRES"},
    "LIMPAR ARQUIVOS CARREGADOS": {"en": "CLEAR LOADED FILES", "ru": "ОЧИСТИТЬ ЗАГРУЖЕННЫЕ ФАЙЛЫ", "es": "LIMPIAR ARCHIVOS CARGADOS"},
    "LOCAL DA PASTA DE ORIGEM — usado para ABRIR PASTA e salvar ConversionMap.txt": {"en": "SOURCE FOLDER — used to OPEN FOLDER and save ConversionMap.txt", "ru": "ИСХОДНАЯ ПАПКА — используется для ОТКРЫТЬ ПАПКУ и сохранения ConversionMap.txt", "es": "CARPETA DE ORIGEN — se usa para ABRIR CARPETA y guardar ConversionMap.txt"},
    "Você também pode arrastar arquivos ou pastas para esta área.": {"en": "You can also drag files or folders into this area.", "ru": "Вы также можете перетащить файлы или папки в эту область.", "es": "También puede arrastrar archivos o carpetas a esta área."},
    "Inteligência de renomeação": {"en": "Renaming intelligence", "ru": "Интеллект переименования", "es": "Inteligencia de renombrado"},
    "Inteligente (IDs + Wwise + mapa)": {"en": "Smart (IDs + Wwise + map)", "ru": "Интеллектуальный (ID + Wwise + карта)", "es": "Inteligente (IDs + Wwise + mapa)"},
    "Extrair ID: (123), #123 ou [123]": {"en": "Extract ID: (123), #123, or [123]", "ru": "Извлечь ID: (123), #123 или [123]", "es": "Extraer ID: (123), #123 o [123]"},
    "Wwise pós-processado: 123_convertido_HASH": {"en": "Post-processed Wwise: 123_converted_HASH", "ru": "Обработанный Wwise: 123_converted_HASH", "es": "Wwise posprocesado: 123_convertido_HASH"},
    "Remover sufixos Wwise: .created / _dublado": {"en": "Remove Wwise suffixes: .created / _dubbed", "ru": "Удалить суффиксы Wwise: .created / _dublado", "es": "Quitar sufijos Wwise: .created / _dublado"},
    "Usar nome base sem sufixos": {"en": "Use base name without suffixes", "ru": "Использовать базовое имя без суффиксов", "es": "Usar nombre base sin sufijos"},
    "Converter ID PCVR → Standalone por mapas Wwise": {"en": "Remap IDs by Wwise name correspondence", "ru": "Переназначить ID по соответствию имён Wwise", "es": "Remapear IDs por correspondencia de nombres Wwise"},
    "Largura do ID (0 = original)": {"en": "ID width (0 = original)", "ru": "Длина ID (0 = исходная)", "es": "Ancho del ID (0 = original)"},
    "Incluir subpastas": {"en": "Include subfolders", "ru": "Включать подпапки", "es": "Incluir subcarpetas"},
    "Renomear somente selecionados": {"en": "Rename selected only", "ru": "Переименовать только выбранные", "es": "Renombrar solo seleccionados"},
    "Limpar sufixos Wwise": {"en": "Clean Wwise suffixes", "ru": "Очистить суффиксы Wwise", "es": "Limpiar sufijos Wwise"},
    "Usar mapa Name → ID": {"en": "Use Name → ID map", "ru": "Использовать карту Name → ID", "es": "Usar mapa Name → ID"},
    "CARREGAR MAPA(S) WWISE": {"en": "LOAD WWISE MAP(S)", "ru": "ЗАГРУЗИТЬ КАРТУ(Ы) WWISE", "es": "CARGAR MAPA(S) WWISE"},
    "LIMPAR MAPA": {"en": "CLEAR MAP", "ru": "ОЧИСТИТЬ КАРТУ", "es": "LIMPIAR MAPA"},
    "Arquivos carregados — qualquer extensão": {"en": "Loaded files — any extension", "ru": "Загруженные файлы — любое расширение", "es": "Archivos cargados — cualquier extensión"},
    "Pré-visualização — nada é alterado até confirmar": {"en": "Preview — nothing changes until confirmed", "ru": "Предпросмотр — ничего не изменяется до подтверждения", "es": "Vista previa — nada cambia hasta confirmar"},
    "Estado": {"en": "Status", "ru": "Состояние", "es": "Estado"},
    "OK": {"en": "OK", "ru": "ОК", "es": "OK"},
    "CONFLITO": {"en": "CONFLICT", "ru": "КОНФЛИКТ", "es": "CONFLICTO"},
    "SEM ALTERAÇÃO": {"en": "NO CHANGE", "ru": "БЕЗ ИЗМЕНЕНИЙ", "es": "SIN CAMBIOS"},
    "RENOMEADO": {"en": "RENAMED", "ru": "ПЕРЕИМЕНОВАНО", "es": "RENOMBRADO"},
    "renomeação confirmada nesta sessão": {"en": "rename confirmed in this session", "ru": "переименование подтверждено в этой сессии", "es": "renombrado confirmado en esta sesión"},
    "padrão Wwise pós-processado": {"en": "post-processed Wwise pattern", "ru": "обработанный шаблон Wwise", "es": "patrón Wwise posprocesado"},
    "ID entre parênteses": {"en": "ID in parentheses", "ru": "ID в скобках", "es": "ID entre paréntesis"},
    "ID após #": {"en": "ID after #", "ru": "ID после #", "es": "ID después de #"},
    "ID entre colchetes": {"en": "ID in brackets", "ru": "ID в квадратных скобках", "es": "ID entre corchetes"},
    "ID identificado pelo rótulo": {"en": "ID identified by label", "ru": "ID по метке", "es": "ID identificado por etiqueta"},
    "nome já composto apenas por ID": {"en": "name already contains only the ID", "ru": "имя уже состоит только из ID", "es": "el nombre ya contiene solo el ID"},
    "número final do nome": {"en": "final number in the name", "ru": "последнее число в имени", "es": "número final del nombre"},
    "sufixo Wwise removido": {"en": "Wwise suffix removed", "ru": "суффикс Wwise удалён", "es": "sufijo Wwise eliminado"},
    "nenhum sufixo Wwise encontrado": {"en": "no Wwise suffix found", "ru": "суффикс Wwise не найден", "es": "no se encontró sufijo Wwise"},
    "nome base normalizado": {"en": "normalized base name", "ru": "нормализованное базовое имя", "es": "nombre base normalizado"},
    "carregue os mapas PCVR e Standalone": {"en": "load the PCVR and Standalone maps", "ru": "загрузите карты PCVR и Standalone", "es": "cargue los mapas PCVR y Standalone"},
    "ID PCVR não encontrado no mapa": {"en": "PCVR ID not found in the map", "ru": "ID PCVR не найден в карте", "es": "ID PCVR no encontrado en el mapa"},
    "padrão Wwise pós-processado não encontrado": {"en": "post-processed Wwise pattern not found", "ru": "обработанный шаблон Wwise не найден", "es": "no se encontró el patrón Wwise posprocesado"},
    "sufixo Wwise removido sem ID confiável": {"en": "Wwise suffix removed without a reliable ID", "ru": "суффикс Wwise удалён без надёжного ID", "es": "sufijo Wwise eliminado sin un ID fiable"},
    "dois ou mais arquivos receberiam o mesmo nome": {"en": "two or more files would receive the same name", "ru": "два или более файла получат одно имя", "es": "dos o más archivos recibirían el mismo nombre"},
    "o nome de destino já existe": {"en": "the destination name already exists", "ru": "имя назначения уже существует", "es": "el nombre de destino ya existe"},
    "Nome atual": {"en": "Current name", "ru": "Текущее имя", "es": "Nombre actual"},
    "Novo nome": {"en": "New name", "ru": "Новое имя", "es": "Nuevo nombre"},
    "Inteligência aplicada": {"en": "Applied intelligence", "ru": "Применённая логика", "es": "Inteligencia aplicada"},
    "Escolha uma pasta ou adicione arquivos de qualquer extensão.": {"en": "Choose a folder or add files of any extension.", "ru": "Выберите папку или добавьте файлы любого расширения.", "es": "Elija una carpeta o añada archivos de cualquier extensión."},
    "Arquivos: 0 | Prontos: 0 | Conflitos: 0 | Sem alteração: 0": {"en": "Files: 0 | Ready: 0 | Conflicts: 0 | No change: 0", "ru": "Файлы: 0 | Готово: 0 | Конфликты: 0 | Без изменений: 0", "es": "Archivos: 0 | Listos: 0 | Conflictos: 0 | Sin cambios: 0"},
    "Arquivos:": {"en": "Files:", "ru": "Файлы:", "es": "Archivos:"},
    "Prontos:": {"en": "Ready:", "ru": "Готово:", "es": "Listos:"},
    "Conflitos:": {"en": "Conflicts:", "ru": "Конфликты:", "es": "Conflictos:"},
    "Sem alteração:": {"en": "No change:", "ru": "Без изменений:", "es": "Sin cambios:"},
    "Prévia atualizada. Revise os nomes antes de confirmar.": {"en": "Preview updated. Review the names before confirming.", "ru": "Предпросмотр обновлён. Проверьте имена перед подтверждением.", "es": "Vista previa actualizada. Revise los nombres antes de confirmar."},
    "Nenhum mapa Wwise carregado": {"en": "No Wwise map loaded", "ru": "Карта Wwise не загружена", "es": "No se cargó ningún mapa Wwise"},
    "Nenhum mapa Wwise carregado; a prévia usa as regras internas.": {"en": "No Wwise map loaded; the preview uses built-in rules.", "ru": "Карта Wwise не загружена; предпросмотр использует встроенные правила.", "es": "No se cargó ningún mapa Wwise; la vista previa usa las reglas internas."},
    "Nenhum mapa Wwise carregado; a prévia usa apenas regras internas.": {"en": "No Wwise map loaded; the preview uses only built-in rules.", "ru": "Карта Wwise не загружена; предпросмотр использует только встроенные правила.", "es": "No se cargó ningún mapa Wwise; la vista previa usa solo las reglas internas."},
    "Mapa Wwise limpo. A prévia agora usa apenas as regras internas.": {"en": "Wwise map cleared. The preview now uses only built-in rules.", "ru": "Карта Wwise очищена. Предпросмотр теперь использует только встроенные правила.", "es": "Mapa Wwise limpiado. La vista previa ahora usa solo las reglas internas."},
    "Todos os mapas Wwise foram removidos da sessão; o uso de mapa foi desativado.": {"en": "All Wwise maps were removed from the session; map usage was disabled.", "ru": "Все карты Wwise удалены из сеанса; использование карты отключено.", "es": "Se eliminaron todos los mapas Wwise de la sesión; se desactivó su uso."},
    "Ao ativar esta opção, os silêncios do início e do final dos áudios serão cortados antes do ajuste de duração. Atenção: essa ferramenta também pode remover uma pequena parte da fala no começo e no fim. Confira os áudios após a conversão.": {
        "en": "When enabled, silence at the beginning and end of the audio is cut before duration adjustment. Warning: this tool may also remove a small part of the speech at the beginning and end. Check the audio after conversion.",
        "ru": "При включении тишина в начале и конце аудио удаляется перед изменением длительности. Внимание: инструмент может удалить небольшую часть речи в начале и конце. Проверьте аудио после конвертации.",
        "es": "Al activarla, el silencio inicial y final del audio se corta antes de ajustar la duración. Atención: esta herramienta también puede eliminar una pequeña parte de la voz al principio y al final. Compruebe los audios después de la conversión.",
    },
    "FFmpeg: converte e processa áudio e vídeo; é usado para gerar o formato de saída.\n\nFFprobe: consulta informações do arquivo, como duração, frequência e canais.\n\nFFplay: reproduz os áudios dentro do Dublaskizon.\n\nSoX: realiza operações de áudio, incluindo o ajuste de tempo usado em alguns áudios maiores.": {
        "en": "FFmpeg: converts and processes audio and video; it generates the output format.\n\nFFprobe: reads file information such as duration, sample rate, and channels.\n\nFFplay: plays audio inside Dublaskizon.\n\nSoX: performs audio operations, including the time adjustment used for some longer audio files.",
        "ru": "FFmpeg: конвертирует и обрабатывает аудио и видео; создаёт выходной формат.\n\nFFprobe: считывает сведения о файле, включая длительность, частоту и каналы.\n\nFFplay: воспроизводит аудио внутри Dublaskizon.\n\nSoX: выполняет операции с аудио, включая изменение времени некоторых длинных файлов.",
        "es": "FFmpeg: convierte y procesa audio y vídeo; genera el formato de salida.\n\nFFprobe: consulta información del archivo, como duración, frecuencia y canales.\n\nFFplay: reproduce audios dentro de Dublaskizon.\n\nSoX: realiza operaciones de audio, incluido el ajuste de tiempo usado en algunos audios más largos.",
    },
    "SELECIONAR TODOS": {"en": "SELECT ALL", "ru": "ВЫБРАТЬ ВСЕ", "es": "SELECCIONAR TODO"},
    "LIMPAR SELEÇÃO": {"en": "CLEAR SELECTION", "ru": "СНЯТЬ ВЫДЕЛЕНИЕ", "es": "LIMPIAR SELECCIÓN"},
    "▶ OUVIR CENA": {"en": "▶ LISTEN TO SCENE", "ru": "▶ СЛУШАТЬ СЦЕНУ", "es": "▶ ESCUCHAR ESCENA"},
    "PARAR ÁUDIO": {"en": "STOP AUDIO", "ru": "ОСТАНОВИТЬ АУДИО", "es": "DETENER AUDIO"},
    "PROCESSAR ÁUDIOS SELECIONADOS": {"en": "PROCESS SELECTED AUDIO", "ru": "ОБРАБОТАТЬ ВЫБРАННОЕ АУДИО", "es": "PROCESAR AUDIOS SELECCIONADOS"},
    "Conjunto completo:": {"en": "Full set:", "ru": "Весь набор:", "es": "Conjunto completo:"},
    "Selecionados: 0 | Duração: 00:00:00 | Tamanho: 0 B": {"en": "Selected: 0 | Duration: 00:00:00 | Size: 0 B", "ru": "Выбрано: 0 | Длительность: 00:00:00 | Размер: 0 Б", "es": "Seleccionados: 0 | Duración: 00:00:00 | Tamaño: 0 B"},
    "Saída estimada": {"en": "Estimated output", "ru": "Расчётный вывод", "es": "Salida estimada"},
    "Duração final": {"en": "Final duration", "ru": "Итоговая длительность", "es": "Duración final"},
    "Arraste arquivos para a tabela ou use ADICIONAR ÁUDIOS. Use Ctrl/Shift para marcar somente os áudios desejados; sem marcação, todos serão usados.": {"en": "Drag files into the table or use ADD AUDIO. Use Ctrl/Shift to mark only the audio you want; without a selection, all files will be used.", "ru": "Перетащите файлы в таблицу или используйте ДОБАВИТЬ АУДИО. Используйте Ctrl/Shift, чтобы выбрать нужные аудио; без выделения используются все файлы.", "es": "Arrastre archivos a la tabla o use AÑADIR AUDIOS. Use Ctrl/Shift para marcar solo los audios deseados; sin selección se usarán todos."},
    "Nenhuma marcação específica: PROCESSAR ÁUDIOS usará toda a lista carregada.": {"en": "No specific selection: PROCESS SELECTED AUDIO will use the entire loaded list.", "ru": "Нет отдельного выделения: ОБРАБОТАТЬ ВЫБРАННОЕ АУДИО использует весь загруженный список.", "es": "Sin selección específica: PROCESAR AUDIOS SELECCIONADOS usará toda la lista cargada."},
    "Reprodução parada.": {"en": "Playback stopped.", "ru": "Воспроизведение остановлено.", "es": "Reproducción detenida."},
    "Juntando": {"en": "Joining", "ru": "Объединение", "es": "Uniendo"},
    "áudio(s) selecionado(s)": {"en": "selected audio file(s)", "ru": "выбранных аудиофайлов", "es": "audio(s) seleccionado(s)"},
    "da lista": {"en": "from the list", "ru": "из списка", "es": "de la lista"},
    "O conjunto unido excedia": {"en": "The joined set exceeded", "ru": "Объединённый набор превышал", "es": "El conjunto unido superaba"},
    "o excedente foi cortado no final.": {"en": "the excess was cut from the end.", "ru": "лишнее было обрезано в конце.", "es": "el exceso se cortó al final."},
    "O total excedia 180 minutos; o processamento foi limitado aos primeiros 180 minutos, cortando o excedente no final.": {"en": "The total exceeded 180 minutes; processing was limited to the first 180 minutes, cutting the excess from the end.", "ru": "Общая длительность превышала 180 минут; обработка ограничена первыми 180 минутами, лишнее обрезано в конце.", "es": "El total superaba 180 minutos; el procesamiento se limitó a los primeros 180 minutos y el exceso se cortó al final."},
    "AJUDA DA CLONAGEM": {"en": "Select one or more audio files in the table. Use Ctrl/Shift to choose only the files you want; if nothing is selected, the whole loaded list is used.\n\nThe selected files are joined into one continuous audio before the target-specific cut. OmniVoice uses up to 25 seconds, ElevenLabs Instant up to 180 seconds, and Professional uses blocks up to 45 minutes and a total of up to 180 minutes.\n\nThe bars show the estimated final duration and output size for the selected format, channels and bitrate. If a limit is exceeded, the excess is cut from the end and a warning is recorded.\n\nUse ▶ LISTEN TO SCENE to play the selected audio inside Dublaskizon.", "ru": "Выберите один или несколько аудиофайлов в таблице. Используйте Ctrl/Shift, чтобы выбрать только нужные файлы; если ничего не выделено, используется весь загруженный список.\n\nВыбранные файлы объединяются в одну непрерывную запись перед обработкой для выбранной цели. OmniVoice использует до 25 секунд, ElevenLabs Instant — до 180 секунд, Professional — блоки до 45 минут и всего до 180 минут.\n\nШкалы показывают расчётную итоговую длительность и размер вывода для выбранного формата, каналов и битрейта. При превышении лимита лишнее обрезается в конце, а предупреждение записывается.\n\nИспользуйте ▶ СЛУШАТЬ СЦЕНУ, чтобы воспроизвести выбранное аудио внутри Dublaskizon.", "es": "Seleccione uno o más audios en la tabla. Use Ctrl/Shift para elegir solo los archivos deseados; si no selecciona ninguno, se usará toda la lista cargada.\n\nLos archivos seleccionados se unen en un audio continuo antes del corte según el destino. OmniVoice usa hasta 25 segundos, ElevenLabs Instant hasta 180 segundos y Professional usa bloques de hasta 45 minutos y un total de hasta 180 minutos.\n\nLas barras muestran la duración final y el tamaño de salida estimados para el formato, los canales y el bitrate elegidos. Si se supera un límite, el exceso se corta al final y se registra un aviso.\n\nUse ▶ ESCUCHAR ESCENA para reproducir el audio seleccionado dentro de Dublaskizon."},
    "OmniVoice VoiceStudio\n\nPadrão: 10 segundos em WAV PCM 16-bit, 44,1 kHz, mono.\nFaixa recomendada: 5–20 segundos; máximo interno: 25 segundos.\nUse uma fala limpa, sem música, ruído ou silêncio excessivo. O conjunto escolhido é unido antes do corte.": {"en": "OmniVoice VoiceStudio\n\nDefault: 10 seconds in 16-bit PCM WAV, 44.1 kHz, mono.\nRecommended range: 5–20 seconds; internal maximum: 25 seconds.\nUse clean speech without music, noise or excessive silence. The selected set is joined before cutting.", "ru": "OmniVoice VoiceStudio\n\nПо умолчанию: 10 секунд в 16-битном PCM WAV, 44,1 кГц, моно.\nРекомендуемый диапазон: 5–20 секунд; внутренний максимум: 25 секунд.\nИспользуйте чистую речь без музыки, шума и лишней тишины. Выбранный набор объединяется перед обрезкой.", "es": "OmniVoice VoiceStudio\n\nPredeterminado: 10 segundos en WAV PCM de 16 bits, 44,1 kHz, mono.\nRango recomendado: 5–20 segundos; máximo interno: 25 segundos.\nUse voz limpia, sin música, ruido ni silencio excesivo. El conjunto elegido se une antes del corte."},
    "ElevenLabs Instant\n\nPadrão: 120 segundos em MP3 256 kbps, 44,1 kHz, mono, para boa compatibilidade e upload menor.\nFaixa recomendada: 60–180 segundos. Limite de tamanho tratado pelo app: 400 MB como margem conservadora.\nEscolha uma voz limpa, contínua e sem música; o excedente é cortado no final.": {"en": "ElevenLabs Instant\n\nDefault: 120 seconds in 256 kbps MP3, 44.1 kHz, mono, for good compatibility and smaller uploads.\nRecommended range: 60–180 seconds. App-handled size limit: 400 MB as a conservative margin.\nChoose clean, continuous speech without music; excess is cut from the end.", "ru": "ElevenLabs Instant\n\nПо умолчанию: 120 секунд в MP3 256 кбит/с, 44,1 кГц, моно — для совместимости и меньшей загрузки.\nРекомендуемый диапазон: 60–180 секунд. Ограничение размера в приложении: 400 МБ как консервативный запас.\nВыберите чистую непрерывную речь без музыки; лишнее обрезается в конце.", "es": "ElevenLabs Instant\n\nPredeterminado: 120 segundos en MP3 de 256 kbps, 44,1 kHz, mono, para buena compatibilidad y cargas menores.\nRango recomendado: 60–180 segundos. Límite de tamaño tratado por la app: 400 MB como margen conservador.\nElija voz limpia y continua, sin música; el exceso se corta al final."},
    "ElevenLabs Professional\n\nPadrão: blocos de 30 minutos em FLAC ou WAV, 44,1 kHz, mono.\nO app organiza o conjunto em blocos de 30–45 minutos, com total de até 180 minutos.\nLimite de tamanho tratado pelo app: 450 MB por bloco como margem conservadora. O excedente total é cortado no final.": {"en": "ElevenLabs Professional\n\nDefault: 30-minute blocks in FLAC or WAV, 44.1 kHz, mono.\nThe app organizes the set into 30–45 minute blocks, with a total of up to 180 minutes.\nApp-handled size limit: 450 MB per block as a conservative margin. Total excess is cut from the end.", "ru": "ElevenLabs Professional\n\nПо умолчанию: блоки по 30 минут в FLAC или WAV, 44,1 кГц, моно.\nПриложение организует набор в блоки 30–45 минут, всего до 180 минут.\nОграничение размера в приложении: 450 МБ на блок как консервативный запас. Лишняя общая длительность обрезается в конце.", "es": "ElevenLabs Professional\n\nPredeterminado: bloques de 30 minutos en FLAC o WAV, 44,1 kHz, mono.\nLa app organiza el conjunto en bloques de 30–45 minutos, hasta 180 minutos en total.\nLímite de tamaño tratado por la app: 450 MB por bloque como margen conservador. El exceso total se corta al final."},
}


def set_current_language(language: str) -> str:
    global CURRENT_LANGUAGE
    language = language if language in LANGUAGE_LABELS else "pt"
    CURRENT_LANGUAGE = language
    return language


def tr(text: Any, language: str | None = None) -> Any:
    if not isinstance(text, str):
        return text
    language = language or CURRENT_LANGUAGE
    if language == "pt":
        return text
    mapping = _TRANSLATIONS.get(text)
    if mapping and language in mapping:
        return mapping[language]
    # Traduz frases compostas, mantendo nomes de arquivos e caminhos intactos.
    result = text
    for source, values in sorted(_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        replacement = values.get(language)
        if replacement and source in result:
            result = result.replace(source, replacement)
    return result


def localized_messagebox(raw_messagebox):
    """Retorna um proxy de messagebox que traduz títulos e mensagens no idioma atual."""
    if raw_messagebox is None:
        return raw_messagebox
    class _LocalizedMessageBox:
        def __getattr__(self, name):
            method = getattr(raw_messagebox, name)
            if name not in {"showinfo", "showwarning", "showerror", "askyesno", "askokcancel", "askretrycancel"}:
                return method
            def localized(title, message, *args, **kwargs):
                return method(tr(title), tr(message), *args, **kwargs)
            return localized
    return _LocalizedMessageBox()


def localized_simpledialog(raw_simpledialog):
    """Proxy para diálogos de texto, traduzindo título e pergunta."""
    if raw_simpledialog is None:
        return raw_simpledialog
    class _LocalizedSimpleDialog:
        def __getattr__(self, name):
            method = getattr(raw_simpledialog, name)
            if name != "askstring":
                return method
            def localized(title, prompt, *args, **kwargs):
                return method(tr(title), tr(prompt), *args, **kwargs)
            return localized
    return _LocalizedSimpleDialog()


def source_text(text: Any) -> Any:
    """Converte uma opção traduzida de volta ao texto português interno."""
    if not isinstance(text, str):
        return text
    if text in _TRANSLATIONS:
        return text
    for source, values in sorted(_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        if text == values.get(CURRENT_LANGUAGE):
            return source
        if text in values.values():
            return source
        translated_prefix = values.get(CURRENT_LANGUAGE)
        if translated_prefix and text.startswith(translated_prefix):
            return source + text[len(translated_prefix):]
    return text


def translate_widget_tree(root, language: str | None = None) -> None:
    """Traduz textos de widgets existentes, preservando a fonte em português."""
    language = set_current_language(language or CURRENT_LANGUAGE)

    def visit(widget):
        try:
            widget_class = str(widget.winfo_class())
        except Exception:
            widget_class = ""
        try:
            if widget_class in {"Tk", "Toplevel"}:
                current_title = str(widget.title())
                previous_title = getattr(widget, "_dublagenskizon_i18n_title_render", None)
                source_title = getattr(widget, "_dublagenskizon_i18n_title_source", None)
                if source_title is None or current_title != previous_title:
                    source_title = current_title
                    setattr(widget, "_dublagenskizon_i18n_title_source", source_title)
                rendered_title = tr(source_title, language)
                widget.title(rendered_title)
                setattr(widget, "_dublagenskizon_i18n_title_render", rendered_title)
        except Exception:
            pass
        try:
            if widget_class not in {"Entry", "TEntry", "Text", "Listbox", "Canvas", "Scrollbar", "TScrollbar", "TCombobox", "Combobox"}:
                current = str(widget.cget("text"))
                if current or hasattr(widget, "_dublagenskizon_i18n_source"):
                    previous_render = getattr(widget, "_dublagenskizon_i18n_render", None)
                    source = getattr(widget, "_dublagenskizon_i18n_source", None)
                    if source is None or current != previous_render:
                        source = current
                        setattr(widget, "_dublagenskizon_i18n_source", source)
                    rendered = tr(source, language)
                    widget.configure(text=rendered)
                    setattr(widget, "_dublagenskizon_i18n_render", rendered)
            if widget_class in {"TCombobox", "Combobox"}:
                values = list(widget.cget("values"))
                rendered_values = list(getattr(widget, "_dublagenskizon_i18n_rendered_values", []))
                sources = getattr(widget, "_dublagenskizon_i18n_values", None)
                if sources is None or values != rendered_values:
                    sources = list(values)
                    setattr(widget, "_dublagenskizon_i18n_values", sources)
                current_value = str(widget.get())
                if current_value in rendered_values and current_value not in sources:
                    source_current = sources[rendered_values.index(current_value)]
                else:
                    source_current = current_value
                new_values = [tr(source, language) for source in sources]
                widget.configure(values=new_values)
                if source_current in sources:
                    widget.set(tr(source_current, language))
                setattr(widget, "_dublagenskizon_i18n_rendered_values", new_values)
            textvariable = str(widget.cget("textvariable"))
            if textvariable and widget_class in {"Label", "TLabel", "Labelframe", "TLabelframe", "Button", "TButton", "Checkbutton", "TCheckbutton", "Radiobutton", "TRadiobutton"}:
                current_value = str(widget.getvar(textvariable))
                previous_render = getattr(widget, "_dublagenskizon_i18n_var_render", None)
                source_value = getattr(widget, "_dublagenskizon_i18n_var_source", None)
                if source_value is None:
                    source_value = current_value
                    setattr(widget, "_dublagenskizon_i18n_var_source", source_value)
                elif current_value != previous_render:
                    source_value = source_text(current_value)
                    setattr(widget, "_dublagenskizon_i18n_var_source", source_value)
                rendered_value = tr(source_value, language)
                widget.setvar(textvariable, rendered_value)
                setattr(widget, "_dublagenskizon_i18n_var_render", rendered_value)
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                visit(child)
        except Exception:
            pass

    visit(root)
    try:
        for child_name in root.tk.call("winfo", "children", ".").split():
            if child_name != str(root):
                visit(root.nametowidget(child_name))
    except Exception:
        pass


def translation_table() -> dict[str, dict[str, str]]:
    return _TRANSLATIONS.copy()


_HELP_STEPS = {
    "clone": [
        "1. Selecione o modelo e o modo de geração.",
        "2. Confira os pares WAV + TXT na lista de cenas.",
        "3. Ajuste a descrição se estiver usando Voice Design.",
        "4. Clique em INICIAR DUBLAGEM e acompanhe o progresso.",
    ],
    "review": [
        "1. Selecione uma cena na lista de revisão.",
        "2. Confira ou edite o texto em português e salve a alteração.",
        "3. Use Aprovar, Rejeitar ou REFAZER CENA conforme o resultado.",
        "4. Use o player para ouvir o arquivo real carregado.",
    ],
    "converter": [
        "1. Carregue os áudios originais e dublados.",
        "2. Escolha o formato e a organização da saída.",
        "3. Ative a remoção de silêncio somente se desejar esse corte.",
        "4. Clique em CONVERTER AUDIOS e acompanhe a barra de progresso.",
    ],
    "format": [
        "1. Carregue arquivos, uma pasta ou use um dos botões laranja do projeto.",
        "2. Escolha somente o formato de saída desejado.",
        "3. Confira a pasta de saída e clique em CONVERTER FORMATOS.",
        "4. Use INICIAR no player para ouvir um arquivo convertido.",
    ],
    "terminal": [
        "1. Escolha um comando pronto ou digite um comando no campo.",
        "2. Clique em EXECUTAR para rodar o diagnóstico no projeto.",
        "3. Leia a saída no painel e use LIMPAR quando quiser apagar o resultado.",
    ],
    "wem_filter": [
        "1. Adicione arquivos, escolha uma pasta ou arraste arquivos e pastas para a lista.",
        "2. Escolha a regra inteligente e confira a prévia antes de aplicar.",
        "3. Use PROCESSAR TUDO para gerar o TXT de IDs + nomes e renomear com segurança.",
        "4. Se necessário, use DESFAZER ÚLTIMA RENOMEAÇÃO para restaurar os nomes anteriores.",
    ],
    "voice_clone": [
        "1. Adicione ou arraste um ou mais áudios; a tabela mostra duração, tamanho, formato, amostragem e canais.",
        "2. Escolha OmniVoice, ElevenLabs Instant ou ElevenLabs Professional.",
        "3. Ajuste o corte em silêncio, o formato, os canais e a normalização de pico.",
        "4. Clique em PROCESSAR ÁUDIOS e confira as saídas na pasta organizada do destino.",
    ],
}


def help_steps(tab_key: str, language: str | None = None) -> list[str]:
    """Retorna instruções localizadas para a aba ativa, sem alterar dados do projeto."""
    return [tr(step, language) for step in _HELP_STEPS.get(tab_key, _HELP_STEPS["clone"])]


def help_source_steps(tab_key: str) -> list[str]:
    """Retorna as chaves-fonte dos passos para testes e manutenção."""
    return list(_HELP_STEPS.get(tab_key, _HELP_STEPS["clone"]))


def help_tab_label(tab_key: str, language: str | None = None) -> str:
    labels = {
        "clone": "CLONAGEM + DUBLAGEM",
        "review": "REVISÃO",
        "converter": "CONVERTER DURAÇÃO",
        "format": "CONVERTER FORMATOS",
        "wem_filter": "FILTRO RENOMEAR .WEM",
        "voice_clone": "REDIMENSIONAR ÁUDIO PARA CLONAR",
        "terminal": "COMANDOS",
    }
    return tr(labels.get(tab_key, labels["clone"]), language)
