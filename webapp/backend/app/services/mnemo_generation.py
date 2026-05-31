# Файл для генерации мнемоники

from __future__ import annotations
import json
import logging
import re
import time
import unicodedata
import urllib.request
from urllib.parse import urlencode
from dataclasses import dataclass
from typing import Optional

from app.core.config import Settings
from app.schemas.mnemo import ImageGeneratorChoice, VerseProvider
from app.services.verse_prompt import append_rhyme_retry_block, build_poem_prompt_with_examples
from app.services.verse_rhymes import get_ipa, get_word_ru_sound, last_tokens_rhyme
from openai import OpenAI

logger = logging.getLogger(__name__)

# Настройки провайдеров
@dataclass(frozen=True)
class MnemoProvidersConfig:
    # Chad
    chad_api_key: str = ""
    chad_text_model: str = ""
    # GPTunnel
    gptunnel_api_key: str = ""
    gptunnel_base_url: str = "https://gptunnel.ru/v1"
    gptunnel_text_model: str = "gpt-5.4"
    # Yandex
    yandex_cloud_api_key: str = ""
    yandex_cloud_folder: str = ""
    yandex_cloud_model: str = "deepseek-v32/latest"
    yandex_cloud_base_url: str = "https://ai.api.cloud.yandex.net/v1"
    # MashaGPT
    mashagpt_api_key: str = ""
    mashagpt_api_url: str = "https://api.mashagpt.ru/v1"
    mashagpt_image_model: str = "grok-imagine-text-to-image"
    # RuGPT
    rugpt_api_key: str = ""
    rugpt_base_url: str = "https://api.rugpt.io/api/private/b2b"
    rugpt_image_model: str = "black-forest-labs/FLUX.1-schnell"
    rugpt_image_aspect_ratio: str = "16:9"
    # DeepAI
    deepai_api_key: str = ""
    deepai_image_api_url: str = "https://api.deepai.org/api/text2img"
    deepai_image_width: str = "1024"
    deepai_image_height: str = "576"
    deepai_image_generator_version: str = "hd"
    deepai_genius_preference: str = "graphic"
    deepai_super_genius_resolution: str = "2k"
    # Debug
    mnemo_verbose_verse_debug: bool = False


def mnemo_providers_config_from_settings(settings: Settings) -> MnemoProvidersConfig:
    return MnemoProvidersConfig(
        chad_api_key=(settings.chad_api_key or "").strip(),
        chad_text_model=(settings.chad_text_model or "").strip(),
        gptunnel_api_key=(settings.gptunnel_api_key or "").strip(),
        gptunnel_base_url=(settings.gptunnel_base_url or "").strip(),
        gptunnel_text_model=(settings.gptunnel_text_model or "").strip(),
        yandex_cloud_api_key=(settings.yandex_cloud_api_key or "").strip(),
        yandex_cloud_folder=(settings.yandex_cloud_folder or "").strip(),
        yandex_cloud_model=(settings.yandex_cloud_model or "").strip(),
        yandex_cloud_base_url=(settings.yandex_cloud_base_url or "").strip(),
        mashagpt_api_key=(settings.mashagpt_api_key or "").strip(),
        mashagpt_api_url=(settings.mashagpt_api_url or "").strip(),
        mashagpt_image_model=(settings.mashagpt_image_model or "").strip(),
        rugpt_api_key=(settings.rugpt_api_key or "").strip(),
        rugpt_base_url=(settings.rugpt_base_url or "").strip(),
        rugpt_image_model=(settings.rugpt_image_model or "").strip(),
        rugpt_image_aspect_ratio=(settings.rugpt_image_aspect_ratio or "").strip(),
        deepai_api_key=(settings.deepai_api_key or "").strip(),
        deepai_image_api_url=(settings.deepai_image_api_url or "").strip(),
        deepai_image_width=(settings.deepai_image_width or "").strip(),
        deepai_image_height=(settings.deepai_image_height or "").strip(),
        deepai_image_generator_version=(settings.deepai_image_generator_version or "").strip(),
        deepai_genius_preference=(settings.deepai_genius_preference or "").strip(),
        deepai_super_genius_resolution=(settings.deepai_super_genius_resolution or "").strip(),
        mnemo_verbose_verse_debug=bool(settings.mnemo_verbose_verse_debug),
    )

# Логирование
def _verse_model_env_summary(verse_provider: VerseProvider, cfg: MnemoProvidersConfig) -> str:
    if verse_provider == "yandex":
        return f"YANDEX_CLOUD_MODEL={cfg.yandex_cloud_model!r}"
    if verse_provider == "chad":
        return f"CHAD_TEXT_MODEL={cfg.chad_text_model!r}"
    return (
        f"GPTUNNEL_TEXT_MODEL={cfg.gptunnel_text_model!r} "
        f"GPTUNNEL_BASE_URL={cfg.gptunnel_base_url!r}"
    )

# Логирование
def _image_side_env_summary(image_generator: ImageGeneratorChoice, cfg: MnemoProvidersConfig) -> str:
    if image_generator == "deepai-text2img":
        return "DeepAI text2img"
    if image_generator == "grok-imagine-text-to-image":
        return f"MashaGPT MASHAGPT_IMAGE_MODEL={cfg.mashagpt_image_model!r}"
    return f"RuGPT RUGPT_IMAGE_MODEL={cfg.rugpt_image_model!r}"

# Результат полной генерации мнемоники
@dataclass
class MnemoGenerated:
    mnemonic_phrase_ru: str           # Стих на русском языке
    image_prompt: str                 # Промпт для генерации изображения
    image_data: Optional[bytes]       # Бинарные данные изображения
    image_content_type: Optional[str] # MIME-тип
    verse_source: str                 # Генератор

# Отчёт о качестве сгенерированного стихотворения
@dataclass
class VerseQualityReport:
    ok: bool                          # Прошёл ли стих проверку
    phrase: str                       # Очищенный текст стиха
    issues_for_model: list[str]       # Список проблем
    positives_for_model: list[str]    # Список удачных моментов


# Требование для изображения
_IMAGE_PROMPT_PREFIX = (
    "Only illustrations without words. No letters in any language, no numbers, no captions, no road signs"
)

# Суффикс с требованием отсутствия текста
_IMAGE_PROMPT_NO_TEXT_SUFFIX = (
    "Critically: no text, no English, no Russian, no inscriptions; only a drawing without letters or numbers. "
    "The image should not contain any alphabet characters. "
    "Критично: никакого текста — ни английского, ни русского, ни надписей; только рисунок без букв и цифр. "
    "На изображении не должно быть ни одного символа алфавита."
)


# Генерация стихотворения через API сервиса ChadGPT
def _call_chad_verse(prompt: str, cfg: MnemoProvidersConfig) -> Optional[str]:
    api_key = cfg.chad_api_key.strip()
    model = cfg.chad_text_model.strip()
    url = f"https://ask.chadgpt.ru/api/public/{model}"

    request_json = {
        "message": prompt,
        "api_key": api_key
    }

    try:
        data = json.dumps(request_json, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            out = json.loads(raw)

        # Chad возвращает is_success = true при успехе
        if out.get("is_success"):
            verse_text = out.get("response", "").strip()
            if verse_text:
                # Удаляем кавычки, которые модель могла добавить
                clean_text = re.sub(r'^["\']|["\']$', '', verse_text)
                return clean_text
        return None
    except Exception as e:
        logger.warning("[CHAD VERSE] request failed: %s", e)
        return None

# Извлекаем текст ответа из JSON-ответов различных OpenAI-совместимых API
def _extract_openai_chat_completion_text(out: dict) -> str:
    # Проверяем, нет ли ошибки в ответе
    err = out.get("error")
    if err is not None:
        if isinstance(err, dict):
            em = err.get("message") or err.get("code") or err.get("type") or json.dumps(err, ensure_ascii=False)
        else:
            em = str(err)
        logger.warning("[GPTUNNEL VERSE] API error: %s", em)
        return ""
    
    # Пытаемся получить choices - список вариантов ответа
    choices = out.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    ch0 = choices[0]
    
    # Прямой текст в поле "text"
    if isinstance(ch0.get("text"), str) and ch0["text"].strip():
        return ch0["text"].strip()
  
    # Стандартный OpenAI формат с message.content
    msg = ch0.get("message")
    if not isinstance(msg, dict):
        # Некоторые API возвращают content прямо в choices[0]
        if isinstance(ch0.get("content"), str) and ch0["content"].strip():
            return ch0["content"].strip()
        return ""
    
    # Извлекаем content из message
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    
    # Content может быть списком частей
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif isinstance(part.get("text"), str):
                    parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
        if parts:
            return "".join(parts).strip()
        
    # Mодель могла отказаться отвечать
    refusal = msg.get("refusal")
    if isinstance(refusal, str) and refusal.strip():
        logger.warning("[GPTUNNEL VERSE] Model refusal: %r", refusal[:200])

    return ""

# Генерация стихотворения через GPTunnel
def _call_gptunnel_verse(prompt: str, cfg: MnemoProvidersConfig) -> Optional[str]:
    api_key = cfg.gptunnel_api_key.strip()
    base_url = cfg.gptunnel_base_url.strip().rstrip("/")
    model = cfg.gptunnel_text_model.strip()
    url = f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты помогаешь запомнить слово и пишешь детские стихотворения. "
                    "Отвечай только двумя строками с рифмой, без пояснений."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 500,
        "temperature": 0.7,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            out = json.loads(raw)

        text = _extract_openai_chat_completion_text(out if isinstance(out, dict) else {})

        if text:
            clean_text = re.sub(r'^["\']|["\']$', "", text)
            return clean_text

        # Диагностика пустого ответа (для отладки)
        o = out if isinstance(out, dict) else {}
        ch = (o.get("choices") or [])[:1]
        ch0 = ch[0] if ch and isinstance(ch[0], dict) else {}
        logger.warning(
            "[GPTUNNEL VERSE] Empty completion: id=%r model=%r choices=%s finish_reason=%r msg_keys=%s",
            o.get("id"),
            o.get("model"),
            len(o.get("choices") or []),
            ch0.get("finish_reason"),
            list((ch0.get("message") or {}).keys()) if isinstance(ch0.get("message"), dict) else None,
        )
        # Логируем сырой ответ для отладки
        if cfg.mnemo_verbose_verse_debug:
            preview = json.dumps(o, ensure_ascii=False)[:1200]
            logger.debug("[GPTUNNEL VERSE] Raw response preview: %s", preview)
        return None
    except Exception as e:
        logger.warning("[GPTUNNEL VERSE] Request failed: %s", e)
        return None

# Генерация стихотворения через Yandex Cloud API
def _call_yandex_verse(prompt: str, cfg: MnemoProvidersConfig) -> Optional[str]:
    api_key = cfg.yandex_cloud_api_key.strip()
    folder = cfg.yandex_cloud_folder.strip()
    model_suffix = cfg.yandex_cloud_model.strip()
    base_url = cfg.yandex_cloud_base_url.strip().rstrip("/")
    model_id = f"gpt://{folder}/{model_suffix}"

    client = OpenAI(api_key=api_key, base_url=base_url)

    # Пробуем метод responses.create
    try:
        if hasattr(client, "responses") and hasattr(client.responses, "create"):
            resp = client.responses.create(
                model=model_id,
                temperature=0.5,
                instructions="Ты помогаешь запомнить слово и пишешь детские стихотворения. "
                    "Отвечай только двумя строками стиха с рифмой, без пояснений.",
                input=prompt,
                max_output_tokens=500,
            )
            text = getattr(resp, "output_text", "")
            if text:
                clean = re.sub(r'^["\']|["\']$', "", text.strip())
                return clean
    except Exception as e:
        logger.warning("[YANDEX VERSE] responses.create: %s", e)

    # Пробуем стандартный метод chat.completions.create
    try:
        chat = client.chat.completions.create(
            model=model_id,
            temperature=0.5,
            max_tokens=500,
            messages=[
                {"role": "system", "content": "Ты помогаешь запомнить слово и пишешь детские стихотворения. "
                    "Отвечай только двумя строками стихотворения с рифмой, без пояснений."},
                {"role": "user", "content": prompt},
            ],
        )
        msg = chat.choices[0].message
        text = (msg.content or "").strip() if msg else ""
        if text:
            clean = re.sub(r'^["\']|["\']$', "", text)
            return clean
    except Exception as e:
        logger.warning("[YANDEX VERSE] chat.completions: %s", e)

    return None 

# Генерация изображения через MashaGPT API
def _call_mashagpt_image(prompt: str, cfg: MnemoProvidersConfig) -> Optional[bytes]:
    api_key = cfg.mashagpt_api_key.strip()
    base_url = cfg.mashagpt_api_url.rstrip("/")
    model = cfg.mashagpt_image_model.strip()
    create_task_url = f"{base_url}/tasks/{model}"

    payload = {
        "prompt": prompt,
        "aspectRatio": "3:2"
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": api_key,
    }

    try:
        # Создаём задачу
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(create_task_url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            out = json.loads(raw)

        task_id = out.get("id")
        if not task_id:
            return None

        # Опрашиваем статус задачи
        max_attempts = 60
        poll_interval = 3
        status_url = f"{base_url}/tasks/{task_id}"

        for attempt in range(1, max_attempts + 1):
            time.sleep(poll_interval)

            try:
                check_req = urllib.request.Request(status_url, headers=headers, method="GET")
                with urllib.request.urlopen(check_req, timeout=30) as check_resp:
                    check_raw = check_resp.read().decode("utf-8", errors="replace")
                    check_out = json.loads(check_raw)

                current_status = check_out.get("status")
                if attempt == 1 or attempt % 10 == 0:
                    logger.info("[MASHAGPT IMAGE] poll %s/%s task_id=%r status=%r", attempt, max_attempts, task_id, current_status)

                if current_status == "COMPLETED":
                    # Извлекаем URL готового изображения
                    output_data = check_out.get("output")
                    image_url = None

                    if isinstance(output_data, dict):
                        image_url = output_data.get("url") or output_data.get("image_url")
                    elif isinstance(output_data, str):
                        image_url = output_data
                    elif isinstance(output_data, list) and output_data:
                        image_url = output_data[0]

                    if image_url:
                        # Скачиваем изображение
                        img_req = urllib.request.Request(image_url, headers={"User-Agent": "MnemoCardsImageFetcher/1.0"})
                        with urllib.request.urlopen(img_req, timeout=60) as img_resp:
                            return img_resp.read()

                elif current_status in ("FAILED", "ERROR"):
                    return None

            except Exception:
                continue

        return None

    except Exception as e:
        logger.warning("[MASHAGPT IMAGE] Request failed: %s", e)
        return None

# Генерация изображения через RuGPT API
def _call_rugpt_image(prompt: str, cfg: MnemoProvidersConfig) -> Optional[bytes]:
    api_key = cfg.rugpt_api_key.strip()
    base_url = cfg.rugpt_base_url.rstrip("/")
    model = cfg.rugpt_image_model.strip()
    aspect = cfg.rugpt_image_aspect_ratio.strip()

    create_url = f"{base_url}/image/generation"
    payload = {
        "model": model,
        "prompt": prompt,
        "params": {
            "aspectRatio": aspect,
            "attachedFiles": [],
            "enhancePrompt": False,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-rugpt-key": api_key,
    }

    try:
        # Создаём задачу
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(create_url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            out = json.loads(raw)

        inner = out.get("data") if isinstance(out, dict) else None
        job_uuid = (inner or {}).get("uuid") if isinstance(inner, dict) else None
        if not job_uuid:
            return None

        # Опрашиваем статус
        max_attempts = 60
        poll_interval = 2
        job_url = f"{base_url}/image/generation/jobs/{job_uuid}"

        for attempt in range(1, max_attempts + 1):
            time.sleep(poll_interval if attempt > 1 else 0)
            try:
                poll_req = urllib.request.Request(job_url, headers=headers, method="GET")
                with urllib.request.urlopen(poll_req, timeout=45) as poll_resp:
                    poll_raw = poll_resp.read().decode("utf-8", errors="replace")
                    poll_out = json.loads(poll_raw)
            except Exception:
                continue

            pdata = poll_out.get("data") if isinstance(poll_out, dict) else None
            if not isinstance(pdata, dict):
                continue
            st = pdata.get("status")
            if attempt == 1 or attempt % 10 == 0:
                logger.info("[RUGPT IMAGE] poll %s/%s job=%r status=%r", attempt, max_attempts, job_uuid, st)
            
            if st == "failed":
                return None
            if st == "completed":
                image_url = pdata.get("urls")
                if isinstance(image_url, list) and image_url:
                    image_url = image_url[0]
                if isinstance(image_url, str) and image_url.startswith("http"):
                    img_req = urllib.request.Request(image_url, headers={"User-Agent": "MnemoCardsImageFetcher/1.0"})
                    with urllib.request.urlopen(img_req, timeout=120) as img_resp:
                        return img_resp.read()

        return None

    except Exception as e:
        logger.warning("[RUGPT IMAGE] Request failed: %s", e)
        return None

# Извлекаем URL изображения из ответа DeepAI API
def _deepai_extract_output_url(out: object) -> Optional[str]:
    if not isinstance(out, dict):
        return None
    u = out.get("output_url") or out.get("url")
    if isinstance(u, str) and u.startswith("http"):
        return u
    return None

# Генерация изображения через DeepAI API
def _call_deepai_image(prompt: str, cfg: MnemoProvidersConfig) -> Optional[bytes]:
    api_key = cfg.deepai_api_key.strip()
    endpoint = cfg.deepai_image_api_url.strip().rstrip("/")
    width = cfg.deepai_image_width.strip()
    height = cfg.deepai_image_height.strip()
    version = cfg.deepai_image_generator_version.strip()

    # Negative prompt
    neg = (
        "text, typography, letters, words, numbers, watermark, signature, caption, subtitles"
    )

    form: dict[str, str] = {
        "text": prompt,
        "width": width,
        "height": height,
        "image_generator_version": version,
        "negative_prompt": neg,
    }
    
    # Дополнительные параметры для разных версий
    if version == "genius":
        form["genius_preference"] = cfg.deepai_genius_preference.strip()
    
    if version == "super_genius":
        form["resolution"] = cfg.deepai_super_genius_resolution.strip()

    try:
        data = urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "api-key": api_key,
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            out = json.loads(raw)

        image_url = _deepai_extract_output_url(out)
        if not image_url:
            preview = json.dumps(out, ensure_ascii=False)[:500] if isinstance(out, dict) else str(out)[:500]
            logger.warning("[DEEPAI IMAGE] No output URL in response: %s", preview)
            return None
        
        # Скачиваем изображение по полученному URL
        img_req = urllib.request.Request(image_url, headers={"User-Agent": "MnemoCardsImageFetcher/1.0"})
        with urllib.request.urlopen(img_req, timeout=120) as img_resp:
            return img_resp.read()
    except Exception as e:
        logger.warning("[DEEPAI IMAGE] Request failed: %s", e)
        return None

# Добавляем к промпту для картинки требования "без текста"
def _finalize_image_prompt_for_api(prompt: str) -> str:
    p = (prompt or "").strip()
    if not p:
        return f"{_IMAGE_PROMPT_PREFIX.strip()}{_IMAGE_PROMPT_NO_TEXT_SUFFIX}"

    low = p.lower()
    already = "zero text anywhere" in low and "никакого текста" in low
    if already:
        if "pure wordless illustration only" in low[:300]:
            return p
        return f"{_IMAGE_PROMPT_PREFIX}{p}"

    return f"{_IMAGE_PROMPT_PREFIX}{p}{_IMAGE_PROMPT_NO_TEXT_SUFFIX}"

# Очищаеv и нормализуеv список частей для промпта картинки
def _normalized_image_parts(parts: Optional[list]) -> list[str]:
    return [p.strip() for p in (parts or []) if p and str(p).strip()]

# Формируем промпт для генерации изображения на основе декомпозиции
def _build_image_prompt(parts: Optional[list[str]] = None) -> str:
    raw_parts = _normalized_image_parts(parts)
    if not raw_parts:
        logger.error("[IMAGE] _build_image_prompt: список частей декомпозиции пуст")
        return ""

    joined = ", ".join(raw_parts[:8])  # Берём не более 8 частей
    scene = f"Cartoon illustration from decomposed visual ideas — show only as drawings and objects, no labels: {joined}."
    image_prompt = f"A colorful flat cartoon style. {scene}"
    return _finalize_image_prompt_for_api(image_prompt)

# Удаляем Markdown-разметку из текста
def _strip_model_markdown_noise(text: str) -> str:
    s = (text or "").replace("**", "").replace("__", "")
    s = re.sub(r"(?<=\w)\*(?=\w)", "", s)
    return s

# Определяем является ли строка служебным комментарием, который нужно удалить
def _is_verse_meta_comment_line(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return True
    if s.startswith("---") or re.fullmatch(r"-{2,}", s):
        return True
    low = s.lower()
    if low.startswith("перепишу") or low.startswith("попробую"):
        return True
    return False

# Извлекаем из ответа модели именно две строки стиха, отбрасывая всё лишнее
def _pick_verse_two_lines(raw: str) -> str:
    s = _strip_model_markdown_noise(raw or "")
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    body: list[str] = []
    for ln in lines:
        if _is_verse_meta_comment_line(ln):
            continue
        if len(ln) < 3:
            continue
        body.append(ln)
    
    if len(body) >= 2:
        return f"{body[0]}\n{body[1]}"
    if len(body) == 1:
        return body[0]
    if len(lines) >= 2:
        return f"{lines[0]}\n{lines[1]}"
    return (raw or "").strip()

# Извлекаем последнее слово строки, очищая его от знаков препинания
def _last_line_token(line: str) -> str:
    s = (line or "").rstrip()
    s = re.sub(r"[.!?,;:—–\-]+$", "", s).strip()
    if not s:
        return ""
    parts = s.split()
    if not parts:
        return ""
    raw = parts[-1]
    return re.sub(
        r"^[^\wа-яА-ЯёЁa-zA-Z]+|[^\wа-яА-ЯёЁa-zA-Z]+$",
        "",
        raw,
        flags=re.UNICODE,
    )


def _strip_cyrillic_word_stress(token: str) -> str:
    """Убирает комбинирующее ударение (чудо́), чтобы совпало [а-яё]+ и IPA-рифма."""
    if not token:
        return ""
    nfd = unicodedata.normalize("NFD", token.strip())
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


# Считаем вхождения изучаемого слова как отдельный токен
def _study_word_occurrences_bounded(phrase_lower: str, study_word_lower: str) -> int:
    w = study_word_lower.strip().lower()
    if not w:
        return 0
    pat = rf"(?<!\w){re.escape(w)}(?!\w)"
    return len(re.findall(pat, phrase_lower, flags=re.UNICODE))


# Проверяем качество сгенерированного стихотворения
def _evaluate_verse_quality(
    verse: str,
    word: str,
    translation_ru: str,
    verse_learning_lang: str,
    ipa: str,
) -> VerseQualityReport:
    issues: list[str] = []
    positives: list[str] = []
    
    # Нормализуем
    foreign_word = word.strip().lower()
    translation = (translation_ru or "").strip().lower()
    phrase = (verse or "").strip()
    
    # Получаем подсказку для рифмы
    rhyme_hint = get_word_ru_sound(foreign_word)
    vlc = (verse_learning_lang or "en").strip().lower()[:2] or "en"

    # Проверка пустоты
    if not phrase:
        issues.append("Стих пустой, нужны две строки")
        return VerseQualityReport(False, phrase, issues, positives)

    # Очистка от Markdown и лишних символов
    phrase = _strip_model_markdown_noise(phrase)
    lines = [ln.strip() for ln in phrase.splitlines() if ln.strip()]

    # Проверка 2 строк
    if len(lines) < 2:
        issues.append(f"Нужно 2 строки, сейчас {len(lines)}.")
        return VerseQualityReport(False, phrase, issues, positives)

    line1, line2 = lines[0], lines[1]
    phrase = f"{line1}\n{line2}"
    verse_lower = phrase.lower()

    # Проверка на русском языке
    if not re.search(r"[а-яё]", phrase, re.IGNORECASE):
        issues.append("Стих должен быть на русском языке")

    # Одно изучаемое слово
    n_study = _study_word_occurrences_bounded(verse_lower, foreign_word)
    if n_study == 0:
        issues.append(f"В стихе должно быть изучаемое слово «{foreign_word}» (ISO {vlc}).")
    elif n_study > 1:
        issues.append(f"Изучаемое слово «{foreign_word}» встречается {n_study} раз, должно ровно 1 раз")
    else:
        positives.append(f"Изучаемое слово «{foreign_word}» есть в стихе (язык изучения {vlc})")

    # Проверка перевода
    if translation and translation not in verse_lower:
        # Разбиваем перевод на части
        translation_parts = re.split(r"[\s,;]+", translation)
        found = any(part in verse_lower for part in translation_parts if len(part) >= 2)
        if not found:
            issues.append(f"Смысл перевода '{translation}' должен быть понятен из контекста")
        else:
            positives.append(f"Перевод '{translation}' присутствует в стихе")
    elif translation:
        positives.append(f"Перевод '{translation}' есть в стихе")

    # Проверка структуры строк
    structure_ok = True
    last_word_line1 = _last_line_token(line1)
    last_word_line2 = _last_line_token(line2)
    last_word1_plain = _strip_cyrillic_word_stress(last_word_line1)
    last_word1_lower = last_word1_plain.lower() if last_word1_plain else ""
    last_word2_lower = last_word_line2.lower() if last_word_line2 else ""

    # Проверка конца первой строки
    if not last_word_line1:
        issues.append("Первая строка должна заканчиваться русским словом")
        structure_ok = False
    else:
        # Должно быть русское слово
        if re.search(r"[a-zA-Z]", last_word_line1):
            issues.append("Первая строка должна заканчиваться русским словом, без латинских букв")
            structure_ok = False
        elif "-" in last_word_line1:
            issues.append("В конце первой строки одно русское слово (без дефиса)")
            structure_ok = False
        elif not re.fullmatch(r"[а-яё]+", last_word1_lower):
            issues.append("Последнее слово первой строки должно быть одним русским словом")
            structure_ok = False
        else:
            positives.append(f"Первая строка заканчивается русским словом «{last_word1_lower}».")

    # Проверка конца второй строки
    if last_word2_lower != foreign_word:
        issues.append(f"Вторая строка должна заканчиваться изучаемым словом «{foreign_word}»")
        structure_ok = False
    else:
        positives.append("Вторая строка заканчивается изучаемым словом")

    # Проверка рифмы
    rhyme_ok = True
    if last_word_line1 and last_word_line2:
        # Проверяем, рифмуется ли русское слово с иностранным
        rhymes = last_tokens_rhyme(
            last_word1_plain or last_word_line1,  # без ударения для IPA
            last_word_line2,      # иностранное слово
            target_word_en=foreign_word,
            target_ipa=ipa
        )
        if not rhymes:
            hint = f" Попробуй слова, похожие на '{rhyme_hint[-2:]}'." if rhyme_hint else ""
            disp = last_word1_lower or last_word_line1
            issues.append(f"Слово '{disp}' не рифмуется с '{foreign_word}'.{hint}")
            rhyme_ok = False
        else:
            disp = last_word1_lower or last_word_line1
            positives.append(f"Рифма есть: {disp} — {foreign_word}")
    else:
        issues.append("Не удалось определить последние слова строк")
        rhyme_ok = False

    # Проверка длины строк
    if len(line1) < 5 or len(line2) < 5:
        issues.append(f"Строки слишком короткие ({len(line1)} и {len(line2)} символов)")
    if len(line1) > 120 or len(line2) > 100:
        issues.append("Строки слишком длинные")

    # Итоговая оценка
    ok = structure_ok and rhyme_ok and len(issues) <= 2
    return VerseQualityReport(ok, phrase, issues, positives)

# Основная функция генерации стихотворений
def _generate_verse(
    word: str,
    trans: str,
    phonetic_ipa: str,
    verse_prompt_template: str | None = None,
    *,
    verse_learning_lang: str = "en",
    verse_provider: VerseProvider,
    providers: MnemoProvidersConfig,
    verse_max_retries: int = 5,
) -> tuple[str, str]:
    max_tries = max(1, min(10, verse_max_retries))
    vlc = (verse_learning_lang or "en").strip().lower()[:2] or "en"
    ipa = (phonetic_ipa or "").strip() or get_ipa(word, lang=vlc)

    base_prompt = build_poem_prompt_with_examples(
        word=word,
        translation_ru=trans,
        phonetic_ipa=ipa,
        template=verse_prompt_template,
        verse_learning_lang=vlc,
    )
    
    logger.info(
        "[MNEMO] verse: word=%r provider=%s verse_learning_lang=%s quality_check=on max_tries=%s",
        word,
        verse_provider,
        vlc,
        max_tries,
    )

    failed_quality_once = False

    for attempt in range(max_tries):
        prompt = (
            append_rhyme_retry_block(base_prompt, word, ipa, verse_learning_lang=vlc)
            if failed_quality_once
            else base_prompt
        )

        verse_text: Optional[str] = None
        verse_source = "fallback"

        # Вызываем нужного провайдера
        t_api = time.perf_counter()
        if verse_provider == "yandex":
            verse_text = _call_yandex_verse(prompt, providers)
            if verse_text:
                verse_source = "yandex"
        elif verse_provider == "chad":
            verse_text = _call_chad_verse(prompt, providers)
            if verse_text:
                verse_source = "chad"
        else:  # gptunnel по умолчанию
            verse_text = _call_gptunnel_verse(prompt, providers)
            if verse_text:
                verse_source = "gptunnel"
        api_s = time.perf_counter() - t_api
        logger.info(
            "[MNEMO] timing verse_model_s=%.3f attempt=%d/%d provider=%s got_text=%s",
            api_s,
            attempt + 1,
            max_tries,
            verse_provider,
            bool(verse_text and verse_text.strip()),
        )

        if verse_text and verse_text.strip():
            phrase_for_check = _pick_verse_two_lines(verse_text)

            report = _evaluate_verse_quality(phrase_for_check, word, trans, vlc, ipa)
            if report.ok:
                return phrase_for_check, verse_source
            
            failed_quality_once = True
            # Если качество не прошло, логируем проблемы и пробуем снова
            logger.warning(
                "[VERSE] Quality check failed (attempt=%d/%d word=%r): %s",
                attempt + 1,
                max_tries,
                word,
                "; ".join(report.issues_for_model) if report.issues_for_model else "(no detail)",
            )

    # Если все попытки провалились, то возвращаем запасной вариант
    return f"Запомни слово «{word}» — это {trans}.", "fallback"

# Генерация изображения через выбранного провайдера
def _generate_image(
    prompt: str,
    *,
    image_generator: ImageGeneratorChoice,
    providers: MnemoProvidersConfig,
) -> tuple[Optional[bytes], Optional[str]]:
    image_data = None
    content_type = None
    prompt = _finalize_image_prompt_for_api(prompt)

    t_img = time.perf_counter()

    # Вызываем нужного провайдера
    if image_generator == "deepai-text2img":
        image_data = _call_deepai_image(prompt, providers)
        if image_data:
            content_type = "image/png"
    elif image_generator == "grok-imagine-text-to-image":
        image_data = _call_mashagpt_image(prompt, providers)
        if image_data:
            content_type = "image/png"
    else:  # rugpt по умолчанию
        image_data = _call_rugpt_image(prompt, providers)
        if image_data:
            content_type = "image/png"
    logger.info(
        "[MNEMO] timing image_model_s=%.3f generator=%s success=%s",
        time.perf_counter() - t_img,
        image_generator,
        bool(image_data),
    )

    return image_data, content_type

# Главный класс для генерации мнемонических карточек
class mnemoClass:
    def __init__(self, providers: MnemoProvidersConfig | None = None) -> None:
        self.providers = providers or MnemoProvidersConfig()

    def generate(
        self,                      
        word_en: str,                              # Слово
        translation_ru: str,                       # Перевод
        parts: Optional[list] = None,              # Части декомпозиции
        phonetic_ipa: str = "",                    # IPA-транскрипция
        verse_prompt_template: str | None = None,  # Шаблон промпта для стиха
        *,                                         # Только именованные параметры
        verse_learning_language: str = "en",       # Язык изучаемого слова
        verse_provider: VerseProvider,             # Какой API для стиха
        image_generator: ImageGeneratorChoice,     # Какой API для картинки
        verse_max_retries: int = 5,                # Максимальное число попыток генерации стихотворения
    ) -> MnemoGenerated:
        try:
            word = (word_en or "").strip()
            trans = (translation_ru or "").strip()

            logger.info("[MNEMO] pipeline: word=%r translation=%r parts=%s | verse_provider=%s | image_generator=%s",
                        word, trans, parts, verse_provider, image_generator)
            logger.info(
                "[MNEMO] pipeline providers: verse=%s | image=%s",
                _verse_model_env_summary(verse_provider, self.providers),
                _image_side_env_summary(image_generator, self.providers),
            )

            # Генерируем стихотворение
            t_verse = time.perf_counter()
            phrase, verse_source = _generate_verse(
                word=word,
                trans=trans,
                phonetic_ipa=phonetic_ipa,
                verse_prompt_template=verse_prompt_template,
                verse_learning_lang=verse_learning_language,
                verse_provider=verse_provider,
                providers=self.providers,
                verse_max_retries=verse_max_retries,
            )
            logger.info(
                "[MNEMO] timing verse_pipeline_s=%.3f source=%s provider=%s",
                time.perf_counter() - t_verse,
                verse_source,
                verse_provider,
            )

            # Генерируем изображение
            image_parts_ok = _normalized_image_parts(parts)
            if not image_parts_ok:
                image_prompt = ""
                image_data = None
                content_type = None
            else:
                image_prompt = _build_image_prompt(parts=parts)
                image_data, content_type = _generate_image(
                    image_prompt,
                    image_generator=image_generator,
                    providers=self.providers,
                )

            # Формируем результат
            gen = MnemoGenerated(
                mnemonic_phrase_ru=phrase,
                image_prompt=image_prompt,
                image_data=image_data,
                image_content_type=content_type,
                verse_source=verse_source,
            )

            logger.info("Generation completed for %s, verse source: %s", word, verse_source)
            return gen

        except Exception as e:
            logger.exception("ERROR in generate: %s: %s", type(e).__name__, e)
            # Возвращаем fallback в случае любой ошибки
            return MnemoGenerated(
                mnemonic_phrase_ru=f"Запомни слово «{word_en}» — это {translation_ru}.",
                image_prompt="",
                image_data=None,
                image_content_type=None,
                verse_source="error_fallback",
            )