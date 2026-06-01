"""
Perfboard / Prototyping Board Planner
A digital tool to plan perfboard layouts before soldering.
Run with: python perfboard_planner.py
Requires: Pillow  →  pip install Pillow
"""

import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, filedialog
import math
import string

try:
    from PIL import Image, ImageDraw, ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ─────────────────────────────────────────────
#  CONSTANTS  (non-spatial ones stay fixed)
# ─────────────────────────────────────────────
BG_GREEN    = "#2d5a27"   # PCB green
PAD_RING    = "#a8b8a0"   # silver pad ring
PAD_COPPER  = "#c8a040"   # copper centre
PAD_HOVER   = "#e0e060"   # hover highlight
WIRE_WIDTH  = 3

WIRE_COLORS = {
    "Red":    "#e53935",
    "Black":  "#212121",
    "Yellow": "#fdd835",
    "Green":  "#43a047",
    "Blue":   "#1e88e5",
    "White":  "#f5f5f5",
    "Orange": "#fb8c00",
    "Purple": "#8e24aa",
}

MODE_LABEL  = "label"
MODE_WIRE   = "wire"
MODE_DELETE = "delete"

# Fallback canvas dimensions used on first draw before the window is realised
_FALLBACK_W = 850
_FALLBACK_H = 650


# ─────────────────────────────────────────────
#  TOOLTIP  (lightweight, no extra lib)
# ─────────────────────────────────────────────
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text   = text
        self.tip    = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(self.tip, text=self.text, background="#ffffe0",
                       relief="solid", borderwidth=1, font=("Courier", 8))
        lbl.pack()

    def hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ─────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────
class PerfboardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Perfboard Planner")
        self.configure(bg="#1a1a2e")
        self.resizable(True, True)

        # ── state ──
        self.rows       = tk.IntVar(value=24)
        self.cols       = tk.IntVar(value=18)
        self.mode       = tk.StringVar(value=MODE_WIRE)
        self.wire_color = tk.StringVar(value="Red")
        self.custom_color = "#e53935"

        # data stores
        self.pin_labels: dict[tuple, str]   = {}   # (r,c) → label
        self.wires:      list[dict]          = []   # list of wire dicts
        self.pad_items:  dict[tuple, tuple] = {}   # (r,c) → (ring_id, hole_id, …)

        # wiring temp state
        self.wire_start: tuple | None = None
        self.ghost_line: int | None   = None

        # hover
        self.hovered: tuple | None     = None
        self.hover_text_id: int | None = None

        # ── dynamic spacing (calculated in generate_board) ──
        self._pad_spacing  = 36
        self._pad_radius   = 11
        self._hole_radius  = 4
        self._label_offset = 28
        self._label_font   = ("Courier", 9, "bold")
        self._pin_font     = ("Courier", 7, "bold")

        # debounce token for resize events
        self._resize_job: str | None = None

        self._build_ui()
        # Wait until the window is mapped so winfo_width/height are valid
        self.after(120, self.generate_board)

    # ─────────────────────────────────────────
    #  UI CONSTRUCTION
    # ─────────────────────────────────────────
    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Left panel ──
        panel = tk.Frame(self, bg="#16213e", width=220)
        panel.grid(row=0, column=0, sticky="ns", padx=(8, 0), pady=8)
        panel.grid_propagate(False)

        self._section(panel, "BOARD CONFIG")
        self._lbl_entry(panel, "Rows",    self.rows)
        self._lbl_entry(panel, "Columns", self.cols)
        btn_gen = ttk.Button(panel, text="⟳  Generate Board", command=self.generate_board)
        btn_gen.pack(fill="x", padx=10, pady=(4, 10))

        self._section(panel, "INTERACTION MODE")
        for txt, val, tip in [
            ("✏  Label Mode",  MODE_LABEL,  "Click pad → assign pin name"),
            ("〰  Wire Mode",   MODE_WIRE,   "Click two pads → draw wire"),
            ("✕  Delete Mode", MODE_DELETE, "Click wire/label → delete"),
        ]:
            rb = ttk.Radiobutton(panel, text=txt, variable=self.mode,
                                 value=val, command=self._on_mode_change)
            rb.pack(anchor="w", padx=14, pady=2)
            ToolTip(rb, tip)

        self._section(panel, "WIRE COLOR")
        color_frame = tk.Frame(panel, bg="#16213e")
        color_frame.pack(fill="x", padx=10)
        for i, (name, hex_) in enumerate(WIRE_COLORS.items()):
            rb = tk.Radiobutton(
                color_frame, text=name, variable=self.wire_color, value=name,
                bg="#16213e", fg="#e0e0e0", selectcolor="#0f3460",
                activebackground="#16213e", activeforeground="#e0e0e0",
                font=("Courier", 9), indicatoron=False,
                relief="flat", borderwidth=0,
                command=lambda h=hex_: self._set_color(h)
            )
            rb.grid(row=i // 2, column=i % 2, sticky="w", padx=4, pady=1)

        btn_custom = ttk.Button(panel, text="⬛  Custom Color…", command=self._pick_color)
        btn_custom.pack(fill="x", padx=10, pady=(6, 0))

        self.color_preview = tk.Label(panel, text="  Active color  ",
                                      bg=self.custom_color, fg="white",
                                      font=("Courier", 8), relief="flat")
        self.color_preview.pack(fill="x", padx=10, pady=(3, 10))

        self._section(panel, "ACTIONS")
        ttk.Button(panel, text="🗑  Clear Board",     command=self.clear_board).pack(fill="x", padx=10, pady=3)
        ttk.Button(panel, text="💾  Export as Image", command=self.export_image).pack(fill="x", padx=10, pady=3)

        # status bar at bottom of panel
        self.status = tk.Label(panel, text="Ready", bg="#0f3460", fg="#a0cfff",
                               font=("Courier", 8), anchor="w", wraplength=200)
        self.status.pack(side="bottom", fill="x", padx=4, pady=4)

        # ── Right canvas area (no scrollbars) ──
        canvas_frame = tk.Frame(self, bg="#1a1a2e")
        canvas_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame, bg=BG_GREEN,
                                cursor="crosshair", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # ── Bindings ──
        self.canvas.bind("<Button-1>",   self._on_canvas_click)
        self.canvas.bind("<Motion>",     self._on_mouse_move)
        self.canvas.bind("<Leave>",      self._on_mouse_leave)
        # Bind resize: debounced so rapid dragging doesn't spam redraws
        self.canvas.bind("<Configure>",  self._on_canvas_resize)

        # style
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton",  background="#0f3460", foreground="#e0e0ff",
                        font=("Courier", 9, "bold"), borderwidth=0, focuscolor="none")
        style.map("TButton", background=[("active", "#1a4a8a")])
        style.configure("TRadiobutton", background="#16213e", foreground="#e0e0e0",
                        font=("Courier", 9))
        style.configure("TEntry",  fieldbackground="#0f3460", foreground="#e0e0ff",
                        insertcolor="white", font=("Courier", 10))
        style.configure("TLabel",  background="#16213e", foreground="#e0e0e0")

    def _section(self, parent, title):
        tk.Label(parent, text=title, bg="#0f3460", fg="#a0cfff",
                 font=("Courier", 8, "bold"), anchor="w"
                 ).pack(fill="x", padx=6, pady=(10, 2))

    def _lbl_entry(self, parent, label, var):
        row = tk.Frame(parent, bg="#16213e")
        row.pack(fill="x", padx=10, pady=2)
        tk.Label(row, text=f"{label}:", bg="#16213e", fg="#c0c0d0",
                 font=("Courier", 9), width=8, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=var, width=6).pack(side="left")

    # ─────────────────────────────────────────
    #  COLOR HELPERS
    # ─────────────────────────────────────────
    def _set_color(self, hex_color):
        self.custom_color = hex_color
        self.color_preview.configure(bg=hex_color)

    def _pick_color(self):
        _, hex_ = colorchooser.askcolor(color=self.custom_color, title="Pick Wire Color")
        if hex_:
            self.wire_color.set("Custom")
            self._set_color(hex_)

    def _active_color(self):
        name = self.wire_color.get()
        return WIRE_COLORS.get(name, self.custom_color)

    # ─────────────────────────────────────────
    #  RESIZE HANDLER  (debounced)
    # ─────────────────────────────────────────
    def _on_canvas_resize(self, event):
        """Debounce rapid resize events; redraw once the user stops dragging."""
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._resize_redraw)

    def _resize_redraw(self):
        self._resize_job = None
        self.generate_board()

    # ─────────────────────────────────────────
    #  DYNAMIC SPACING ENGINE
    # ─────────────────────────────────────────
    def _compute_spacing(self, rows: int, cols: int):
        """
        Calculate the largest square pad pitch that fits the current canvas.
        Also derives all proportional sub-measurements and stores them as
        instance attributes so every drawing helper can read them.
        """
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        # Use fallback on first paint (window not yet fully realised)
        if cw < 10:
            cw = _FALLBACK_W
        if ch < 10:
            ch = _FALLBACK_H

        # The grid occupies (cols+1) pitches wide and (rows+1) pitches tall
        # (+1 accounts for the label gutter on each axis which is ~0.75 pitches,
        #  using a full pitch keeps the maths simple and gives a small margin)
        pitch_w = cw / (cols + 1.5)
        pitch_h = ch / (rows + 1.5)
        spacing = max(10, min(pitch_w, pitch_h))   # at least 10 px so it never collapses

        self._pad_spacing  = spacing
        # Scale pads proportionally: at default spacing=36 → radius=11, hole=4
        self._pad_radius   = max(3, spacing * 11 / 36)
        self._hole_radius  = max(1.5, spacing * 4 / 36)
        # Label gutter = one full pitch worth of space
        self._label_offset = spacing

        # Font sizes: scale with spacing, clamped so they stay legible
        lbl_size = max(6, min(12, int(spacing * 9 / 36)))
        pin_size = max(5, min(10, int(spacing * 7 / 36)))
        self._label_font = ("Courier", lbl_size, "bold")
        self._pin_font   = ("Courier", pin_size, "bold")

    # ─────────────────────────────────────────
    #  BOARD GENERATION
    # ─────────────────────────────────────────
    def generate_board(self):
        try:
            r = max(2, min(50, self.rows.get()))
            c = max(2, min(80, self.cols.get()))
        except tk.TclError:
            messagebox.showerror("Input Error", "Rows and Columns must be integers.")
            return

        self.rows.set(r)
        self.cols.set(c)

        # Compute dynamic spacing BEFORE drawing
        self._compute_spacing(r, c)

        # wipe canvas state
        self.canvas.delete("all")
        self.pad_items.clear()
        self.wire_start    = None
        self.ghost_line    = None
        self.hovered       = None
        self.hover_text_id = None

        # Prune data that no longer fits the new grid dimensions
        def valid(rc): return 0 <= rc[0] < r and 0 <= rc[1] < c
        self.pin_labels = {k: v for k, v in self.pin_labels.items() if valid(k)}
        self.wires      = [w for w in self.wires if valid(w["start"]) and valid(w["end"])]

        # Board pixel size (derived from dynamic spacing)
        board_w = self._label_offset + c * self._pad_spacing + self._pad_spacing * 0.5
        board_h = self._label_offset + r * self._pad_spacing + self._pad_spacing * 0.5

        # No scrollregion needed — just cover the canvas
        self.canvas.configure(scrollregion=(0, 0, board_w, board_h))

        self._draw_board_bg(r, c, board_w, board_h)
        self._draw_labels(r, c)
        self._draw_pads(r, c)
        self._redraw_wires()
        self._redraw_pin_labels()

        self._status(f"Board: {r} rows × {c} cols  |  {r*c} pads")

    def _draw_board_bg(self, r, c, w, h):
        # PCB border
        self.canvas.create_rectangle(2, 2, w - 2, h - 2,
                                     fill=BG_GREEN, outline="#1a3a18", width=3)
        # subtle grid lines
        for ri in range(r):
            for ci in range(c):
                x, y = self._pad_xy(ri, ci)
                self.canvas.create_line(x, self._label_offset, x, h - self._pad_spacing * 0.25,
                                        fill="#264f22", width=1, dash=(2, 6))
                self.canvas.create_line(self._label_offset, y, w - self._pad_spacing * 0.25, y,
                                        fill="#264f22", width=1, dash=(2, 6))

    def _draw_labels(self, r, c):
        # Column labels: A, B, C … AA, AB …
        for ci in range(c):
            x, _ = self._pad_xy(0, ci)
            lbl = self._col_label(ci)
            self.canvas.create_text(x, self._label_offset // 2,
                                    text=lbl, fill="#80c080",
                                    font=self._label_font, anchor="center")
        # Row labels: 1, 2, 3 …
        for ri in range(r):
            _, y = self._pad_xy(ri, 0)
            self.canvas.create_text(self._label_offset // 2, y,
                                    text=str(ri + 1), fill="#80c080",
                                    font=self._label_font, anchor="center")

    def _draw_pads(self, r, c):
        for ri in range(r):
            for ci in range(c):
                self._draw_single_pad(ri, ci)

    def _draw_single_pad(self, ri, ci, hovered=False):
        x, y = self._pad_xy(ri, ci)
        pr   = self._pad_radius
        hr   = self._hole_radius

        # remove old canvas items for this pad
        if (ri, ci) in self.pad_items:
            for item in self.pad_items[(ri, ci)]:
                self.canvas.delete(item)

        ring_color = PAD_HOVER if hovered else PAD_RING
        outer = self.canvas.create_oval(
            x - pr, y - pr, x + pr, y + pr,
            fill=ring_color, outline="#606060", width=1,
            tags=(f"pad_{ri}_{ci}", "pad")
        )
        inner = self.canvas.create_oval(
            x - hr, y - hr, x + hr, y + hr,
            fill=PAD_COPPER, outline="#a07020", width=1,
            tags=(f"pad_{ri}_{ci}", "pad")
        )

        # small pin label indicator
        label_id = None
        if (ri, ci) in self.pin_labels:
            lbl = self.pin_labels[(ri, ci)][:4]
            label_id = self.canvas.create_text(
                x, y + pr + max(4, pr * 0.5),
                text=lbl, fill="#ffff80",
                font=self._pin_font, anchor="center",
                tags=(f"pinlabel_{ri}_{ci}", "pinlabel")
            )

        items = (outer, inner) if label_id is None else (outer, inner, label_id)
        self.pad_items[(ri, ci)] = items

    # ─────────────────────────────────────────
    #  COORDINATE HELPERS
    # ─────────────────────────────────────────
    def _pad_xy(self, ri, ci):
        """Convert grid (row, col) → canvas pixel (x, y) using dynamic spacing."""
        half = self._pad_spacing / 2
        x = self._label_offset + ci * self._pad_spacing + half
        y = self._label_offset + ri * self._pad_spacing + half
        return x, y

    def _xy_to_pad(self, x, y):
        """Return (row, col) for a canvas coordinate, or None."""
        half = self._pad_spacing / 2
        ci = round((x - self._label_offset - half) / self._pad_spacing)
        ri = round((y - self._label_offset - half) / self._pad_spacing)
        r, c = self.rows.get(), self.cols.get()
        if 0 <= ri < r and 0 <= ci < c:
            px, py = self._pad_xy(ri, ci)
            if math.hypot(x - px, y - py) <= self._pad_radius + 4:
                return (ri, ci)
        return None

    @staticmethod
    def _col_label(ci):
        """0→A, 25→Z, 26→AA, 27→AB …"""
        result = ""
        ci += 1
        while ci:
            ci, rem = divmod(ci - 1, 26)
            result = string.ascii_uppercase[rem] + result
        return result

    # ─────────────────────────────────────────
    #  WIRE DRAWING
    # ─────────────────────────────────────────
    def _redraw_wires(self):
        self.canvas.delete("wire")
        for w in self.wires:
            self._draw_wire(w)

    def _draw_wire(self, w):
        x1, y1 = self._pad_xy(*w["start"])
        x2, y2 = self._pad_xy(*w["end"])
        mid_x = (x1 + x2) / 2
        pts = [x1, y1, mid_x, y1, mid_x, y2, x2, y2]
        line_id = self.canvas.create_line(
            *pts, fill=w["color"], width=WIRE_WIDTH,
            smooth=True, capstyle="round", joinstyle="round",
            tags=("wire", f"wire_{id(w)}")
        )
        w["canvas_id"] = line_id

    def _redraw_pin_labels(self):
        r, c = self.rows.get(), self.cols.get()
        for ri in range(r):
            for ci in range(c):
                self._draw_single_pad(ri, ci)

    # ─────────────────────────────────────────
    #  EVENT HANDLERS
    # ─────────────────────────────────────────
    def _on_mode_change(self):
        self.wire_start = None
        if self.ghost_line:
            self.canvas.delete(self.ghost_line)
            self.ghost_line = None
        self._status(f"Mode: {self.mode.get().capitalize()}")

    def _on_canvas_click(self, event):
        # No scrollregion offset needed — canvas coordinates == event coordinates
        cx, cy = float(event.x), float(event.y)
        mode = self.mode.get()

        if mode == MODE_LABEL:
            self._handle_label_click(cx, cy)
        elif mode == MODE_WIRE:
            self._handle_wire_click(cx, cy)
        elif mode == MODE_DELETE:
            self._handle_delete_click(cx, cy)

    def _handle_label_click(self, cx, cy):
        pad = self._xy_to_pad(cx, cy)
        if pad is None:
            return
        existing = self.pin_labels.get(pad, "")
        dialog = PinLabelDialog(self, existing)
        self.wait_window(dialog)
        if dialog.result is not None:
            if dialog.result.strip():
                self.pin_labels[pad] = dialog.result.strip()
            else:
                self.pin_labels.pop(pad, None)
            self._draw_single_pad(*pad, hovered=(pad == self.hovered))
            self._status(f"Label set: {self._pad_name(pad)} → '{dialog.result}'")

    def _handle_wire_click(self, cx, cy):
        pad = self._xy_to_pad(cx, cy)
        if pad is None:
            return

        if self.wire_start is None:
            self.wire_start = pad
            self._draw_single_pad(*pad, hovered=True)
            self._status(f"Wire from {self._pad_name(pad)} — click destination pad")
        else:
            if pad == self.wire_start:
                self.wire_start = None
                self._draw_single_pad(*pad)
                if self.ghost_line:
                    self.canvas.delete(self.ghost_line)
                    self.ghost_line = None
                return
            wire = {
                "start":     self.wire_start,
                "end":       pad,
                "color":     self._active_color(),
                "canvas_id": None,
            }
            self.wires.append(wire)
            self._draw_wire(wire)
            self._status(
                f"Wire: {self._pad_name(self.wire_start)} → {self._pad_name(pad)}"
                f"  [{wire['color']}]"
            )
            self._draw_single_pad(*self.wire_start)
            self.wire_start = None
            if self.ghost_line:
                self.canvas.delete(self.ghost_line)
                self.ghost_line = None

    def _handle_delete_click(self, cx, cy):
        # Check wire first
        items = self.canvas.find_closest(cx, cy, halo=5)
        for item in items:
            tags = self.canvas.gettags(item)
            if "wire" in tags:
                for w in list(self.wires):
                    if w.get("canvas_id") == item:
                        self.canvas.delete(item)
                        self.wires.remove(w)
                        self._status("Wire deleted")
                        return
        # Check pad label
        pad = self._xy_to_pad(cx, cy)
        if pad and pad in self.pin_labels:
            del self.pin_labels[pad]
            self._draw_single_pad(*pad)
            self._status(f"Label removed: {self._pad_name(pad)}")

    def _on_mouse_move(self, event):
        cx, cy = float(event.x), float(event.y)
        pad = self._xy_to_pad(cx, cy)

        # update hover highlight
        if pad != self.hovered:
            if self.hovered:
                self._draw_single_pad(*self.hovered, hovered=False)
            if pad:
                self._draw_single_pad(*pad, hovered=True)
            self.hovered = pad

        # ghost wire while in wire mode with start selected
        if self.mode.get() == MODE_WIRE and self.wire_start:
            if self.ghost_line:
                self.canvas.delete(self.ghost_line)
            sx, sy = self._pad_xy(*self.wire_start)
            mid_x = (sx + cx) / 2
            self.ghost_line = self.canvas.create_line(
                sx, sy, mid_x, sy, mid_x, cy, cx, cy,
                fill=self._active_color(), width=2,
                dash=(6, 4), smooth=True, tags="ghost"
            )

        # hover tooltip for pin label
        if self.hover_text_id:
            self.canvas.delete(self.hover_text_id)
            self.hover_text_id = None
        if pad and pad in self.pin_labels:
            x, y = self._pad_xy(*pad)
            self.hover_text_id = self.canvas.create_text(
                x, y - self._pad_radius - 8,
                text=self.pin_labels[pad],
                fill="#ffff00", font=("Courier", 9, "bold"),
                anchor="s",
                tags="hoverlabel"
            )

    def _on_mouse_leave(self, _):
        if self.hovered:
            self._draw_single_pad(*self.hovered, hovered=False)
            self.hovered = None
        if self.hover_text_id:
            self.canvas.delete(self.hover_text_id)
            self.hover_text_id = None

    # ─────────────────────────────────────────
    #  UTILITIES
    # ─────────────────────────────────────────
    def _pad_name(self, rc):
        return f"{self._col_label(rc[1])}{rc[0]+1}"

    def _status(self, msg):
        self.status.configure(text=msg)

    def clear_board(self):
        if not messagebox.askyesno("Clear Board", "Wipe all wires and labels?"):
            return
        self.pin_labels.clear()
        self.wires.clear()
        self.wire_start = None
        self.generate_board()
        self._status("Board cleared")

    def export_image(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("PostScript", "*.ps"), ("All files", "*.*")],
            title="Export Board Layout"
        )
        if not path:
            return

        if path.endswith(".ps"):
            self.canvas.postscript(file=path, colormode="color")
            self._status(f"Exported PostScript → {path}")
            return

        if PIL_AVAILABLE:
            ps_data = self.canvas.postscript(colormode="color")
            try:
                from PIL import EpsImagePlugin
                import io
                img = Image.open(io.BytesIO(ps_data.encode("latin-1")))
                img.save(path)
                self._status(f"Exported PNG → {path}")
                return
            except Exception:
                pass

            # Fallback: screenshot the canvas widget area
            x = self.canvas.winfo_rootx()
            y = self.canvas.winfo_rooty()
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            img.save(path)
            self._status(f"Exported screenshot → {path}")
        else:
            ps_path = path.replace(".png", ".ps")
            self.canvas.postscript(file=ps_path, colormode="color")
            messagebox.showinfo(
                "PIL not installed",
                f"Pillow is not installed; saved as PostScript:\n{ps_path}\n\n"
                "Install Pillow for PNG export:  pip install Pillow"
            )
            self._status(f"Saved PostScript → {ps_path}")


# ─────────────────────────────────────────────
#  PIN LABEL DIALOG
# ─────────────────────────────────────────────
class PinLabelDialog(tk.Toplevel):
    def __init__(self, parent, existing=""):
        super().__init__(parent)
        self.title("Assign Pin Label")
        self.configure(bg="#16213e")
        self.resizable(False, False)
        self.result = None

        tk.Label(self, text="Pin Name:", bg="#16213e", fg="#a0cfff",
                 font=("Courier", 10, "bold")).pack(padx=20, pady=(16, 4))

        self.entry = ttk.Entry(self, font=("Courier", 12), width=14)
        self.entry.pack(padx=20, pady=4)
        self.entry.insert(0, existing)
        self.entry.select_range(0, "end")
        self.entry.focus()

        btn_frame = tk.Frame(self, bg="#16213e")
        btn_frame.pack(pady=(6, 16))
        ttk.Button(btn_frame, text="OK",     command=self._ok).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Clear",  command=self._clear).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=6)

        self.entry.bind("<Return>", lambda _: self._ok())
        self.entry.bind("<Escape>", lambda _: self.destroy())

        self.transient(parent)
        self.grab_set()

        # center over parent
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + pw//2 - w//2}+{py + ph//2 - h//2}")

    def _ok(self):
        self.result = self.entry.get()
        self.destroy()

    def _clear(self):
        self.result = ""
        self.destroy()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = PerfboardApp()
    app.mainloop()