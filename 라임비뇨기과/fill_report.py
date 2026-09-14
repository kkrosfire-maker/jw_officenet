import os
import sys
from copy import deepcopy

import docx
from docx.oxml.ns import qn
from docx.shared import Pt

CHECK, UNCHECK = "■", "□"


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def checklist(options, selected, sep):
    parts = []
    for opt in options:
        mark = CHECK if opt == selected else UNCHECK
        parts.append(f"{mark}{opt}")
    return sep.join(parts)


def _copy_mark_format(paragraph, run):
    # An empty template cell has no run, only a paragraph-mark <w:rPr> that
    # carries the intended font/size. A run added with python-docx inherits
    # nothing and falls back to the 11pt document default, which is why the
    # 성명 / 검사기관명 values used to print larger than their labels. Copy the
    # paragraph mark's formatting onto the new run so every field matches.
    pPr = paragraph._p.find(qn("w:pPr"))
    if pPr is None:
        return
    mark_rpr = pPr.find(qn("w:rPr"))
    if mark_rpr is None:
        return
    rPr = run._r.get_or_add_rPr()
    for tag in ("w:rFonts", "w:sz", "w:szCs", "w:b", "w:i"):
        if rPr.find(qn(tag)) is None:
            src = mark_rpr.find(qn(tag))
            if src is not None:
                rPr.append(deepcopy(src))


def set_paragraph_text(paragraph, text):
    runs = paragraph.runs
    if not runs:
        _copy_mark_format(paragraph, paragraph.add_run(text))
        return
    runs[0].text = text
    for run in runs[1:]:
        run.text = ""


def _ensure_min_lines(cell, min_lines, start_index=0):
    """Guarantees the cell reserves at least `min_lines` writing rows below
    `start_index` (a fixed label sits at index 0 in the 기타소견 box), padding
    with blank paragraphs. Never trims - longer content keeps all its lines."""
    while len(cell.paragraphs) - start_index < min_lines:
        cell.add_paragraph()


def _para_max_pt(p):
    sizes = [r.font.size.pt for r in p.runs if r.font.size is not None]
    pPr = p._p.find(qn("w:pPr"))
    if pPr is not None:
        rPr = pPr.find(qn("w:rPr"))
        if rPr is not None and rPr.find(qn("w:sz")) is not None:
            sizes.append(int(rPr.find(qn("w:sz")).get(qn("w:val"))) / 2)
    return max(sizes) if sizes else 10.0


def _tighten_paragraph(p, exact=True):
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if exact:
        # An exact line height stops 한글 from applying its ~1.6x default
        # leading on import (what pushed the report onto a second page).
        # Scale it to the paragraph's own font so nothing clips.
        pf.line_spacing = Pt(_para_max_pt(p) * 1.25)
    else:
        pf.line_spacing = 1.0


def _compact_spacing(doc):
    """한글's .docx importer inflates every paragraph's leading, which is what
    pushed the report onto a second page. Tighten the spacing everywhere so the
    한글 output collapses back to one page (Word already fits)."""
    for p in doc.paragraphs:
        _tighten_paragraph(p, exact=False)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _tighten_paragraph(p, exact=True)


def _tight_cell_margins(table, tb=20, lr=80):
    tblPr = table._tbl.tblPr
    for existing in tblPr.findall(qn("w:tblCellMar")):
        tblPr.remove(existing)
    mar = tblPr.makeelement(qn("w:tblCellMar"), {})
    for side, width in (("top", tb), ("left", lr), ("bottom", tb), ("right", lr)):
        e = mar.makeelement(qn(f"w:{side}"), {})
        e.set(qn("w:w"), str(width))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tblPr.append(mar)


def _unbold_table(table):
    # The user's template carries bold sample text in a few value cells
    # (성명 / 검사자 / 판독자), which made those fields print heavier than the
    # rest. Force every run in the table back to regular weight.
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.bold = False


def _set_cell_font_size(cell, pt):
    half = str(int(pt * 2))
    for p in cell.paragraphs:
        for r in p.runs:
            r.font.size = Pt(pt)
        # Also stamp the paragraph-mark rPr (creating it if absent) so blank
        # padding lines get the same size/height as the text lines.
        pPr = p._p.get_or_add_pPr()
        mark_rpr = pPr.find(qn("w:rPr"))
        if mark_rpr is None:
            mark_rpr = pPr.makeelement(qn("w:rPr"), {})
            pPr.append(mark_rpr)
        for tag in ("w:sz", "w:szCs"):
            e = mark_rpr.find(qn(tag))
            if e is None:
                e = mark_rpr.makeelement(qn(tag), {})
                mark_rpr.append(e)
            e.set(qn("w:val"), half)


def _shrink_paragraph(p_el, pt=6):
    pPr = p_el.get_or_add_pPr()
    rPr = pPr.find(qn("w:rPr"))
    if rPr is None:
        rPr = pPr.makeelement(qn("w:rPr"), {})
        pPr.append(rPr)
    for tag in ("w:sz", "w:szCs"):
        e = rPr.find(qn(tag))
        if e is None:
            e = rPr.makeelement(qn(tag), {})
            rPr.append(e)
        e.set(qn("w:val"), str(int(pt * 2)))


def _set_box_border(cell, sz=6):
    """Puts an explicit single-line border on all four sides of a cell.
    The template leaves the 기타소견 / 결론 boxes to the table style, which
    한글's .docx importer drops - so draw them on the cell itself."""
    tcPr = cell._tc.get_or_add_tcPr()
    for existing in tcPr.findall(qn("w:tcBorders")):
        tcPr.remove(existing)
    borders = tcPr.makeelement(qn("w:tcBorders"), {})
    for side in ("top", "left", "bottom", "right"):
        edge = borders.makeelement(qn(f"w:{side}"), {})
        edge.set(qn("w:val"), "single")
        edge.set(qn("w:sz"), str(sz))
        edge.set(qn("w:space"), "0")
        edge.set(qn("w:color"), "000000")
        borders.append(edge)
    tcPr.append(borders)


def set_cell_text(cell, text):
    set_paragraph_text(cell.paragraphs[0], text)


def set_cell_multiline(cell, text, start_index=0):
    lines = (text or "").split("\n")
    while len(cell.paragraphs) < start_index + len(lines):
        cell.add_paragraph()
    paragraphs = cell.paragraphs
    for offset, line in enumerate(lines):
        set_paragraph_text(paragraphs[start_index + offset], line)
    for p in paragraphs[start_index + len(lines):]:
        set_paragraph_text(p, "")


def detail_or_blank(detail, blank_width=18):
    if detail:
        return f"({detail})"
    return "(" + " " * blank_width + ")"


EXAM_TYPE_OPTIONS = [
    "경직장 전립선·정낭 초음파",
    "진단적 초음파",
    "진단적 초음파 (도플러 가산)",
    "제한적 초음파",
]

PRESENCE_OPTIONS = ["없음", "있음"]

TABLE3_FIELDS = [
    (1, "border", ["명확함", "불명확 또는 불규칙"]),
    (2, "symmetry", ["대칭", "비대칭"]),
    (3, "calcification", PRESENCE_OPTIONS),
    (4, "median_cyst", PRESENCE_OPTIONS),
    (5, "acute_inflammation", PRESENCE_OPTIONS),
    (6, "bladder_protrusion", PRESENCE_OPTIONS),
    (7, "bladder_stone_tumor", PRESENCE_OPTIONS),
]


def generate_docx(data, output_path, template_path=None):
    template_path = template_path or resource_path("초음파_판독지.docx")
    doc = docx.Document(template_path)

    # --- 1. 환자정보 (2 rows x 4 cols: label | value | label | value) ---
    t0 = doc.tables[0]
    set_cell_text(t0.rows[0].cells[1], data.get("reg_no", ""))
    set_cell_text(t0.rows[0].cells[3], data.get("patient_name", ""))
    set_cell_text(t0.rows[1].cells[1], data.get("birth_or_age", ""))
    set_cell_text(t0.rows[1].cells[3], checklist(["남", "여"], data.get("sex"), "  "))

    # --- 2. 검사정보 (5 rows x 4 cols: col0/col1 vertically merged) ---
    t1 = doc.tables[1]
    set_cell_text(t1.rows[0].cells[1], checklist(EXAM_TYPE_OPTIONS, data.get("exam_type"), "\n"))
    set_cell_text(t1.rows[0].cells[3], data.get("exam_date", ""))
    examiner = data.get("examiner_name", "")
    examiner_license = data.get("examiner_license", "")
    set_cell_text(
        t1.rows[1].cells[3],
        f"{examiner}    ({examiner_license})" if examiner or examiner_license else "",
    )
    set_cell_text(t1.rows[2].cells[3], data.get("read_date", ""))
    reader = data.get("reader_name", "")
    reader_license = data.get("reader_license", "")
    set_cell_text(
        t1.rows[3].cells[3],
        f"{reader}    ({reader_license})" if reader or reader_license else "",
    )
    set_cell_text(t1.rows[4].cells[3], data.get("institution", ""))

    # --- 3-(1). 필수 소견 (5 rows x 3 cols: label | value | detail) ---
    t2 = doc.tables[2]
    vol_total = data.get("vol_total", "")
    vol_transition = data.get("vol_transition", "")
    set_cell_text(t2.rows[0].cells[1], f"{vol_total} cc" if vol_total else "cc")
    set_cell_text(t2.rows[1].cells[1], f"{vol_transition} cc" if vol_transition else "cc")
    for row, field in [(2, "focal_lesion"), (3, "hyper_vascular"), (4, "seminal_vesicle")]:
        set_cell_text(t2.rows[row].cells[1], checklist(PRESENCE_OPTIONS, data.get(field), "  "))
        set_cell_text(t2.rows[row].cells[2], detail_or_blank(data.get(f"{field}_detail", "")))

    # --- 3-(2). 선택적 기술 (8 rows x 2 cols: label | checklist + detail) ---
    t3 = doc.tables[3]
    shape_options = ["삼각형", "타원형", "원형", "세로타원형"]
    set_cell_text(t3.rows[0].cells[1], checklist(shape_options, data.get("shape"), " "))
    for row, field, options in TABLE3_FIELDS:
        base = checklist(options, data.get(field), " ")
        detail = data.get(f"{field}_detail", "")
        set_cell_text(t3.rows[row].cells[1], f"{base} {detail_or_blank(detail, 8)}")

    # --- 기타소견 박스 (own 1x1 table; paragraph 0 is the fixed label) ---
    t4 = doc.tables[4]
    set_cell_multiline(t4.rows[0].cells[0], data.get("other_findings", ""), start_index=1)

    # --- 4. 결론 박스 (own 1x1 table) ---
    t5 = doc.tables[5]
    set_cell_multiline(t5.rows[0].cells[0], data.get("conclusion", ""), start_index=0)

    # 기타소견 박스: 안내문구(문단 0) 아래로 최소 4줄 확보. 결론 박스: 최소 5줄.
    # 내용이 그보다 길면 그대로 다 남긴다. 두 칸 모두 8pt 고정.
    _ensure_min_lines(t4.rows[0].cells[0], min_lines=4, start_index=1)
    _ensure_min_lines(t5.rows[0].cells[0], min_lines=5, start_index=0)
    for cell in (t4.rows[0].cells[0], t5.rows[0].cells[0]):
        _set_cell_font_size(cell, 8)
        _set_box_border(cell)

    trailing = doc.element.body.findall(qn("w:p"))
    if trailing:
        _shrink_paragraph(trailing[-1], pt=4)

    # Collapse the inter-line padding 한글 would otherwise add, pull the table
    # cell margins in tight (keeps the .hwp on one page too), and drop the
    # template's stray bold so every field prints at the same weight.
    _compact_spacing(doc)
    for table in doc.tables:
        _tight_cell_margins(table)
        _unbold_table(table)

    doc.save(output_path)


# ===================== 음낭 초음파 판독지 =====================

SCROTAL_EXAM_TYPE_OPTIONS = [
    "음낭 초음파",
    "진단적 초음파",
    "진단적 초음파 (도플러 가산)",
    "제한적 초음파",
]
SCROTAL_EXISTENCE_OPTIONS = ["음낭내 있음", "음낭내에 없음"]
SCROTAL_TESTIS_CATEGORIES = ["종양", "석회화", "염증"]
SCROTAL_EPID_CATEGORIES = ["종양", "비대", "염증"]
SCROTAL_OTHER_CATEGORIES = ["음낭수종", "정계정맥류"]
SCROTAL_FLOW_CATEGORIES = ["혈류감소", "과혈관성병변"]


def _presence_marks(data, key_prefix, options=PRESENCE_OPTIONS):
    val = data.get(f"{key_prefix}_presence", options[0])
    return tuple(CHECK if val == opt else UNCHECK for opt in options)


def _cat_mark(data, key_prefix, cat):
    return CHECK if data.get(f"{key_prefix}_cat_{cat}") else UNCHECK


def _finding_extra(data, key_prefix, categories=None):
    """선택된 카테고리 + 상세텍스트를 괄호 안에 넣을 문자열로 합친다."""
    parts = [c for c in (categories or []) if data.get(f"{key_prefix}_cat_{c}")]
    detail = (data.get(f"{key_prefix}_detail") or "").strip()
    if detail:
        parts.append(f"기타: {detail}" if categories else detail)
    return ", ".join(parts)


def _fill_trailing_freeform(doc, start_idx, text, min_lines=3):
    """표(table)가 아니라 본문 문단으로 남겨진 결론란을 채운다. 템플릿에
    남은 문단 수보다 줄이 많으면 문서 끝에 문단을 추가한다."""
    lines = (text or "").split("\n")
    while len(lines) < min_lines:
        lines.append("")
    paras = doc.paragraphs
    for i, line in enumerate(lines):
        idx = start_idx + i
        if idx < len(paras):
            set_paragraph_text(paras[idx], line)
        else:
            doc.add_paragraph(line)


def _scrotal_side_lines(data, side):
    p = f"sc_{side}_"

    existence = data.get(f"{p}existence_presence", "")
    m_in = CHECK if existence == "음낭내 있음" else UNCHECK
    m_out = CHECK if existence == "음낭내에 없음" else UNCHECK
    line_existence = f"음낭내 고환 존재 여부\t \t{m_in} 음낭내 있음 \t{m_out} 음낭내에 없음 \t\t"

    vol = (data.get(f"{p}vol_cc") or "").strip()
    length = (data.get(f"{p}length_cm") or "").strip()
    line_volume = f"고환의 부피 (또는 장축의 길이)\t{vol} cc  (또는 {length} cm) "

    def presence_line(label, key, categories):
        m0, m1 = _presence_marks(data, f"{p}{key}")
        extra = _finding_extra(data, f"{p}{key}", categories)
        return f"{label} \t\t\t{m0} 없음\t{m1} 있음 ({extra})"

    line_testis = presence_line("고환의 이상 유무", "testis", SCROTAL_TESTIS_CATEGORIES)
    line_epid = presence_line("부고환 이상 유무", "epid", SCROTAL_EPID_CATEGORIES)
    line_other = presence_line("기타 음낭 이상 소견", "other", SCROTAL_OTHER_CATEGORIES)

    m0, m1 = _presence_marks(data, f"{p}flow")
    flow_extra = _finding_extra(data, f"{p}flow", SCROTAL_FLOW_CATEGORIES)
    line_flow = f"고환 내 혈류 이상 (도플러 검사시)\t{m0} 없음\t{m1} 있음 ({flow_extra})"

    return [line_existence, line_volume, line_testis, line_epid, line_other, line_flow]


def generate_docx_scrotal(data, output_path, template_path=None):
    template_path = template_path or resource_path("음낭_초음파_판독지.docx")
    doc = docx.Document(template_path)

    t0 = doc.tables[0]
    set_cell_text(t0.rows[0].cells[1], data.get("sc_reg_no", ""))
    set_cell_text(t0.rows[0].cells[3], data.get("sc_patient_name", ""))
    set_cell_text(t0.rows[1].cells[1], data.get("sc_birth_or_age", ""))
    set_cell_text(t0.rows[1].cells[3], checklist(["남", "여"], data.get("sc_sex"), "  "))

    t1 = doc.tables[1]
    exam_cell = t1.rows[0].cells[1]
    exam_selected = data.get("sc_exam_type", SCROTAL_EXAM_TYPE_OPTIONS[0])
    for i, opt in enumerate(SCROTAL_EXAM_TYPE_OPTIONS):
        mark = CHECK if opt == exam_selected else UNCHECK
        original = exam_cell.paragraphs[i].text
        set_paragraph_text(exam_cell.paragraphs[i], mark + original[1:])
    set_cell_text(t1.rows[0].cells[3], data.get("sc_exam_date", ""))
    examiner = data.get("sc_examiner_name", "")
    examiner_license = data.get("sc_examiner_license", "")
    set_cell_text(
        t1.rows[1].cells[3],
        f"{examiner}    ({examiner_license})" if examiner or examiner_license else "",
    )
    set_cell_text(t1.rows[2].cells[3], data.get("sc_read_date", ""))
    reader = data.get("sc_reader_name", "")
    reader_license = data.get("sc_reader_license", "")
    set_cell_text(
        t1.rows[3].cells[3],
        f"{reader}    ({reader_license})" if reader or reader_license else "",
    )
    set_cell_text(t1.rows[4].cells[3], data.get("sc_institution", ""))

    for idx, text in zip([7, 8, 9, 10, 11, 12], _scrotal_side_lines(data, "rt")):
        set_paragraph_text(doc.paragraphs[idx], text)
    for idx, text in zip([15, 16, 17, 18, 19, 20], _scrotal_side_lines(data, "lt")):
        set_paragraph_text(doc.paragraphs[idx], text)

    t2 = doc.tables[2]
    set_cell_multiline(t2.rows[0].cells[0], data.get("sc_other_findings", ""), start_index=1)
    _ensure_min_lines(t2.rows[0].cells[0], min_lines=4, start_index=1)
    _set_cell_font_size(t2.rows[0].cells[0], 8)
    _set_box_border(t2.rows[0].cells[0])

    _fill_trailing_freeform(doc, 25, data.get("sc_conclusion", ""), min_lines=4)

    _compact_spacing(doc)
    for table in doc.tables:
        _tight_cell_margins(table)
        _unbold_table(table)

    doc.save(output_path)


# ===================== 신장·부신·방광 초음파 판독지 =====================

KIDNEY_EXAM_TYPE_OPTIONS = [
    "신장·부신 초음파",
    "방광 초음파",
    "신장부신초음파 및 도플러",
    "방광초음파 및 도플러",
    "기타",
]
KIDNEY_FOCAL_CATEGORIES = ["낭종", "고형종괴", "기타병변"]
URETER_STONE_OPTIONS = ["없음 또는 모름", "있음"]


def generate_docx_kidney(data, output_path, template_path=None):
    template_path = template_path or resource_path("신장부신방광_초음파_판독지.docx")
    doc = docx.Document(template_path)

    t0 = doc.tables[0]
    set_cell_text(t0.rows[0].cells[1], data.get("kd_reg_no", ""))
    set_cell_text(t0.rows[0].cells[3], data.get("kd_patient_name", ""))
    set_cell_text(t0.rows[1].cells[1], data.get("kd_birth_or_age", ""))
    set_cell_text(t0.rows[1].cells[3], checklist(["남", "여"], data.get("kd_sex"), "  "))

    t1 = doc.tables[1]
    exam_cell = t1.rows[0].cells[1]
    exam_selected = data.get("kd_exam_type", "")
    exam_other_detail = (data.get("kd_exam_type_detail") or "").strip()
    for i, opt in enumerate(KIDNEY_EXAM_TYPE_OPTIONS):
        mark = CHECK if opt == exam_selected else UNCHECK
        original = exam_cell.paragraphs[i].text
        if opt == "기타" and exam_selected == opt and exam_other_detail:
            text = f"{mark}기타 {exam_other_detail}"
        else:
            text = mark + original[1:]
        set_paragraph_text(exam_cell.paragraphs[i], text)
    set_cell_text(t1.rows[0].cells[3], data.get("kd_exam_date", ""))
    examiner = data.get("kd_examiner_name", "")
    examiner_license = data.get("kd_examiner_license", "")
    set_cell_text(
        t1.rows[1].cells[3],
        f"{examiner}    ({examiner_license})" if examiner or examiner_license else "",
    )
    set_cell_text(t1.rows[2].cells[3], data.get("kd_read_date", ""))
    reader = data.get("kd_reader_name", "")
    reader_license = data.get("kd_reader_license", "")
    set_cell_text(
        t1.rows[3].cells[3],
        f"{reader}    ({reader_license})" if reader or reader_license else "",
    )
    set_cell_text(t1.rows[4].cells[3], data.get("kd_institution", ""))

    m0, m1 = _presence_marks(data, "kd_renal_echo")
    rt, lt = _cat_mark(data, "kd_renal_echo", "우신"), _cat_mark(data, "kd_renal_echo", "좌신")
    line7 = f"신장 실질의 에코 이상\t\t{m0} 없음\t\t{m1} 있음 ({rt}우신 {lt}좌신) \t\t"

    m0, m1 = _presence_marks(data, "kd_renal_size")
    rt, lt = _cat_mark(data, "kd_renal_size", "우신"), _cat_mark(data, "kd_renal_size", "좌신")
    line8 = f"신장의 크기 이상\t\t\t{m0} 없음  \t{m1} 있음 ({rt}우신 {lt}좌신) "

    m0, m1 = _presence_marks(data, "kd_focal")
    c1 = _cat_mark(data, "kd_focal", "낭종")
    c2 = _cat_mark(data, "kd_focal", "고형종괴")
    c3 = _cat_mark(data, "kd_focal", "기타병변")
    line9 = f"신장의 국소병변 \t\t\t{m0} 없음 \t\t{m1} 있음 ({c1}낭종 {c2}고형종괴 {c3}기타병변)"

    m0, m1 = _presence_marks(data, "kd_hydro")
    rt, lt = _cat_mark(data, "kd_hydro", "우신"), _cat_mark(data, "kd_hydro", "좌신")
    line10 = f"수신증 \t\t\t\t{m0} 없음\t\t{m1} 있음 ({rt}우신 {lt}좌신)"

    m0, m1 = _presence_marks(data, "kd_renal_stone")
    rt, lt = _cat_mark(data, "kd_renal_stone", "우측"), _cat_mark(data, "kd_renal_stone", "좌측")
    detail = (data.get("kd_renal_stone_detail") or "").strip()
    line11 = f"신결석\t\t\t\t{m0} 없음\t\t{m1} 있음 ({rt}우측        {lt}좌측         {detail})"

    m0, m1 = _presence_marks(data, "kd_ureter_stone", URETER_STONE_OPTIONS)
    rt, lt = _cat_mark(data, "kd_ureter_stone", "우측"), _cat_mark(data, "kd_ureter_stone", "좌측")
    detail = (data.get("kd_ureter_stone_detail") or "").strip()
    line12 = f"요관결석\t\t\t\t{m0} 없음 또는 모름\t{m1} 있음 ({rt}우측        {lt}좌측         {detail})"

    m0, m1 = _presence_marks(data, "kd_adrenal")
    rt, lt = _cat_mark(data, "kd_adrenal", "우측"), _cat_mark(data, "kd_adrenal", "좌측")
    line13 = f"부신 이상 \t\t\t{m0} 없음\t\t{m1} 있음 ({rt}우측 {lt}좌측)"

    m0, m1 = _presence_marks(data, "kd_upper_other")
    detail = (data.get("kd_upper_other_detail") or "").strip()
    line14 = f"기타 소견 \t\t\t{m0} 없음\t\t{m1} 있음 ({detail})"

    for idx, text in zip(
        [7, 8, 9, 10, 11, 12, 13, 14],
        [line7, line8, line9, line10, line11, line12, line13, line14],
    ):
        set_paragraph_text(doc.paragraphs[idx], text)

    m0, m1 = _presence_marks(data, "kd_bladder_wall")
    line17 = f"방광벽 비후\t\t\t{m0} 없음\t\t{m1} 있음 "
    m0, m1 = _presence_marks(data, "kd_bladder_tumor")
    line18 = f"방광 종양\t\t\t{m0} 없음\t\t{m1} 있음 "
    m0, m1 = _presence_marks(data, "kd_bladder_stone")
    line19 = f"방광 결석\t\t\t{m0} 없음\t\t{m1} 있음 "
    m0, m1 = _presence_marks(data, "kd_lower_other")
    detail = (data.get("kd_lower_other_detail") or "").strip()
    line20 = f"기타 소견 \t\t\t{m0} 없음\t\t{m1} 있음 ({detail})"

    for idx, text in zip([17, 18, 19, 20], [line17, line18, line19, line20]):
        set_paragraph_text(doc.paragraphs[idx], text)

    t2 = doc.tables[2]
    set_cell_multiline(t2.rows[0].cells[0], data.get("kd_upper_findings", ""), start_index=1)
    _ensure_min_lines(t2.rows[0].cells[0], min_lines=3, start_index=1)
    t3 = doc.tables[3]
    set_cell_multiline(t3.rows[0].cells[0], data.get("kd_lower_findings", ""), start_index=1)
    _ensure_min_lines(t3.rows[0].cells[0], min_lines=3, start_index=1)
    for cell in (t2.rows[0].cells[0], t3.rows[0].cells[0]):
        _set_cell_font_size(cell, 8)
        _set_box_border(cell)

    _fill_trailing_freeform(doc, 23, data.get("kd_conclusion", ""), min_lines=4)

    _compact_spacing(doc)
    for table in doc.tables:
        _tight_cell_margins(table)
        _unbold_table(table)

    doc.save(output_path)


def convert_to_pdf(docx_path, pdf_path):
    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    word = None
    try:
        # DispatchEx always starts a brand-new Word process instead of attaching
        # to one that may already be running (e.g. a leftover instance stuck
        # behind a dialog), which is what made PDF conversion silently hang/fail
        # while the .docx (plain file write, no Word involved) always succeeded.
        word = win32.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable: suppress macro/security prompts
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        wdoc = word.Documents.Open(os.path.abspath(docx_path))
        wdoc.SaveAs(os.path.abspath(pdf_path), FileFormat=17)
        wdoc.Close(False)
    finally:
        if word is not None:
            word.Quit()
        pythoncom.CoUninitialize()


def _kill_stale_hwp():
    # A 한글 instance left stuck behind its security prompt poisons every later
    # COM call ("원격 프로시저를 호출하지 못했습니다"), so clear leftovers first.
    import subprocess

    for name in ("Hwp.exe", "HwpFrame.exe"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", name],
                capture_output=True, check=False,
            )
        except Exception:
            pass


def convert_to_hwp(docx_path, hwp_path):
    """Opens the generated .docx in Hancom Office 한글 and re-saves it as .hwp.
    Requires 한글 (HancomOffice) to be installed on the machine."""
    import pythoncom
    import win32com.client as win32

    _kill_stale_hwp()
    pythoncom.CoInitialize()
    hwp = None
    try:
        # DispatchEx starts a fresh 한글 process (late binding, so no gen_py
        # cache write is needed inside the frozen exe).
        hwp = win32.DispatchEx("HWPFrame.HwpObject")
        try:
            # Approve automation up front so 한글 doesn't stop on its security
            # prompt when opening/saving a file it didn't create.
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        try:
            hwp.SetMessageBoxMode(0x00020000)  # auto-dismiss modal dialogs
        except Exception:
            pass
        if os.path.exists(hwp_path):
            os.remove(hwp_path)
        # format "" lets 한글 auto-detect the .docx; forceopen skips the
        # "another program is using this file" nag.
        hwp.Open(os.path.abspath(docx_path), "", "forceopen:true")
        hwp.SaveAs(os.path.abspath(hwp_path), "HWP", "")
    finally:
        if hwp is not None:
            try:
                hwp.Clear(1)  # discard without a "save changes?" prompt
            except Exception:
                pass
            try:
                hwp.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _generate_hwp(data, output_path, fill_fn, template_path=None):
    """Fills the template (via fill_fn) and writes the report as a 한글
    (.hwp) file. Returns [output_path]."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_docx = os.path.join(tmp_dir, "report.docx")
        fill_fn(data, tmp_docx, template_path=template_path)
        convert_to_hwp(tmp_docx, output_path)
    return [output_path]


def _generate_jpg(data, output_path, fill_fn, template_path=None, dpi=200):
    """Renders the filled report (via fill_fn) as JPG image(s). Returns the
    list of files written (more than one file when the report spans multiple
    pages)."""
    import tempfile

    import fitz  # PyMuPDF

    base, _ = os.path.splitext(output_path)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_docx = os.path.join(tmp_dir, "report.docx")
        tmp_pdf = os.path.join(tmp_dir, "report.pdf")
        fill_fn(data, tmp_docx, template_path=template_path)
        convert_to_pdf(tmp_docx, tmp_pdf)

        written = []
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        with fitz.open(tmp_pdf) as pdf:
            for i, page in enumerate(pdf):
                path = output_path if i == 0 else f"{base}_{i + 1}.jpg"
                pix = page.get_pixmap(matrix=matrix)
                pix.save(path)
                written.append(path)
        return written


def generate_hwp(data, output_path, template_path=None):
    return _generate_hwp(data, output_path, generate_docx, template_path)


def generate_jpg(data, output_path, template_path=None, dpi=200):
    return _generate_jpg(data, output_path, generate_docx, template_path, dpi)


def generate_hwp_scrotal(data, output_path, template_path=None):
    return _generate_hwp(data, output_path, generate_docx_scrotal, template_path)


def generate_jpg_scrotal(data, output_path, template_path=None, dpi=200):
    return _generate_jpg(data, output_path, generate_docx_scrotal, template_path, dpi)


def generate_hwp_kidney(data, output_path, template_path=None):
    return _generate_hwp(data, output_path, generate_docx_kidney, template_path)


def generate_jpg_kidney(data, output_path, template_path=None, dpi=200):
    return _generate_jpg(data, output_path, generate_docx_kidney, template_path, dpi)
