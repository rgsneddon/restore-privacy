"""Pens / Word-class document model (handmade Raskul — not Microsoft Word).

Core: paragraphs with character runs, styles, alignment, lists, tables,
image placeholders, find/replace, undo/redo, JSON round-trip.

Honesty: Word-class *core* outcomes — not full OOXML/VBA/collaboration parity.
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator

KIND = "pens_document"
SCHEMA_VERSION = 2

# Paragraph styles (Word-class core set)
STYLE_NORMAL = "Normal"
STYLE_HEADING1 = "Heading1"
STYLE_HEADING2 = "Heading2"
STYLE_HEADING3 = "Heading3"
STYLE_QUOTE = "Quote"
PARAGRAPH_STYLES = frozenset(
    {STYLE_NORMAL, STYLE_HEADING1, STYLE_HEADING2, STYLE_HEADING3, STYLE_QUOTE}
)

ALIGN_LEFT = "left"
ALIGN_CENTER = "center"
ALIGN_RIGHT = "right"
ALIGN_JUSTIFY = "justify"
ALIGNMENTS = frozenset({ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT, ALIGN_JUSTIFY})

LIST_BULLET = "bullet"
LIST_NUMBER = "number"


@dataclass
class CharFormat:
    """Character (run) formatting."""

    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_size: float | None = None  # points; None = inherit
    font_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "bold": bool(self.bold),
            "italic": bool(self.italic),
            "underline": bool(self.underline),
        }
        if self.font_size is not None:
            d["font_size"] = float(self.font_size)
        if self.font_name:
            d["font_name"] = str(self.font_name)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CharFormat":
        data = data or {}
        size = data.get("font_size")
        return cls(
            bold=bool(data.get("bold")),
            italic=bool(data.get("italic")),
            underline=bool(data.get("underline")),
            font_size=float(size) if size is not None else None,
            font_name=(str(data["font_name"]) if data.get("font_name") else None),
        )

    def merge(self, **kwargs: Any) -> "CharFormat":
        d = asdict(self)
        d.update({k: v for k, v in kwargs.items() if k in d})
        return CharFormat.from_dict(d)


@dataclass
class Run:
    """Contiguous text with one character format."""

    text: str
    format: CharFormat = field(default_factory=CharFormat)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "format": self.format.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Run":
        return cls(
            text=str(data.get("text") or ""),
            format=CharFormat.from_dict(data.get("format") if isinstance(data.get("format"), dict) else {}),
        )


@dataclass
class Paragraph:
    """Block of text: one or more runs + paragraph style/alignment/list."""

    runs: list[Run] = field(default_factory=list)
    style: str = STYLE_NORMAL
    align: str = ALIGN_LEFT
    list_type: str | None = None  # None | bullet | number
    list_level: int = 0
    # Back-compat: plain text ctor still works via from_text

    def __post_init__(self) -> None:
        if self.style not in PARAGRAPH_STYLES:
            self.style = STYLE_NORMAL
        if self.align not in ALIGNMENTS:
            self.align = ALIGN_LEFT
        if self.list_type not in (None, LIST_BULLET, LIST_NUMBER):
            self.list_type = None
        self.list_level = max(0, int(self.list_level or 0))

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)

    @text.setter
    def text(self, value: str) -> None:
        """Replace entire paragraph plain text (collapses runs — prefer replace_in_runs)."""
        fmt = self.runs[0].format if self.runs else CharFormat()
        self.runs = [Run(text=str(value), format=copy.deepcopy(fmt))]

    def replace_in_runs(
        self,
        needle: str,
        replacement: str,
        *,
        case_sensitive: bool = True,
    ) -> int:
        """Replace *needle* inside each run, preserving that run's CharFormat.

        Does not merge/split across run boundaries (keeps per-run bold/italic).
        Returns number of replacements.
        """
        if not needle:
            return 0
        count = 0
        if case_sensitive:
            for r in self.runs:
                n = r.text.count(needle)
                if n:
                    r.text = r.text.replace(needle, replacement)
                    count += n
        else:
            pattern = re.compile(re.escape(needle), re.IGNORECASE)
            for r in self.runs:
                new, n = pattern.subn(replacement, r.text)
                if n:
                    r.text = new
                    count += n
        return count

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        style: str = STYLE_NORMAL,
        align: str = ALIGN_LEFT,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        font_size: float | None = None,
        list_type: str | None = None,
        list_level: int = 0,
    ) -> "Paragraph":
        fmt = CharFormat(
            bold=bold,
            italic=italic,
            underline=underline,
            font_size=font_size,
        )
        return cls(
            runs=[Run(text=str(text), format=fmt)],
            style=style,
            align=align,
            list_type=list_type,
            list_level=list_level,
        )

    def apply_char_format(self, **kwargs: Any) -> None:
        """Apply character formatting to all runs in this paragraph."""
        for r in self.runs:
            r.format = r.format.merge(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runs": [r.to_dict() for r in self.runs],
            "style": self.style,
            "align": self.align,
            "list_type": self.list_type,
            "list_level": self.list_level,
            # convenience for simple readers
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Paragraph":
        runs_raw = data.get("runs")
        if isinstance(runs_raw, list) and runs_raw:
            runs = [Run.from_dict(r) for r in runs_raw if isinstance(r, dict)]
        else:
            # Schema v1: plain text + style
            runs = [Run(text=str(data.get("text") or ""), format=CharFormat())]
        return cls(
            runs=runs or [Run(text="", format=CharFormat())],
            style=str(data.get("style") or STYLE_NORMAL),
            align=str(data.get("align") or ALIGN_LEFT),
            list_type=data.get("list_type"),
            list_level=int(data.get("list_level") or 0),
        )


@dataclass
class TableCell:
    paragraphs: list[Paragraph] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)

    def set_text(self, text: str) -> None:
        self.paragraphs = [Paragraph.from_text(text)]

    def to_dict(self) -> dict[str, Any]:
        return {"paragraphs": [p.to_dict() for p in self.paragraphs]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableCell":
        paras = [
            Paragraph.from_dict(p)
            for p in (data.get("paragraphs") or [])
            if isinstance(p, dict)
        ]
        if not paras and "text" in data:
            paras = [Paragraph.from_text(str(data.get("text") or ""))]
        return cls(paragraphs=paras or [Paragraph.from_text("")])


@dataclass
class Table:
    """Simple grid of cells (Word-class core table)."""

    rows: list[list[TableCell]] = field(default_factory=list)
    table_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    @property
    def nrows(self) -> int:
        return len(self.rows)

    @property
    def ncols(self) -> int:
        return max((len(r) for r in self.rows), default=0)

    def cell(self, row: int, col: int) -> TableCell:
        return self.rows[row][col]

    def set_cell_text(self, row: int, col: int, text: str) -> None:
        self.rows[row][col].set_text(text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_id": self.table_id,
            "rows": [[c.to_dict() for c in row] for row in self.rows],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Table":
        rows: list[list[TableCell]] = []
        for row in data.get("rows") or []:
            if not isinstance(row, list):
                continue
            rows.append(
                [TableCell.from_dict(c) if isinstance(c, dict) else TableCell() for c in row]
            )
        return cls(
            rows=rows,
            table_id=str(data.get("table_id") or uuid.uuid4().hex[:10]),
        )

    @classmethod
    def create(cls, nrows: int, ncols: int, fill: str = "") -> "Table":
        nrows = max(1, int(nrows))
        ncols = max(1, int(ncols))
        rows = [
            [TableCell(paragraphs=[Paragraph.from_text(fill)]) for _ in range(ncols)]
            for _ in range(nrows)
        ]
        return cls(rows=rows)


@dataclass
class ImagePlaceholder:
    """Attachment hook for images (binary deferred; structure round-trips)."""

    name: str
    alt: str = ""
    image_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    # Optional future: content_type, data_uri, path

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "name": self.name,
            "alt": self.alt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImagePlaceholder":
        return cls(
            name=str(data.get("name") or "image"),
            alt=str(data.get("alt") or ""),
            image_id=str(data.get("image_id") or uuid.uuid4().hex[:10]),
        )


@dataclass
class Block:
    """Document block: paragraph | table | image."""

    kind: str  # paragraph | table | image
    paragraph: Paragraph | None = None
    table: Table | None = None
    image: ImagePlaceholder | None = None
    block_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind, "block_id": self.block_id}
        if self.kind == "paragraph" and self.paragraph is not None:
            d["paragraph"] = self.paragraph.to_dict()
        elif self.kind == "table" and self.table is not None:
            d["table"] = self.table.to_dict()
        elif self.kind == "image" and self.image is not None:
            d["image"] = self.image.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Block":
        kind = str(data.get("kind") or "paragraph")
        if kind == "table":
            return cls(
                kind="table",
                table=Table.from_dict(data.get("table") or {}),
                block_id=str(data.get("block_id") or uuid.uuid4().hex[:10]),
            )
        if kind == "image":
            return cls(
                kind="image",
                image=ImagePlaceholder.from_dict(data.get("image") or {}),
                block_id=str(data.get("block_id") or uuid.uuid4().hex[:10]),
            )
        para_data = data.get("paragraph")
        if isinstance(para_data, dict):
            para = Paragraph.from_dict(para_data)
        else:
            # legacy flat paragraph dict
            para = Paragraph.from_dict(data)
        return cls(
            kind="paragraph",
            paragraph=para,
            block_id=str(data.get("block_id") or uuid.uuid4().hex[:10]),
        )

    @classmethod
    def paragraph_block(cls, para: Paragraph) -> "Block":
        return cls(kind="paragraph", paragraph=para)

    @classmethod
    def table_block(cls, table: Table) -> "Block":
        return cls(kind="table", table=table)

    @classmethod
    def image_block(cls, image: ImagePlaceholder) -> "Block":
        return cls(kind="image", image=image)


@dataclass
class Document:
    """Pens document — Word-class core model (Raskul handmade)."""

    title: str
    blocks: list[Block] = field(default_factory=list)
    styles: dict[str, Any] = field(
        default_factory=lambda: {
            "theme": "default",
            "font": "system",
            "product": "Pens",
            "maker": "Raskul",
        }
    )
    doc_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    schema_version: int = SCHEMA_VERSION

    # --- compatibility views ---
    @property
    def paragraphs(self) -> list[Paragraph]:
        """Paragraph objects in document order (skips tables/images)."""
        out: list[Paragraph] = []
        for b in self.blocks:
            if b.kind == "paragraph" and b.paragraph is not None:
                out.append(b.paragraph)
        return out

    @paragraphs.setter
    def paragraphs(self, value: list[Paragraph]) -> None:
        self.blocks = [Block.paragraph_block(p) for p in value]

    @property
    def body(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)

    @body.setter
    def body(self, value: str) -> None:
        # Replace pure paragraph content with a single body paragraph if empty blocks
        text = str(value or "")
        if not self.blocks:
            if text:
                self.blocks = [Block.paragraph_block(Paragraph.from_text(text))]
            return
        # Sync: rebuild from lines for simple assignment
        lines = text.split("\n") if text else [""]
        self.blocks = [Block.paragraph_block(Paragraph.from_text(line)) for line in lines]

    def _sync_compat(self) -> None:
        """No-op hook kept for call sites that re-sync body."""
        return

    # --- builders ---
    def add_paragraph(
        self,
        text: str,
        style: str = STYLE_NORMAL,
        *,
        align: str = ALIGN_LEFT,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        font_size: float | None = None,
        list_type: str | None = None,
        list_level: int = 0,
        index: int | None = None,
    ) -> Paragraph:
        p = Paragraph.from_text(
            text,
            style=style,
            align=align,
            bold=bold,
            italic=italic,
            underline=underline,
            font_size=font_size,
            list_type=list_type,
            list_level=list_level,
        )
        block = Block.paragraph_block(p)
        if index is None:
            self.blocks.append(block)
        else:
            self.blocks.insert(max(0, index), block)
        return p

    def add_heading(self, text: str, level: int = 1) -> Paragraph:
        level = min(3, max(1, int(level)))
        style = {1: STYLE_HEADING1, 2: STYLE_HEADING2, 3: STYLE_HEADING3}[level]
        return self.add_paragraph(text, style=style, bold=True)

    def add_bullet(self, text: str, *, level: int = 0) -> Paragraph:
        return self.add_paragraph(text, list_type=LIST_BULLET, list_level=level)

    def add_numbered(self, text: str, *, level: int = 0) -> Paragraph:
        return self.add_paragraph(text, list_type=LIST_NUMBER, list_level=level)

    def add_table(self, nrows: int, ncols: int, fill: str = "") -> Table:
        t = Table.create(nrows, ncols, fill=fill)
        self.blocks.append(Block.table_block(t))
        return t

    def add_image_placeholder(self, name: str, alt: str = "") -> ImagePlaceholder:
        img = ImagePlaceholder(name=name, alt=alt)
        self.blocks.append(Block.image_block(img))
        return img

    def delete_block(self, index: int) -> None:
        if 0 <= index < len(self.blocks):
            del self.blocks[index]

    def move_block(self, from_index: int, to_index: int) -> None:
        if not (0 <= from_index < len(self.blocks)):
            return
        block = self.blocks.pop(from_index)
        to_index = max(0, min(len(self.blocks), to_index))
        self.blocks.insert(to_index, block)

    def plain_text(self) -> str:
        """Full plain text including table cells (for find)."""
        parts: list[str] = []
        for b in self.blocks:
            if b.kind == "paragraph" and b.paragraph is not None:
                parts.append(b.paragraph.text)
            elif b.kind == "table" and b.table is not None:
                for row in b.table.rows:
                    for cell in row:
                        parts.append(cell.text)
            elif b.kind == "image" and b.image is not None:
                parts.append(f"[{b.image.name}]")
        return "\n".join(parts)

    def find_all(self, needle: str, *, case_sensitive: bool = True) -> list[dict[str, Any]]:
        """Locate needle occurrences; returns list of {block_index, kind, start, end, snippet}."""
        if not needle:
            return []
        hits: list[dict[str, Any]] = []
        flags = 0 if case_sensitive else re.IGNORECASE
        for i, b in enumerate(self.blocks):
            if b.kind == "paragraph" and b.paragraph is not None:
                text = b.paragraph.text
                for m in re.finditer(re.escape(needle), text, flags):
                    hits.append(
                        {
                            "block_index": i,
                            "kind": "paragraph",
                            "start": m.start(),
                            "end": m.end(),
                            "snippet": text[max(0, m.start() - 20) : m.end() + 20],
                        }
                    )
            elif b.kind == "table" and b.table is not None:
                for ri, row in enumerate(b.table.rows):
                    for ci, cell in enumerate(row):
                        text = cell.text
                        for m in re.finditer(re.escape(needle), text, flags):
                            hits.append(
                                {
                                    "block_index": i,
                                    "kind": "table",
                                    "row": ri,
                                    "col": ci,
                                    "start": m.start(),
                                    "end": m.end(),
                                    "snippet": text[max(0, m.start() - 20) : m.end() + 20],
                                }
                            )
        return hits

    def replace_all(
        self,
        needle: str,
        replacement: str,
        *,
        case_sensitive: bool = True,
    ) -> int:
        """Replace all occurrences in paragraphs and table cells. Returns count.

        Uses per-run replacement so bold/italic/underline on other runs survive.
        """
        if not needle:
            return 0
        count = 0
        for b in self.blocks:
            if b.kind == "paragraph" and b.paragraph is not None:
                count += b.paragraph.replace_in_runs(
                    needle, replacement, case_sensitive=case_sensitive
                )
            elif b.kind == "table" and b.table is not None:
                for row in b.table.rows:
                    for cell in row:
                        for p in cell.paragraphs:
                            count += p.replace_in_runs(
                                needle, replacement, case_sensitive=case_sensitive
                            )
        return count

    def restore_snapshot(self, raw: str) -> None:
        """Reload document state *in place* from dumps() JSON (shared identity).

        Callers holding a reference to this Document see undo/redo results
        without rebinding to a new instance.
        """
        other = Document.loads(raw)
        self.title = other.title
        self.blocks = other.blocks
        self.styles = other.styles
        self.doc_id = other.doc_id
        self.schema_version = other.schema_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": KIND,
            "schema_version": self.schema_version,
            "product": "Pens",
            "maker": "Raskul",
            "title": self.title,
            "body": self.body,
            "blocks": [b.to_dict() for b in self.blocks],
            # v1 compat mirror
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "styles": dict(self.styles),
            "doc_id": self.doc_id,
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def save(self, path: str | Any) -> None:
        from pathlib import Path

        Path(path).write_text(self.dumps() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Any) -> "Document":
        from pathlib import Path

        return cls.loads(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def loads(cls, raw: str) -> "Document":
        data = json.loads(raw)
        blocks_raw = data.get("blocks")
        blocks: list[Block] = []
        if isinstance(blocks_raw, list) and blocks_raw:
            blocks = [Block.from_dict(b) for b in blocks_raw if isinstance(b, dict)]
        else:
            # Schema v1: paragraphs only
            for p in data.get("paragraphs") or []:
                if isinstance(p, dict):
                    blocks.append(Block.paragraph_block(Paragraph.from_dict(p)))
        if not blocks and data.get("body"):
            blocks = [Block.paragraph_block(Paragraph.from_text(str(data.get("body") or "")))]
        styles = dict(data.get("styles") or {})
        styles.setdefault("product", "Pens")
        styles.setdefault("maker", "Raskul")
        return cls(
            title=str(data.get("title") or "Untitled"),
            blocks=blocks,
            styles=styles,
            doc_id=str(data.get("doc_id") or uuid.uuid4().hex[:12]),
            schema_version=int(data.get("schema_version") or SCHEMA_VERSION),
        )


def create_document(title: str = "Untitled", body: str = "") -> Document:
    d = Document(title=title)
    if body:
        d.add_paragraph(body)
    return d


class DocumentEditor:
    """Edit API with undo/redo on the real Document model."""

    def __init__(self, document: Document, *, max_history: int = 64) -> None:
        self.document = document
        self.max_history = max(1, int(max_history))
        self._undo: list[str] = []
        self._redo: list[str] = []

    def _push(self) -> None:
        self._undo.append(self.document.dumps())
        if len(self._undo) > self.max_history:
            self._undo = self._undo[-self.max_history :]
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.document.dumps())
        raw = self._undo.pop()
        # Mutate the same Document instance so caller-held refs stay in sync.
        self.document.restore_snapshot(raw)
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.document.dumps())
        raw = self._redo.pop()
        self.document.restore_snapshot(raw)
        return True

    def add_paragraph(self, text: str, **kwargs: Any) -> Paragraph:
        self._push()
        return self.document.add_paragraph(text, **kwargs)

    def add_heading(self, text: str, level: int = 1) -> Paragraph:
        self._push()
        return self.document.add_heading(text, level=level)

    def add_bullet(self, text: str, **kwargs: Any) -> Paragraph:
        self._push()
        return self.document.add_bullet(text, **kwargs)

    def add_numbered(self, text: str, **kwargs: Any) -> Paragraph:
        self._push()
        return self.document.add_numbered(text, **kwargs)

    def add_table(self, nrows: int, ncols: int, fill: str = "") -> Table:
        self._push()
        return self.document.add_table(nrows, ncols, fill=fill)

    def delete_block(self, index: int) -> None:
        self._push()
        self.document.delete_block(index)

    def move_block(self, from_index: int, to_index: int) -> None:
        self._push()
        self.document.move_block(from_index, to_index)

    def replace_all(self, needle: str, replacement: str, **kwargs: Any) -> int:
        self._push()
        n = self.document.replace_all(needle, replacement, **kwargs)
        if n == 0 and self._undo:
            # no-op: drop empty undo frame
            self._undo.pop()
        return n

    def apply_format_to_paragraph(self, index: int, **kwargs: Any) -> None:
        """Apply char format to paragraph block at *index* among all blocks."""
        if not (0 <= index < len(self.document.blocks)):
            return
        b = self.document.blocks[index]
        if b.kind != "paragraph" or b.paragraph is None:
            return
        self._push()
        b.paragraph.apply_char_format(**kwargs)

    def set_paragraph_align(self, index: int, align: str) -> None:
        if not (0 <= index < len(self.document.blocks)):
            return
        b = self.document.blocks[index]
        if b.kind != "paragraph" or b.paragraph is None:
            return
        if align not in ALIGNMENTS:
            return
        self._push()
        b.paragraph.align = align
