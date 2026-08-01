"""Presentation-like deck (PowerPoint pillar) with multi-slide reorder."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Slide:
    title: str
    body: str = ""
    notes: str = ""
    slide_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class Presentation:
    title: str
    slides: list[Slide] = field(default_factory=list)
    deck_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def add_slide(self, title: str, body: str = "") -> Slide:
        s = Slide(title=title, body=body)
        self.slides.append(s)
        return s

    def reorder_slide(self, from_index: int, to_index: int) -> None:
        if not self.slides:
            raise IndexError("no slides")
        n = len(self.slides)
        if from_index < 0 or from_index >= n or to_index < 0 or to_index >= n:
            raise IndexError("slide index out of range")
        slide = self.slides.pop(from_index)
        self.slides.insert(to_index, slide)

    def move_slide_forward(self, index: int) -> None:
        if index < len(self.slides) - 1:
            self.reorder_slide(index, index + 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "deck",
            "title": self.title,
            "deck_id": self.deck_id,
            "slides": [asdict(s) for s in self.slides],
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def loads(cls, raw: str) -> "Presentation":
        data = json.loads(raw)
        slides = [
            Slide(
                title=str(s.get("title") or ""),
                body=str(s.get("body") or ""),
                notes=str(s.get("notes") or ""),
                slide_id=str(s.get("slide_id") or uuid.uuid4().hex[:8]),
            )
            for s in (data.get("slides") or [])
        ]
        return cls(
            title=str(data.get("title") or "Deck"),
            slides=slides,
            deck_id=str(data.get("deck_id") or uuid.uuid4().hex[:12]),
        )


def create_presentation(title: str = "Presentation") -> Presentation:
    p = Presentation(title=title)
    p.add_slide("Title", "Restore Privacy Office")
    return p
