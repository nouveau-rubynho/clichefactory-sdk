"""
Convert office documents (DOC, DOCX, ODT) to PDF for parsing.

Used by DocParser for formats that Docling does not support natively (.doc, .odt).
Requires pandoc and/or LibreOffice (soffice) installed on the system.
"""
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_office_to_pdf_path(filepath: str, mime: str) -> str:
    """
    Convert DOCX / DOC / ODT to PDF using pandoc or soffice.

    Requires `pandoc` (and a LaTeX engine) or LibreOffice installed on the system.
    Returns path to the output PDF file.
    """
    input_path = Path(filepath)
    output_path = input_path.with_suffix(".pdf")

    if mime == "application/msword":  # Legacy Word .doc format
        logger.info(f"Calling doc_to_pdf to convert {input_path} via soffice old school doc to pdf.")
        output_path = Path(doc_to_pdf(input_path, input_path.parent.resolve()))
        return str(output_path.resolve())

    logger.info(f"Running pandoc to convert {input_path.name} -> {output_path.name}")
    try:
        subprocess.run(
            [
                "pandoc",
                str(input_path),
                "-o",
                str(output_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        logger.error(
            "Pandoc conversion failed: returncode=%s, stderr=%s",
            e.returncode,
            e.stderr.decode("utf-8", errors="ignore"),
        )
        raise RuntimeError(f"Pandoc failed to convert office document {input_path.name} to PDF") from e

    if not output_path.exists():
        raise RuntimeError("Pandoc reported success but output.pdf is missing in temp directory")

    return str(output_path.resolve())


def convert_office_bytes_to_pdf_bytes(content: bytes, filename: str, mime: str) -> bytes:
    """
    Convert an office file (DOCX/DOC/ODT/etc.) to PDF and return PDF bytes.
    Uses pandoc for most formats, and `doc_to_pdf` (soffice) for legacy .doc.

    Requirements:
      - pandoc installed (and whatever it needs for PDF output),
      - and/or LibreOffice (soffice) for legacy .doc via doc_to_pdf.
    """
    suffix = Path(filename).suffix or ""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        input_path = tmpdir_path / f"input{suffix}"
        input_path.write_bytes(content)

        output_path = tmpdir_path / "output.pdf"

        # Legacy Word .doc
        if mime == "application/msword" or suffix.lower() == ".doc":
            logger.info(f"Converting legacy DOC via soffice: {input_path}")
            produced = Path(doc_to_pdf(input_path, tmpdir_path.resolve()))
            pdf_path = produced if produced.suffix.lower() == ".pdf" else output_path

        else:
            logger.info(f"Running pandoc: {input_path.name} -> {output_path.name}")
            try:
                subprocess.run(
                    ["pandoc", str(input_path), "-o", str(output_path)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as e:
                logger.error(
                    "Pandoc conversion failed: returncode=%s, stderr=%s",
                    e.returncode,
                    e.stderr.decode("utf-8", errors="ignore"),
                )
                raise RuntimeError(f"Pandoc failed to convert {filename} ({mime}) to PDF") from e

            pdf_path = output_path

        if not pdf_path.exists():
            raise RuntimeError("Conversion reported success but PDF output is missing")

        return pdf_path.read_bytes()


def doc_to_pdf(input_path: Path, output_dir: Path) -> str:
    """Convert a legacy .doc file to PDF using LibreOffice (soffice)."""
    logger.info(f"Running soffice to convert {input_path.name} -> pdf")
    cmd = [
        "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(input_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    output_file = Path(output_dir) / (Path(input_path).stem + ".pdf")
    return str(output_file)
