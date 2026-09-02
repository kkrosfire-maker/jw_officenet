import calendar
import datetime
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import fill_report

PRESENCE_OPTIONS = ["없음", "있음"]

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
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        vscrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        hscrollbar = ttk.Scrollbar(self, orient="horizontal", command=canvas.xview)
        self.body = ttk.Frame(canvas)

        self.body.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
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
        self.geometry("1080x820")

        self.vars = {}
        self.last_dir = _load_last_dir()

        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=8, pady=8)
        root = scroll.body

        self._build_patient_section(root)
        self._build_exam_section(root)
        self._build_required_findings_section(root)
        self._build_optional_findings_section(root)
        self._build_conclusion_section(root)
        self._build_actions(root)

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
        if detail_key:
            dvar = tk.StringVar()
            ttk.Entry(parent, textvariable=dvar, width=28).grid(row=r, column=2, sticky="w", padx=6)
            self.vars[detail_key] = dvar
        return r

    # ---------- sections ----------

    def _build_patient_section(self, root):
        box = ttk.LabelFrame(root, text="1. 환자정보")
        box.pack(fill="x", padx=4, pady=6)
        self._entry_row(box, "등록번호", "reg_no")
        self._entry_row(box, "성명", "patient_name")
        self._entry_row(box, "생년월일 또는 나이", "birth_or_age")
        self._radio_row(box, "성별", "sex", ["남", "여"])

    def _build_exam_section(self, root):
        box = ttk.LabelFrame(root, text="2. 검사정보")
        box.pack(fill="x", padx=4, pady=6)
        r = self._next_row(box)
        ttk.Label(box, text="검사명").grid(row=r, column=0, sticky="w", padx=(4, 8), pady=2)
        options_frame = ttk.Frame(box)
        options_frame.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
        var = tk.StringVar(value=fill_report.EXAM_TYPE_OPTIONS[0])
        for opt in fill_report.EXAM_TYPE_OPTIONS:
            ttk.Radiobutton(options_frame, text=opt, value=opt, variable=var).pack(side="left", padx=2)
        self.vars["exam_type"] = var

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

        result = tk.StringVar(value=PRESET)
        self.vars[key] = result

        choice = tk.StringVar(value=PRESET)
        custom = tk.StringVar()

        frame = ttk.Frame(parent)
        frame.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
        ttk.Combobox(
            frame, textvariable=choice, state="readonly",
            values=[PRESET, CUSTOM], width=18,
        ).pack(side="left")
        entry = ttk.Entry(frame, textvariable=custom, width=24)
        entry.pack(side="left", padx=6)

        def sync(*_):
            if choice.get() == CUSTOM:
                entry.configure(state="normal")
                result.set(custom.get())
            else:
                entry.configure(state="disabled")
                result.set(choice.get())

        choice.trace_add("write", sync)
        custom.trace_add("write", sync)
        sync()
        return r

    def _build_required_findings_section(self, root):
        box = ttk.LabelFrame(root, text="3-(1). 검사 소견 (필수)")
        box.pack(fill="x", padx=4, pady=6)
        self._entry_row(box, "① 전립선 전체 용적 (cc)", "vol_total", width=10)
        self._entry_row(box, "② 전립선 이행대 용적 (cc)", "vol_transition", width=10)
        self._radio_row(box, "③ 전립선내 국소 병변", "focal_lesion", PRESENCE_OPTIONS, "focal_lesion_detail")
        self._radio_row(box, "④ 과혈관성 병변(도플러)", "hyper_vascular", PRESENCE_OPTIONS, "hyper_vascular_detail")
        self._radio_row(box, "⑤ 정낭 이상소견", "seminal_vesicle", PRESENCE_OPTIONS, "seminal_vesicle_detail")

    def _build_optional_findings_section(self, root):
        box = ttk.LabelFrame(root, text="3-(2). 검사 소견 (선택적 기술)")
        box.pack(fill="x", padx=4, pady=6)

        r = self._next_row(box)
        ttk.Label(box, text="① 전립선의 모양").grid(row=r, column=0, sticky="w", padx=(4, 8), pady=2)
        options_frame = ttk.Frame(box)
        options_frame.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
        var = tk.StringVar(value="")
        for opt in ["삼각형", "타원형", "원형", "세로타원형"]:
            ttk.Radiobutton(options_frame, text=opt, value=opt, variable=var).pack(side="left", padx=2)
        self.vars["shape"] = var

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
        text = tk.Text(box, height=4, wrap="word")
        text.grid(row=r, column=0, columnspan=3, sticky="ew", padx=4, pady=2)
        box.columnconfigure(2, weight=1)
        self.vars["other_findings"] = text

    def _build_conclusion_section(self, root):
        box = ttk.LabelFrame(root, text="4. 결론 (필수)")
        box.pack(fill="x", padx=4, pady=6)
        text = tk.Text(box, height=5, wrap="word")
        text.pack(fill="x", padx=4, pady=2)
        self.vars["conclusion"] = text

    def _build_actions(self, root):
        row = ttk.Frame(root)
        row.pack(fill="x", padx=4, pady=12)
        ttk.Button(row, text="Word로 저장", command=self.on_save_word).pack(side="left")
        ttk.Button(row, text="한글로 저장", command=self.on_save_hwp).pack(side="left", padx=8)
        ttk.Button(row, text="JPG로 저장", command=self.on_save_jpg).pack(side="left")
        ttk.Button(row, text="인쇄", command=self.on_print).pack(side="left", padx=8)

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

    def on_print(self):
        data = self._collect_data()
        if not self._confirm_required(data):
            return

        self.config(cursor="watch")
        self.update()
        try:
            # 인쇄 = JPG로 만들어 그림판으로 넘긴 뒤 바로 인쇄.
            fill_report.generate_and_print(data)
        except Exception as e:
            messagebox.showerror(
                "오류",
                f"인쇄 중 오류가 발생했습니다:\n{e}\n(MS Word가 설치되어 있어야 합니다.)",
            )
            return
        finally:
            self.config(cursor="")

        messagebox.showinfo("인쇄", "그림판으로 인쇄 작업을 보냈습니다.")


if __name__ == "__main__":
    ReportApp().mainloop()
