"""PDF discovery helpers for the data directory."""

import re
from pathlib import Path


def _natural_sort_key(path: Path) -> list[str | int]:
    """Return a sort key that mixes alphabetical and numeric ordering.

    Splits the filename into alternating text and integer chunks so that
    ``page_2.pdf`` sorts before ``page_10.pdf``.
    """
    parts = re.split(r"(\d+)", path.name)
    return [int(part) if part.isdigit() else part for part in parts]


def iter_pdfs(path: Path, recursive: bool = False) -> Path:
    """Find a single PDF in a directory.

    Args:
    """
    for f in path.iterdir():
        if f.is_file() and f.suffix.lower() == ".pdf":
            yield f
        if recursive and f.is_dir():
            yield from iter_pdfs(f)


def list_pdfs(path: str | Path, recursive: bool = False) -> list[Path]:
    """List PDF files in a directory, sorted in natural order.

    Args:
        path: Directory containing the PDFs.
        recurvice: If ``True``, search subdirectories recursively.

    Returns:
        A list of ``Path`` objects pointing to ``*.pdf`` files.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        NotADirectoryError: If ``path`` is not a directory.
        ValueError: If no PDF is found.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PATH_TO_DATA directory not found: {p}")
    if not p.is_dir():
        raise NotADirectoryError(f"PATH_TO_DATA is not a directory: {p}")

    pdfs = sorted(iter_pdfs(p, recursive), key=_natural_sort_key)
    return pdfs


def first_pdf(path: str | Path) -> Path:
    """Return the first PDF from the data directory.

    Thin wrapper around :func:`list_pdfs` for the common single-file case.

    Args:
        path: Directory containing the PDFs.

    Returns:
        The first PDF path (sorted in natural order).
    """
    return list_pdfs(path)[0]
