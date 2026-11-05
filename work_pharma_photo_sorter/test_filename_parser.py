import pytest

from filename_parser import parse_filename
import photo_sort
import pharma_zip

LOOKUP = {
    "미래웰_연세산부인과의원": "A",
    "미더스메디칼의원": "B",
    "다솜의원(연제구)": "C",
    "다솜의원": "D",
    "서울 가정의원": "E",
    "백세내과의원": "F",
    "연세산부인과의원": "G",
    "오혜연산부인과의원": "H",
}


@pytest.mark.parametrize("name,pharma", [
    ("휘마의원 9월 구주제약2.png", "구주제약"),
    ("인성의원 9월 알리코제약(주)2.png", "알리코제약"),
    ("인성의원 9월 (주)셀트리온제약.png", "셀트리온제약"),
    ("개나리소아청소년과병원 7월 코오롱제약_1.png", "코오롱제약"),
    ("미더스메디칼_삼익제약.jpg", "삼익제약"),
    ("미더스 (1).jpg", "기타"),
    ("인성의원 10월 (주)셀트리온제약 2.jpg", "셀트리온제약"),
    ("라임비뇨기과의원 10월 (주)제뉴원사이언스 (1).jpg", "제뉴원사이언스"),
    ("논현메디칼의원 09월 ▲ 서울제약.png", "서울제약"),
])
def test_pharma(name, pharma):
    assert parse_filename(name).pharma == pharma
    assert pharma_zip.extract_pharma(name) == pharma


@pytest.mark.parametrize("name,key", [
    ("미래웰_연세산부인과의원 12월 아주약품(주).png", "미래웰_연세산부인과의원"),
    ("미더스메디칼_삼익제약.jpg", "미더스메디칼의원"),          # 유사 매칭
    ("다솜의원(연제구) 9월 명문제약.png", "다솜의원(연제구)"),
    ("서울 가정의원 9월 삼익제약.png", "서울 가정의원"),        # 병원명에 공백
    ("(추가) 연세산부인과 08월 명문2.png", "연세산부인과의원"),  # 앞의 (추가) 제거 후 유사 매칭
    ("백세내과 9월 안국약품.png", None),                        # 엑셀에 '의원' 붙기 전 이름
])
def test_hospital(name, key):
    r = photo_sort.classify([name], LOOKUP)[0]
    assert (r.matched_key or None) == key


def test_similar_name_is_not_misrouted():
    """엑셀에 없는 '연세산부인과의원'이 이름이 비슷한 '오혜연산부인과의원'으로 가면 안 된다."""
    lookup = {"오혜연산부인과의원": "H"}
    r = photo_sort.classify(["연세산부인과의원 9월 명문제약.png"], lookup)[0]
    assert r.match_type == "none"


PAREN_LOOKUP = {
    "하나삼성의원(김포)": "건스",
    "다솜의원(양산)": "네오벤타",
    "다솜의원(연제구)": "네오벤타",
    "연세산부인과의원(김포)": "정원유니어스",
    "연세산부인과의원(계양구)": "미래웰메디칼",
}


@pytest.mark.parametrize("name,manager", [
    ("하나삼성의원 10월 알리코제약.jpg", "건스"),          # 파일명에 괄호 없음
    ("하나삼성의원(경기) 10월 알리코제약.jpg", "건스"),    # 파일명 괄호가 엑셀과 다름
    ("다솜의원 10월 명문제약.jpg", "네오벤타"),            # 지점은 달라도 담당자가 같으면 묶음
    ("연세산부인과의원(김포) 10월 명문제약.jpg", "정원유니어스"),  # 동명 지점은 괄호로 구분
    ("연세산부인과의원(계양구) 10월 명문제약.jpg", "미래웰메디칼"),
])
def test_parenthetical_ignored_unless_branches_differ(name, manager):
    r = photo_sort.classify([name], PAREN_LOOKUP)[0]
    assert r.match_type != "none" and r.manager == manager


def test_ambiguous_branch_is_not_guessed():
    """담당자가 갈리는 동명 지점은 괄호 없이는 섞지 않고 미분류로 남긴다."""
    r = photo_sort.classify(["연세산부인과의원 10월 명문제약.jpg"], PAREN_LOOKUP)[0]
    assert r.match_type == "none"
    r = photo_sort.classify(["연세산부인과의원(인천) 10월 명문제약.jpg"], PAREN_LOOKUP)[0]
    assert r.match_type == "none"
