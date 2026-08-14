"""Windows product UI chrome: center placement, size floors, Evolve cards, switches.

Aligns the desktop shell with Evolve dark chrome (indigo ring, teal secondary)
and restoreprivacy.online panel-card language. Classic Tk cannot do CSS
``border-radius``; multi-frame rings approximate rounded boxes.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional

# --- Evolve-inspired neon / box tokens (indigo ring, teal secondary) ---
NEON_BORDER = "#6C63FF"  # Evolve accent
NEON_BORDER_DIM = "#00D9C0"  # Evolve secondary / connected
NEON_GLOW_SOFT = "#1A1F2B"  # Evolve fill
CARD_BG = "#151922"  # Evolve card
CHROME_DARKISH = "#0D0F14"  # Evolve canvas
SWITCH_TRACK_OFF = "#2A3142"
SWITCH_TRACK_ON = "#6C63FF"
SWITCH_KNOB = "#FFFFFF"
SWITCH_WIDTH = 52
SWITCH_HEIGHT = 28
SWITCH_PAD = 3
HERO_ORB_SIZE = 88

# Default / minimum geometries (width, height) — room for hero orb
SURFACE_SIZES: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    # surface: (default_wh, min_wh)
    "main": ((640, 760), (580, 640)),
    "licence": ((560, 540), (520, 480)),
    "keygen": ((560, 480), (520, 420)),
    "renew": ((560, 420), (520, 380)),
    "settings": ((680, 900), (600, 760)),
    "settings_first_run": ((700, 920), (620, 780)),
}


def parse_size(geometry: str) -> tuple[int, int]:
    """Parse ``WxH`` or ``WxH+X+Y`` into (width, height)."""
    raw = (geometry or "").strip().lower()
    if not raw:
        return 0, 0
    # Drop position if present
    body = raw.split("+", 1)[0].split("-", 1)[0]
    if "x" not in body:
        return 0, 0
    w_s, h_s = body.split("x", 1)
    try:
        return max(0, int(w_s)), max(0, int(h_s))
    except ValueError:
        return 0, 0


def center_geometry(
    width: int,
    height: int,
    screen_w: int,
    screen_h: int,
    *,
    min_margin: int = 8,
) -> str:
    """Return Tk geometry ``WxH+X+Y`` centered on a rectangular work area.

    Pure helper (no Tk) so unit tests can drive real placement math.
    """
    w = max(1, int(width))
    h = max(1, int(height))
    sw = max(w, int(screen_w))
    sh = max(h, int(screen_h))
    x = max(min_margin, (sw - w) // 2)
    y = max(min_margin, (sh - h) // 2)
    # Keep fully on-screen when possible
    if x + w > sw - min_margin:
        x = max(min_margin, sw - w - min_margin)
    if y + h > sh - min_margin:
        y = max(min_margin, sh - h - min_margin)
    return f"{w}x{h}+{x}+{y}"


def surface_default_size(surface: str) -> tuple[int, int]:
    """Default (width, height) for a named product surface."""
    key = (surface or "main").strip().lower()
    default, _mn = SURFACE_SIZES.get(key, SURFACE_SIZES["main"])
    return default


def surface_min_size(surface: str) -> tuple[int, int]:
    """Minimum (width, height) floor for a named product surface."""
    key = (surface or "main").strip().lower()
    _d, mn = SURFACE_SIZES.get(key, SURFACE_SIZES["main"])
    return mn


def surface_geometry_string(surface: str) -> str:
    """Default ``WxH`` string for *surface* (no position — apply center after)."""
    w, h = surface_default_size(surface)
    return f"{w}x{h}"


def apply_centered_window(
    win: Any,
    *,
    surface: str = "main",
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Size *win*, set minsize floors, center on the screen work area.

    Returns the geometry string applied. Uses ``winfo_screenwidth/height`` when
    available (primary monitor); pure math is in :func:`center_geometry`.
    """
    dw, dh = surface_default_size(surface)
    mw, mh = surface_min_size(surface)
    w = int(width if width is not None else dw)
    h = int(height if height is not None else dh)
    w = max(w, mw)
    h = max(h, mh)
    try:
        win.minsize(mw, mh)
    except Exception:
        pass
    try:
        win.update_idletasks()
        sw = int(win.winfo_screenwidth())
        sh = int(win.winfo_screenheight())
    except Exception:
        sw, sh = 1920, 1080
    geo = center_geometry(w, h, sw, sh)
    try:
        win.geometry(geo)
    except Exception:
        pass
    return geo


def make_neon_card(
    parent: Any,
    *,
    padx: int = 14,
    pady: int = 12,
    bg: str = CARD_BG,
    ring: str = NEON_BORDER,
    glow: str = NEON_GLOW_SOFT,
) -> tuple[Any, Any]:
    """Build an Evolve-like indigo-ringed card; return ``(inner_content, outer_frame)``.

    Outer accent ring + soft fill glow + panel body (rounded language via
    padding and multi-layer frames — classic Tk has no true border-radius).
    """
    outer = tk.Frame(parent, bg=ring, bd=0, highlightthickness=0)
    glow_fr = tk.Frame(outer, bg=glow, bd=0, highlightthickness=0)
    glow_fr.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
    body = tk.Frame(
        glow_fr,
        bg=bg,
        bd=0,
        highlightthickness=0,
        padx=padx,
        pady=pady,
    )
    body.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
    return body, outer


class HeroStatusOrb(tk.Frame):
    """Circular residual-status orb (disconnected / connecting / connected / error)."""

    def __init__(
        self,
        master: Any,
        *,
        size: int = HERO_ORB_SIZE,
        bg: str = CARD_BG,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, bg=bg, **kwargs)
        self._size = max(48, int(size))
        self._state = "disconnected"
        self.canvas = tk.Canvas(
            self,
            width=self._size,
            height=self._size,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self.set_state("disconnected")

    def set_state(
        self,
        state: str,
        *,
        tokens: dict[str, str] | None = None,
    ) -> None:
        """Redraw the orb for *state* using shipped :func:`hero_orb_palette`."""
        from client.ui_theme import hero_orb_palette

        self._state = (state or "disconnected").strip().lower() or "disconnected"
        pal = hero_orb_palette(self._state, tokens)
        self._draw(pal)

    def _draw(self, pal: dict[str, str]) -> None:
        c = self.canvas
        n = self._size
        c.delete("all")
        try:
            c.configure(bg=self["bg"])
        except Exception:
            pass
        # Soft outer glow
        c.create_oval(2, 2, n - 2, n - 2, fill=pal["glow"], outline="")
        # Ring
        inset = 8
        c.create_oval(
            inset,
            inset,
            n - inset,
            n - inset,
            fill=pal["core"],
            outline=pal["ring"],
            width=4,
        )
        # Inner core dot
        d = n // 5
        mid = n // 2
        c.create_oval(
            mid - d,
            mid - d,
            mid + d,
            mid + d,
            fill=pal["dot"],
            outline=pal["ring"],
            width=1,
        )


class SwitchToggle(tk.Frame):
    """Pill on/off switch bound to a ``BooleanVar`` (Settings toggles)."""

    def __init__(
        self,
        master: Any,
        variable: tk.BooleanVar,
        *,
        command: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, bg=kwargs.pop("bg", CARD_BG), **kwargs)
        self.variable = variable
        self._command = command
        self.canvas = tk.Canvas(
            self,
            width=SWITCH_WIDTH,
            height=SWITCH_HEIGHT,
            bg=self["bg"],
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)
        try:
            self.variable.trace_add("write", lambda *_a: self._redraw())
        except Exception:
            try:
                self.variable.trace("w", lambda *_a: self._redraw())
            except Exception:
                pass
        self._redraw()

    def _on_click(self, _event: Any = None) -> None:
        self.variable.set(not bool(self.variable.get()))
        if self._command is not None:
            try:
                self._command()
            except Exception:
                pass
        self._redraw()

    def _redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        on = bool(self.variable.get())
        track = SWITCH_TRACK_ON if on else SWITCH_TRACK_OFF
        # Rounded track (two circles + rectangle)
        r = SWITCH_HEIGHT // 2
        w, h = SWITCH_WIDTH, SWITCH_HEIGHT
        c.create_oval(0, 0, h, h, fill=track, outline=NEON_BORDER if on else track, width=1)
        c.create_oval(w - h, 0, w, h, fill=track, outline=NEON_BORDER if on else track, width=1)
        c.create_rectangle(r, 0, w - r, h, fill=track, outline=track)
        # Knob
        pad = SWITCH_PAD
        knob_d = h - 2 * pad
        if on:
            kx0 = w - pad - knob_d
        else:
            kx0 = pad
        c.create_oval(
            kx0,
            pad,
            kx0 + knob_d,
            pad + knob_d,
            fill=SWITCH_KNOB,
            outline=NEON_BORDER_DIM if on else "#94A3B8",
            width=1,
        )


def style_primary_button(btn: Any, *, neon: bool = True) -> None:
    """Apply flat primary button chrome with optional neon highlight ring."""
    try:
        btn.configure(
            relief=tk.FLAT,
            bd=0,
            highlightthickness=2 if neon else 0,
            highlightbackground=NEON_BORDER if neon else btn.cget("bg"),
            highlightcolor=NEON_BORDER if neon else btn.cget("bg"),
            cursor="hand2",
        )
    except Exception:
        pass


def wheel_delta_to_scroll_units(
    delta: int | float | None = None,
    *,
    num: int | None = None,
) -> int:
    """Map a wheel/trackpad event into ``canvas.yview_scroll`` units.

    Pure helper (no Tk). Conventions:
    - Windows / macOS ``MouseWheel``: *delta* > 0 → scroll content up (negative units)
    - X11 ``Button-4`` (num=4) → up; ``Button-5`` (num=5) → down
    Returns 0 when the event has no vertical scroll meaning.
    """
    if num == 4:
        return -3
    if num == 5:
        return 3
    try:
        d = int(delta) if delta is not None else 0
    except (TypeError, ValueError):
        return 0
    if d == 0:
        return 0
    # Windows reports multiples of 120; trackpads may send smaller steps
    if abs(d) >= 120:
        return int(-1 * (d / 120))
    # Fine-grained trackpad deltas
    return -1 if d > 0 else 1


def apply_canvas_wheel_scroll(canvas: Any, units: int) -> bool:
    """Scroll *canvas* by *units* via ``yview_scroll``. Returns True if applied."""
    if not units:
        return False
    try:
        canvas.yview_scroll(int(units), "units")
        return True
    except Exception:
        return False


def mousewheel_event_scroll_units(event: Any) -> int:
    """Extract scroll units from a Tk wheel event (real ``Event`` or mock)."""
    num = getattr(event, "num", None)
    try:
        num_i = int(num) if num is not None else None
    except (TypeError, ValueError):
        num_i = None
    delta = getattr(event, "delta", None)
    return wheel_delta_to_scroll_units(delta, num=num_i)


def bind_scrollable_canvas(
    canvas: Any,
    *roots: Any,
) -> Callable[[], None]:
    """Bind wheel / trackpad / Button-4/5 on *canvas* and descendant trees.

    Windows Tk often delivers ``<MouseWheel>`` only to the hovered child, not
    the parent Canvas — so we bind the canvas, each *root*, and walk children.
    Also uses ``bind_all`` while the pointer is over the canvas tree (Enter/Leave)
    so two-finger trackpad scroll works without focusing the scrollbar.

    Returns an **unbind** callable (safe to call multiple times / on destroy).
    """

    def _on_wheel(event: Any) -> str | None:
        units = mousewheel_event_scroll_units(event)
        if apply_canvas_wheel_scroll(canvas, units):
            return "break"
        return None

    bound: list[tuple[Any, str]] = []

    def _bind_one(widget: Any) -> None:
        if widget is None:
            return
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            try:
                widget.bind(seq, _on_wheel, add="+")
                bound.append((widget, seq))
            except Exception:
                pass

    def _bind_tree(widget: Any) -> None:
        _bind_one(widget)
        try:
            children = widget.winfo_children()
        except Exception:
            return
        for ch in children:
            _bind_tree(ch)

    _bind_one(canvas)
    for root in roots:
        if root is not None:
            _bind_tree(root)

    # While pointer is over the scroll surface, catch wheel globally (Windows)
    all_seqs = ("<MouseWheel>", "<Button-4>", "<Button-5>")
    all_bound = False

    def _bind_all(_event: Any = None) -> None:
        nonlocal all_bound
        if all_bound:
            return
        for seq in all_seqs:
            try:
                canvas.bind_all(seq, _on_wheel)
            except Exception:
                pass
        all_bound = True

    def _unbind_all(_event: Any = None) -> None:
        nonlocal all_bound
        if not all_bound:
            return
        for seq in all_seqs:
            try:
                canvas.unbind_all(seq)
            except Exception:
                pass
        all_bound = False

    try:
        canvas.bind("<Enter>", _bind_all, add="+")
        canvas.bind("<Leave>", _unbind_all, add="+")
        for root in roots:
            if root is None:
                continue
            try:
                root.bind("<Enter>", _bind_all, add="+")
                root.bind("<Leave>", _unbind_all, add="+")
            except Exception:
                pass
    except Exception:
        pass

    def unbind() -> None:
        _unbind_all()
        for widget, seq in bound:
            try:
                widget.unbind(seq)
            except Exception:
                pass
        bound.clear()

    return unbind
