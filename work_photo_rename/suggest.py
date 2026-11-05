"""제약사 후보·자동 입력 모듈 — "이 병원에서 이 제약사가 후보인가 / 자동으로 채워도 되나"의 규칙을 한곳에 모은다.

화면(main)은 아래 결과를 그리기만 한다.
  - candidates     : 제약사 칸에 보여 줄 기본 후보와 보조 후보(입력할 때만 뒤에 덧붙는 후보)
  - autofill       : 사진에서 읽은 제약사 글자로 칸을 미리 채울 이름
  - sole_pharma    : 그 병원·처방월에 제약사가 하나뿐이면 그 이름
master 는 ledger.MasterExcel (병원·제약사 이력). prefer 는 사용자가 최근에 저장한 표기({정규화 이름: 표기}).
"""
from names import norm


def candidates(master, hospital: str, month: str, prefer=None):
    """(기본 후보, 보조 후보).
    엑셀에 있는 병원: 기본 = 그 병원에서 최근 3개월 안에 처방이 나온 제약사(선택한 월이 맨 앞, 가나다순),
                      보조 = 그 밖의 제약사 전체 (새 제약사 대비).
    엑셀에 없는 병원: 기본 = 제약사 전체, 보조 = 없음."""
    prefer = prefer or {}
    if hospital in set(master.hospitals()):
        mine = master.names.dedupe(master.hospital_pharmas(hospital, month), prefer, sort=True)
        rest = master.names.dedupe(master.all_pharmas(), prefer, drop_norms={norm(p) for p in mine}, sort=True)
        return mine, rest
    return master.names.dedupe(master.all_pharmas(), prefer, sort=True), []


def autofill(master, hospital: str, current: str, raw, prefer=None):
    """사진에서 읽은 제약사 글자(raw)와 가장 비슷한 이름. 칸이 이미 채워져 있거나 글자가 없거나 비슷한 게 없으면 None.
    (그 병원 제약사는 점수를 조금 더 쳐줄 뿐, 다른 병원 제약사도 대상이다)"""
    if (current or "").strip() or not raw:
        return None
    name, _score = master.match_pharma(raw, (hospital or "").strip(), prefer)
    return name


def sole_pharma(master, hospital: str, month: str, year, current: str = ""):
    """그 병원·처방월에 엑셀에 올라 있는 제약사가 정확히 하나이고 칸이 비어 있으면 그 이름, 아니면 None."""
    if (current or "").strip():
        return None
    mine = master.pharmas_for((hospital or "").strip(), month, year)
    return mine[0] if len(mine) == 1 else None
