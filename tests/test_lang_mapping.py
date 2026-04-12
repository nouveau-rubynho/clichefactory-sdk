"""Tests for OCR language mapping utilities."""
from __future__ import annotations

import pytest

from clichefactory._engine.parsers.parser_utils.lang_mapping import (
    split_lang_string,
    to_easyocr_list,
    to_rapidocr_script,
    to_tesseract_list,
    to_tesseract_string,
)


class TestSplitLangString:
    def test_single_lang(self):
        assert split_lang_string("eng") == ["eng"]

    def test_multi_lang_plus(self):
        assert split_lang_string("slv+eng") == ["slv", "eng"]

    def test_multi_lang_three(self):
        assert split_lang_string("deu+fra+eng") == ["deu", "fra", "eng"]

    def test_empty_string_defaults_to_eng(self):
        assert split_lang_string("") == ["eng"]

    def test_whitespace_stripped(self):
        assert split_lang_string(" deu + eng ") == ["deu", "eng"]

    def test_comma_also_works(self):
        assert split_lang_string("deu,eng") == ["deu", "eng"]


class TestTesseract:
    def test_list(self):
        assert to_tesseract_list("slv+eng") == ["slv", "eng"]

    def test_string(self):
        assert to_tesseract_string("slv+eng") == "slv+eng"

    def test_single(self):
        assert to_tesseract_list("eng") == ["eng"]
        assert to_tesseract_string("eng") == "eng"

    def test_empty_fallback(self):
        assert to_tesseract_list("") == ["eng"]
        assert to_tesseract_string("") == "eng"


class TestEasyOCR:
    def test_eng_maps_to_en(self):
        assert to_easyocr_list("eng") == ["en"]

    def test_slv_eng(self):
        result = to_easyocr_list("slv+eng")
        assert result == ["sl", "en"]

    def test_deu_fra(self):
        result = to_easyocr_list("deu+fra")
        assert result == ["de", "fr"]

    def test_all_common_mappings(self):
        assert "en" in to_easyocr_list("eng")
        assert "de" in to_easyocr_list("deu")
        assert "fr" in to_easyocr_list("fra")
        assert "es" in to_easyocr_list("spa")
        assert "it" in to_easyocr_list("ita")
        assert "ru" in to_easyocr_list("rus")
        assert "ja" in to_easyocr_list("jpn")
        assert "ko" in to_easyocr_list("kor")
        assert "sl" in to_easyocr_list("slv")

    def test_unknown_code_passed_through(self):
        result = to_easyocr_list("xyz")
        assert result == ["xyz"]

    def test_empty_defaults_to_en(self):
        assert to_easyocr_list("") == ["en"]

    def test_multi_with_mixed_known_unknown(self):
        result = to_easyocr_list("eng+xyz")
        assert result == ["en", "xyz"]


class TestRapidOCR:
    def test_eng_maps_to_en(self):
        assert to_rapidocr_script("eng") == "en"

    def test_latin_languages(self):
        for code in ["deu", "fra", "spa", "ita", "slv", "pol", "ces", "hrv"]:
            assert to_rapidocr_script(code) == "latin", f"{code} should map to latin"

    def test_cyrillic_languages(self):
        for code in ["rus", "ukr", "bel", "bul", "srp"]:
            assert to_rapidocr_script(code) == "cyrillic", f"{code} should map to cyrillic"

    def test_cjk_languages(self):
        assert to_rapidocr_script("chi_sim") == "ch"
        assert to_rapidocr_script("chi_tra") == "chinese_cht"
        assert to_rapidocr_script("jpn") == "japan"
        assert to_rapidocr_script("kor") == "korean"

    def test_arabic(self):
        assert to_rapidocr_script("ara") == "arabic"

    def test_indic(self):
        assert to_rapidocr_script("hin") == "devanagari"

    def test_greek(self):
        assert to_rapidocr_script("ell") == "el"

    def test_thai(self):
        assert to_rapidocr_script("tha") == "th"

    def test_multi_lang_uses_first_known(self):
        assert to_rapidocr_script("slv+eng") == "latin"
        assert to_rapidocr_script("eng+slv") == "en"

    def test_unknown_defaults_to_en(self):
        assert to_rapidocr_script("xyz") == "en"

    def test_empty_defaults_to_en(self):
        assert to_rapidocr_script("") == "en"


class TestImagePipelineOptions:
    """Test that ImagePipelineOptions correctly delegates to shared mapping."""

    def test_get_tesseract_lang(self):
        from clichefactory._engine.parsers.parser_utils.image.image_pipeline_options import ImagePipelineOptions
        opts = ImagePipelineOptions(engine="pytesseract", lang="deu+eng")
        assert opts.get_tesseract_lang() == "deu+eng"

    def test_get_easyocr_lang(self):
        from clichefactory._engine.parsers.parser_utils.image.image_pipeline_options import ImagePipelineOptions
        opts = ImagePipelineOptions(engine="easyocr", lang="slv+eng")
        assert opts.get_easyocr_lang() == ["sl", "en"]

    def test_get_rapidocr_lang(self):
        from clichefactory._engine.parsers.parser_utils.image.image_pipeline_options import ImagePipelineOptions
        opts = ImagePipelineOptions(engine="rapidocr", lang="deu")
        assert opts.get_rapidocr_lang() == "latin"

    def test_default_lang_is_eng(self):
        from clichefactory._engine.parsers.parser_utils.image.image_pipeline_options import ImagePipelineOptions
        opts = ImagePipelineOptions()
        assert opts.lang == "eng"
        assert opts.get_tesseract_lang() == "eng"
        assert opts.get_easyocr_lang() == ["en"]
        assert opts.get_rapidocr_lang() == "en"
