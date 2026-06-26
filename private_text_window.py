from __future__ import annotations

import ctypes
import json
from pathlib import Path
import struct
import sys
import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
from tkinter import ttk


APP_DIR = Path(__file__).resolve().parent
HISTORY_PATH = APP_DIR / "history.txt"
PAGES_PATH = APP_DIR / "pages.json"
SETTINGS_PATH = APP_DIR / "settings.json"
ICON_PATH = APP_DIR / "private_text_window.ico"
IS_WINDOWS = sys.platform.startswith("win")

DEFAULT_SETTINGS = {
    "opacity": 0.92,
    "font_size": 18,
    "visible_chars": 20,
    "borderless": False,
    "expanded": False,
    "topmost": True,
    "geometry": "420x180+120+120",
    "cursor": 0,
    "current_page_id": "page-1",
    "grip_shade": 17,
    "borderless_outline": False,
}

MIN_WINDOW_WIDTH = 96
MIN_TEXT_WIDTH = 56
RESIZE_GRIP_SIZE = 16


def clamp(value: int | float, low: int | float, high: int | float) -> int | float:
    return max(low, min(high, value))


def coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text_atomic(path: Path, content: str) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def make_page(page_id: str, name: str, text: str = "", cursor: int = 0) -> dict:
    safe_text = text if isinstance(text, str) else str(text)
    safe_cursor = int(clamp(cursor, 0, len(safe_text)))
    return {
        "id": page_id,
        "name": name.strip() or page_id,
        "text": safe_text,
        "cursor": safe_cursor,
    }


def load_pages(settings: dict) -> tuple[list[dict], str]:
    if PAGES_PATH.exists():
        try:
            saved = json.loads(PAGES_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        pages, current_page_id = normalize_pages_data(saved)
        if pages:
            return pages, current_page_id

    legacy_text = read_text(HISTORY_PATH)
    legacy_cursor = coerce_int(settings.get("cursor"), 0)
    page = make_page("page-1", "1", legacy_text, legacy_cursor)
    return [page], page["id"]


def normalize_pages_data(data: object) -> tuple[list[dict], str]:
    if not isinstance(data, dict):
        return [], "page-1"

    raw_pages = data.get("pages")
    if not isinstance(raw_pages, list):
        return [], "page-1"

    pages: list[dict] = []
    used_ids: set[str] = set()
    for index, raw_page in enumerate(raw_pages, start=1):
        if not isinstance(raw_page, dict):
            continue
        page_id = str(raw_page.get("id") or f"page-{index}")
        if page_id in used_ids:
            page_id = f"page-{index}"
        while page_id in used_ids:
            page_id = f"page-{index}-{len(used_ids) + 1}"
        used_ids.add(page_id)

        name = str(raw_page.get("name") or index)
        text = raw_page.get("text")
        if not isinstance(text, str):
            text = "" if text is None else str(text)
        cursor = coerce_int(raw_page.get("cursor"), 0)
        pages.append(make_page(page_id, name, text, cursor))

    if not pages:
        return [], "page-1"

    current_page_id = str(data.get("current_page_id") or pages[0]["id"])
    if not any(page["id"] == current_page_id for page in pages):
        current_page_id = pages[0]["id"]
    return pages, current_page_id


def ensure_icon_file() -> None:
    if ICON_PATH.exists():
        return

    width = 32
    height = 32
    pixels = bytearray()
    for y in range(height - 1, -1, -1):
        for x in range(width):
            r, g, b, a = 0, 0, 0, 0
            in_page = 5 <= x <= 26 and 4 <= y <= 27
            if in_page:
                r, g, b, a = 248, 248, 248, 255
                if x in (5, 26) or y in (4, 27):
                    r, g, b = 34, 34, 34
                if x == 11 and 10 <= y <= 21:
                    r, g, b = 0, 0, 0
                if 15 <= x <= 22 and y in (11, 16, 21):
                    r, g, b = 90, 90, 90
            pixels.extend((b, g, r, a))

    mask_stride = ((width + 31) // 32) * 4
    and_mask = bytes(mask_stride * height)
    dib_header = struct.pack(
        "<IIIHHIIIIII",
        40,
        width,
        height * 2,
        1,
        32,
        0,
        len(pixels),
        0,
        0,
        0,
        0,
    )
    image = dib_header + bytes(pixels) + and_mask
    icon_dir = struct.pack("<HHH", 0, 1, 1)
    icon_entry = struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32, len(image), 22)
    ICON_PATH.write_bytes(icon_dir + icon_entry + image)


def load_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if SETTINGS_PATH.exists():
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        if isinstance(saved, dict):
            settings.update(saved)
    settings["opacity"] = float(clamp(coerce_float(settings.get("opacity"), 0.92), 0.3, 1.0))
    settings["font_size"] = int(clamp(coerce_int(settings.get("font_size"), 18), 8, 72))
    settings["visible_chars"] = int(clamp(coerce_int(settings.get("visible_chars"), 20), 1, 5000))
    settings["cursor"] = int(max(0, coerce_int(settings.get("cursor"), 0)))
    settings["borderless"] = False
    settings["expanded"] = coerce_bool(settings.get("expanded"), False)
    settings["topmost"] = coerce_bool(settings.get("topmost"), True)
    settings["current_page_id"] = str(settings.get("current_page_id") or DEFAULT_SETTINGS["current_page_id"])
    settings["grip_shade"] = int(clamp(coerce_int(settings.get("grip_shade"), 17), 0, 100))
    settings["borderless_outline"] = coerce_bool(settings.get("borderless_outline"), False)
    if not isinstance(settings.get("geometry"), str):
        settings["geometry"] = DEFAULT_SETTINGS["geometry"]
    return settings


class PrivateTextWindow:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.pages, self.current_page_id = load_pages(self.settings)
        self.full_text = ""
        self.cursor = 0
        self.load_current_page_to_buffer()
        self.expanded = bool(self.settings["expanded"])
        self.display_start = 0
        self._rendering = False
        self._save_after_id: str | None = None
        self._settings_save_after_id: str | None = None
        self._status_after_id: str | None = None
        self._visible_chars_after_id: str | None = None
        self._drag_start: tuple[int, int, int, int] | None = None
        self._resize_start: tuple[int, int, int, int] | None = None
        self._restore_borderless_after_minimize = False
        self._refreshing_taskbar_icon = False
        self.quick_panel: tk.Toplevel | None = None
        self.quick_page_combo: ttk.Combobox | None = None

        self.root = tk.Tk()
        self.grip_shade_var = tk.IntVar(value=self.settings["grip_shade"])
        self.borderless_outline_var = tk.BooleanVar(value=self.settings["borderless_outline"])
        self.expanded_var = tk.BooleanVar(value=self.expanded)
        self.root.title("Private Text")
        self.set_window_icon()
        try:
            self.root.geometry(str(self.settings["geometry"]))
        except tk.TclError:
            self.settings["geometry"] = DEFAULT_SETTINGS["geometry"]
            self.root.geometry(DEFAULT_SETTINGS["geometry"])
        self.apply_window_minsize()
        self.root.configure(bg="white")
        self.root.attributes("-alpha", self.settings["opacity"])
        self.root.attributes("-topmost", self.settings["topmost"])
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.font = ("Microsoft YaHei UI", self.settings["font_size"])

        self.drag_strip = tk.Frame(self.root, height=8, bg="white", cursor="fleur")
        self.drag_strip.bind("<ButtonPress-1>", self.start_drag)
        self.drag_strip.bind("<B1-Motion>", self.drag_window)

        self.toolbar = tk.Frame(self.root, bg="#f7f7f7", padx=8, pady=6)
        self._build_toolbar()

        self.text = tk.Text(
            self.root,
            bg="white",
            fg="black",
            insertbackground="black",
            selectbackground="#d8e8ff",
            relief="flat",
            bd=0,
            highlightthickness=0,
            wrap="char",
            undo=True,
            padx=8,
            pady=6,
            font=self.font,
        )
        self.text.pack(fill="both", expand=True)
        self.text.bind("<KeyPress>", self.on_key_press)
        self.text.bind("<ButtonPress-1>", self.on_text_click)
        self.text.bind("<ButtonRelease-1>", self.sync_from_expanded_event)
        self.text.bind("<KeyRelease>", self.sync_from_expanded_event)
        self.text.bind("<<Modified>>", self.on_text_modified)
        self.text.bind("<Enter>", self.focus_editor)
        self.root.bind("<Enter>", self.focus_editor)
        self.root.bind("<Configure>", self.on_configure)
        self.root.bind("<Map>", self.on_map)

        self.resize_grip = tk.Frame(self.root, bg=self.grip_color(), cursor="size_nw_se")
        self.resize_grip.bind("<ButtonPress-1>", self.start_resize)
        self.resize_grip.bind("<B1-Motion>", self.resize_window)
        self.resize_grip.bind("<Double-Button-1>", self.show_quick_panel)
        self.resize_grip.bind("<Button-3>", self.show_quick_panel)
        self.outline_top = tk.Frame(self.root, bg="#b8b8b8")
        self.outline_bottom = tk.Frame(self.root, bg="#b8b8b8")
        self.outline_left = tk.Frame(self.root, bg="#b8b8b8")
        self.outline_right = tk.Frame(self.root, bg="#b8b8b8")

        self.status_label = tk.Label(
            self.root,
            text="",
            bg="white",
            fg="#1f883d",
            bd=0,
            padx=4,
            pady=2,
            font=("Microsoft YaHei UI", 9),
        )
        self.bind_shortcuts()
        self.root.bind_all("<Button-1>", self.close_quick_panel_on_outside, add="+")
        self.apply_chrome()
        self.render()
        self.root.after(50, self.focus_editor)
        self.root.after(120, lambda: self.force_taskbar_icon(refresh=True))

    def set_window_icon(self) -> None:
        try:
            ensure_icon_file()
            self.root.iconbitmap(str(ICON_PATH))
        except (OSError, tk.TclError):
            pass

    def min_window_height(self) -> int:
        font_size = int(clamp(coerce_int(self.settings.get("font_size"), 18), 8, 72))
        text_line_height = round(font_size * 1.55)
        text_padding = 18
        drag_strip_height = 8
        outline_allowance = 4
        return max(48, text_line_height + text_padding + drag_strip_height + outline_allowance)

    def min_window_width(self) -> int:
        return max(MIN_WINDOW_WIDTH, MIN_TEXT_WIDTH + RESIZE_GRIP_SIZE + 24)

    def apply_window_minsize(self) -> None:
        self.root.minsize(self.min_window_width(), self.min_window_height())

    def grip_color(self) -> str:
        shade = int(clamp(coerce_int(self.settings.get("grip_shade"), 17), 0, 100))
        channel = 250 - round(shade * 1.45)
        channel = int(clamp(channel, 105, 250))
        return f"#{channel:02x}{channel:02x}{channel:02x}"

    def apply_grip_shade(self) -> None:
        self.settings["grip_shade"] = int(clamp(coerce_int(self.settings.get("grip_shade"), 17), 0, 100))
        self.grip_shade_var.set(self.settings["grip_shade"])
        self.resize_grip.configure(bg=self.grip_color())
        self.schedule_settings_save()

    def apply_borderless_outline(self) -> None:
        for frame in (self.outline_top, self.outline_bottom, self.outline_left, self.outline_right):
            frame.place_forget()
        if not self.settings["borderless"] or not self.settings["borderless_outline"]:
            return

        thickness = 2
        self.outline_top.place(x=0, y=0, relwidth=1.0, height=thickness)
        self.outline_bottom.place(x=0, rely=1.0, relwidth=1.0, height=thickness, anchor="sw")
        self.outline_left.place(x=0, y=0, width=thickness, relheight=1.0)
        self.outline_right.place(relx=1.0, y=0, width=thickness, relheight=1.0, anchor="ne")
        for frame in (self.outline_top, self.outline_bottom, self.outline_left, self.outline_right):
            frame.lift()
        self.resize_grip.lift()

    def show_quick_panel(self, event: tk.Event) -> str:
        if not self.settings["borderless"]:
            return "break"
        self._resize_start = None
        if self.quick_panel is None or not self.quick_panel.winfo_exists():
            self.quick_panel = self.build_quick_panel()
        self.position_quick_panel(event.x_root, event.y_root)
        self.quick_panel.deiconify()
        self.quick_panel.lift()
        self.quick_panel.focus_force()
        return "break"

    def build_quick_panel(self) -> tk.Toplevel:
        panel = tk.Toplevel(self.root)
        panel.title("常用功能")
        panel.overrideredirect(True)
        panel.configure(bg="#f7f7f7")
        panel.attributes("-topmost", True)

        header = tk.Frame(panel, bg="#f7f7f7")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 6))
        tk.Label(header, text="常用功能", bg="#f7f7f7", fg="#222222", font=("Microsoft YaHei UI", 9, "bold")).pack(
            side="left"
        )
        ttk.Button(header, text="关闭", command=self.close_quick_panel).pack(side="right")

        ttk.Label(panel, text="当前页面", background="#f7f7f7").grid(row=1, column=0, padx=3, pady=(0, 6), sticky="w")
        self.quick_page_combo = ttk.Combobox(
            panel,
            textvariable=self.page_var,
            state="readonly",
            width=14,
        )
        self.quick_page_combo.grid(row=1, column=1, padx=3, pady=(0, 6), sticky="w")
        self.quick_page_combo.bind("<<ComboboxSelected>>", self.switch_page_from_combo)
        self.refresh_page_controls()

        actions = [
            ("复制当前页", self.copy_all),
            ("清空当前页", self.clear_all),
            ("新建页面", self.new_page),
            ("重命名", self.rename_current_page),
            ("删除页面", self.delete_current_page),
            ("上一页", self.previous_page),
            ("下一页", self.next_page),
            ("字号 +", lambda: self.adjust_font_size(1)),
            ("字号 -", lambda: self.adjust_font_size(-1)),
            ("显示字数 +", lambda: self.adjust_visible_chars(5)),
            ("显示字数 -", lambda: self.adjust_visible_chars(-5)),
            ("透明度 +", lambda: self.adjust_opacity(0.05)),
            ("透明度 -", lambda: self.adjust_opacity(-0.05)),
            ("有边框设置栏", self.toggle_borderless),
            ("快捷键", self.show_shortcut_summary),
            ("退出", self.close),
        ]
        for index, (label, command) in enumerate(actions):
            row = 2 + index // 2
            column = index % 2
            ttk.Button(panel, text=label, width=12, command=command).grid(row=row, column=column, padx=3, pady=3)

        shade_row = 2 + (len(actions) + 1) // 2
        ttk.Label(panel, text="显示字数", background="#f7f7f7").grid(
            row=shade_row,
            column=0,
            padx=3,
            pady=(8, 3),
            sticky="w",
        )
        ttk.Button(panel, text="-", width=3, command=lambda: self.adjust_visible_chars(-5)).grid(
            row=shade_row,
            column=1,
            padx=3,
            pady=(8, 3),
            sticky="w",
        )
        ttk.Button(panel, text="+", width=3, command=lambda: self.adjust_visible_chars(5)).grid(
            row=shade_row,
            column=1,
            padx=(42, 3),
            pady=(8, 3),
            sticky="w",
        )
        visible_spin = ttk.Spinbox(
            panel,
            from_=1,
            to=5000,
            textvariable=self.visible_chars_var,
            width=8,
            command=self.set_visible_chars_from_toolbar,
        )
        visible_spin.grid(row=shade_row + 1, column=0, columnspan=2, padx=3, pady=(0, 3), sticky="w")
        visible_spin.bind("<KeyRelease>", self.schedule_visible_chars_from_input)
        visible_spin.bind("<Return>", lambda _event: self.set_visible_chars_from_toolbar())
        visible_spin.bind("<FocusOut>", lambda _event: self.set_visible_chars_from_toolbar())

        shade_row += 2
        toggle_frame = tk.Frame(panel, bg="#f7f7f7")
        toggle_frame.grid(row=shade_row, column=0, columnspan=2, padx=3, pady=(8, 3), sticky="w")
        ttk.Checkbutton(
            toggle_frame,
            text="展开当前页",
            variable=self.expanded_var,
            command=self.set_expanded_from_panel,
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            toggle_frame,
            text="置顶窗口",
            variable=self.topmost_var,
            command=self.set_topmost_from_toolbar,
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            toggle_frame,
            text="增强边界线",
            variable=self.borderless_outline_var,
            command=self.set_borderless_outline_from_panel,
        ).pack(side="left")

        shade_row += 1
        ttk.Label(panel, text="方块深浅", background="#f7f7f7").grid(
            row=shade_row,
            column=0,
            padx=3,
            pady=(8, 3),
            sticky="w",
        )
        ttk.Button(panel, text="-", width=3, command=lambda: self.adjust_grip_shade(-5)).grid(
            row=shade_row,
            column=1,
            padx=3,
            pady=(8, 3),
            sticky="w",
        )
        ttk.Button(panel, text="+", width=3, command=lambda: self.adjust_grip_shade(5)).grid(
            row=shade_row,
            column=1,
            padx=(42, 3),
            pady=(8, 3),
            sticky="w",
        )
        ttk.Scale(
            panel,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.grip_shade_var,
            command=self.set_grip_shade_from_panel,
            length=130,
        ).grid(row=shade_row + 1, column=0, columnspan=2, padx=3, pady=(0, 3), sticky="ew")

        panel.grid_columnconfigure(0, minsize=132)
        panel.grid_columnconfigure(1, minsize=132)
        panel.bind("<Escape>", lambda _event: self.close_quick_panel())
        panel.withdraw()
        return panel

    def position_quick_panel(self, x_root: int, y_root: int) -> None:
        if self.quick_panel is None:
            return
        self.quick_panel.update_idletasks()
        width = self.quick_panel.winfo_reqwidth()
        height = self.quick_panel.winfo_reqheight()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        margin = 8
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        right_x = root_x + root_width + margin
        left_x = root_x - width - margin

        if right_x + width <= screen_width:
            x = right_x
        elif left_x >= 0:
            x = left_x
        else:
            x = int(clamp(x_root - width + 12, 0, max(0, screen_width - width)))

        preferred_y = root_y + max(0, (root_height - height) // 2)
        y = int(clamp(preferred_y, 0, max(0, screen_height - height)))
        self.quick_panel.geometry(f"+{x}+{y}")

    def close_quick_panel(self) -> None:
        if self.quick_panel is not None and self.quick_panel.winfo_exists():
            self.quick_panel.withdraw()

    def close_quick_panel_on_outside(self, event: tk.Event) -> None:
        if self.quick_panel is None or not self.quick_panel.winfo_exists() or not self.quick_panel.winfo_viewable():
            return
        if event.widget.winfo_toplevel() is self.quick_panel:
            return
        if event.widget is self.resize_grip:
            return
        self.close_quick_panel()

    def set_grip_shade_from_panel(self, _value: str | None = None) -> None:
        self.settings["grip_shade"] = int(clamp(self.grip_shade_var.get(), 0, 100))
        self.apply_grip_shade()

    def adjust_grip_shade(self, delta: int) -> str:
        self.settings["grip_shade"] = int(clamp(self.settings["grip_shade"] + delta, 0, 100))
        self.apply_grip_shade()
        return "break"

    def set_borderless_outline_from_panel(self) -> None:
        self.settings["borderless_outline"] = bool(self.borderless_outline_var.get())
        self.apply_borderless_outline()
        self.schedule_settings_save()

    def show_shortcut_summary(self) -> None:
        messagebox.showinfo(
            "快捷键汇总",
            "\n".join(
                [
                    "Ctrl+B：切换无边框 / 有边框设置栏",
                    "Ctrl+E：展开 / 收起当前页",
                    "Ctrl+N：新建页面",
                    "Ctrl+W：删除当前页面",
                    "Ctrl+R：重命名当前页面",
                    "Ctrl+Tab / Ctrl+Shift+Tab：下一页 / 上一页",
                    "Alt+1 到 Alt+9：切换第 1-9 页",
                    "隐藏模式 Ctrl+C：复制当前页全部内容",
                    "任意模式 Ctrl+Shift+C：复制当前页全部内容",
                    "Ctrl+Shift+Delete：清空当前页内容",
                    "Ctrl+M：最小化到任务栏",
                    "Ctrl+T：切换置顶",
                    "Ctrl+Up / Ctrl+Down：提高 / 降低透明度",
                    "Ctrl+= / Ctrl+-：增大 / 减小字体",
                    "隐藏模式 Ctrl+Right / Ctrl+Left：增加 / 减少显示字数",
                    "隐藏模式 Left / Right：移动输入光标",
                ]
            ),
            parent=self.root,
        )
        self.focus_editor()

    def _build_toolbar(self) -> None:
        self.borderless_var = tk.BooleanVar(value=self.settings["borderless"])
        self.topmost_var = tk.BooleanVar(value=self.settings["topmost"])
        self.opacity_var = tk.IntVar(value=round(self.settings["opacity"] * 100))
        self.font_size_var = tk.IntVar(value=self.settings["font_size"])
        self.visible_chars_var = tk.IntVar(value=self.settings["visible_chars"])
        self.page_var = tk.StringVar()
        self._page_options: list[str] = []

        ttk.Checkbutton(
            self.toolbar,
            text="无边框",
            variable=self.borderless_var,
            command=self.set_borderless_from_toolbar,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")
        ttk.Checkbutton(
            self.toolbar,
            text="置顶",
            variable=self.topmost_var,
            command=self.set_topmost_from_toolbar,
        ).grid(row=0, column=1, padx=(0, 12), sticky="w")

        ttk.Label(self.toolbar, text="透明度").grid(row=0, column=2, padx=(0, 4), sticky="e")
        ttk.Scale(
            self.toolbar,
            from_=30,
            to=100,
            orient="horizontal",
            variable=self.opacity_var,
            command=self.set_opacity_from_toolbar,
            length=110,
        ).grid(row=0, column=3, padx=(0, 12), sticky="ew")

        ttk.Label(self.toolbar, text="字号").grid(row=0, column=4, padx=(0, 4), sticky="e")
        font_spin = ttk.Spinbox(
            self.toolbar,
            from_=8,
            to=72,
            textvariable=self.font_size_var,
            width=4,
            command=self.set_font_size_from_toolbar,
        )
        font_spin.grid(row=0, column=5, padx=(0, 12), sticky="w")
        font_spin.bind("<Return>", lambda _event: self.set_font_size_from_toolbar())
        font_spin.bind("<FocusOut>", lambda _event: self.set_font_size_from_toolbar())

        ttk.Label(self.toolbar, text="显示字数").grid(row=0, column=6, padx=(0, 4), sticky="e")
        visible_spin = ttk.Spinbox(
            self.toolbar,
            from_=1,
            to=5000,
            textvariable=self.visible_chars_var,
            width=6,
            command=self.set_visible_chars_from_toolbar,
        )
        visible_spin.grid(row=0, column=7, padx=(0, 12), sticky="w")
        visible_spin.bind("<KeyRelease>", self.schedule_visible_chars_from_input)
        visible_spin.bind("<Return>", lambda _event: self.set_visible_chars_from_toolbar())
        visible_spin.bind("<FocusOut>", lambda _event: self.set_visible_chars_from_toolbar())

        ttk.Button(self.toolbar, text="展开全部", command=self.toggle_expanded).grid(
            row=0, column=8, padx=(0, 6), sticky="w"
        )
        ttk.Button(self.toolbar, text="复制全部", command=self.copy_all).grid(
            row=0, column=9, padx=(0, 6), sticky="w"
        )
        ttk.Button(self.toolbar, text="最小化", command=self.minimize_to_taskbar).grid(
            row=0, column=10, padx=(0, 6), sticky="w"
        )
        ttk.Button(self.toolbar, text="清空", command=self.clear_all).grid(row=0, column=11, sticky="w")
        ttk.Label(self.toolbar, text="页面").grid(row=1, column=0, padx=(0, 4), pady=(6, 0), sticky="e")
        self.page_combo = ttk.Combobox(
            self.toolbar,
            textvariable=self.page_var,
            state="readonly",
            width=18,
        )
        self.page_combo.grid(row=1, column=1, columnspan=2, padx=(0, 10), pady=(6, 0), sticky="ew")
        self.page_combo.bind("<<ComboboxSelected>>", self.switch_page_from_combo)
        ttk.Button(self.toolbar, text="新建", command=self.new_page).grid(
            row=1, column=3, padx=(0, 6), pady=(6, 0), sticky="w"
        )
        ttk.Button(self.toolbar, text="重命名", command=self.rename_current_page).grid(
            row=1, column=4, padx=(0, 6), pady=(6, 0), sticky="w"
        )
        ttk.Button(self.toolbar, text="删除", command=self.delete_current_page).grid(
            row=1, column=5, padx=(0, 6), pady=(6, 0), sticky="w"
        )
        self.toolbar.grid_columnconfigure(3, weight=1)
        self.refresh_page_controls()

    def bind_shortcuts(self) -> None:
        for sequence in ("<Control-b>", "<Control-B>"):
            self.root.bind_all(sequence, self.toggle_borderless)
        for sequence in ("<Control-e>", "<Control-E>"):
            self.root.bind_all(sequence, self.toggle_expanded)
        for sequence in ("<Control-Shift-c>", "<Control-Shift-C>"):
            self.root.bind_all(sequence, self.copy_all)
        for sequence in ("<Control-t>", "<Control-T>"):
            self.root.bind_all(sequence, self.toggle_topmost)
        for sequence in ("<Control-q>", "<Control-Q>"):
            self.root.bind_all(sequence, self.close_from_shortcut)
        for sequence in ("<Control-m>", "<Control-M>"):
            self.root.bind_all(sequence, self.minimize_to_taskbar)
        for sequence in ("<Control-n>", "<Control-N>"):
            self.root.bind_all(sequence, self.new_page)
        for sequence in ("<Control-w>", "<Control-W>"):
            self.root.bind_all(sequence, self.delete_current_page)
        for sequence in ("<Control-r>", "<Control-R>"):
            self.root.bind_all(sequence, self.rename_current_page)
        self.root.bind_all("<Control-Tab>", self.next_page)
        self.root.bind_all("<Control-Shift-Tab>", self.previous_page)
        for page_number in range(1, 10):
            self.root.bind_all(f"<Alt-Key-{page_number}>", self.switch_page_by_alt_number)
        self.root.bind_all("<Control-Up>", lambda _event: self.adjust_opacity(0.05))
        self.root.bind_all("<Control-Down>", lambda _event: self.adjust_opacity(-0.05))
        self.root.bind_all("<Control-plus>", lambda _event: self.adjust_font_size(1))
        self.root.bind_all("<Control-equal>", lambda _event: self.adjust_font_size(1))
        self.root.bind_all("<Control-KP_Add>", lambda _event: self.adjust_font_size(1))
        self.root.bind_all("<Control-minus>", lambda _event: self.adjust_font_size(-1))
        self.root.bind_all("<Control-KP_Subtract>", lambda _event: self.adjust_font_size(-1))
        self.root.bind_all("<Control-Shift-Delete>", self.clear_all)

    def focus_editor(self, _event: tk.Event | None = None) -> None:
        self.text.focus_set()

    def current_page(self) -> dict:
        for page in self.pages:
            if page["id"] == self.current_page_id:
                return page
        self.current_page_id = self.pages[0]["id"]
        return self.pages[0]

    def current_page_index(self) -> int:
        for index, page in enumerate(self.pages):
            if page["id"] == self.current_page_id:
                return index
        self.current_page_id = self.pages[0]["id"]
        return 0

    def load_current_page_to_buffer(self) -> None:
        page = self.current_page()
        self.full_text = page.get("text", "")
        self.cursor = int(clamp(coerce_int(page.get("cursor"), 0), 0, len(self.full_text)))
        page["cursor"] = self.cursor

    def persist_current_page_from_buffer(self) -> None:
        page = self.current_page()
        self.cursor = int(clamp(self.cursor, 0, len(self.full_text)))
        page["text"] = self.full_text
        page["cursor"] = self.cursor

    def sync_editor_before_page_change(self) -> None:
        if self.expanded:
            self.sync_from_expanded(schedule=False)
        elif self.text.edit_modified():
            self.sync_from_hidden_widget()
            self.text.edit_modified(False)
        self.persist_current_page_from_buffer()

    def page_display_name(self, index: int, page: dict) -> str:
        return f"{index + 1}. {page['name']}"

    def refresh_page_controls(self) -> None:
        self._page_options = [self.page_display_name(index, page) for index, page in enumerate(self.pages)]
        self.page_combo.configure(values=self._page_options)
        if self.quick_page_combo is not None and self.quick_page_combo.winfo_exists():
            self.quick_page_combo.configure(values=self._page_options)
        current_index = self.current_page_index()
        self.page_var.set(self._page_options[current_index])

    def switch_page_from_combo(self, _event: tk.Event | None = None) -> None:
        selected = self.page_var.get()
        if selected not in self._page_options:
            self.refresh_page_controls()
            return
        self.switch_to_page_index(self._page_options.index(selected))

    def switch_page_by_alt_number(self, event: tk.Event) -> str:
        if event.keysym in {str(number) for number in range(1, 10)}:
            self.switch_to_page_index(int(event.keysym) - 1)
        return "break"

    def switch_to_page_index(self, index: int) -> str:
        if index < 0 or index >= len(self.pages):
            return "break"
        if index == self.current_page_index():
            return "break"
        self.sync_editor_before_page_change()
        self.current_page_id = self.pages[index]["id"]
        self.load_current_page_to_buffer()
        self.settings["current_page_id"] = self.current_page_id
        self.refresh_page_controls()
        self.render()
        self.schedule_save()
        self.schedule_settings_save()
        self.show_status(f"已切换到页面：{self.current_page()['name']}")
        return "break"

    def next_page(self, _event: tk.Event | None = None) -> str:
        if not self.pages:
            return "break"
        return self.switch_to_page_index((self.current_page_index() + 1) % len(self.pages))

    def previous_page(self, _event: tk.Event | None = None) -> str:
        if not self.pages:
            return "break"
        return self.switch_to_page_index((self.current_page_index() - 1) % len(self.pages))

    def next_page_id(self) -> str:
        used_ids = {page["id"] for page in self.pages}
        number = len(self.pages) + 1
        while f"page-{number}" in used_ids:
            number += 1
        return f"page-{number}"

    def next_page_name(self) -> str:
        used_names = {page["name"] for page in self.pages}
        number = 1
        while str(number) in used_names:
            number += 1
        return str(number)

    def new_page(self, _event: tk.Event | None = None) -> str:
        self.sync_editor_before_page_change()
        page = make_page(self.next_page_id(), self.next_page_name())
        self.pages.append(page)
        self.current_page_id = page["id"]
        self.load_current_page_to_buffer()
        self.settings["current_page_id"] = self.current_page_id
        self.refresh_page_controls()
        self.render()
        self.schedule_save()
        self.schedule_settings_save()
        self.show_status(f"已新建页面：{page['name']}")
        return "break"

    def rename_current_page(self, _event: tk.Event | None = None) -> str:
        page = self.current_page()
        new_name = simpledialog.askstring("重命名页面", "请输入页面名称：", initialvalue=page["name"], parent=self.root)
        if new_name is None:
            return "break"
        new_name = new_name.strip()
        if not new_name:
            messagebox.showinfo("无法重命名", "页面名称不能为空。")
            return "break"
        page["name"] = new_name
        self.refresh_page_controls()
        self.schedule_save()
        self.show_status(f"已重命名页面：{new_name}")
        self.focus_editor()
        return "break"

    def delete_current_page(self, _event: tk.Event | None = None) -> str:
        if len(self.pages) <= 1:
            messagebox.showinfo("无法删除", "至少需要保留一个页面。")
            return "break"
        current_index = self.current_page_index()
        page = self.current_page()
        if not messagebox.askyesno("确认删除页面", f"确定要删除页面“{page['name']}”吗？此操作不可撤销。"):
            return "break"
        del self.pages[current_index]
        new_index = min(current_index, len(self.pages) - 1)
        self.current_page_id = self.pages[new_index]["id"]
        self.load_current_page_to_buffer()
        self.settings["current_page_id"] = self.current_page_id
        self.refresh_page_controls()
        self.render()
        self.schedule_save()
        self.schedule_settings_save()
        self.show_status("已删除页面")
        return "break"

    def apply_chrome(self) -> None:
        borderless = bool(self.settings["borderless"])
        self.root.overrideredirect(borderless)
        self.borderless_var.set(borderless)

        self.toolbar.pack_forget()
        self.drag_strip.pack_forget()
        self.resize_grip.place_forget()

        if borderless:
            self.drag_strip.pack(side="top", fill="x", before=self.text)
            self.resize_grip.place(relx=1.0, rely=1.0, anchor="se", width=16, height=16)
        else:
            self.close_quick_panel()
            self.toolbar.pack(side="top", fill="x", before=self.text)
        self.apply_borderless_outline()
        self.root.after(20, self.root.update_idletasks)
        self.root.after(60, lambda: self.force_taskbar_icon(refresh=borderless))

    def force_taskbar_icon(self, refresh: bool = False) -> None:
        if not IS_WINDOWS:
            return
        try:
            self.root.update_idletasks()
            user32 = ctypes.windll.user32
            hwnd = int(self.root.winfo_id())
            parent_hwnd = int(user32.GetParent(hwnd))
            target_hwnd = parent_hwnd or hwnd

            gwl_exstyle = -20
            ws_ex_toolwindow = 0x00000080
            ws_ex_appwindow = 0x00040000
            swp_nomove = 0x0002
            swp_nosize = 0x0001
            swp_nozorder = 0x0004
            swp_framechanged = 0x0020

            get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            style = int(get_long(target_hwnd, gwl_exstyle))
            style = (style | ws_ex_appwindow) & ~ws_ex_toolwindow
            set_long(target_hwnd, gwl_exstyle, style)
            user32.SetWindowPos(
                target_hwnd,
                0,
                0,
                0,
                0,
                0,
                swp_nomove | swp_nosize | swp_nozorder | swp_framechanged,
            )
            if refresh and self.root.state() != "iconic":
                self._refreshing_taskbar_icon = True
                self.root.withdraw()
                self.root.after(30, self.restore_after_taskbar_refresh)
        except (AttributeError, OSError, tk.TclError):
            self._refreshing_taskbar_icon = False
            return

    def restore_after_taskbar_refresh(self) -> None:
        self.root.deiconify()
        self.root.attributes("-topmost", self.settings["topmost"])
        self._refreshing_taskbar_icon = False
        self.focus_editor()

    def apply_visual_settings(self) -> None:
        self.settings["font_size"] = int(clamp(int(self.settings["font_size"]), 8, 72))
        self.settings["visible_chars"] = int(clamp(int(self.settings["visible_chars"]), 1, 5000))
        self.settings["opacity"] = float(clamp(float(self.settings["opacity"]), 0.3, 1.0))
        self.font = ("Microsoft YaHei UI", self.settings["font_size"])
        self.apply_window_minsize()
        self.text.configure(font=self.font)
        self.root.attributes("-alpha", self.settings["opacity"])
        self.root.attributes("-topmost", self.settings["topmost"])
        self.opacity_var.set(round(self.settings["opacity"] * 100))
        self.font_size_var.set(self.settings["font_size"])
        self.visible_chars_var.set(self.settings["visible_chars"])
        self.topmost_var.set(self.settings["topmost"])
        self.expanded_var.set(self.expanded)
        self.render()
        self.schedule_settings_save()

    def render(self) -> None:
        self._rendering = True
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

        if self.expanded:
            self.text.insert("1.0", self.full_text)
            self.text.mark_set("insert", self.index_from_offset(self.cursor))
            self.text.see("insert")
        else:
            visible_count = int(self.settings["visible_chars"])
            self.display_start = max(0, self.cursor - visible_count)
            visible_text = self.full_text[self.display_start : self.cursor]
            self.text.insert("1.0", visible_text)
            self.text.mark_set("insert", "end-1c")
            self.text.see("insert")
        self.text.edit_modified(False)
        self._rendering = False

    def on_key_press(self, event: tk.Event) -> str | None:
        shortcut_result = self.handle_shortcut_key(event)
        if shortcut_result == "break":
            return "break"

        if self.expanded:
            return None

        keysym = event.keysym
        if keysym == "Left":
            self.move_cursor(-1)
        elif keysym == "Right":
            self.move_cursor(1)
        elif keysym == "Home":
            self.set_cursor(0)
        elif keysym == "End":
            self.set_cursor(len(self.full_text))
        elif keysym == "BackSpace":
            self.delete_before_cursor()
        elif keysym == "Delete":
            self.delete_after_cursor()
        else:
            return None
        return "break"

    def handle_shortcut_key(self, event: tk.Event) -> str | None:
        ctrl = self.has_ctrl(event)
        shift = self.has_shift(event)
        keysym = event.keysym
        lower = keysym.lower()

        if ctrl and lower == "v" and not self.expanded:
            self.paste_at_cursor()
            return "break"
        if ctrl and lower == "c" and (shift or not self.expanded):
            self.copy_all()
            return "break"
        if ctrl and lower == "b":
            self.toggle_borderless()
            return "break"
        if ctrl and lower == "e":
            self.toggle_expanded()
            return "break"
        if ctrl and lower == "t":
            self.toggle_topmost()
            return "break"
        if ctrl and lower == "m":
            self.minimize_to_taskbar()
            return "break"
        if ctrl and lower == "q":
            self.close()
            return "break"
        if ctrl and lower == "n":
            self.new_page()
            return "break"
        if ctrl and lower == "w":
            self.delete_current_page()
            return "break"
        if ctrl and lower == "r":
            self.rename_current_page()
            return "break"
        if ctrl and keysym == "Tab":
            if shift:
                self.previous_page()
            else:
                self.next_page()
            return "break"
        if self.has_alt(event) and keysym in {str(number) for number in range(1, 10)}:
            self.switch_to_page_index(int(keysym) - 1)
            return "break"
        if ctrl and keysym == "Up":
            self.adjust_opacity(0.05)
            return "break"
        if ctrl and keysym == "Down":
            self.adjust_opacity(-0.05)
            return "break"
        if ctrl and keysym in ("plus", "equal", "KP_Add"):
            self.adjust_font_size(1)
            return "break"
        if ctrl and keysym in ("minus", "KP_Subtract"):
            self.adjust_font_size(-1)
            return "break"
        if ctrl and keysym == "Right" and not self.expanded:
            self.adjust_visible_chars(20 if shift else 5)
            return "break"
        if ctrl and keysym == "Left" and not self.expanded:
            self.adjust_visible_chars(-20 if shift else -5)
            return "break"
        if ctrl and shift and keysym == "Delete":
            self.clear_all()
            return "break"
        return None

    def has_ctrl(self, event: tk.Event) -> bool:
        return bool(int(event.state) & 0x0004)

    def has_shift(self, event: tk.Event) -> bool:
        return bool(int(event.state) & 0x0001)

    def has_alt(self, event: tk.Event) -> bool:
        return bool(int(event.state) & 0x0008)

    def has_ctrl_or_alt(self, event: tk.Event) -> bool:
        state = int(event.state)
        return bool(state & 0x0004) or bool(state & 0x0008)

    def insert_text(self, value: str) -> None:
        self.full_text = self.full_text[: self.cursor] + value + self.full_text[self.cursor :]
        self.cursor += len(value)
        self.persist_cursor()
        self.render()
        self.schedule_save()

    def paste_at_cursor(self) -> None:
        try:
            value = self.root.clipboard_get()
        except tk.TclError:
            return
        if value:
            self.insert_text(value)

    def move_cursor(self, delta: int) -> None:
        self.set_cursor(self.cursor + delta)

    def set_cursor(self, value: int) -> None:
        self.cursor = int(clamp(value, 0, len(self.full_text)))
        self.persist_cursor()
        self.render()

    def delete_before_cursor(self) -> None:
        if self.cursor <= 0:
            return
        self.full_text = self.full_text[: self.cursor - 1] + self.full_text[self.cursor :]
        self.cursor -= 1
        self.persist_cursor()
        self.render()
        self.schedule_save()

    def delete_after_cursor(self) -> None:
        if self.cursor >= len(self.full_text):
            return
        self.full_text = self.full_text[: self.cursor] + self.full_text[self.cursor + 1 :]
        self.persist_cursor()
        self.render()
        self.schedule_save()

    def on_text_click(self, event: tk.Event) -> str | None:
        if self.expanded:
            return None
        self.text.focus_set()
        clicked_index = self.text.index(f"@{event.x},{event.y}")
        offset = self.offset_from_index(clicked_index)
        self.set_cursor(self.display_start + offset)
        return "break"

    def on_text_modified(self, _event: tk.Event) -> None:
        if self._rendering:
            self.text.edit_modified(False)
            return
        if not self.text.edit_modified():
            return
        if self.expanded:
            self.sync_from_expanded()
        else:
            self.sync_from_hidden_widget()
        self.text.edit_modified(False)

    def sync_from_hidden_widget(self) -> None:
        old_segment = self.full_text[self.display_start : self.cursor]
        new_segment = self.text.get("1.0", "end-1c")
        old_insert_offset = self.cursor - self.display_start
        new_insert_offset = self.offset_from_index("insert")
        if old_segment == new_segment and old_insert_offset == new_insert_offset:
            return

        prefix = 0
        prefix_limit = min(len(old_segment), len(new_segment))
        while prefix < prefix_limit and old_segment[prefix] == new_segment[prefix]:
            prefix += 1

        suffix = 0
        old_remaining = len(old_segment) - prefix
        new_remaining = len(new_segment) - prefix
        while (
            suffix < old_remaining
            and suffix < new_remaining
            and old_segment[len(old_segment) - 1 - suffix] == new_segment[len(new_segment) - 1 - suffix]
        ):
            suffix += 1

        global_start = self.display_start + prefix
        global_end = self.display_start + len(old_segment) - suffix
        inserted = new_segment[prefix : len(new_segment) - suffix if suffix else len(new_segment)]
        self.full_text = self.full_text[:global_start] + inserted + self.full_text[global_end:]
        self.cursor = int(clamp(self.display_start + self.offset_from_index("insert"), 0, len(self.full_text)))
        self.persist_current_page_from_buffer()
        self.persist_cursor()
        self.schedule_save()
        self.render()

    def sync_from_expanded_event(self, _event: tk.Event) -> None:
        if self.expanded and not self._rendering:
            self.sync_from_expanded(schedule=True)

    def sync_from_expanded(self, schedule: bool = True) -> None:
        if not self.expanded:
            return
        self.full_text = self.text.get("1.0", "end-1c")
        self.cursor = int(clamp(self.offset_from_index("insert"), 0, len(self.full_text)))
        self.persist_current_page_from_buffer()
        self.persist_cursor()
        if schedule:
            self.schedule_save()

    def offset_from_index(self, index: str) -> int:
        count = self.text.count("1.0", index, "chars")
        if not count:
            return 0
        return int(count[0])

    def index_from_offset(self, offset: int) -> str:
        safe_offset = int(clamp(offset, 0, len(self.full_text)))
        return f"1.0 + {safe_offset} chars"

    def copy_all(self, _event: tk.Event | None = None) -> str:
        if self.expanded:
            self.sync_from_expanded(schedule=False)
        self.root.clipboard_clear()
        self.root.clipboard_append(self.full_text)
        self.root.update()
        self.show_status("已复制全部内容")
        return "break"

    def show_status(self, message: str, timeout_ms: int = 1500) -> None:
        if self._status_after_id is not None:
            self.root.after_cancel(self._status_after_id)
            self._status_after_id = None
        self.status_label.configure(text=message)
        self.status_label.lift()
        self.status_label.place(relx=0.0, rely=1.0, x=8, y=-8, anchor="sw")
        self._status_after_id = self.root.after(timeout_ms, self.clear_status)

    def clear_status(self) -> None:
        self._status_after_id = None
        self.status_label.place_forget()

    def clear_all(self, _event: tk.Event | None = None) -> str:
        if not messagebox.askyesno("确认清空", "确定要清空全部已输入内容吗？此操作不可撤销。"):
            return "break"
        self.full_text = ""
        self.cursor = 0
        self.persist_current_page_from_buffer()
        self.persist_cursor()
        self.render()
        self.schedule_save()
        return "break"

    def toggle_expanded(self, _event: tk.Event | None = None) -> str:
        self.set_expanded_state(not self.expanded)
        return "break"

    def set_expanded_from_panel(self) -> None:
        self.set_expanded_state(bool(self.expanded_var.get()))

    def set_expanded_state(self, expanded: bool) -> None:
        if expanded == self.expanded:
            self.expanded_var.set(self.expanded)
            return
        if self.expanded:
            self.sync_from_expanded(schedule=False)
        self.expanded = expanded
        self.settings["expanded"] = self.expanded
        self.expanded_var.set(self.expanded)
        self.render()
        self.schedule_save()
        self.schedule_settings_save()

    def toggle_borderless(self, _event: tk.Event | None = None) -> str:
        self.settings["borderless"] = not bool(self.settings["borderless"])
        self.apply_chrome()
        self.schedule_settings_save()
        self.focus_editor()
        return "break"

    def set_borderless_from_toolbar(self) -> None:
        self.settings["borderless"] = bool(self.borderless_var.get())
        self.apply_chrome()
        self.schedule_settings_save()

    def toggle_topmost(self, _event: tk.Event | None = None) -> str:
        self.settings["topmost"] = not bool(self.settings["topmost"])
        self.apply_visual_settings()
        return "break"

    def set_topmost_from_toolbar(self) -> None:
        self.settings["topmost"] = bool(self.topmost_var.get())
        self.apply_visual_settings()

    def set_opacity_from_toolbar(self, _value: str | None = None) -> None:
        self.settings["opacity"] = float(clamp(self.opacity_var.get() / 100, 0.3, 1.0))
        self.apply_visual_settings()

    def adjust_opacity(self, delta: float) -> str:
        self.settings["opacity"] = float(clamp(self.settings["opacity"] + delta, 0.3, 1.0))
        self.apply_visual_settings()
        return "break"

    def set_font_size_from_toolbar(self) -> None:
        self.settings["font_size"] = int(clamp(self.font_size_var.get(), 8, 72))
        self.apply_visual_settings()

    def adjust_font_size(self, delta: int) -> str:
        self.settings["font_size"] = int(clamp(self.settings["font_size"] + delta, 8, 72))
        self.apply_visual_settings()
        return "break"

    def set_visible_chars_from_toolbar(self, _value: str | None = None) -> None:
        try:
            value = int(self.visible_chars_var.get())
        except (tk.TclError, ValueError):
            return
        self.settings["visible_chars"] = int(clamp(value, 1, 5000))
        self.visible_chars_var.set(self.settings["visible_chars"])
        if self.expanded:
            self.set_expanded_state(False)
        self.apply_visual_settings()

    def schedule_visible_chars_from_input(self, _event: tk.Event | None = None) -> None:
        if self._visible_chars_after_id is not None:
            self.root.after_cancel(self._visible_chars_after_id)
        self._visible_chars_after_id = self.root.after(120, self.apply_visible_chars_from_input)

    def apply_visible_chars_from_input(self) -> None:
        self._visible_chars_after_id = None
        self.set_visible_chars_from_toolbar()

    def adjust_visible_chars(self, delta: int) -> str:
        self.settings["visible_chars"] = int(clamp(self.settings["visible_chars"] + delta, 1, 5000))
        self.visible_chars_var.set(self.settings["visible_chars"])
        if self.expanded:
            self.set_expanded_state(False)
        self.apply_visual_settings()
        return "break"

    def start_drag(self, event: tk.Event) -> None:
        self._drag_start = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

    def drag_window(self, event: tk.Event) -> None:
        if not self._drag_start:
            return
        start_x, start_y, window_x, window_y = self._drag_start
        new_x = window_x + event.x_root - start_x
        new_y = window_y + event.y_root - start_y
        self.root.geometry(f"+{new_x}+{new_y}")

    def start_resize(self, event: tk.Event) -> None:
        self._resize_start = (
            event.x_root,
            event.y_root,
            self.root.winfo_width(),
            self.root.winfo_height(),
        )

    def resize_window(self, event: tk.Event) -> None:
        if not self._resize_start:
            return
        start_x, start_y, width, height = self._resize_start
        new_width = max(self.min_window_width(), width + event.x_root - start_x)
        new_height = max(self.min_window_height(), height + event.y_root - start_y)
        self.root.geometry(f"{new_width}x{new_height}")

    def on_configure(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        if self._refreshing_taskbar_icon:
            return
        if self.root.state() == "iconic":
            return
        self.settings["geometry"] = self.root.geometry()
        self.schedule_settings_save()

    def on_map(self, event: tk.Event) -> None:
        if event.widget is not self.root or not self._restore_borderless_after_minimize:
            return
        self._restore_borderless_after_minimize = False
        self.root.after(80, self.restore_borderless_after_minimize)

    def restore_borderless_after_minimize(self) -> None:
        if self.root.state() == "iconic":
            self._restore_borderless_after_minimize = True
            return
        self.settings["borderless"] = True
        self.apply_chrome()
        self.focus_editor()

    def minimize_to_taskbar(self, _event: tk.Event | None = None) -> str:
        if self.expanded:
            self.sync_from_expanded(schedule=False)
            self.schedule_save()
        self._restore_borderless_after_minimize = bool(self.settings["borderless"])
        if self._restore_borderless_after_minimize:
            self.settings["borderless"] = False
            self.apply_chrome()
            self.root.update_idletasks()
        self.root.iconify()
        return "break"

    def persist_cursor(self) -> None:
        self.settings["cursor"] = int(clamp(self.cursor, 0, len(self.full_text)))
        self.settings["current_page_id"] = self.current_page_id
        self.persist_current_page_from_buffer()
        self.schedule_save()
        self.schedule_settings_save()

    def schedule_save(self) -> None:
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = self.root.after(250, self.save_now)

    def schedule_settings_save(self) -> None:
        if self._settings_save_after_id is not None:
            self.root.after_cancel(self._settings_save_after_id)
        self._settings_save_after_id = self.root.after(250, self.save_settings_now)

    def save_now(self) -> None:
        self._save_after_id = None
        self.persist_current_page_from_buffer()
        data = {
            "version": 1,
            "current_page_id": self.current_page_id,
            "pages": self.pages,
        }
        write_text_atomic(PAGES_PATH, json.dumps(data, ensure_ascii=False, indent=2))
        self.save_settings_now()

    def save_settings_now(self) -> None:
        self._settings_save_after_id = None
        self.settings["expanded"] = bool(self.expanded)
        self.settings["cursor"] = int(clamp(self.cursor, 0, len(self.full_text)))
        self.settings["current_page_id"] = self.current_page_id
        self.settings["borderless_outline"] = bool(self.settings["borderless_outline"])
        write_text_atomic(SETTINGS_PATH, json.dumps(self.settings, ensure_ascii=False, indent=2))

    def close(self) -> None:
        if self.expanded:
            self.sync_from_expanded(schedule=False)
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
            self._save_after_id = None
        if self._settings_save_after_id is not None:
            self.root.after_cancel(self._settings_save_after_id)
            self._settings_save_after_id = None
        if self._status_after_id is not None:
            self.root.after_cancel(self._status_after_id)
            self._status_after_id = None
        if self._visible_chars_after_id is not None:
            self.root.after_cancel(self._visible_chars_after_id)
            self._visible_chars_after_id = None
        if self.quick_panel is not None and self.quick_panel.winfo_exists():
            self.quick_panel.destroy()
            self.quick_panel = None
        self.save_now()
        self.root.destroy()

    def close_from_shortcut(self, _event: tk.Event | None = None) -> str:
        self.close()
        return "break"

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    PrivateTextWindow().run()
