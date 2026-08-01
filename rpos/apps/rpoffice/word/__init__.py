"""Word-processor document model (from-scratch Office Word pillar)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Paragraph:
    text: str
    style: str = "Normal"  # Normal | Heading1 | Heading2 | Quote


@dataclass
class Document:
    title: str
    body: str = ""
    paragraphs: list[Paragraph] = field(default_factory=list)
    styles: dict[str, Any] = field(default_factory=lambda: {"theme": "default", "font": "system"})
    doc_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def add_paragraph(self, text: str, style: str = "Normal") -> Paragraph:
        p = Paragraph(text=text, style=style)
        self.paragraphs.append(p)
        # Keep body in sync for simple consumers
        self.body = "\n".join(x.text for x in self.paragraphs)
        return p

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "word",
            "title": self.title,
            "body": self.body,
            "paragraphs": [asdict(p) for p in self.paragraphs],
            "styles": dict(self.styles),
            "doc_id": self.doc_id,
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def loads(cls, raw: str) -> "Document":
        data = json.loads(raw)
        paras = [
            Paragraph(text=str(p.get("text") or ""), style=str(p.get("style") or "Normal"))
            for p in (data.get("paragraphs") or [])
        ]
        doc = cls(
            title=str(data.get("title") or "Untitled"),
            body=str(data.get("body") or ""),
            paragraphs=paras,
            styles=dict(data.get("styles") or {}),
            doc_id=str(data.get("doc_id") or uuid.uuid4().hex[:12]),
        )
        if not doc.paragraphs and doc.body:
            doc.paragraphs = [Paragraph(text=doc.body)]
        return doc


def create_document(title: str = "Untitled", body: str = "") -> Document:
    d = Document(title=title, body=body)
    if body:
        d.paragraphs = [Paragraph(text=body)]
    return d
