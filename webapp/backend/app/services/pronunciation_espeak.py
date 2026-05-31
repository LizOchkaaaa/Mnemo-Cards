# Синтез произношения через espeak-ng

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from app.services.ipa_word import espeak_voice_for_lang, normalize_ipa_lang_code

logger = logging.getLogger(__name__)

_MAX_CHARS = 280

# Очищаем перед отправкой в eSpeak
def sanitize_speech_text(text: str) -> str:
    t = (text or "").strip()
    # Удаляем непечатные символы
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", t)
    t = " ".join(t.split())
    if len(t) > _MAX_CHARS:
        t = t[:_MAX_CHARS]
    return t

# Возвращает WAV-аудио
def synthesize_word_wav_espeak(word: str, lang: str | None) -> bytes | None:
    exe = shutil.which("espeak-ng")
    # Очистка
    txt = sanitize_speech_text(word)
    if not txt:
        return None
    # Выбор голоса
    voice = espeak_voice_for_lang(lang)
    code = normalize_ipa_lang_code(lang)

    fd, tmp_path_str = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    path = Path(tmp_path_str)

    try:
        subprocess.run(
            [
                exe,
                "-v", voice,
                "-s", "150",      # скорость речи
                "-w", str(path),  # сохранить в файл
                txt               # текст для произношения
            ],
            check=True,
            timeout=60, 
            env={**os.environ, "LANG": "C.UTF-8"},
            capture_output=True,
            text=True,
        )
        
        # Читаем WAV-файл как байты
        data = path.read_bytes()
        
        # Проверка размера
        if len(data) < 120:
            logger.info("[SPEECH] espeak output too small (%s bytes) word=%r lang=%s", len(data), txt[:40], code)
            return None
        
        return data
        
    except (subprocess.CalledProcessError, OSError, TimeoutError) as exc:
        logger.info("[SPEECH] espeak-ng failed word=%r lang=%s: %s", txt[:40], code, exc)
        return None
        
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass