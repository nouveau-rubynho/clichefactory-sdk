"""
Shared OCR language mapping utilities.

The SDK accepts language codes in Tesseract format (e.g. "eng", "slv+eng", "deu+fra").
Each OCR engine needs its own format. This module centralises the conversion so the
image pipeline and PDF/Docling pipeline share one mapping table.

Supported format:
    User input: Tesseract-style, "+" separated (e.g. "slv+eng")
    Tesseract:  same string or list ["slv", "eng"]
    EasyOCR:    ISO 639-1 list     ["sl", "en"]
    RapidOCR:   LangRec enum value (script-family based, e.g. "latin", "en")
"""
from __future__ import annotations

# Tesseract ISO 639-2/3 -> EasyOCR ISO 639-1 (or EasyOCR's own short code).
# Only languages that differ from the Tesseract code need an entry;
# EasyOCR also accepts some 3-letter codes natively but the mapping keeps it safe.
_TESSERACT_TO_EASYOCR: dict[str, str] = {
    "eng": "en",
    "deu": "de",
    "fra": "fr",
    "spa": "es",
    "ita": "it",
    "por": "pt",
    "nld": "nl",
    "pol": "pl",
    "rus": "ru",
    "ukr": "uk",
    "bel": "be",
    "ara": "ar",
    "hin": "hi",
    "ben": "bn",
    "jpn": "ja",
    "kor": "ko",
    "chi_sim": "ch_sim",
    "chi_tra": "ch_tra",
    "tha": "th",
    "vie": "vi",
    "tur": "tr",
    "ces": "cs",
    "ron": "ro",
    "hun": "hu",
    "swe": "sv",
    "nor": "no",
    "dan": "da",
    "fin": "fi",
    "ell": "el",
    "heb": "he",
    "ind": "id",
    "msa": "ms",
    "tam": "ta",
    "tel": "te",
    "kat": "ka",
    "bul": "bg",
    "hrv": "hr",
    "srp": "rs_latin",
    "slv": "sl",
    "slk": "sk",
}

# Tesseract lang code -> RapidOCR LangRec string value.
# RapidOCR works at the script-family level, not individual languages.
_TESSERACT_TO_RAPIDOCR_SCRIPT: dict[str, str] = {
    "eng": "en",
    # Latin-script languages
    "deu": "latin", "fra": "latin", "spa": "latin", "ita": "latin",
    "por": "latin", "nld": "latin", "pol": "latin", "ces": "latin",
    "ron": "latin", "hun": "latin", "swe": "latin", "nor": "latin",
    "dan": "latin", "fin": "latin", "tur": "latin", "ind": "latin",
    "msa": "latin", "vie": "latin", "hrv": "latin", "slv": "latin",
    "slk": "latin",
    # Cyrillic
    "rus": "cyrillic", "ukr": "cyrillic", "bel": "cyrillic",
    "bul": "cyrillic", "srp": "cyrillic",
    # CJK
    "chi_sim": "ch", "chi_tra": "chinese_cht",
    "jpn": "japan", "kor": "korean",
    # Arabic
    "ara": "arabic",
    # Indic / other scripts
    "hin": "devanagari", "ben": "devanagari",
    "tam": "ta", "tel": "te", "kat": "ka",
    # Greek
    "ell": "el",
    # Thai
    "tha": "th",
}

_RAPIDOCR_DEFAULT_SCRIPT = "en"


def split_lang_string(lang: str) -> list[str]:
    """Split "slv+eng" into ["slv", "eng"]. Falls back to ["eng"] for empty input."""
    parts = [x.strip() for x in lang.replace("+", ",").split(",") if x.strip()]
    return parts or ["eng"]


def to_tesseract_list(lang: str) -> list[str]:
    """Convert "slv+eng" to ["slv", "eng"] for Docling's TesseractOcrOptions."""
    return split_lang_string(lang)


def to_tesseract_string(lang: str) -> str:
    """Return the raw Tesseract format string (passthrough, validated)."""
    return "+".join(split_lang_string(lang))


def to_easyocr_list(lang: str) -> list[str]:
    """Convert "slv+eng" to ["sl", "en"] for EasyOCR."""
    parts = split_lang_string(lang)
    return [_TESSERACT_TO_EASYOCR.get(p, p) for p in parts] or ["en"]


def to_rapidocr_script(lang: str) -> str:
    """
    Map user lang string to a single RapidOCR LangRec value.

    RapidOCR operates at the script level (e.g. "latin" covers French, German,
    Slovenian, etc.).  When multiple languages are given, the first one with a
    known mapping wins.  Falls back to "en" (English model).
    """
    for code in split_lang_string(lang):
        script = _TESSERACT_TO_RAPIDOCR_SCRIPT.get(code)
        if script:
            return script
    return _RAPIDOCR_DEFAULT_SCRIPT
