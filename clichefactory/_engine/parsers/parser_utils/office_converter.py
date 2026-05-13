"""
Convert office documents (DOC, ODT) to PDF for parsing.

Used by DocParser for formats that Docling does not support natively
(.doc, .odt). LibreOffice's headless ``soffice`` binary handles both
formats directly, so it is the only hard runtime requirement now.
Pandoc is supported as a fallback path for hosts that ship pandoc but
not LibreOffice; this is best-effort and not used by the default
service deployment.
"""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


_SOFFICE_EXTENSIONS = frozenset({".doc", ".odt"})
_SOFFICE_MIMES = frozenset(
    {
        "application/msword",
        "application/vnd.oasis.opendocument.text",
    }
)


def _should_use_soffice(suffix: str, mime: str) -> bool:
    return suffix.lower() in _SOFFICE_EXTENSIONS or mime in _SOFFICE_MIMES


def convert_office_to_pdf_path(filepath: str, mime: str) -> str:
    """
    Convert an office file at *filepath* to PDF and return the output PDF path.

    Prefers ``soffice`` (LibreOffice headless) for legacy ``.doc`` and
    ``.odt``. Falls back to ``pandoc`` only if neither the suffix nor the
    MIME maps to a soffice-handled format. Either ``soffice`` or
    ``pandoc`` must be available on PATH.
    """
    input_path = Path(filepath)
    suffix = input_path.suffix.lower()

    if _should_use_soffice(suffix, mime):
        logger.info("Converting %s via soffice (LibreOffice headless)", input_path.name)
        return doc_to_pdf(input_path, input_path.parent.resolve())

    output_path = input_path.with_suffix(".pdf")
    logger.info("Running pandoc to convert %s -> %s", input_path.name, output_path.name)
    _run_pandoc(input_path, output_path)
    return str(output_path.resolve())


def convert_office_bytes_to_pdf_bytes(content: bytes, filename: str, mime: str) -> bytes:
    """
    Convert in-memory office bytes (DOC/ODT/…) to PDF bytes.

    Routes ``.doc`` and ``.odt`` through ``soffice``; other office
    formats fall through to ``pandoc`` if available.
    """
    suffix = Path(filename).suffix or ""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        input_path = tmpdir_path / f"input{suffix}"
        input_path.write_bytes(content)

        if _should_use_soffice(suffix, mime):
            logger.info("Converting %s via soffice (LibreOffice headless)", input_path.name)
            produced = Path(doc_to_pdf(input_path, tmpdir_path.resolve()))
            pdf_path = produced if produced.exists() else tmpdir_path / "output.pdf"
        else:
            pdf_path = tmpdir_path / "output.pdf"
            logger.info("Running pandoc: %s -> %s", input_path.name, pdf_path.name)
            _run_pandoc(input_path, pdf_path)

        if not pdf_path.exists():
            raise RuntimeError(
                f"Office conversion reported success but {pdf_path.name} is missing"
            )

        return pdf_path.read_bytes()


def doc_to_pdf(input_path: Path, output_dir: Path) -> str:
    """Convert a legacy ``.doc`` or ``.odt`` file to PDF using ``soffice``."""
    soffice = shutil.which("soffice")
    if soffice is None:
        raise RuntimeError(
            "soffice (LibreOffice headless) is required to convert "
            f"{input_path.name} but was not found on PATH. Install "
            "libreoffice-core (and the writer component) in the runtime image."
        )

    logger.info("Running soffice to convert %s -> pdf", input_path.name)
    cmd = [
        soffice,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(input_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "LibreOffice conversion failed:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    output_file = Path(output_dir) / (input_path.stem + ".pdf")
    return str(output_file)


def _run_pandoc(input_path: Path, output_path: Path) -> None:
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise RuntimeError(
            f"pandoc is required to convert {input_path.name} but was not "
            "found on PATH. Either install pandoc or use a LibreOffice-backed "
            "format (.doc, .odt)."
        )
    try:
        subprocess.run(
            [pandoc, str(input_path), "-o", str(output_path)],
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
        raise RuntimeError(
            f"Pandoc failed to convert {input_path.name} to PDF"
        ) from e
