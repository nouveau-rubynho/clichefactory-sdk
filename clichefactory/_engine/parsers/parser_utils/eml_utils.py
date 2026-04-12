# ---- Utility helpers for eml parsing
from email.message import Message
import re
from typing import Dict, List, Optional

import logging
from clichefactory._engine.models.normalized_doc import NormalizedDoc

logger = logging.getLogger(__name__)

def normalize_newlines(text: str) -> str:
    """RFC 5322–compliant email messages must use CRLF (\r\n) as line endings.
    Python’s email package preserves those line endings in most body extraction paths 
    unless you normalize them.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,})(?P<space>\s+)(?P<title>.*?)(?P<trailing>\s*#*\s*)$")

def demote_headings(markdown: str, *, delta: int = 1, max_level: int = 6) -> str:
    """
    Demote headings (#, ##, ###...) by `delta`.
    - Ignores headings inside fenced code blocks.
    - Any resulting level > max_level becomes bold text: **Title** (instead of ####### Title).
    """
    if not markdown:
        return ""

    out: List[str] = []
    in_fence = False

    for line in markdown.splitlines():
        stripped = line.lstrip()

        # Track fenced code blocks (``` or ~~~). Simple + robust enough for most outputs.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append(line)
            continue

        if in_fence:
            out.append(line)
            continue

        m = _HEADING_RE.match(line)
        if not m:
            out.append(line)
            continue

        old_level = len(m.group("hashes"))
        new_level = old_level + delta
        title = m.group("title").strip()

        if new_level > max_level:
            # Turn "too-deep headings" into bold paragraphs.
            # Keep it simple and predictable.
            out.append(f"**{title}**")
        else:
            out.append(f"{'#' * new_level} {title}")

    return "\n".join(out)


def build_plain_text(headers: Message, body_plain: Optional[str], attachments: Optional[List[NormalizedDoc]]) -> str:
    lines: List[str] = []

    subject = headers.get("Subject", "(no subject)")
    lines.append(subject)
    lines.append("")

    # Headers as plain text (no heading)
    for name in ["From", "To", "Cc", "Bcc", "Date", "Message-ID"]:
        val = headers.get(name)
        if val:
            lines.append(f"{name}: {val}")

    if body_plain:
        lines.append("")
        lines.append(body_plain.strip())

    if attachments:
        for i, att in enumerate(attachments, start=1):
            lines.append("")
            lines.append(f"[Attachment {i}]")
            lines.append(att.get_plain_text().strip())

    return "\n".join(lines).strip() + "\n"


def build_markdown(headers: Message, body_plain: Optional[str], attachments: Optional[List[NormalizedDoc]]) -> str:
    md: List[str] = []

    subject = headers.get("Subject", "(no subject)")
    md.append(f"# {subject}")
    md.append("")

    # Headers as plain text (NOT headings)
    header_lines: List[str] = []
    for name in ["From", "To", "Cc", "Bcc", "Date", "Message-ID"]:
        val = headers.get(name)
        if val:
            header_lines.append(f"**{name}:** {val}")

    if header_lines:
        md.extend(header_lines)
        md.append("")

    # Body as plain text
    if body_plain and body_plain.strip():
        md.append("## Email body")
        md.append(body_plain.strip())
        md.append("")

    # Attachments: each is an H2, inner headings demoted by +1
    if attachments:
        md.append("# Email attachments")
        for idx, att in enumerate(attachments, start=1):
            title = getattr(att, "filename", None) or f"Attachment {idx}"
            md.append(f"## {title}")
            md.append("")

            att_md = (att.get_markdown() or "").strip()
            if att_md:
                md.append(demote_headings(att_md, delta=2, max_level=6))
            else:
                md.append("_Empty attachment_")

            md.append("")

    if not (header_lines or (body_plain and body_plain.strip()) or attachments):
        md.append("_No email content available_")
        md.append("")

    return "\n".join(md).rstrip() + "\n"


def extract_body(msg: Message) -> Dict[str, Optional[str]]:
    """
    Prefer text/plain; fall back to text/html (with very naive tag stripping).
    Returns dict with 'text_plain' and 'text_html' keys.
    """
    text_plain = None
    text_html = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = part.get_content_disposition()
            if disposition == "attachment":
                continue  # skip attachments here

            try:
                payload = part.get_content()  # type: ignore
            except Exception:
                continue  # TODO: Should we continue or throw?

            if content_type == "text/plain" and text_plain is None and isinstance(payload, str):
                text_plain = normalize_newlines(payload)
            elif content_type == "text/html" and text_html is None and isinstance(payload, str):
                text_html = normalize_newlines(payload)
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_content() # type: ignore
        except Exception:
            payload = None
        if content_type == "text/plain" and isinstance(payload, str):
            text_plain = normalize_newlines(payload)
        elif content_type == "text/html" and isinstance(payload, str):
            text_html = normalize_newlines(payload)

    # Fallback: crude HTML->text if plain missing
    if text_plain is None and text_html is not None:
        import re
        # Very naive stripping – replace <br> with newlines, then strip tags.
        text = text_html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        text = re.sub(r"<[^>]+>", "", text)
        text_plain = text

    return {"text_plain": text_plain, "text_html": text_html}

