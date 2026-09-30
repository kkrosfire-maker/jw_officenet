"""openpyxl 로 저장하면 사라지는 슬라이서를 원본에서 다시 옮겨 붙인다.

openpyxl 은 슬라이서를 모른다. 슬라이서는 엑셀 파일(=zip) 안에서
`xl/slicers/`, `xl/slicerCaches/` 부품과 그것을 화면에 앉히는 `xl/drawings/`
부품으로 되어 있는데, openpyxl 은 이 부품들을 읽지도 쓰지도 않는다. 그래서
파일을 열어 저장하면 표는 남고 슬라이서만 통째로 빠진다.

여기서는 저장이 끝난 뒤에 **원본에서 그 부품들을 그대로 복사**해 넣는다.
부품을 새로 만드는 것이 아니라 원본 바이트를 옮기므로 슬라이서의 모양·위치·
정렬 순서가 원본과 같다. 짝은 시트 이름으로 찾으므로 행 수가 달라진 파일
(연도만 남긴 바탕화면 파일)에도 그대로 붙는다.
"""
from __future__ import annotations

import posixpath
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

REL_WORKSHEET = f"{NS_REL}/worksheet"
REL_DRAWING = f"{NS_REL}/drawing"
REL_SLICER = "http://schemas.microsoft.com/office/2007/relationships/slicer"
REL_SLICER_CACHE = "http://schemas.microsoft.com/office/2007/relationships/slicerCache"

WORKBOOK = "xl/workbook.xml"
CONTENT_TYPES = "[Content_Types].xml"

RID = re.compile(r'\br:id="([^"]+)"')


@dataclass(frozen=True)
class _Rel:
    id: str
    type: str
    part: str          # zip 안의 정규화된 경로


@dataclass
class _SheetJob:
    name: str
    target_part: str
    slicer_rels: list[_Rel]
    drawing_rel: Optional[_Rel]
    ext: str           # 원본 시트의 slicerList ext 조각


# ---------------------------------------------------------------- zip / 관계

def _rels_name(part: str) -> str:
    folder, base = posixpath.split(part)
    return posixpath.join(folder, "_rels", base + ".rels")


def _resolve(base_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def _read_rels(zf: zipfile.ZipFile, part: str) -> list[_Rel]:
    name = _rels_name(part)
    if name not in zf.namelist():
        return []
    root = ET.fromstring(zf.read(name))
    rels = []
    for node in root.findall(f"{{{NS_PKG_REL}}}Relationship"):
        if node.get("TargetMode") == "External":
            continue
        rels.append(
            _Rel(
                id=node.get("Id", ""),
                type=node.get("Type", ""),
                part=_resolve(part, node.get("Target", "")),
            )
        )
    return rels


def _sheet_parts(zf: zipfile.ZipFile) -> dict[str, str]:
    """시트 이름 → 워크시트 부품 경로."""
    by_rid = {r.id: r.part for r in _read_rels(zf, WORKBOOK) if r.type == REL_WORKSHEET}
    root = ET.fromstring(zf.read(WORKBOOK))
    sheets = {}
    for node in root.iter(f"{{{NS_MAIN}}}sheet"):
        part = by_rid.get(node.get(f"{{{NS_REL}}}id") or "")
        if part:
            sheets[node.get("name", "")] = part
    return sheets


def _free_rids(rels: list[_Rel]) -> Iterator[str]:
    used = {r.id for r in rels}
    number = 1
    while True:
        candidate = f"rId{number}"
        number += 1
        if candidate not in used:
            used.add(candidate)
            yield candidate


# ---------------------------------------------------------------- 문자열 손질
#
# 부품을 XML 로 다시 써내면 openpyxl 이 쓴 다른 내용까지 바뀔 수 있어서,
# 고칠 자리에만 문자열을 끼워 넣는다.

def _ext_blocks(xml: str) -> Iterator[str]:
    """`<ext ...>...</ext>` 조각을 하나씩 돌려준다 (중첩은 없다고 본다)."""
    start = 0
    while True:
        open_at = xml.find("<ext ", start)
        if open_at < 0:
            return
        close_at = xml.find("</ext>", open_at)
        if close_at < 0:
            return
        yield xml[open_at : close_at + len("</ext>")]
        start = close_at + len("</ext>")


def _find_ext(xml: str, needle: str) -> str:
    for block in _ext_blocks(xml):
        if needle in block:
            return block
    return ""


def _remap_rids(fragment: str, mapping: dict[str, str]) -> str:
    """조각 안의 r:id 를 새 관계 ID 로 바꾸고 r 접두사를 그 자리에서 선언한다.

    이미 붙어 있던 선언은 먼저 떼어낸다. 한 번 고친 파일을 다시 원본으로 쓸 때
    (원본 → 바탕화면 파일) 같은 선언이 두 번 들어가면 XML 이 깨진다.
    """
    fragment = fragment.replace(f' xmlns:r="{NS_REL}"', "")

    def swap(match: re.Match) -> str:
        return f'xmlns:r="{NS_REL}" r:id="{mapping.get(match.group(1), match.group(1))}"'

    return RID.sub(swap, fragment)


def _add_ext(xml: str, root_tag: str, ext: str) -> str:
    """`<extLst>` 는 부모의 맨 끝에 와야 한다. 있으면 그 안에, 없으면 새로 만든다."""
    closing = f"</{root_tag}>"
    end = xml.rindex(closing)
    if xml[:end].rstrip().endswith("</extLst>"):
        at = xml.rindex("</extLst>", 0, end)
        return xml[:at] + ext + xml[at:]
    return xml[:end] + f"<extLst>{ext}</extLst>" + xml[end:]


def _add_drawing(xml: str, rid: str) -> str:
    """`<drawing>` 은 pageSetup 뒤, tableParts/extLst 앞에 와야 한다."""
    element = f'<drawing xmlns:r="{NS_REL}" r:id="{rid}"/>'
    for anchor in ("<tableParts", "<extLst"):
        at = xml.rfind(anchor)
        if at > 0:
            return xml[:at] + element + xml[at:]
    at = xml.rindex("</worksheet>")
    return xml[:at] + element + xml[at:]


def _add_rels(xml: str, rels: list[tuple[str, str, str]]) -> str:
    """(id, type, part) 들을 관계 파일에 더한다."""
    added = "".join(
        f'<Relationship Id="{rid}" Type="{rtype}" Target="/{part}"/>'
        for rid, rtype, part in rels
    )
    at = xml.rindex("</Relationships>")
    return xml[:at] + added + xml[at:]


def _empty_rels() -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{NS_PKG_REL}"></Relationships>'
    ).encode("utf-8")


def _add_content_types(xml: str, donor_ct: str, parts: list[str]) -> str:
    """복사한 부품의 형식 선언을 원본에서 가져와 더한다."""
    added = []
    for part in parts:
        if f'PartName="/{part}"' in xml:
            continue
        override = re.search(r'<Override PartName="/%s"[^>]*/>' % re.escape(part), donor_ct)
        if override:
            added.append(override.group(0))
            continue
        extension = posixpath.splitext(part)[1].lstrip(".")
        if not extension or re.search(r'<Default Extension="%s"' % re.escape(extension), xml, re.I):
            continue
        default = re.search(
            r'<Default Extension="%s"[^>]*/>' % re.escape(extension), donor_ct, re.I
        )
        if default:
            added.append(default.group(0))
    if not added:
        return xml
    at = xml.rindex("</Types>")
    return xml[:at] + "".join(added) + xml[at:]


# ---------------------------------------------------------------- 본체

def _collect(zf: zipfile.ZipFile, part: str, into: dict[str, bytes], skip: set[str]) -> None:
    """부품과 그 부품이 가리키는 것들을 함께 챙긴다."""
    if part in into or part not in zf.namelist():
        return
    into[part] = zf.read(part)
    rels_name = _rels_name(part)
    if rels_name in zf.namelist():
        into[rels_name] = zf.read(rels_name)
        for rel in _read_rels(zf, part):
            if rel.part not in skip:
                _collect(zf, rel.part, into, skip)


def _jobs(donor_zip: zipfile.ZipFile, target_zip: zipfile.ZipFile) -> list[_SheetJob]:
    target_sheets = _sheet_parts(target_zip)
    jobs = []
    for name, donor_part in _sheet_parts(donor_zip).items():
        rels = _read_rels(donor_zip, donor_part)
        slicer_rels = [r for r in rels if r.type == REL_SLICER]
        if not slicer_rels:
            continue
        target_part = target_sheets.get(name)
        if target_part is None:
            continue
        if any(r.type == REL_SLICER for r in _read_rels(target_zip, target_part)):
            continue  # 이미 살아 있다
        jobs.append(
            _SheetJob(
                name=name,
                target_part=target_part,
                slicer_rels=slicer_rels,
                drawing_rel=next((r for r in rels if r.type == REL_DRAWING), None),
                ext=_find_ext(donor_zip.read(donor_part).decode("utf-8"), "slicerList"),
            )
        )
    return jobs


def restore_slicers(donor: str | Path, target: str | Path) -> int:
    """`donor` 의 슬라이서를 `target` 에 옮긴다. 옮긴 슬라이서 개수를 돌려준다.

    시트 이름으로 짝을 맞추므로 두 파일의 행 수가 달라도 된다. 원본에 슬라이서가
    없거나 대상에 이미 살아 있으면 아무것도 하지 않고 0 을 돌려준다.
    """
    donor, target = Path(donor), Path(target)
    if not donor.exists() or not target.exists():
        return 0

    with zipfile.ZipFile(donor) as donor_zip, zipfile.ZipFile(target) as target_zip:
        jobs = _jobs(donor_zip, target_zip)
        if not jobs:
            return 0

        parts = {name: target_zip.read(name) for name in target_zip.namelist()}
        donor_ct = donor_zip.read(CONTENT_TYPES).decode("utf-8")
        copied: dict[str, bytes] = {}
        keep = set(parts)          # 대상에 이미 있는 부품은 건드리지 않는다
        slicers = 0

        # 1) 워크북 수준 — 슬라이서 캐시
        cache_rels = [r for r in _read_rels(donor_zip, WORKBOOK) if r.type == REL_SLICER_CACHE]
        cache_map: dict[str, str] = {}
        new_rels: list[tuple[str, str, str]] = []
        rids = _free_rids(_read_rels(target_zip, WORKBOOK))
        for rel in cache_rels:
            _collect(donor_zip, rel.part, copied, keep)
            cache_map[rel.id] = next(rids)
            new_rels.append((cache_map[rel.id], REL_SLICER_CACHE, rel.part))

        if new_rels:
            rels_name = _rels_name(WORKBOOK)
            parts[rels_name] = _add_rels(
                parts.get(rels_name, _empty_rels()).decode("utf-8"), new_rels
            ).encode("utf-8")
            ext = _find_ext(donor_zip.read(WORKBOOK).decode("utf-8"), "slicerCaches")
            if ext:
                parts[WORKBOOK] = _add_ext(
                    parts[WORKBOOK].decode("utf-8"), "workbook", _remap_rids(ext, cache_map)
                ).encode("utf-8")

        # 2) 시트 수준 — 슬라이서 부품과 그것을 앉히는 그림
        for job in jobs:
            rids = _free_rids(_read_rels(target_zip, job.target_part))
            added: list[tuple[str, str, str]] = []
            slicer_map: dict[str, str] = {}
            for rel in job.slicer_rels:
                _collect(donor_zip, rel.part, copied, keep)
                slicer_map[rel.id] = next(rids)
                added.append((slicer_map[rel.id], REL_SLICER, rel.part))
                slicers += donor_zip.read(rel.part).decode("utf-8").count("<slicer ")

            sheet_xml = parts[job.target_part].decode("utf-8")
            if job.drawing_rel is not None:
                _collect(donor_zip, job.drawing_rel.part, copied, keep)
                drawing_rid = next(rids)
                added.append((drawing_rid, REL_DRAWING, job.drawing_rel.part))
                sheet_xml = _add_drawing(sheet_xml, drawing_rid)
            if job.ext:
                sheet_xml = _add_ext(sheet_xml, "worksheet", _remap_rids(job.ext, slicer_map))

            parts[job.target_part] = sheet_xml.encode("utf-8")
            rels_name = _rels_name(job.target_part)
            parts[rels_name] = _add_rels(
                parts.get(rels_name, _empty_rels()).decode("utf-8"), added
            ).encode("utf-8")

        # 3) 부품 형식 선언
        parts.update(copied)
        parts[CONTENT_TYPES] = _add_content_types(
            parts[CONTENT_TYPES].decode("utf-8"), donor_ct, sorted(copied)
        ).encode("utf-8")

    temporary = target.with_name(target.name + ".slicer.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as out:
        for name, data in parts.items():
            out.writestr(name, data)
    shutil.move(str(temporary), str(target))
    return slicers
