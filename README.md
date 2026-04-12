# ClicheFactory (Python SDK)

## Introduction

ClicheFactory is a structured data extraction SDK. It parses documents (PDF, images, Office, email, etc.) and extracts structured data into Pydantic models — locally with your own LLM keys, or via the ClicheFactory service. Training is managed through [ClicheFactory](https://clichefactory.com); the SDK consumes trained artifacts via `artifact_id`.

## Installing

```bash
pip install clichefactory
```

For local parsing/OCR (Docling/PyMuPDF/Tesseract/etc.):

```bash
pip install "clichefactory[local]"
```

## Quickstart

### Local extraction from text

```python
from pydantic import BaseModel
from clichefactory import Endpoint, factory

class Invoice(BaseModel):
    invoice_number: str | None = None
    total_amount: float | None = None

client = factory(
    mode="local",
    model=Endpoint(provider_model="gemini/gemini-3-flash-preview", api_key="..."),
)

c = client.cliche(Invoice)
invoice = c.extract(text="Invoice #123 total 99.00 EUR")
print(invoice)
```

Local mode does **not** pick a default model: you must pass `model=Endpoint(...)` (or `llm=` for compatibility) **or** set `LLM_MODEL_NAME` and `LLM_API_KEY` in the environment. If parsing options use OCR LLM fallback or VLM refinement, configure an OCR LLM the same way (`ocr_model` / `OCR_MODEL_*` env vars) or disable those fallbacks (see [`ParsingOptions`](#parsingoptions)).

### Local extraction from file

Requires `clichefactory[local]`. Parses the document (OCR if needed), converts to markdown, then extracts structured data via the LLM.

```python
invoice = c.extract(file="/path/to/invoice.pdf")
```

### Fast extraction (file bytes direct to LLM)

Skips OCR/parsing entirely — sends the raw file to a multimodal LLM.

```python
invoice = c.extract(file="invoice.pdf", mode="fast")
```

### Service mode (SaaS)

```python
from clichefactory import factory

client = factory(api_key="cliche-...")  # mode defaults to "service"

c = client.cliche(Invoice)
invoice = c.extract(file="/path/to/invoice.pdf")
```

**Service URL:** By default the SDK uses `http://127.0.0.1:4000` (local aio-server). For production, set the environment variable **`CLICHEFACTORY_API_URL`** to `https://api.clichefactory.com`, or pass **`base_url=`** to `factory()` explicitly (this overrides the env var).

Local paths (and raw bytes) are automatically uploaded by the SDK before the service processes them.

### Trained extraction

Training is done through [ClicheFactory](https://ClicheFactory.com). Once you have a trained artifact, use it via `artifact_id`:

```python
from clichefactory import factory

client = factory(api_key="cliche-...")
cliche = client.cliche(Invoice, artifact_id="art_8cee...")
result = cliche.extract(file="document.pdf")
```

**API keys:** Use a key from **ClicheFactory → Settings → API Keys** (`cliche-...`). Those keys authenticate as your account and are billed against your credits. They are not the same as internal aio-server operator keys used between services.

**BYOK vs hosted (service mode):**

- **BYOK** — Pass `model=Endpoint(..., api_key=...)` (and optionally `ocr_model=`) so extraction/OCR use your LLM credentials. Billing uses the BYOK rate.
- **Hosted** — Omit `model` / `ocr_model` so the platform runs the LLMs. Your Pydantic schema must still match the trained pipeline’s output shape (as exported from ClicheFactory).

**Explicit `mode` vs artifact default:** You can pass `mode=` (e.g. `mode="trained"`) or omit it. When the artifact defines a pipeline mode (e.g. `robust-trained`), the service can apply that mode automatically if you do not override it.

**`robust-trained`:** Requires an artifact trained with the verification pipeline (`VerifiedExtractor`). If you only trained a single-step extractor, use default extraction or `mode="trained"` instead of forcing `robust-trained`.

## Extraction modes

| Mode | Local | Service | Description |
|------|-------|---------|-------------|
| `None` (default) | yes | yes | Parse document -> markdown -> LLM extraction |
| `"fast"` | yes | yes | Send raw file bytes directly to LLM (no OCR) |
| `"trained"` | - | yes | Uses a trained artifact (DSPy `BaseExtractor` on OCR text) |
| `"robust"` | - | yes | Untrained extract + verify (two-stage) |
| `"robust-trained"` | - | yes | Trained extract + verify; **artifact must be trained for verification** |

```python
invoice = c.extract(file="/path/to/invoice.pdf", mode="robust")
```

## Document to markdown

Convert any supported file to a structured markdown representation.

```python
doc = client.to_markdown(file="invoice.pdf")
print(doc.get_markdown())
print(doc.get_pages())
```

Service mode (set `mode="service"` on the call; it is separate from `factory(mode=...)`):

```python
doc = client.to_markdown(file="invoice.pdf", mode="service")

# Fast mode (VLM-only, no parser pipeline)
doc = client.to_markdown(file="invoice.pdf", mode="service", parser="fast")
```

The returned document object provides:
- `get_markdown()` — full markdown text
- `get_plain_text()` — plain text without formatting
- `get_pages()` — list of page objects
- `get_sections()` — list of section objects
- `get_tables()` — list of table objects
- `get_images()` — list of image objects

Not every pipeline has all of these options.

## Batch operations

Process multiple files concurrently with configurable parallelism.

### Batch extraction

```python
results = c.extract_batch(
    files=["./data/doc1.pdf", "./data/doc2.pdf", "./data/doc3.pdf"],
    max_concurrency=5,
    mode="fast",
)
for invoice in results:
    print(invoice.vendor_name, invoice.total_with_vat)
```

### Batch markdown

```python
docs = client.to_markdown_batch(
    files=["a.pdf", "b.pdf", "c.pdf"],
    max_concurrency=5,
)
for doc in docs:
    print(len(doc.get_markdown()), "chars")
```

Service mode (presign + OCR on the server for each file):

```python
docs = client.to_markdown_batch(
    files=["a.pdf", "b.pdf"],
    mode="service",
    max_concurrency=5,
)
```

## SaaS pricing (service mode)

Billing applies only when using **`mode="service"`** with a ClicheFactory API key. Local runs are not metered by the platform.

**Free tier**

- **10** lifetime extraction pages (metered per processed page). Those pages are free regardless of full-service vs BYOK.

**Paid usage** (credit balance)

- After free extraction pages are exhausted, extraction is billed per page from your balance.
- **Full-service** means the platform runs the LLMs. **BYOK** (bring your own key) applies when you supply your own LLM API key on the client (for example via `Endpoint(..., api_key=...)` or envelope config as implemented in the SDK).

Default rates (USD; the API may override these per deployment via stored rate rows):

| Operation | Full-service | BYOK |
|-----------|--------------|------|
| Extraction (per page) | $0.005 | $0.0005 |
| Training | via [ClicheFactory](https://clichefactory.com) | via [ClicheFactory](https://clichefactory.com) |

## Configuration

### `Endpoint` (BYOK LLM config)

```python
from clichefactory import Endpoint

model = Endpoint(
    provider_model="gemini/gemini-3-flash-preview",
    api_key="...",
    max_tokens=100000,
    temperature=1.0,
    num_retries=8,
    api_base=None,    # for Ollama: "http://localhost:11434"
)

client = factory(mode="local", model=model)
```

### Advanced multi-model overrides

Most users should set only `model`. If you need role-specific endpoints, override per role:

```python
client = factory(
    mode="service",
    api_key="cliche-...",
    model=Endpoint(provider_model="gemini/gemini-3-flash-preview", api_key="..."),  # extraction default
    ocr_model=Endpoint(provider_model="gemini/gemini-3-flash-preview", api_key="..."),  # optional
)
```

Per-call overrides are also available:

```python
invoice = c.extract(file="/path/to/invoice.pdf", model=Endpoint(...), ocr_model=Endpoint(...))
```

### `ParsingOptions`

Fine-grained control over local-mode document parsing. `ParsingOptions` only applies to local extraction — in service mode the platform selects the optimal parsing strategy and this parameter is ignored.

```python
from clichefactory import ParsingOptions

parsing = ParsingOptions(
    pdf_image_parser="docling",              # "docling", "docling_vlm", "vision_layout" (SaaS-only)
    pdf_fallback_to_ocr_llm=True,            # fall back to LLM OCR when local parser fails
    pdf_structured_fallback_to_image=False,   # retry structured PDFs as image-scanned on failure
    pdf_ocr_engine="rapidocr",               # "rapidocr", "tesseract", "easyocr"
    pdf_ocr_lang="eng",                      # language code(s), see OCR language section below
    use_ocr_llm_body=True,                   # use LLM for body text when parser supports it

    image_parser="rapidocr",                 # "rapidocr", "pytesseract", "docling", "ocr_llm"
    image_parser_fallback=True,              # fall back to ocr_llm on failure
    image_parser_lang="eng",                 # language code(s), see OCR language section below
)

client = factory(mode="local", model=model, parsing=parsing)
```

### Environment variables

For **local** runs, the primary extraction defaults are:

| Role | Variables | Notes |
|------|-----------|--------|
| Extraction LLM | `LLM_MODEL_NAME`, `LLM_API_KEY` | Also accepted: `MODEL_NAME` / `MODEL_API_KEY`, `EXTRACTION_LLM_MODEL_NAME` / `EXTRACTION_LLM_API_KEY`. **No implicit default model** — if unset, local extraction fails until you configure a model. |
| OCR LLM (optional) | `OCR_MODEL_NAME`, `OCR_MODEL_API_KEY` | Used when you set a separate OCR endpoint; otherwise OCR reuses the extraction model when your parsing options need an OCR LLM. Aliases include `OCR_LLM_MODEL_NAME` / `OCR_LLM_API_KEY` and `OCR_API_KEY`. |

Optional endpoints override extraction/OCR on `factory()` via `model` and `ocr_model`.

For **service** mode, the only URL-related environment variable is **`CLICHEFACTORY_API_URL`** (unless you pass `base_url=` to `factory()`, which wins).

### Ollama (local model inference)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama run llama3.2:1b
```

```python
client = factory(
    mode="local",
    model=Endpoint(provider_model="ollama/llama3.2:1b", api_key="", api_base="http://localhost:11434"),
)
```

Current scope: Ollama supports text extraction only (`extract(text=...)`). File parsing and OCR paths are not supported for Ollama.

## PDF parser selection

| Parser | Config value | Description |
|--------|-------------|-------------|
| Docling | `"docling"` | Local OCR + table structure via Docling (default). Full structured output. |
| VLM direct | `"fast"` extraction mode | Sends the whole PDF to the LLM. No layout structure, fastest. |
| Docling + VLM | `"docling_vlm"` | Docling for structure + per-page VLM refinement. |
| Vision Layout | `"vision_layout"` | More performant layout detection. **SaaS-only**. |

Set via `ParsingOptions(pdf_image_parser=...)` or on `factory(parsing=...)`.

### OCR LLM fallback for Docling-based parsers

Docling-based parsers can fall back to **OCR LLM** (your configured vision-capable model) when Docling produces empty or degenerate output. Controlled by `pdf_fallback_to_ocr_llm` (default `True`). That path requires a configured OCR LLM (or the same model as extraction).

### Parallel OCR LLM refinement calls

VLM-oriented parsers (e.g. `docling_vlm`) can issue multiple parallel **OCR LLM** calls per document (per-page or per-table) to keep latency under control.

## ClicheFactory UI integration

Documents extracted via the SDK appear in [ClicheFactory](https://ClicheFactory.com) **only when
you set both `project` and `task`** on the factory. Documents without explicit
scope are extraction-only and won't appear in the ClicheFactory UI.

```python
from clichefactory import factory

client = factory(
    api_key="cliche-...",
    project="42",   # ClicheFactory Project ID (visible in URL: /projects/42/)
    task="108",      # ClicheFactory Batch ID (visible in URL: /batch/108/)
)

# Extractions will appear under that project/batch in ClicheFactory
result = client.cliche(MySchema).extract(file="document.pdf")
```

Documents sync automatically every ~30 minutes, or immediately via the
"Sync from SDK" button in the ClicheFactory UI.

If you omit `project`/`task`, extraction works normally — your data just
won't be visible in ClicheFactory.

**Tenant id (HTTP APIs):** User API keys resolve to a **tenant id** stored with the key (typically your ClicheFactory user id as a string, e.g. `"1"`). Envelope `tenant_id="default"` is rewritten server-side to that tenant for inference. When calling aio-server REST endpoints directly (e.g. listing documents), pass **`tenant_id` matching your key’s tenant**, not the literal string `"default"`, or the request will be rejected.

## OCR language configuration

Languages are specified using **Tesseract format** everywhere — the SDK converts internally for each engine. Use `+` to combine multiple languages (e.g. `"slv+eng"` for Slovenian + English).

```python
parsing = ParsingOptions(
    pdf_ocr_lang="deu+eng",     # German + English for PDFs
    image_parser_lang="fra",    # French for images
)
```

The default language is `"eng"` (English).

### How languages work per OCR engine

| Engine | Config value | Language handling | System dependency |
|--------|-------------|-------------------|-------------------|
| **Tesseract** | `pdf_ocr_engine="tesseract"` / `image_parser="pytesseract"` | Uses Tesseract format directly (`"slv+eng"`). Requires matching `.traineddata` files under `$TESSDATA_PREFIX`. | Tesseract binary on `PATH` |
| **RapidOCR** | `pdf_ocr_engine="rapidocr"` / `image_parser="rapidocr"` | Maps language to a script family (e.g. `"eng"` → English model, `"deu"` → Latin model). No per-language model download needed. | None (pure Python, ONNX) |
| **EasyOCR** | `pdf_ocr_engine="easyocr"` / `image_parser="easyocr"` | Converts to ISO 639-1 codes (e.g. `"eng"` → `"en"`, `"deu"` → `"de"`). Downloads per-language models on first use. | None (pure Python, PyTorch) |
| **Docling** | `image_parser="docling"` | Uses Docling's built-in image conversion. No language parameter. | None |
| **OCR LLM** | `image_parser="ocr_llm"` | VLM-based — the model handles language detection automatically. | Configured `ocr_model` |

### Common language codes

| Language | Code | Notes |
|----------|------|-------|
| English | `eng` | Default |
| German | `deu` | |
| French | `fra` | |
| Spanish | `spa` | |
| Italian | `ita` | |
| Slovenian | `slv` | |
| Polish | `pol` | |
| Russian | `rus` | Cyrillic script |
| Chinese (Simplified) | `chi_sim` | |
| Japanese | `jpn` | |
| Korean | `kor` | |
| Arabic | `ara` | RTL script |

Multi-language example: `"slv+eng"` (Slovenian + English), `"deu+fra"` (German + French).

### RapidOCR script families

RapidOCR operates at the script level, not individual languages. Multiple Latin-script languages (German, French, Slovenian, etc.) all map to the `latin` model. The SDK handles this mapping automatically — you still specify languages in Tesseract format.

| Script family | Covers |
|--------------|--------|
| `en` | English (dedicated model) |
| `latin` | German, French, Spanish, Italian, Slovenian, Polish, etc. |
| `cyrillic` | Russian, Ukrainian, Bulgarian, Serbian |
| `ch` | Chinese (Simplified) |
| `japan` | Japanese |
| `korean` | Korean |
| `arabic` | Arabic |
| `devanagari` | Hindi, Bengali |

## Local parsing dependencies

### DOC/ODT conversion

For legacy Office files (`.doc`, `.odt`), the parser converts files to PDF first, then processes them through the PDF pipeline.

This requires external system tools if you run it locally and not in service mode:

- `pandoc` for general Office -> PDF conversion
- `LibreOffice` (`soffice`) for legacy `.doc` conversion

If these tools are missing, `.doc`/`.odt` parsing will fail at runtime.

### Tesseract OCR

If using a Docling Tesseract-based OCR engine, ensure:

- Tesseract is installed and on `PATH`
- The language data directory is configured via `TESSDATA_PREFIX`

```bash
# macOS with Homebrew
export TESSDATA_PREFIX="/opt/homebrew/opt/tesseract/share/tessdata"
```

Languages configured in `pdf_ocr_lang` must have matching `.traineddata` files under `$TESSDATA_PREFIX`.

### RapidOCR font

Docling uses RapidOCR which may try to download a font (FZYTK.TTF) at runtime. Set a local font path to avoid this:

```bash
export DOCLING_OCR_FONT_PATH="/path/to/a/unicode.ttf"
```

On macOS, a system font is usually available automatically when this variable is unset.
On Linux/Windows or restricted environments, setting `DOCLING_OCR_FONT_PATH` is recommended.

## Supported file types

| Extension(s) | Parser | Notes |
|-------------|--------|-------|
| `.pdf` | PdfRouterParser | Classifies structured vs scanned, routes accordingly |
| `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp` | ImageRouterParser | Routes to configured image parser |
| `.docx` | DocxParser | Via Docling |
| `.doc`, `.odt` | DocParser|
| `.xlsx` | XlsxParser |
| `.csv` | CsvParser | Auto-detect delimiter and header |
| `.eml` | EmlParser | RFC 2822 with recursive attachment parsing |
| `.txt`, `.md` | TextParser | Passthrough with encoding detection |
