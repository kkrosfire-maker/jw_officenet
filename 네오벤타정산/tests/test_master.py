"""T14 — 제품 마스터 초기화와 대조 리포트."""
from __future__ import annotations

from core import lawdata
from core.master import Product, ProductMaster, Settings
from core.utils import parse_threshold

from .conftest import LAWDATA


def test_t14_초기화_대조_리포트(init_result):
    """변환자료 값과 요율표 값이 다른 항목을 찾는다.

    PRD 가 든 3건은 반드시 나와야 한다. 요율표에서 보험코드를 되찾은 제품도
    대조 대상이 되므로(아도르정 60→58% 등) 그보다 많이 나오는 것이 정상이다.
    """
    found = {(d.제품명, d.항목, d.변환엑셀값, d.요율표값) for d in init_result.diffs}
    assert ("카프릴정50mg", "단가", 170, 497) in found
    assert ("토피솔밀크로션 20g", "단가", 3754, 3574) in found
    assert ("코부테롤패취0.5mg", "수수료", 0.36, 0.4) in found
    assert len(init_result.diffs) >= 3
    # 모든 차이는 실제로 값이 다른 것이어야 한다
    assert all(d.변환엑셀값 != d.요율표값 for d in init_result.diffs)


def test_요율표_역매칭으로_보험코드를_되찾는다(init_result):
    """변환엑셀에만 있던 제품도 요율표에서 이름이 같으면 코드를 채운다."""
    names = {name for name, *_ in init_result.recovered}
    assert "아도르정10mg" in names
    assert "파리아톤정10mg" in names
    # 자동으로 채운 것은 이름이 정확히 같은 경우뿐이다
    assert all(score >= 1.0 for *_, score in init_result.recovered)
    master = init_result.master
    for name, code, *_ in init_result.recovered:
        assert master.by_code(code) is not None


def test_비슷하기만_한_이름은_자동으로_채우지_않는다(init_result):
    """용량이 다른 제품이 잘못 붙는 것을 막는다 (75mg vs 37.5mg)."""
    suggested = {name for name, *_ in init_result.suggestions}
    assert "록사틴서방캡슐 75mg" in suggested
    assert all(score < 1.0 for *_, score in init_result.suggestions)
    # 추천만 하고 코드는 비워 둔다
    master = init_result.master
    for name, *_ in init_result.suggestions:
        product = next(p for p in master.products if p.최종제품명 == name)
        assert product.code_unknown


def test_초기화_lawdata_코드쌍(init_result):
    assert init_result.pair_count == 49


def test_초기화된_마스터가_lawdata_코드를_모두_안다(init_result):
    master = init_result.master
    pairs = lawdata.product_code_pairs(LAWDATA)
    unknown = [
        code
        for code, names in pairs.items()
        if master.by_code(code) is None and not any(master.by_alias(n) for n in names)
    ]
    assert unknown == []


def test_코드_미확인_제품은_none_으로_표시된다(init_result):
    unknown = [p for p in init_result.master.products if p.code_unknown]
    assert len(unknown) == len(init_result.unmatched)
    assert all(p.code_display == "none" for p in unknown)
    known = [p for p in init_result.master.products if not p.code_unknown]
    assert all(p.code_display == p.보험코드 for p in known)


def test_최소인정금액_초기화(init_result):
    settings = init_result.settings
    assert settings.threshold("명문제약")["value"] == 100_000
    assert settings.threshold("코오롱제약")["value"] == 100_000
    # '없음' 은 판정하지 않는다
    보령 = settings.threshold("보령제약")
    assert 보령["known"] and 보령["value"] is None
    # 금액인정 시트에 없는 안국뉴팜은 기본값 100000
    assert settings.threshold("안국뉴팜")["value"] == 100_000


def test_애매한_금액은_확인필요로_남는다(init_result):
    settings = init_result.settings
    assert settings.thresholds["에이프로젠제약"]["needs_input"] is True
    assert settings.thresholds["바이넥스"]["needs_input"] is True


def test_제약사명_별칭(init_result):
    assert init_result.settings.company_display("유니메드제약") == "유니메드"
    assert init_result.settings.company_display("명문제약") == "명문제약"


def test_최소금액_파싱():
    assert parse_threshold("10만원") == (100_000, False)
    assert parse_threshold("30만원") == (300_000, False)
    assert parse_threshold("없음") == (None, False)
    assert parse_threshold("10만원 (26.04부터)")[1] is True
    assert parse_threshold("1만원 이상")[1] is True


def test_코드연결로_이전코드가_쌓인다():
    master = ProductMaster([Product(보험코드="AAA", 최종제품명="코미정", 별칭=["코미정"])])
    product = master.by_code("AAA")
    master.link_code(product, "BBB", "코미정[삭제된 제품]")
    assert product.보험코드 == "BBB"
    assert "AAA" in product.이전보험코드
    assert master.by_code("AAA") is product
    assert master.by_code("BBB") is product
    assert master.by_alias("코미정[삭제된 제품]") is product


def test_마스터_저장과_로딩(tmp_path, init_result):
    path = tmp_path / "product_master.xlsx"
    init_result.master.save(path)
    again = ProductMaster.load(path)
    assert len(again.products) == len(init_result.master.products)
    before = {p.보험코드: p for p in init_result.master.products}
    for product in again.products:
        origin = before[product.보험코드]
        assert product.최종제품명 == origin.최종제품명
        assert product.별칭 == origin.별칭
        assert product.구간인센 == origin.구간인센


def test_설정_저장과_로딩(tmp_path, init_result):
    path = tmp_path / "settings.json"
    init_result.settings.save(path)
    again = Settings.load(path)
    assert again.company_aliases == init_result.settings.company_aliases
    assert again.threshold("안국뉴팜")["value"] == 100_000
