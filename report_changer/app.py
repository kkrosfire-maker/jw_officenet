"""수탁업체명 자동 변환 프로그램 - GUI (tkinter)

PRD.md §6 화면 구성 참고.
"""
from __future__ import annotations

import os
import sys
import re
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, Tk as DndTk

import core
import config
import theme


def _parse_dnd_paths(data: str) -> list[str]:
    """tkinterdnd2가 주는 드롭 데이터 문자열을 파일 경로 목록으로 분해한다.

    경로에 공백이 있으면 {C:/경로/파일.xlsx} 처럼 중괄호로 감싸져 들어온다.
    """
    return [m.group(1) if m.group(1) is not None else m.group(2)
            for m in re.finditer(r"\{([^}]*)\}|(\S+)", data)]


def _first_xlsx(paths: list[str]) -> str | None:
    for p in paths:
        if p.lower().endswith(".xlsx"):
            return p
    return None


def _configure_stripes(tree: ttk.Treeview):
    tree.tag_configure("evenrow", background=theme.ROW_EVEN)
    tree.tag_configure("oddrow", background=theme.ROW_ODD)


def _restripe(tree: ttk.Treeview):
    """현재 표시 순서 기준으로 줄무늬 태그를 다시 매긴다(추가/삭제/정렬 후 호출)."""
    for i, iid in enumerate(tree.get_children()):
        tree.item(iid, tags=("evenrow" if i % 2 == 0 else "oddrow",))


def _apply_window_icon(win):
    """소스 실행·exe 실행 모두에서 app.ico를 창 아이콘으로 적용한다."""
    here = Path(__file__).resolve().parent
    for root in (Path(getattr(sys, "_MEIPASS", here)), here, here.parent):
        ico = root / "app.ico"
        if ico.exists():
            try:
                win.iconbitmap(default=str(ico))
            except Exception:
                pass
            return


class App(DndTk):
    def __init__(self):
        super().__init__()
        self.title("수탁업체명 자동 변환 프로그램")
        _apply_window_icon(self)

        self.cfg = config.load_config()

        self.target_path: str | None = None
        self.ref_path: str | None = self.cfg.get("ref_path")
        if self.ref_path and not Path(self.ref_path).exists():
            self.ref_path = None
        self.last_save_path: str | None = None

        theme.apply(self)
        self._build_ui()

        # 좌우 너비는 내용에 맞춰 고정하고, 위아래(결과 표 영역)만 늘릴 수 있게 한다.
        self.update_idletasks()
        width = self.winfo_reqwidth()
        self.geometry(f"{width}x680")
        self.minsize(width, 500)
        self.resizable(False, True)

    # ---------------------------------------------------------- UI 구성
    def _build_ui(self):
        frm_files = ttk.LabelFrame(self, text="파일 설정 (끌어놓기 가능)")
        frm_files.pack(fill="x", padx=10, pady=6)
        frm_files.columnconfigure(1, weight=1)

        DROP_HINT = "여기로 끌어놓거나 선택하세요"

        ttk.Label(frm_files, text="정산파일").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.lbl_target = theme.drop_box(frm_files, text=DROP_HINT)
        self.lbl_target.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(frm_files, text="파일 선택", command=self.on_select_target).grid(
            row=0, column=2, padx=8, pady=4
        )
        for w in (frm_files, self.lbl_target):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop_target)

        ttk.Label(frm_files, text="담당자 기준파일").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ref_text = Path(self.ref_path).name if self.ref_path else DROP_HINT
        self.lbl_ref = theme.drop_box(frm_files, text=ref_text)
        if self.ref_path:
            self.lbl_ref.config(fg=theme.NAVY)
        self.lbl_ref.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(frm_files, text="교체", command=self.on_select_ref).grid(row=1, column=2, padx=8, pady=4)
        self.lbl_ref.drop_target_register(DND_FILES)
        self.lbl_ref.dnd_bind("<<Drop>>", self._on_drop_ref)

        # 변환 결과 (변환 전에는 비어있다가, 변환 후 채워짐)
        frm_result = ttk.LabelFrame(self, text="변환 결과")
        frm_result.pack(fill="both", expand=True, padx=10, pady=6)

        self.lbl_result_summary = ttk.Label(
            frm_result, text="(아직 변환하지 않았습니다)", style="Muted.TLabel", justify="left"
        )
        self.lbl_result_summary.pack(fill="x", padx=8, pady=8, anchor="w")

        ttk.Label(frm_result, text="미스매칭 처리 내역", font=("", 9, "bold")).pack(
            fill="x", padx=8, anchor="w"
        )

        frm_tree = ttk.Frame(frm_result)
        frm_tree.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        self.mis_columns = ("rows", "kind", "key", "hospital", "count", "outcome", "manager")
        self.tree_mismatch = ttk.Treeview(frm_tree, columns=self.mis_columns, show="headings", height=10)
        for col, head, width in (
            ("rows", "행", 90), ("kind", "구분", 80), ("key", "매칭 실패 값", 180),
            ("hospital", "병원명", 130), ("count", "건수", 50),
            ("outcome", "처리 결과", 80), ("manager", "담당자", 100),
        ):
            self.tree_mismatch.heading(col, text=head)
            self.tree_mismatch.column(col, width=width, anchor="w")
        _configure_stripes(self.tree_mismatch)
        scroll2 = ttk.Scrollbar(frm_tree, orient="vertical", command=self.tree_mismatch.yview)
        self.tree_mismatch.configure(yscrollcommand=scroll2.set)
        self.tree_mismatch.pack(side="left", fill="both", expand=True)
        scroll2.pack(side="right", fill="y")
        self._placeholder_mode = True
        self.tree_mismatch.bind("<Configure>", self._on_tree_resize)
        self._fill_placeholder_rows()

        # 하단 액션 바 - 왼쪽: 부가 기능, 오른쪽 끝: 변환 실행(가장 중요한 동작)
        frm_actions = ttk.Frame(self)
        frm_actions.pack(fill="x", padx=10, pady=(0, 10))
        self.btn_open_file = ttk.Button(
            frm_actions, text="결과 파일 열기", command=self._open_result_file, state="disabled"
        )
        self.btn_open_file.pack(side="left")
        self.btn_open_folder = ttk.Button(
            frm_actions, text="폴더 열기", command=self._open_result_folder, state="disabled"
        )
        self.btn_open_folder.pack(side="left", padx=(6, 0))
        ttk.Button(frm_actions, text="변환 실행", style="Accent.TButton", command=self.on_run).pack(
            side="right"
        )
        ttk.Button(frm_actions, text="매핑 목록 관리", command=self.on_manage_mappings).pack(
            side="right", padx=(0, 6)
        )

        self.lbl_status = ttk.Label(self, text="", foreground=theme.TEAL)
        self.lbl_status.pack(fill="x", padx=10, pady=(0, 6))

    # ---------------------------------------------------------- 결과 영역
    def _fill_placeholder_rows(self):
        """변환 전(또는 미스매칭이 없을 때)에도 표 전체가 줄무늬로 채워지도록 빈 행을 채운다.

        실제 위젯 높이에 맞춰 행 개수를 계산하므로 창을 늘려도 끝까지 음영이 이어진다.
        """
        self._placeholder_mode = True
        height_px = self.tree_mismatch.winfo_height()
        try:
            rowheight = int(ttk.Style().lookup("Treeview", "rowheight") or 20)
        except Exception:
            rowheight = 20
        count = max(10, height_px // max(rowheight, 1) + 2)

        self.tree_mismatch.delete(*self.tree_mismatch.get_children())
        empty = [""] * len(self.mis_columns)
        for i in range(count):
            self.tree_mismatch.insert(
                "", "end", values=empty, tags=("evenrow" if i % 2 == 0 else "oddrow",)
            )

    def _on_tree_resize(self, event):
        if self._placeholder_mode:
            self._fill_placeholder_rows()

    def _reset_result_area(self):
        self.lbl_result_summary.config(text="(아직 변환하지 않았습니다)", style="Muted.TLabel")
        self._fill_placeholder_rows()
        self.last_save_path = None
        self.btn_open_file.config(state="disabled")
        self.btn_open_folder.config(state="disabled")

    def _show_result(self, *, total_rows, matched_biz, matched_product, added, skipped, save_path,
                      mismatch_log=None):
        summary = (
            f"전체 행 수: {total_rows}   |   기본 매칭(사업자번호): {matched_biz}   |   "
            f"예외 매칭(윤병옥내과): {matched_product}\n"
            f"이번에 새로 확인해 기준엑셀에 추가: {added}건   |   건너뛴(미확인): {skipped}건\n"
            f"저장 위치: {save_path}"
        )
        self.lbl_result_summary.config(text=summary, style="TLabel")

        if mismatch_log:
            self._placeholder_mode = False
            self.tree_mismatch.delete(*self.tree_mismatch.get_children())
            for item in mismatch_log:
                self.tree_mismatch.insert("", "end", values=(
                    item["rows"], item["kind"], item["key"], item["hospital"],
                    item["count"], item["outcome"], item["manager"],
                ))
            _restripe(self.tree_mismatch)
        else:
            self._fill_placeholder_rows()

        self.last_save_path = save_path
        self.btn_open_file.config(state="normal")
        self.btn_open_folder.config(state="normal")

    def _open_result_file(self):
        if self.last_save_path:
            os.startfile(self.last_save_path)

    def _open_result_folder(self):
        if self.last_save_path:
            os.startfile(str(Path(self.last_save_path).parent))

    # ---------------------------------------------------------- 파일 선택
    def _set_target_path(self, path: str):
        self.target_path = path
        self.lbl_target.config(text=Path(path).name, fg=theme.NAVY)

    def on_select_target(self):
        path = filedialog.askopenfilename(
            title="변경할 엑셀파일 선택",
            filetypes=[("Excel 파일", "*.xlsx")],
        )
        if not path:
            return
        self._set_target_path(path)

    def _on_drop_target(self, event):
        path = _first_xlsx(_parse_dnd_paths(event.data))
        if not path:
            messagebox.showerror("오류", "엑셀(.xlsx) 파일을 끌어놓아주세요.")
            return
        self._set_target_path(path)

    def _set_ref_path(self, path: str):
        if self.ref_path and Path(self.ref_path).resolve() != Path(path).resolve():
            if not messagebox.askyesno(
                "기준엑셀 교체",
                "기준엑셀을 완전히 새 파일로 교체합니다.\n"
                "지금까지 이 프로그램이 추가해온 매핑 내용이 새 파일에는 없을 수 있습니다.\n계속할까요?",
            ):
                return
        self.ref_path = path
        self.lbl_ref.config(text=Path(path).name, fg=theme.NAVY)
        self.cfg["ref_path"] = path
        config.save_config(self.cfg)

    def on_select_ref(self):
        initialdir = str(Path(self.ref_path).parent) if self.ref_path else None
        path = filedialog.askopenfilename(
            title="기준엑셀 선택",
            filetypes=[("Excel 파일", "*.xlsx")],
            initialdir=initialdir,
        )
        if not path:
            return
        self._set_ref_path(path)

    def _on_drop_ref(self, event):
        path = _first_xlsx(_parse_dnd_paths(event.data))
        if not path:
            messagebox.showerror("오류", "엑셀(.xlsx) 파일을 끌어놓아주세요.")
            return
        self._set_ref_path(path)

    # ---------------------------------------------------------- 기준엑셀 로드 공통
    def _require_ref(self) -> core.ReferenceData | None:
        if not self.ref_path:
            messagebox.showerror("오류", "기준엑셀을 먼저 선택해주세요.")
            return None
        try:
            return core.load_reference(self.ref_path)
        except core.ReferenceFormatError as e:
            messagebox.showerror("기준엑셀 형식 오류", str(e))
            return None
        except Exception as e:
            messagebox.showerror("오류", f"기준엑셀을 여는 중 오류가 발생했습니다.\n{e}")
            return None

    # ---------------------------------------------------------- 매핑 목록 관리
    def on_manage_mappings(self):
        if not self.ref_path:
            messagebox.showerror("오류", "기준엑셀을 먼저 선택해주세요.")
            return
        ManageMappingsDialog(self, self.ref_path)

    # ---------------------------------------------------------- 변환 실행
    def on_run(self):
        if not self.target_path:
            messagebox.showerror("오류", "변경할 엑셀파일을 먼저 선택해주세요.")
            return
        ref = self._require_ref()
        if ref is None:
            return

        self._reset_result_area()

        try:
            result = core.process_target_file(self.target_path, ref)
        except core.ExcelNotAvailableError as e:
            messagebox.showerror("Excel 실행 오류", str(e))
            return
        except core.TargetFormatError as e:
            messagebox.showerror("변경할 엑셀파일 형식 오류", str(e))
            return
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("오류", f"변환 처리 중 오류가 발생했습니다.\n{e}")
            return

        warnings = core.validate_target_headers(result.sheet)
        if warnings:
            msg = "\n".join(warnings)
            if not messagebox.askyesno("헤더 형식 경고", f"{msg}\n\n그래도 계속할까요?"):
                core.close_target(result)
                return

        groups = core.group_mismatches(result.mismatches, ref)
        added_biz = 0
        added_product = 0
        mismatch_log = []
        if groups:
            managers = core.all_manager_names(ref)
            for group in groups:
                action, manager = MismatchDialog.ask(self, group, managers)
                if action == "confirm":
                    core.resolve_mismatch_group(ref, result, group, manager)
                    if group.kind == "biz":
                        added_biz += 1
                    else:
                        added_product += 1
                    managers = core.all_manager_names(ref)
                    outcome, outcome_manager = "기준엑셀에 추가", manager
                else:
                    core.skip_mismatch_group(result, group)
                    outcome, outcome_manager = "건너뜀", ""
                mismatch_log.append({
                    "rows": ", ".join(str(i.row) for i in group.items),
                    "kind": "사업자번호" if group.kind == "biz" else "제품명",
                    "key": group.key,
                    "hospital": group.hospital,
                    "count": len(group.items),
                    "outcome": outcome,
                    "manager": outcome_manager,
                })

            if ref.pending_biz_rows or ref.pending_product_rows:
                try:
                    core.backup_reference_file(ref.path)
                    core.save_reference(ref)
                except Exception as e:
                    traceback.print_exc()
                    messagebox.showerror("오류", f"기준엑셀 저장 중 오류가 발생했습니다.\n{e}")
                    core.close_target(result)
                    return

        # 결과 저장 대화상자 (FR-8) - 기본 파일명: yymmdd_원본파일명.xlsx
        last_save_dir = self.cfg.get("last_save_dir") or str(Path(self.target_path).parent)
        src = Path(self.target_path)
        default_name = f"{datetime.now().strftime('%y%m%d')}_{src.stem}{src.suffix}"
        save_path = filedialog.asksaveasfilename(
            title="결과 저장",
            initialdir=last_save_dir,
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel 파일", "*.xlsx")],
        )
        if not save_path:
            core.close_target(result)
            messagebox.showinfo("취소됨", "저장이 취소되어 결과 파일을 만들지 않았습니다.")
            return

        try:
            core.commit_and_save(result, save_path)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("오류", f"결과 파일 저장 중 오류가 발생했습니다.\n{e}")
            return

        self.cfg["last_save_dir"] = str(Path(save_path).parent)
        config.save_config(self.cfg)

        total_rows = result.last_data_row - core.TARGET_DATA_START_ROW + 1
        self.lbl_status.config(text="변환 완료")
        self._show_result(
            total_rows=total_rows,
            matched_biz=result.matched_biz_count,
            matched_product=result.matched_product_count,
            added=added_biz + added_product,
            skipped=result.skipped_count,
            save_path=save_path,
            mismatch_log=mismatch_log,
        )


class MismatchDialog(tk.Toplevel):
    """FR-5.2/5.3: 미스매칭 그룹 하나를 사용자에게 보여주고 확인/건너뛰기를 받는다."""

    def __init__(self, parent, group: core.MismatchGroup, managers: list[str]):
        super().__init__(parent)
        self.group = group
        self.result_action = "skip"
        self.result_manager = ""

        self.title("미스매칭 확인")
        self.resizable(False, False)
        theme.style_toplevel(self)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

        kind_label = "사업자번호" if group.kind == "biz" else "제품명(윤병옥내과)"
        rows_desc = ", ".join(str(i.row) for i in group.items[:10])
        if len(group.items) > 10:
            rows_desc += f" 외 {len(group.items) - 10}건"

        info = (
            f"매칭 실패 종류: {kind_label}\n"
            f"매칭 실패 값: {group.key}\n"
            f"병원명: {group.hospital}\n"
            f"해당 행: {rows_desc}\n"
            f"(총 {len(group.items)}건, 같은 값은 한 번만 확인하면 전부 반영됩니다)"
        )
        ttk.Label(self, text=info, justify="left", wraplength=400).pack(padx=12, pady=12, anchor="w")

        if group.suggestions:
            frm_sug = ttk.LabelFrame(self, text="비슷한 기존 등록 (참고용 - 자동 매칭에는 쓰이지 않음)")
            frm_sug.pack(fill="x", padx=12, pady=(0, 6))
            for cand_key, cand_manager, ratio in group.suggestions:
                row = ttk.Frame(frm_sug)
                row.pack(fill="x", padx=6, pady=3)
                text = f"'{cand_key}'  →  담당자: {cand_manager}  (유사도 {int(ratio * 100)}%)"
                ttk.Label(row, text=text, wraplength=320, justify="left").pack(side="left", fill="x", expand=True)
                ttk.Button(
                    row, text="이 담당자로", width=10,
                    command=lambda m=cand_manager: self._fill_manager(m),
                ).pack(side="right")

        frm = ttk.Frame(self)
        frm.pack(fill="x", padx=12, pady=6)
        ttk.Label(frm, text="담당자:").pack(side="left")
        self.combo_manager = ttk.Combobox(frm, values=managers, width=25)
        self.combo_manager.pack(side="left", padx=6)

        frm_btn = ttk.Frame(self)
        frm_btn.pack(fill="x", padx=12, pady=16)
        ttk.Button(frm_btn, text="기준엑셀에 추가", style="Accent.TButton", command=self._on_confirm).pack(
            side="right", padx=4
        )
        ttk.Button(frm_btn, text="지금은 건너뛰기", command=self._on_skip).pack(side="right", padx=4)

    def _fill_manager(self, manager: str):
        self.combo_manager.set(manager)

    def _on_confirm(self):
        manager = self.combo_manager.get().strip()
        if not manager:
            messagebox.showerror("오류", "담당자를 입력하거나 선택해주세요.")
            return
        self.result_action = "confirm"
        self.result_manager = manager
        self.destroy()

    def _on_skip(self):
        self.result_action = "skip"
        self.destroy()

    @staticmethod
    def ask(parent, group: core.MismatchGroup, managers: list[str]):
        dlg = MismatchDialog(parent, group, managers)
        parent.wait_window(dlg)
        return dlg.result_action, dlg.result_manager


class ManageMappingsDialog(tk.Toplevel):
    """FR-6.3: 기준엑셀의 현재 매핑 목록을 조회·수정·삭제 (매핑 직접 추가도 이 화면의 [추가] 버튼으로 대체).

    목록 셀을 더블클릭하면 그 자리에서 바로 값을 고칠 수 있고(인라인 편집), 삭제도
    화면에서만 먼저 반영된다 — 실제 파일에는 [저장] 버튼을 눌러야 한 번에 기록된다.
    """

    BIZ_COLUMNS = ("biz_no", "hospital", "manager")
    PRODUCT_COLUMNS = ("product", "manager")

    def __init__(self, parent: App, ref_path: str):
        super().__init__(parent)
        self.parent = parent
        self.ref_path = ref_path
        self.title("기준엑셀 매핑 목록 관리")
        self.geometry("700x520")
        theme.style_toplevel(self)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._dirty = False
        self._edit_entry = None

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_biz = ttk.Frame(nb)
        self.tab_product = ttk.Frame(nb)
        nb.add(self.tab_biz, text="거래처별 담당자")
        nb.add(self.tab_product, text="윤병옥내과")

        self.tree_biz = self._build_tree(self.tab_biz, self.BIZ_COLUMNS, ("사업자번호", "거래처명", "담당자"))
        self.tree_product = self._build_tree(self.tab_product, self.PRODUCT_COLUMNS, ("품목", "담당자"))

        self._load_biz_rows()
        self._load_product_rows()

        self._build_row_buttons(self.tab_biz, self.tree_biz, len(self.BIZ_COLUMNS))
        self._build_row_buttons(self.tab_product, self.tree_product, len(self.PRODUCT_COLUMNS))

        ttk.Label(self, text="셀을 더블클릭하면 바로 수정할 수 있습니다. 삭제/수정 후 [저장]을 눌러야 파일에 반영됩니다.",
                  style="Muted.TLabel").pack(fill="x", padx=8, pady=(0, 4))

        frm_bottom = ttk.Frame(self)
        frm_bottom.pack(fill="x", padx=8, pady=(0, 8))
        self.btn_save = ttk.Button(frm_bottom, text="저장", style="Accent.TButton", command=self._on_save_all)
        self.btn_save.pack(side="right", padx=4)
        ttk.Button(frm_bottom, text="닫기", command=self._on_close).pack(side="right", padx=4)

    def _build_tree(self, parent, columns, headings):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)
        for col, head in zip(columns, headings):
            tree.heading(col, text=head)
            tree.column(col, width=180)
        _configure_stripes(tree)
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        tree.bind("<Double-1>", lambda e, t=tree, cols=columns: self._on_cell_double_click(e, t, cols))
        return tree

    def _build_row_buttons(self, parent, tree, num_columns):
        frm = ttk.Frame(parent)
        frm.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(frm, text="추가", command=lambda t=tree, n=num_columns: self._add_row(t, n)).pack(side="left", padx=4)
        ttk.Button(frm, text="선택 행 삭제", command=lambda t=tree: self._delete_row(t)).pack(side="left", padx=4)

    def _add_row(self, tree, num_columns):
        iid = tree.insert("", "end", values=[""] * num_columns)
        tree.selection_set(iid)
        tree.see(iid)
        _restripe(tree)
        self._mark_dirty()

    def _load_biz_rows(self):
        self.tree_biz.delete(*self.tree_biz.get_children())
        for r in core.read_biz_table(self.ref_path):
            self.tree_biz.insert("", "end", values=(r["biz_no"], r["hospital"], r["manager"]))
        _restripe(self.tree_biz)

    def _load_product_rows(self):
        self.tree_product.delete(*self.tree_product.get_children())
        for r in core.read_product_table(self.ref_path):
            self.tree_product.insert("", "end", values=(r["product"], r["manager"]))
        _restripe(self.tree_product)

    def _mark_dirty(self):
        self._dirty = True

    # ---------------------------------------------------------- 인라인 편집
    def _on_cell_double_click(self, event, tree, columns):
        if self._edit_entry is not None:
            self._edit_entry.destroy()
            self._edit_entry = None

        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = tree.identify_row(event.y)
        col_id = tree.identify_column(event.x)
        if not row_id or not col_id:
            return
        col_index = int(col_id.replace("#", "")) - 1
        col_name = columns[col_index]
        bbox = tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, w, h = bbox

        entry = tk.Entry(tree)
        entry.insert(0, tree.set(row_id, col_name))
        entry.select_range(0, "end")
        entry.focus()
        entry.place(x=x, y=y, width=w, height=h)
        self._edit_entry = entry

        def commit(event=None):
            if self._edit_entry is None:
                return
            tree.set(row_id, col_name, entry.get())
            entry.destroy()
            self._edit_entry = None
            self._mark_dirty()

        def cancel(event=None):
            entry.destroy()
            self._edit_entry = None

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", cancel)

    def _delete_row(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("안내", "먼저 목록에서 행을 선택해주세요.")
            return
        if not messagebox.askyesno("삭제 확인", "선택한 행을 목록에서 제거할까요? (저장을 눌러야 실제 파일에 반영됩니다)"):
            return
        for iid in sel:
            tree.delete(iid)
        _restripe(tree)
        self._mark_dirty()

    # ---------------------------------------------------------- 저장
    @staticmethod
    def _is_blank(v) -> bool:
        return v is None or str(v).strip() == ""

    def _collect_rows(self, tree, field_names) -> list[dict] | None:
        """트리 내용을 dict 목록으로 모은다. 완전히 빈 행은 건너뛰고, 일부만 채워진
        행이 있으면 사용자에게 알리고 None을 반환해 저장을 중단시킨다."""
        rows = []
        for iid in tree.get_children():
            values = tree.item(iid)["values"]
            if all(self._is_blank(v) for v in values):
                continue
            if any(self._is_blank(v) for v in values):
                messagebox.showerror(
                    "오류", "빈 칸이 있는 행이 있습니다. 모든 칸을 채우거나 행을 삭제한 뒤 저장해주세요."
                )
                return None
            rows.append({name: v for name, v in zip(field_names, values)})
        return rows

    def _on_save_all(self):
        biz_rows = self._collect_rows(self.tree_biz, ("biz_no", "hospital", "manager"))
        if biz_rows is None:
            return
        product_rows = self._collect_rows(self.tree_product, ("product", "manager"))
        if product_rows is None:
            return
        try:
            core.backup_reference_file(self.ref_path)
            core.overwrite_biz_table(self.ref_path, biz_rows)
            core.overwrite_product_table(self.ref_path, product_rows)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("오류", f"저장 중 오류가 발생했습니다.\n{e}")
            return
        self._dirty = False
        messagebox.showinfo("완료", "기준엑셀에 저장되었습니다.")
        self._load_biz_rows()
        self._load_product_rows()

    def _on_close(self):
        if self._dirty:
            if not messagebox.askyesno("저장 안 됨", "저장하지 않은 변경사항이 있습니다. 저장하지 않고 닫을까요?"):
                return
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
