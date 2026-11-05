"""설정·메모 보관 모듈 — 프로그램이 기억해 두는 것들(JSON 파일)의 키와 읽기·쓰기를 한곳에서 안다.

Settings  : JPG 저장 폴더(out_dir), 최근에 쓴 제약사 표기(recent_pharma), 병원별로 목록에서 지운 제약사(hidden)
MemoStore : 병원×제약사별 특이사항 메모 (월이 바뀌어도 이어서 보인다)
화면(main)은 딕셔너리 키 이름을 알 필요 없이 아래 메서드만 부른다.
"""
import json
from pathlib import Path

from names import memo_key, norm


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return default


class Settings:
    def __init__(self, path):
        self.path = Path(path)
        self._d = _read_json(self.path, {})
        if not isinstance(self._d, dict):
            self._d = {}
        self.hidden = set(self._d.get("hidden_pharma", []))     # memo_key 들 (Ledger.hidden 과 같은 집합을 같이 쓴다)

    def save(self):
        """실패해도 프로그램은 계속 쓰게 조용히 넘어간다 (설정일 뿐이라). 성공 여부를 돌려준다."""
        self._d["hidden_pharma"] = sorted(self.hidden)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._d, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception:
            return False

    # JPG 저장 폴더
    @property
    def out_dir(self):
        v = self._d.get("out_dir")
        return Path(v) if v else None

    def set_out_dir(self, d):
        self._d["out_dir"] = str(d)
        self.save()

    # 최근에 쓴 제약사 표기
    @property
    def recent_pharma(self) -> dict:
        return self._d.setdefault("recent_pharma", {})

    def remember_pharma(self, pharma: str):
        """최근에 쓴 표기를 기억 → 같은 이름(norm)의 비슷한 표기 중 이것만 후보에 보인다."""
        if norm(pharma):
            self.recent_pharma[norm(pharma)] = pharma.strip()
            self.save()

    # 목록에서 지운 제약사
    def hide_pharma(self, hospital, pharma):
        self.hidden.add(memo_key(hospital, pharma))
        self.save()

    def unhide_pharma(self, hospital, pharma) -> bool:
        """지웠던 제약사를 다시 저장하면 목록에 복귀. 실제로 복귀시켰으면 True."""
        k = memo_key(hospital, pharma)
        if k not in self.hidden:
            return False
        self.hidden.discard(k)
        self.save()
        return True


class MemoStore:
    def __init__(self, path):
        self.path = Path(path)
        self.data = _read_json(self.path, {})
        if not isinstance(self.data, dict):
            self.data = {}

    def set(self, hospital, pharma, text):
        """메모를 바꾸고 파일에 쓴다. 파일 쓰기에 실패하면 예외."""
        self.data[memo_key(hospital, pharma)] = text
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
