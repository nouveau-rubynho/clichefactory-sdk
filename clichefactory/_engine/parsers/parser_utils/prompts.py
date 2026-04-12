"""
Shared prompt templates for PDF and image parsers.
"""

# Docling VLM (per-page refinement)
FULL_PAGE_VLM_PROMPT = """Refine this document page. Below is OCR-derived Markdown for this page. Use the page image as the source of truth: fix errors, improve formatting, and preserve structure (headings, lists, tables). Output only the refined Markdown. Do NOT use ```markdown``` or code fences.

OCR Markdown for this page:
{page_markdown}
"""

# Docling per-partes (body + placeholders)
BODY_EXTRACT_FULL_DOC_PROMPT = """Extract all body text from this PDF as Markdown. Where you see a table (in reading order), output exactly one placeholder per table: [TABLE_1], [TABLE_2], …, up to [TABLE_{num_tables}]. Where you see a figure or image, output [FIGURE_1], [FIGURE_2], …, up to [FIGURE_{num_figures}]. Do NOT transcribe any table or figure content—only mark positions with placeholders. Preserve document structure (headings, paragraphs, lists). Output only the Markdown. Do NOT use ``` code fences."""

BODY_EXTRACT_FULL_DOC_NO_VISUALS_PROMPT = """Extract all text from this PDF as Markdown. Preserve document structure (headings, paragraphs, lists). Output only the Markdown. Do NOT use ``` code fences."""

TABLE_VLM_PROMPT_SINGLE_TEMPLATE = """Table {table_index} is located at [x={x:.0f}, y={y:.0f}, width={width:.0f}, height={height:.0f}] on the page. Surrounding context: {context_snippet}.
Here is the crop of that area. Please transcribe the content as a Markdown table, correcting OCR errors based on context. Output only the Markdown table (e.g. | col1 | col2 |\n|---|\n| a | b |). Do not add any text before or after."""

TABLE_VLM_PROMPT_MULTI = """The following image(s) show one table that spans multiple pages. Extract the full table content as a single Markdown table. Output only the Markdown table. Do NOT use ``` code fences."""

FIGURE_VLM_PROMPT_TEMPLATE = """You are given an image region from a PDF document (Figure {figure_index}).
Describe its content in Markdown with:
- A short heading (e.g. "### Figure {figure_index}: ...").
- A concise bullet list of key information.
Do not output JSON. Do not include code fences."""

# YOLO per-partes
BODY_EXTRACT_PROMPT = """\
Extract all body text from these PDF page images as Markdown.

You are given page images that may contain large white boxes with placeholders
such as [TABLE_1] or [FIGURE_1] written inside them. These placeholders mark
tables and figures that will be transcribed separately.

Transcribe the visible body text and these placeholders in natural reading
order. Do not attempt to reconstruct the content inside the white boxes; just
copy the placeholder tokens exactly as they appear.

Preserve document structure (headings, paragraphs, lists). Output only the
Markdown. Do NOT use ``` code fences."""

BODY_EXTRACT_NO_VISUALS_PROMPT = """\
Extract all text from these PDF page images as Markdown. Preserve document
structure (headings, paragraphs, lists). Output only the Markdown. Do NOT use
``` code fences."""

TABLE_VLM_PROMPT = """\
You are given an image region from a PDF that is expected to be a table
(Table {index}, page {page}) located at [x={x:.0f}, y={y:.0f}, width={w:.0f}, height={h:.0f}].

If the region is a table, transcribe it as a Markdown table, correcting OCR
errors where possible.

If it is not actually a table, ignore the table format and instead transcribe
all visible text as normal Markdown lines.

Always output either a Markdown table or plain Markdown text. Output only this
content (no commentary before or after)."""

FIGURE_VLM_PROMPT = """\
You are given an image region from a PDF document (Figure {index}, page {page}).
Describe its content in Markdown with:
- A short heading (e.g. "### Figure {index}: ...").
- A concise bullet list of key information.
Do not output JSON.  Do not include code fences."""

FALLBACK_TABLE_PROMPT = """\
You are improving OCR for a single table in a PDF document.

You receive:
- A snippet of the current Markdown body text, including the placeholder \
{placeholder} where the table should appear.
- The rendered image of the full page that contains this table.

Task:
- Look at the page image and the surrounding text context in the snippet.
- Produce the correct Markdown table that should replace {placeholder}.
- Include all visible rows and columns, with a clear header row if present.
- Do NOT repeat any surrounding non-table text.
- Output ONLY the Markdown table."""

FALLBACK_FIGURE_PROMPT = """\
You are improving OCR for a single figure in a PDF document.

You receive:
- A snippet of the current Markdown body text, including the placeholder \
{placeholder} where the figure should appear.
- The rendered image of the full page that contains this figure.

Task:
- Look at the page image and the surrounding text context in the snippet.
- Produce a short Markdown description that should replace {placeholder}, with:
  - A heading like "### Figure {index}: ...".
  - A concise bullet list of key information from the figure.
- Do NOT repeat large amounts of surrounding body text.
- Output ONLY this Markdown description (no JSON, no code fences)."""
