"""Render a standalone HTML system report to PDF with Qt."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import (
    QFont,
    QPageLayout,
    QPageSize,
    QPdfWriter,
    QTextDocument,
)


def write_system_report_pdf(html: str, path: Path | str) -> None:
    """Write ``html`` to an A4 PDF using Qt's HTML subset.

    Images embedded as base64 data URIs are supported by ``QTextDocument``.
    """
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(150)
    writer.setPageMargins(
        QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter
    )
    document = QTextDocument()
    document.setDefaultFont(QFont("Sans Serif", 9))
    document.setHtml(html)
    document.setPageSize(QSizeF(writer.width(), writer.height()))
    document.print_(writer)


__all__ = ["write_system_report_pdf"]
