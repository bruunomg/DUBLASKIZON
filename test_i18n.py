from pathlib import Path

import i18n


def main() -> None:
    assert set(i18n.LANGUAGE_LABELS) == {"pt", "en", "ru", "es"}
    assert i18n.tr("CONVERTER FORMATOS", "en") == "CONVERT FORMATS"
    assert i18n.tr("CONVERTER FORMATOS", "ru") == "КОНВЕРТИРОВАТЬ ФОРМАТЫ"
    assert i18n.tr("CONVERTER FORMATOS", "es") == "CONVERTIR FORMATOS"
    assert i18n.tr("  Apenas troca o formato; não altera a duração", "en") == "  Only changes the format; does not alter the duration"
    assert i18n.tr("  Apenas troca o formato; não altera a duração", "ru") == "  Только меняет формат; длительность не изменяется"
    assert i18n.tr("  Apenas troca o formato; não altera a duração", "es") == "  Solo cambia el formato; no modifica la duración"
    assert i18n.tr("? AJUDA", "en") == "? HELP"
    assert i18n.tr("? AJUDA: ATIVA", "ru") == "? СПРАВКА: ВКЛ."
    assert i18n.tr("DESATIVAR AJUDA", "es") == "DESACTIVAR AYUDA"
    assert i18n.help_tab_label("terminal", "en") == "COMMANDS"
    assert i18n.help_steps("format", "es")[0].startswith("1.")
    assert i18n.tr("Nenhum par de wav + txt encontrado.", "en") == "No WAV + TXT pair found."
    assert i18n.tr("Nenhuma cena selecionada", "ru") == "Сцена не выбрана"
    assert i18n.tr("Conversão de formato: aguardando", "es") == "Conversión de formato: esperando"
    assert i18n.tr("CARREGAR DA ABA REVISÃO", "en") == "LOAD FROM REVIEW TAB"
    assert i18n.tr("CARREGAR DA CLONAGEM + DUBLAGEM", "ru") == "ЗАГРУЗИТЬ ИЗ КЛОНИРОВАНИЯ + ДУБЛЯЖА"
    assert i18n.tr("CARREGAR DA CONVERSÃO DE FORMATOS", "en") == "LOAD FROM FORMAT CONVERTER"
    assert i18n.tr("ABRIR LOCAL DO ÁUDIO DUBLADO", "en") == "OPEN DUBBED AUDIO LOCATION"
    assert i18n.tr("ABRIR LOCAL DO ÁUDIO ORIGINAL", "es") == "ABRIR UBICACIÓN DEL AUDIO ORIGINAL"
    assert i18n.tr("COPIAR NOME DO ÁUDIO", "ru") == "КОПИРОВАТЬ ИМЯ АУДИО"
    assert i18n.tr("COPIAR LOCAL DO ÁUDIO DUBLADO", "en") == "COPY DUBBED AUDIO LOCATION"
    assert i18n.tr("COPIAR LOCAL DO ÁUDIO ORIGINAL", "es") == "COPIAR UBICACIÓN DEL AUDIO ORIGINAL"
    assert i18n.tr("CONVERTER FORMATOS", "pt") == "CONVERTER FORMATOS"
    assert i18n.tr("Pronúncia do R", "en") == "R pronunciation"
    assert i18n.tr("R SUAVE", "ru") == "МЯГКАЯ R"
    assert i18n.tr("R FORTE", "es") == "R FUERTE"
    i18n.set_current_language("en")
    assert i18n.source_text("CONVERT FORMATOS") == "CONVERT FORMATOS" or i18n.source_text("CONVERT FORMATS") == "CONVERTER FORMATOS"
    assert "FFmpeg:" in i18n.tr("FFmpeg: converte e processa áudio e vídeo; é usado para gerar o formato de saída.\n\nFFprobe: consulta informações do arquivo, como duração, frequência e canais.\n\nFFplay: reproduz os áudios dentro do Dublaskizon.\n\nSoX: realiza operações de áudio, incluindo o ajuste de tempo usado em alguns áudios maiores.", "en")
    assert i18n.set_current_language("pt") == "pt"
    assert i18n.tr("REVISÃO") == "REVISÃO"
    print("i18n_ok")


if __name__ == "__main__":
    main()
