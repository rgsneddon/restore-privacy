"""Slides / PowerPoint-class presentation model (handmade Raskul — not Microsoft PowerPoint).

Core: multi-slide deck, title/body/bullets/notes, add/delete/duplicate/reorder,
undo/redo, JSON round-trip.

Honesty: PowerPoint-class *core* outcomes — not PPTX/VBA/animations/masters/collaboration.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KIND = "slides_presentation"
SCHEMA_VERSION = 2


@dataclass
class Slide:
    """One presentation slide: title, body, bullet items, speaker notes."""

    title: str = ""
    body: str = ""
    bullets: list[str] = field(default_factory=list)
    notes: str = ""
    slide_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def set_title(self, title: str) -> None:
        self.title = str(title)

    def set_body(self, body: str) -> None:
        self.body = str(body)

    def set_notes(self, notes: str) -> None:
        self.notes = str(notes)

    def set_bullets(self, items: list[str]) -> None:
        self.bullets = [str(x) for x in items]

    def add_bullet(self, text: str) -> None:
        self.bullets.append(str(text))

    def clear_bullets(self) -> None:
        self.bullets = []

    def duplicate(self) -> "Slide":
        """Deep-ish copy with a new slide_id."""
        return Slide(
            title=self.title,
            body=self.body,
            bullets=list(self.bullets),
            notes=self.notes,
            slide_id=uuid.uuid4().hex[:8],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "bullets": list(self.bullets),
            "notes": self.notes,
            "slide_id": self.slide_id,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Slide":
        if not isinstance(data, dict):
            return cls()
        bullets_raw = data.get("bullets")
        bullets: list[str] = []
        if isinstance(bullets_raw, list):
            bullets = [str(x) for x in bullets_raw]
        return cls(
            title=str(data.get("title") or ""),
            body=str(data.get("body") or ""),
            bullets=bullets,
            notes=str(data.get("notes") or ""),
            slide_id=str(data.get("slide_id") or uuid.uuid4().hex[:8]),
        )


@dataclass
class Presentation:
    """Multi-slide presentation (PowerPoint-class core)."""

    title: str = "Presentation"
    slides: list[Slide] = field(default_factory=list)
    deck_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    schema_version: int = SCHEMA_VERSION
    active_index: int = 0

    def add_slide(
        self,
        title: str = "Slide",
        body: str = "",
        *,
        notes: str = "",
        bullets: list[str] | None = None,
        index: int | None = None,
    ) -> Slide:
        s = Slide(
            title=title,
            body=body,
            notes=notes,
            bullets=list(bullets or []),
        )
        if index is None:
            self.slides.append(s)
            self.active_index = len(self.slides) - 1
        else:
            if index < 0 or index > len(self.slides):
                raise IndexError("slide insert index out of range")
            self.slides.insert(index, s)
            self.active_index = index
        return s

    def delete_slide(self, index: int) -> Slide:
        if not self.slides:
            raise IndexError("no slides")
        if index < 0 or index >= len(self.slides):
            raise IndexError("slide index out of range")
        removed = self.slides.pop(index)
        if self.slides:
            self.active_index = min(self.active_index, len(self.slides) - 1)
            if self.active_index < 0:
                self.active_index = 0
        else:
            self.active_index = 0
        return removed

    def duplicate_slide(self, index: int) -> Slide:
        if index < 0 or index >= len(self.slides):
            raise IndexError("slide index out of range")
        copy = self.slides[index].duplicate()
        self.slides.insert(index + 1, copy)
        self.active_index = index + 1
        return copy

    def reorder_slide(self, from_index: int, to_index: int) -> None:
        if not self.slides:
            raise IndexError("no slides")
        n = len(self.slides)
        if from_index < 0 or from_index >= n or to_index < 0 or to_index >= n:
            raise IndexError("slide index out of range")
        slide = self.slides.pop(from_index)
        self.slides.insert(to_index, slide)
        self.active_index = to_index

    def move_slide_forward(self, index: int) -> None:
        if index < len(self.slides) - 1:
            self.reorder_slide(index, index + 1)

    def move_slide_backward(self, index: int) -> None:
        if index > 0:
            self.reorder_slide(index, index - 1)

    def get_slide(self, index: int) -> Slide:
        if index < 0 or index >= len(self.slides):
            raise IndexError("slide index out of range")
        return self.slides[index]

    def set_slide_title(self, index: int, title: str) -> None:
        self.get_slide(index).set_title(title)

    def set_slide_body(self, index: int, body: str) -> None:
        self.get_slide(index).set_body(body)

    def set_slide_notes(self, index: int, notes: str) -> None:
        self.get_slide(index).set_notes(notes)

    def set_slide_bullets(self, index: int, items: list[str]) -> None:
        self.get_slide(index).set_bullets(items)

    def slide_titles(self) -> list[str]:
        return [s.title for s in self.slides]

    @property
    def active(self) -> Slide:
        if not self.slides:
            self.add_slide("Title", "Restore Privacy Suite")
        self.active_index = max(0, min(self.active_index, len(self.slides) - 1))
        return self.slides[self.active_index]

    def select_index(self, index: int) -> Slide:
        if not (0 <= index < len(self.slides)):
            raise IndexError("slide index out of range")
        self.active_index = index
        return self.slides[index]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": KIND,
            "schema_version": self.schema_version,
            "product": "Slides",
            "maker": "Raskul",
            "title": self.title,
            "deck_id": self.deck_id,
            "active_index": self.active_index,
            "slides": [s.to_dict() for s in self.slides],
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.dumps() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Presentation":
        return cls.loads(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def loads(cls, raw: str) -> "Presentation":
        data = json.loads(raw)
        fixed: list[Slide] = []
        for s in data.get("slides") or []:
            fixed.append(Slide.from_dict(s if isinstance(s, dict) else {}))
        return cls(
            title=str(data.get("title") or "Presentation"),
            slides=fixed,
            deck_id=str(data.get("deck_id") or uuid.uuid4().hex[:12]),
            schema_version=int(data.get("schema_version") or SCHEMA_VERSION),
            active_index=int(data.get("active_index") or 0),
        )

    def restore_snapshot(self, raw: str) -> None:
        """Reload state in place (shared identity for undo)."""
        other = Presentation.loads(raw)
        self.title = other.title
        self.slides = other.slides
        self.deck_id = other.deck_id
        self.schema_version = other.schema_version
        self.active_index = other.active_index


def create_presentation(title: str = "Presentation") -> Presentation:
    p = Presentation(title=title)
    p.add_slide("Title", "Restore Privacy Suite")
    return p


class PresentationEditor:
    """Edit API with undo/redo on a shared Presentation instance."""

    def __init__(self, presentation: Presentation, *, max_history: int = 64) -> None:
        self.presentation = presentation
        self.max_history = max(1, int(max_history))
        self._undo: list[str] = []
        self._redo: list[str] = []

    def _push(self) -> None:
        self._undo.append(self.presentation.dumps())
        if len(self._undo) > self.max_history:
            self._undo = self._undo[-self.max_history :]
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.presentation.dumps())
        self.presentation.restore_snapshot(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.presentation.dumps())
        self.presentation.restore_snapshot(self._redo.pop())
        return True

    @property
    def deck(self) -> Presentation:
        return self.presentation

    def add_slide(
        self,
        title: str = "Slide",
        body: str = "",
        *,
        notes: str = "",
        bullets: list[str] | None = None,
        index: int | None = None,
    ) -> Slide:
        self._push()
        return self.presentation.add_slide(
            title, body, notes=notes, bullets=bullets, index=index
        )

    def delete_slide(self, index: int) -> Slide:
        self._push()
        return self.presentation.delete_slide(index)

    def duplicate_slide(self, index: int) -> Slide:
        self._push()
        return self.presentation.duplicate_slide(index)

    def reorder_slide(self, from_index: int, to_index: int) -> None:
        self._push()
        self.presentation.reorder_slide(from_index, to_index)

    def move_slide_forward(self, index: int) -> None:
        self._push()
        self.presentation.move_slide_forward(index)

    def move_slide_backward(self, index: int) -> None:
        self._push()
        self.presentation.move_slide_backward(index)

    def set_title(self, index: int, title: str) -> None:
        self._push()
        self.presentation.set_slide_title(index, title)

    def set_body(self, index: int, body: str) -> None:
        self._push()
        self.presentation.set_slide_body(index, body)

    def set_notes(self, index: int, notes: str) -> None:
        self._push()
        self.presentation.set_slide_notes(index, notes)

    def set_bullets(self, index: int, items: list[str]) -> None:
        self._push()
        self.presentation.set_slide_bullets(index, items)

    def select_index(self, index: int) -> Slide:
        return self.presentation.select_index(index)
