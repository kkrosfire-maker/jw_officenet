import json
import os

import webview

import store

HTML_NAME = "정원유니어스_정산대시보드.html"
TITLE = "정원유니어스(주) 정산 대시보드"


class Api:
    def __init__(self):
        self._window = None
        self._dirty = False

    def load(self):
        d, fresh = store.load_dash()
        return {"data": d, "fresh": fresh, "chat": store.chat_status(d)}

    def rev(self):
        return store.current_rev()

    def save(self, data_json, base_rev):
        d = json.loads(data_json)
        rev = store.save_dash(d, int(base_rev))
        if rev is None:
            return {"ok": False, "conflict": True}
        return {"ok": True, "rev": rev, "saved_at": d.get("saved_at", "")}

    def import_chat(self):
        files = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("카톡 대화 내보내기 (*.txt)", "모든 파일 (*.*)"))
        if not files:
            return {"ok": False, "cancel": True}
        r = store.import_chat(files[0] if isinstance(files, (list, tuple)) else files)
        r["chat"] = store.chat_status()
        return r

    def excerpt(self, ev):
        return store.excerpt(ev)

    def chat_range(self, start, end):
        return store.chat_range(int(start), int(end))

    def set_dirty(self, v):
        # 저장 안 된 변경이 있을 때만 창 닫기 전에 확인창을 띄운다
        self._dirty = bool(v)
        if self._window is not None:
            self._window.confirm_close = self._dirty


def main():
    # 예전(GS파마) exe와 같은 웹 저장소를 써서, 거기 남은 상태·메모를 첫 실행 때 옮겨온다
    web_storage = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "GS파마정산대시보드")
    os.makedirs(web_storage, exist_ok=True)
    api = Api()
    webview.settings["ALLOW_DOWNLOADS"] = True
    win = webview.create_window(TITLE, store.resource(HTML_NAME), js_api=api,
                                width=1360, height=900, min_size=(900, 600))
    api._window = win
    webview.start(private_mode=False, storage_path=web_storage,
                  localization={"global.quitConfirmation": "저장하지 않은 변경이 있습니다.\n저장하지 않고 닫을까요? (확인 = 닫기, 취소 = 돌아가기)"})


if __name__ == "__main__":
    main()
