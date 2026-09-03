import calendar
import datetime
import json
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

import fill_report

PRESENCE_OPTIONS = ["없음", "있음"]

# ---- 정원유니어스 디자인 팔레트 (목업 색상 샘플링) ----
GREEN = "#0D4A32"          # 기본 녹색: 번호 뱃지, 강조 버튼, 섹션 제목
GREEN_DARK = "#0A3A28"     # 눌림 상태
GREEN_TINT = "#5E8168"     # 보조 문구 (The Best Medical Partner)
CARD_BORDER = "#C6D3CC"    # 섹션 카드 테두리
FIELD_BORDER = "#B7C4BB"   # 입력칸 테두리
PAGE_BG = "#FFFFFF"
INK = "#1F2A24"
UI_FONT = "맑은 고딕"

# 글자 선명도: 폰트 크기를 '픽셀'(음수)로 지정하면 pt→px 반올림에서 오는
# 흐릿함이 사라지고 정수 픽셀 격자에 딱 맞게 렌더링된다.
FS_SMALL = -12
FS_BODY = -14
FS_BADGE = -14
FS_SECTION = -17
FS_HEAD_TITLE = -28
FS_HEAD_TAG = -14
FS_FOOT_TAG = -12
FS_FOOT_PHONE = -19

A4_RATIO = 297 / 210  # 세로 A4 비율 (1 : 1.414)


def _enable_windows_dpi_awareness():
    """Run the process DPI-aware so Windows renders the window 1:1 instead of
    bitmap-stretching it, which is a common cause of sluggish/blurry text and
    laggy IME (한글) input on scaled displays."""
    if sys.platform != "win32":
        return
    import ctypes

    for attempt in (
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(1),
        lambda: ctypes.windll.user32.SetProcessDPIAware(),
    ):
        try:
            attempt()
            return
        except Exception:
            continue

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".ultrasound_report.json")


def _load_last_dir():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            d = json.load(f).get("last_dir")
        return d if d and os.path.isdir(d) else None
    except Exception:
        return None


def _save_last_dir(directory):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"last_dir": directory}, f, ensure_ascii=False)
    except Exception:
        pass


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, bg=PAGE_BG)
        vscrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        hscrollbar = ttk.Scrollbar(self, orient="horizontal", command=canvas.xview)
        self.body = ttk.Frame(canvas)

        # Coalesce scrollregion recalculation: a raw <Configure> handler runs a
        # full canvas.bbox("all") sweep on every child geometry/focus change,
        # which stutters keyboard (esp. IME) input on a form this size.
        self._sr_job = None

        def apply_scrollregion():
            self._sr_job = None
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except tk.TclError:
                pass

        def queue_scrollregion(_=None):
            if self._sr_job is None:
                self._sr_job = self.after(100, apply_scrollregion)

        self.body.bind("<Configure>", queue_scrollregion)
        canvas_window = canvas.create_window((0, 0), window=self.body, anchor="nw")

        def on_canvas_configure(e):
            # Never shrink the body below what its content actually needs -
            # doing so makes the canvas clip (cut off) labels/entries instead of wrapping them.
            width = max(e.width, self.body.winfo_reqwidth())
            canvas.itemconfig(canvas_window, width=width)

        canvas.bind("<Configure>", on_canvas_configure)
        canvas.configure(yscrollcommand=vscrollbar.set, xscrollcommand=hscrollbar.set)

        vscrollbar.pack(side="right", fill="y")
        hscrollbar.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)


class _InstitutionValue:
    """Resolves 검사기관명 lazily (at save time) instead of running a
    per-keystroke trace, so typing into the 직접입력 field stays responsive."""

    def __init__(self, choice_var, custom_var, preset, custom_label):
        self._choice = choice_var
        self._custom = custom_var
        self._preset = preset
        self._custom_label = custom_label

    def get(self):
        if self._choice.get() == self._custom_label:
            return self._custom.get().strip()
        return self._choice.get()


class DatePicker(tk.Toplevel):
    """A small month calendar popup. Clicking a day writes YYYY-MM-DD into
    the given StringVar and closes."""

    def __init__(self, master, target_var):
        super().__init__(master)
        self.target_var = target_var
        self.title("날짜 선택")
        self.resizable(False, False)
        self.transient(master)

        try:
            base = datetime.date.fromisoformat((target_var.get() or "").strip())
        except ValueError:
            base = datetime.date.today()
        self.year, self.month = base.year, base.month

        self._header = ttk.Frame(self)
        self._header.pack(fill="x", padx=6, pady=(6, 2))
        ttk.Button(self._header, text="◀", width=3,
                   command=lambda: self._shift(-1)).pack(side="left")
        self._title = ttk.Label(self._header, anchor="center")
        self._title.pack(side="left", expand=True)
        ttk.Button(self._header, text="▶", width=3,
                   command=lambda: self._shift(1)).pack(side="left")

        self._grid = ttk.Frame(self)
        self._grid.pack(padx=6, pady=(0, 6))

        ttk.Button(self, text="오늘", command=self._pick_today).pack(
            fill="x", padx=6, pady=(0, 6))

        self._draw()
        self.bind("<Escape>", lambda _: self.destroy())
        self.grab_set()
        self.focus_set()

    def _shift(self, months):
        m = self.month - 1 + months
        self.year += m // 12
        self.month = m % 12 + 1
        self._draw()

    def _pick_today(self):
        self._choose(datetime.date.today())

    def _choose(self, date_obj):
        self.target_var.set(date_obj.isoformat())
        self.destroy()

    def _draw(self):
        for child in self._grid.winfo_children():
            child.destroy()
        self._title.config(text=f"{self.year}년 {self.month}월")

        for i, name in enumerate(["월", "화", "수", "목", "금", "토", "일"]):
            ttk.Label(self._grid, text=name, width=4, anchor="center").grid(
                row=0, column=i, padx=1, pady=1)

        for r, week in enumerate(calendar.Calendar().monthdayscalendar(
                self.year, self.month), start=1):
            for c, day in enumerate(week):
                if day == 0:
                    continue
                ttk.Button(
                    self._grid, text=str(day), width=4,
                    command=lambda d=day: self._choose(
                        datetime.date(self.year, self.month, d)),
                ).grid(row=r, column=c, padx=1, pady=1)


class ReportApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("경직장 전립선·정낭 초음파 판독지 작성기")
        try:
            self.iconbitmap(fill_report.resource_path("정원로고.ico"))
        except tk.TclError:
            pass
        try:
            self.tk.call("tk", "useinputmethods", "1")
        except tk.TclError:
            pass

        self.vars = {}
        self._reset_hooks = []  # called by "새로 작성" to clear every field
        self._imgs = {}         # PhotoImage 참조 유지 (GC 방지)
        self.last_dir = _load_last_dir()

        self._setup_fonts()
        self._apply_a4_geometry()
        self._setup_style()
        self._build_header()
        self._build_footer()

        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=8, pady=8)
        root = scroll.body

        self._build_patient_section(root)
        self._build_exam_section(root)
        self._build_required_findings_section(root)
        self._build_optional_findings_section(root)
        self._build_conclusion_section(root)
        self._build_actions(root)

    # ---------- 디자인 (정원유니어스 목업 리스킨) ----------

    def _setup_fonts(self):
        """Tk 기본 named 폰트를 맑은 고딕 + 픽셀 크기로 교체해 글자를 또렷하게."""
        try:
            self.tk.call("tk", "scaling", 1.0)  # pt 변환 배율 고정 (예측 가능)
        except tk.TclError:
            pass
        self.font_body = tkfont.Font(family=UI_FONT, size=FS_BODY)
        self.font_small = tkfont.Font(family=UI_FONT, size=FS_SMALL)
        self.font_section = tkfont.Font(family=UI_FONT, size=FS_SECTION, weight="bold")
        self.font_badge = tkfont.Font(family=UI_FONT, size=FS_BADGE, weight="bold")
        self.font_head_title = tkfont.Font(family=UI_FONT, size=FS_HEAD_TITLE, weight="bold")
        self.font_head_tag = tkfont.Font(family=UI_FONT, size=FS_HEAD_TAG)
        self.font_foot_tag = tkfont.Font(family=UI_FONT, size=FS_FOOT_TAG)
        self.font_foot_phone = tkfont.Font(family=UI_FONT, size=FS_FOOT_PHONE, weight="bold")
        self.font_btn = tkfont.Font(family=UI_FONT, size=FS_BODY, weight="bold")

        # 위젯이 상속하는 기본 폰트들도 동일하게 맞춘다.
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(family=UI_FONT, size=FS_BODY)
            except tk.TclError:
                pass

    def _apply_a4_geometry(self):
        """세로 A4 비율로, 화면 작업영역에 맞춰 창을 띄운다."""
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        # 작업표시줄·제목표시줄 여유를 두고 화면 높이의 88%까지만
        h = min(1160, int(sh * 0.88))
        w = int(h / A4_RATIO)
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 24)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(640, 820)

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")  # 색상 커스터마이즈가 먹는 테마
        except tk.TclError:
            pass
        self.configure(bg=PAGE_BG)
        base = self.font_body

        style.configure(".", font=base, background=PAGE_BG, foreground=INK)
        for name in ("TFrame", "TLabel", "TLabelframe", "TLabelframe.Label",
                     "TRadiobutton", "TCheckbutton"):
            style.configure(name, background=PAGE_BG, foreground=INK)
        style.map("TLabel", foreground=[("disabled", "#8A968F")])
        style.map("TRadiobutton",
                  background=[("active", PAGE_BG)],
                  foreground=[("disabled", "#8A968F")],
                  indicatorcolor=[("selected", GREEN), ("pressed", GREEN)])

        for name in ("TEntry", "TCombobox"):
            style.configure(name, fieldbackground="white", background="white",
                            foreground=INK, bordercolor=FIELD_BORDER,
                            lightcolor=FIELD_BORDER, darkcolor=FIELD_BORDER,
                            borderwidth=1, padding=3)
        style.configure("TCombobox", arrowcolor=GREEN)
        style.map("TCombobox",
                  fieldbackground=[("readonly", "white")],
                  foreground=[("readonly", INK)])
        style.configure("TButton", foreground=INK, font=base, padding=(8, 4))

        style.configure("SectionTitle.TLabel", foreground=GREEN, font=self.font_section)

        style.configure("Accent.TButton", background=GREEN, foreground="white",
                        bordercolor=GREEN, focuscolor=GREEN, borderwidth=0,
                        padding=(18, 7), font=self.font_btn)
        style.map("Accent.TButton",
                  background=[("active", GREEN_DARK), ("pressed", GREEN_DARK)],
                  foreground=[("disabled", "#D8E2DC")])
        style.configure("Outline.TButton", background="white", foreground=GREEN,
                        bordercolor=GREEN, lightcolor="white", darkcolor="white",
                        borderwidth=1, padding=(15, 6), font=base)
        style.map("Outline.TButton",
                  background=[("active", "#EAF1ED"), ("pressed", "#DEE9E3")],
                  bordercolor=[("active", GREEN), ("pressed", GREEN)])

    def _img(self, name, max_h=None):
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return None
        path = fill_report.resource_path(os.path.join("assets", name))
        try:
            img = Image.open(path)
        except Exception:
            return None
        if max_h and img.height > max_h:
            img.thumbnail((10000, max_h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self._imgs[name] = photo  # 참조 유지
        return photo

    def _build_header(self):
        hdr = tk.Frame(self, bg="white")
        hdr.pack(fill="x", side="top")

        logo = self._img("logo.png", max_h=58)
        if logo is not None:
            tk.Label(hdr, image=logo, bg="white").pack(side="left", padx=(18, 12), pady=12)

        txt = tk.Frame(hdr, bg="white")
        txt.pack(side="left", pady=12)
        tk.Label(txt, text="정원유니어스(주)", bg="white", fg=GREEN,
                 font=self.font_head_title).pack(anchor="w")
        tk.Label(txt, text="The Best Medical Partner", bg="white", fg=GREEN_TINT,
                 font=self.font_head_tag).pack(anchor="w")

        swoosh = self._img("swoosh.png", max_h=80)
        if swoosh is not None:
            tk.Label(hdr, image=swoosh, bg="white").pack(side="right")

        tk.Frame(self, bg=GREEN, height=2).pack(fill="x", side="top")

    def _build_footer(self):
        tk.Frame(self, bg=CARD_BORDER, height=1).pack(fill="x", side="bottom")
        bar = tk.Frame(self, bg="white")
        bar.pack(fill="x", side="bottom")
        box = tk.Frame(bar, bg="white")
        box.pack(side="right", padx=18, pady=6)
        tk.Label(box, text="The Best Medical Partner", bg="white", fg=GREEN_TINT,
                 font=self.font_foot_tag).pack(anchor="e")
        tk.Label(box, text="☎ 010-6498-0999", bg="white", fg=GREEN,
                 font=self.font_foot_phone).pack(anchor="e")

    def _section(self, root, num, title):
        """목업의 카드형 섹션: 녹색 번호 뱃지 + 녹색 제목 + 테두리 카드."""
        border = tk.Frame(root, bg=CARD_BORDER)
        border.pack(fill="x", padx=4, pady=7)
        card = tk.Frame(border, bg=PAGE_BG)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        head = tk.Frame(card, bg=PAGE_BG)
        head.pack(fill="x", anchor="w", padx=12, pady=(9, 4))
        tk.Label(head, text=f" {num} ", bg=GREEN, fg="white",
                 font=self.font_badge).pack(side="left")
        tk.Label(head, text=title, bg=PAGE_BG, fg=GREEN,
                 font=self.font_section).pack(side="left", padx=(8, 0))

        body = tk.Frame(card, bg=PAGE_BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        return body

    # ---------- helpers ----------
    #
    # Every field row below is gridded directly onto its section's LabelFrame
    # (column 0 = label, column 1+ = controls) instead of using a fixed
    # ttk.Label(width=...). ttk.Label's width is a hard pixel cap, not a
    # minimum, so a fixed width silently clipped longer Korean labels.
    # grid() sizes each column to its widest cell instead, so nothing is cut.

    @staticmethod
    def _next_row(parent):
        return parent.grid_size()[1]

    def _entry_row(self, parent, label, key, width=20):
        r = self._next_row(parent)
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(4, 8), pady=2)
        var = tk.StringVar()
        ttk.Entry(parent, textvariable=var, width=width).grid(row=r, column=1, sticky="w", pady=2)
        self.vars[key] = var
        self._reset_hooks.append(lambda v=var: v.set(""))
        return r

    def _date_row(self, parent, label, key):
        r = self._next_row(parent)
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(4, 8), pady=2)
        var = tk.StringVar()
        entry = ttk.Entry(parent, textvariable=var, width=14)
        entry.grid(row=r, column=1, sticky="w", pady=2)

        def open_calendar(_=None):
            DatePicker(self, var)

        # 검사일/판독일 칸을 클릭하면 달력 팝업으로 날짜를 고른다.
        entry.bind("<Button-1>", open_calendar)

        def fill_today():
            var.set(datetime.date.today().isoformat())

        ttk.Button(parent, text="오늘", width=5, command=fill_today).grid(row=r, column=2, sticky="w", padx=4)
        self.vars[key] = var
        self._reset_hooks.append(lambda v=var: v.set(""))
        return r

    def _radio_row(self, parent, label, key, options, detail_key=None):
        r = self._next_row(parent)
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(4, 8), pady=2)
        options_frame = ttk.Frame(parent)
        options_frame.grid(row=r, column=1, sticky="w", pady=2)
        var = tk.StringVar(value="")
        for opt in options:
            ttk.Radiobutton(options_frame, text=opt, value=opt, variable=var).pack(side="left", padx=2)
        self.vars[key] = var
        self._reset_hooks.append(lambda v=var: v.set(""))
        if detail_key:
            dvar = tk.StringVar()
            ttk.Entry(parent, textvariable=dvar, width=28).grid(row=r, column=2, sticky="w", padx=6)
            self.vars[detail_key] = dvar
            self._reset_hooks.append(lambda v=dvar: v.set(""))
        return r

    # ---------- sections ----------

    def _build_patient_section(self, root):
        box = self._section(root, "1", "환자정보")
        self._entry_row(box, "등록번호", "reg_no")
        self._entry_row(box, "성명", "patient_name")
        self._entry_row(box, "생년월일 또는 나이", "birth_or_age")
        self._radio_row(box, "성별", "sex", ["남", "여"])

    def _build_exam_section(self, root):
        box = self._section(root, "2", "검사정보")
        r = self._next_row(box)
        ttk.Label(box, text="검사명").grid(row=r, column=0, sticky="w", padx=(4, 8), pady=2)
        options_frame = ttk.Frame(box)
        options_frame.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
        var = tk.StringVar(value=fill_report.EXAM_TYPE_OPTIONS[0])
        # A4 세로 폭에 맞게 2열로 줄바꿈
        for i, opt in enumerate(fill_report.EXAM_TYPE_OPTIONS):
            ttk.Radiobutton(options_frame, text=opt, value=opt, variable=var).grid(
                row=i // 2, column=i % 2, sticky="w", padx=(0, 14), pady=1)
        self.vars["exam_type"] = var
        self._reset_hooks.append(lambda v=var: v.set(fill_report.EXAM_TYPE_OPTIONS[0]))

        self._date_row(box, "검사일", "exam_date")
        self._entry_row(box, "검사자", "examiner_name", width=14)
        self._entry_row(box, "검사자 면허번호", "examiner_license", width=14)
        self._date_row(box, "판독일", "read_date")
        self._entry_row(box, "판독자", "reader_name", width=14)
        self._entry_row(box, "판독자 면허번호", "reader_license", width=14)
        self._institution_row(box, "검사기관명", "institution")

    def _institution_row(self, parent, label, key):
        # Almost always 라임비뇨기과의원, so default to it and expose a
        # "직접입력" dropdown choice that unlocks a free-text entry.
        PRESET = "라임비뇨기과의원"
        CUSTOM = "직접입력"

        r = self._next_row(parent)
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(4, 8), pady=2)

        choice = tk.StringVar(value=PRESET)
        custom = tk.StringVar()
        self.vars[key] = _InstitutionValue(choice, custom, PRESET, CUSTOM)

        frame = ttk.Frame(parent)
        frame.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
        combo = ttk.Combobox(
            frame, textvariable=choice, state="readonly",
            values=[PRESET, CUSTOM], width=18,
        )
        combo.pack(side="left")
        entry = ttk.Entry(frame, textvariable=custom, width=24, state="disabled")
        entry.pack(side="left", padx=6)

        # Only react when the dropdown actually changes - no per-keystroke work.
        def on_choice(_=None):
            if choice.get() == CUSTOM:
                entry.configure(state="normal")
                entry.focus_set()
            else:
                entry.configure(state="disabled")

        combo.bind("<<ComboboxSelected>>", on_choice)

        def reset():
            choice.set(PRESET)
            custom.set("")
            entry.configure(state="disabled")

        self._reset_hooks.append(reset)
        return r

    def _build_required_findings_section(self, root):
        box = self._section(root, "3-(1)", "검사 소견 (필수)")
        self._entry_row(box, "① 전립선 전체 용적 (cc)", "vol_total", width=10)
        self._entry_row(box, "② 전립선 이행대 용적 (cc)", "vol_transition", width=10)
        self._radio_row(box, "③ 전립선내 국소 병변", "focal_lesion", PRESENCE_OPTIONS, "focal_lesion_detail")
        self._radio_row(box, "④ 과혈관성 병변(도플러)", "hyper_vascular", PRESENCE_OPTIONS, "hyper_vascular_detail")
        self._radio_row(box, "⑤ 정낭 이상소견", "seminal_vesicle", PRESENCE_OPTIONS, "seminal_vesicle_detail")

    def _build_optional_findings_section(self, root):
        box = self._section(root, "3-(2)", "검사 소견 (선택적 기술)")

        r = self._next_row(box)
        ttk.Label(box, text="① 전립선의 모양").grid(row=r, column=0, sticky="w", padx=(4, 8), pady=2)
        options_frame = ttk.Frame(box)
        options_frame.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
        var = tk.StringVar(value="")
        for opt in ["삼각형", "타원형", "원형", "세로타원형"]:
            ttk.Radiobutton(options_frame, text=opt, value=opt, variable=var).pack(side="left", padx=2)
        self.vars["shape"] = var
        self._reset_hooks.append(lambda v=var: v.set(""))

        labels = {
            "border": "② 전립선의 경계",
            "symmetry": "③ 전립선의 대칭",
            "calcification": "④ 석회화",
            "median_cyst": "⑤ 중앙낭종",
            "acute_inflammation": "⑥ 급성 염증 또는 농양",
            "bladder_protrusion": "⑦ 방광내 돌출",
            "bladder_stone_tumor": "⑧ 방광내 결석 또는 종양",
        }
        for _, field, options in fill_report.TABLE3_FIELDS:
            self._radio_row(box, labels[field], field, options, f"{field}_detail")

        r = self._next_row(box)
        ttk.Label(box, text="이상 소견 또는 기타소견에 대한 기술").grid(
            row=r, column=0, columnspan=3, sticky="w", padx=4, pady=(6, 0)
        )
        r = self._next_row(box)
        text = tk.Text(box, height=4, wrap="word", bg="white", relief="solid",
                       bd=1, highlightthickness=1, highlightbackground=FIELD_BORDER,
                       highlightcolor=GREEN, font=self.font_body, padx=4, pady=3)
        text.grid(row=r, column=0, columnspan=3, sticky="ew", padx=4, pady=2)
        box.columnconfigure(2, weight=1)
        self.vars["other_findings"] = text
        self._reset_hooks.append(lambda t=text: t.delete("1.0", "end"))

    def _build_conclusion_section(self, root):
        box = self._section(root, "4", "결론 (필수)")
        text = tk.Text(box, height=5, wrap="word", bg="white", relief="solid",
                       bd=1, highlightthickness=1, highlightbackground=FIELD_BORDER,
                       highlightcolor=GREEN, font=self.font_body, padx=4, pady=3)
        text.pack(fill="x", padx=4, pady=2)
        self.vars["conclusion"] = text
        self._reset_hooks.append(lambda t=text: t.delete("1.0", "end"))

    def _build_actions(self, root):
        row = tk.Frame(root, bg=PAGE_BG)
        row.pack(fill="x", padx=4, pady=(14, 6))
        ttk.Button(row, text="새로 작성", style="Accent.TButton",
                   command=self.on_new).pack(side="left", padx=(0, 16))
        ttk.Button(row, text="Word로 저장", style="Outline.TButton",
                   command=self.on_save_word).pack(side="left", padx=4)
        ttk.Button(row, text="한글로 저장", style="Outline.TButton",
                   command=self.on_save_hwp).pack(side="left", padx=4)
        ttk.Button(row, text="JPG로 저장", style="Outline.TButton",
                   command=self.on_save_jpg).pack(side="left", padx=4)

    def on_new(self):
        if not messagebox.askyesno("새로 작성", "입력한 내용을 모두 지우고 새로 작성하시겠습니까?"):
            return
        for hook in self._reset_hooks:
            try:
                hook()
            except tk.TclError:
                pass

    # ---------- data collection ----------

    def _collect_data(self):
        data = {}
        for key, var in self.vars.items():
            if isinstance(var, tk.Text):
                data[key] = var.get("1.0", "end").rstrip("\n")
            else:
                data[key] = var.get()
        return data

    def _confirm_required(self, data):
        missing = []
        if not data.get("patient_name"):
            missing.append("성명")
        if not data.get("conclusion"):
            missing.append("결론")
        if not missing:
            return True
        return messagebox.askyesno(
            "필수 항목 누락",
            "다음 필수 항목이 비어 있습니다: " + ", ".join(missing) + "\n계속 진행하시겠습니까?",
        )

    def _default_name(self, data):
        parts = [
            (data.get("reg_no") or "").strip(),
            (data.get("patient_name") or "").strip(),
        ]
        parts = [p for p in parts if p]
        return "_".join(parts) if parts else "판독지"

    def _ask_save_path(self, title, ext, filetypes, data):
        path = filedialog.asksaveasfilename(
            title=title,
            defaultextension=ext,
            filetypes=filetypes,
            initialfile=self._default_name(data),
            initialdir=self.last_dir or None,
        )
        if path:
            # Remember where the user saved so the next dialog starts there.
            self.last_dir = os.path.dirname(path)
            _save_last_dir(self.last_dir)
        return path

    def on_save_word(self):
        data = self._collect_data()
        if not self._confirm_required(data):
            return

        docx_path = self._ask_save_path(
            "Word로 저장", ".docx", [("Word 문서", "*.docx")], data
        )
        if not docx_path:
            return

        try:
            fill_report.generate_docx(data, docx_path)
        except Exception as e:
            messagebox.showerror("오류", f"Word 문서 생성 중 오류가 발생했습니다:\n{e}")
            return

        if messagebox.askyesno("저장 완료", "Word 파일이 저장되었습니다.\n폴더를 여시겠습니까?"):
            os.startfile(os.path.dirname(docx_path))

    def on_save_hwp(self):
        data = self._collect_data()
        if not self._confirm_required(data):
            return

        hwp_path = self._ask_save_path(
            "한글로 저장", ".hwp", [("한글 문서", "*.hwp")], data
        )
        if not hwp_path:
            return

        self.config(cursor="watch")
        self.update()
        try:
            fill_report.generate_hwp(data, hwp_path)
        except Exception as e:
            messagebox.showerror(
                "오류",
                f"한글 문서 생성 중 오류가 발생했습니다:\n{e}\n"
                "(한글(HancomOffice)이 설치되어 있어야 변환이 가능합니다.)",
            )
            return
        finally:
            self.config(cursor="")

        if messagebox.askyesno("저장 완료", "한글 파일이 저장되었습니다.\n폴더를 여시겠습니까?"):
            os.startfile(os.path.dirname(hwp_path))

    def on_save_jpg(self):
        data = self._collect_data()
        if not self._confirm_required(data):
            return

        jpg_path = self._ask_save_path(
            "JPG로 저장", ".jpg", [("JPG 이미지", "*.jpg")], data
        )
        if not jpg_path:
            return

        self.config(cursor="watch")
        self.update()
        try:
            written = fill_report.generate_jpg(data, jpg_path)
        except Exception as e:
            messagebox.showerror(
                "오류",
                f"JPG 변환 중 오류가 발생했습니다:\n{e}\n(MS Word가 설치되어 있어야 변환이 가능합니다.)",
            )
            return
        finally:
            self.config(cursor="")

        names = "\n".join(os.path.basename(p) for p in written)
        if messagebox.askyesno("저장 완료", f"JPG 파일이 저장되었습니다.\n{names}\n\n폴더를 여시겠습니까?"):
            os.startfile(os.path.dirname(jpg_path))


if __name__ == "__main__":
    _enable_windows_dpi_awareness()
    ReportApp().mainloop()
