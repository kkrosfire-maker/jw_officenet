#!/usr/bin/env python3
"""
공유오피스 입주자 뉴스 탐색기
공유오피스/소호 사용자 대상 주제 자동 탐색 → 뉴스/블로그/유튜브 TOP 5 제공
"""

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import webbrowser
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from typing import Optional

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_finder_config.json")

CANDIDATE_TOPICS = [
    # 공유오피스 / 소호 직접 관련
    "공유오피스 사업자등록",
    "소호사무실 계약 주의사항",
    "가상오피스 주소 사업자등록",
    "비상주 사업자등록",
    "공유오피스 비용처리",
    # 법인 설립 / 전환
    "1인 법인 설립 비용",
    "개인사업자 법인 전환",
    "법인 설립 절차",
    # 세금 / 회계
    "법인세 신고방법",
    "부가가치세 신고",
    "법인카드 경비처리",
    "세무기장 비용",
    "전자세금계산서 발행",
    # 고용 / 계약
    "프리랜서 계약서 작성",
    "외주용역 세금",
    # 금융 / 지원
    "소상공인 정부지원사업",
    "법인 사업자 대출",
    "스타트업 창업지원금",
    # 운영
    "1인 기업 4대보험",
    "대표이사 급여 설정",
]

C = {
    'bg':      '#f0f2f8',
    'header':  '#1a2744',
    'accent':  '#e8b84b',
    'card':    '#ffffff',
    'text':    '#2d3436',
    'sub':     '#636e72',
    'sep':     '#dfe6e9',
    'news':    '#0984e3',
    'blog':    '#00b894',
    'youtube': '#d63031',
}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    title: str
    url:   str
    meta:  str          # 날짜(뉴스) / 블로거명(블로그) / 채널명(유튜브)
    desc:  str = ''     # 요약 (유튜브는 없음)


# ── Search client (UI와 분리된 데이터 계층) ───────────────────────────────────

class SearchClient:
    """자격증명을 인스턴스에 고정 → 스레드에서 안전하게 호출 가능"""

    def __init__(self, naver_id: str, naver_secret: str, yt_key: str = ''):
        self.naver_id     = naver_id
        self.naver_secret = naver_secret
        self.yt_key       = yt_key

    # ── Naver ─────────────────────────────────────────────────────────────────

    def _naver_raw(self, query: str, kind: str, display: int, sort: str) -> list[dict]:
        url = f"https://openapi.naver.com/v1/search/{kind}.json"
        headers = {
            'X-Naver-Client-Id':     self.naver_id,
            'X-Naver-Client-Secret': self.naver_secret,
        }
        params = {'query': query, 'display': display, 'sort': sort}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json().get('items', [])
        except Exception:
            pass
        return []

    def _naver_total(self, query: str) -> int:
        url = f"https://openapi.naver.com/v1/search/news.json"
        headers = {
            'X-Naver-Client-Id':     self.naver_id,
            'X-Naver-Client-Secret': self.naver_secret,
        }
        params = {'query': query, 'display': 1, 'sort': 'date'}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json().get('total', 0)
        except Exception:
            pass
        return 0

    def search_news(self, query: str, n: int = 5) -> list[SearchResult]:
        items = self._naver_raw(query, 'news', display=n, sort='date')
        return [
            SearchResult(
                title=_strip_html(it.get('title', '')),
                url=it.get('originallink') or it.get('link', ''),
                meta=it.get('pubDate', '')[:16],
                desc=_strip_html(it.get('description', ''))[:90],
            )
            for it in items
        ]

    def search_blog(self, query: str, n: int = 5) -> list[SearchResult]:
        # 이미 사업자 키워드가 포함된 토픽은 중복 추가하지 않음
        blog_q = query if any(k in query for k in ('사업자', '법인', '프리랜서')) \
                       else query + ' 사업자'
        items = self._naver_raw(blog_q, 'blog', display=n, sort='sim')
        return [
            SearchResult(
                title=_strip_html(it.get('title', '')),
                url=it.get('link', ''),
                meta=it.get('bloggername', ''),
                desc=_strip_html(it.get('description', ''))[:90],
            )
            for it in items
        ]

    # ── YouTube ───────────────────────────────────────────────────────────────

    def search_youtube(self, query: str, n: int = 5) -> list[SearchResult]:
        if not self.yt_key:
            return []
        published_after = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        params = {
            'part':              'snippet',
            'q':                 query + ' 사업자',
            'type':              'video',
            'maxResults':        n,
            'order':             'relevance',
            'publishedAfter':    published_after,
            'regionCode':        'KR',
            'relevanceLanguage': 'ko',
            'key':               self.yt_key,
        }
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/search",
                             params=params, timeout=10)
            if r.status_code == 200:
                items = r.json().get('items', [])
                return [
                    SearchResult(
                        title=sn.get('title', ''),
                        url=f"https://www.youtube.com/watch?v={it.get('id',{}).get('videoId','')}",
                        meta=f"📺 {sn.get('channelTitle','')}  |  {sn.get('publishedAt','')[:10]}",
                    )
                    for it in items
                    if (sn := it.get('snippet', {}))
                ]
        except Exception:
            pass
        return []

    def rank_topics(self, topics: list[str],
                    progress_cb=None) -> list[tuple[str, int]]:
        """각 토픽의 최근 뉴스 기사 수로 순위 결정"""
        scores: dict[str, int] = {}
        for i, topic in enumerate(topics):
            scores[topic] = self._naver_total(topic)
            if progress_cb:
                progress_cb(i + 1)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    for code, char in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"'),('&#39;',"'")]:
        text = text.replace(code, char)
    return text.strip()


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class AppConfig:
    naver_id:     str = ''
    naver_secret: str = ''
    yt_key:       str = ''

    @classmethod
    def load(cls) -> 'AppConfig':
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                return cls(
                    naver_id=d.get('naver_id', ''),
                    naver_secret=d.get('naver_secret', ''),
                    yt_key=d.get('yt_key', ''),
                )
            except Exception:
                pass
        return cls()

    def save(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'naver_id': self.naver_id,
                       'naver_secret': self.naver_secret,
                       'yt_key': self.yt_key},
                      f, ensure_ascii=False, indent=2)


# ── UI ────────────────────────────────────────────────────────────────────────

class NewsFinderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("공유오피스 입주자 뉴스 탐색기")
        self.root.geometry("1320x860")
        self.root.configure(bg=C['bg'])
        self.root.resizable(True, True)

        # StringVar — UI 바인딩 전용 (스레드에서 직접 읽지 않음)
        self.sv_naver_id     = tk.StringVar()
        self.sv_naver_secret = tk.StringVar()
        self.sv_yt_key       = tk.StringVar()

        self.popular_topics: list[str] = []

        cfg = AppConfig.load()
        self.sv_naver_id.set(cfg.naver_id)
        self.sv_naver_secret.set(cfg.naver_secret)
        self.sv_yt_key.set(cfg.yt_key)

        self._build_ui()
        self._init_result_panels()

    # ── Config helpers ────────────────────────────────────────────────────────

    def _current_config(self) -> AppConfig:
        return AppConfig(
            naver_id=self.sv_naver_id.get(),
            naver_secret=self.sv_naver_secret.get(),
            yt_key=self.sv_yt_key.get(),
        )

    def _make_client(self) -> SearchClient:
        cfg = self._current_config()
        return SearchClient(cfg.naver_id, cfg.naver_secret, cfg.yt_key)

    # ── UI Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_search_row()
        self._build_topic_row()
        tk.Frame(self.root, bg=C['sep'], height=1).pack(fill='x', padx=20, pady=4)
        self._build_results()

    def _build_header(self):
        h = tk.Frame(self.root, bg=C['header'], height=64)
        h.pack(fill='x')
        h.pack_propagate(False)

        tk.Label(h, text="  공유오피스 입주자 뉴스 탐색기",
                 font=('맑은 고딕', 17, 'bold'),
                 bg=C['header'], fg='white').pack(side='left', padx=20)

        tk.Button(h, text="⚙  API 설정",
                  font=('맑은 고딕', 10),
                  bg=C['accent'], fg=C['header'],
                  relief='flat', padx=14, pady=6,
                  cursor='hand2',
                  command=self._open_settings).pack(side='right', padx=20, pady=14)

    def _build_search_row(self):
        row = tk.Frame(self.root, bg=C['bg'])
        row.pack(fill='x', padx=20, pady=(12, 4))

        self.find_btn = tk.Button(
            row, text="🔍  인기 주제 찾기  (최근 1개월)",
            font=('맑은 고딕', 12, 'bold'),
            bg=C['header'], fg='white',
            relief='flat', padx=20, pady=9,
            cursor='hand2',
            command=self._start_find_topics)
        self.find_btn.pack(side='left')

        self.status_lbl = tk.Label(
            row, text="   ← API 설정 후 클릭하세요",
            font=('맑은 고딕', 10),
            bg=C['bg'], fg=C['sub'])
        self.status_lbl.pack(side='left', padx=12)

        self.progress_var = tk.DoubleVar()
        self.pbar = ttk.Progressbar(
            row, variable=self.progress_var,
            maximum=len(CANDIDATE_TOPICS),
            length=240, mode='determinate')
        self.pbar.pack(side='left', padx=8)

    def _build_topic_row(self):
        outer = tk.Frame(self.root, bg=C['bg'])
        outer.pack(fill='x', padx=20, pady=(4, 6))

        tk.Label(outer, text="인기 주제 TOP 5  —  클릭하여 뉴스 검색",
                 font=('맑은 고딕', 10, 'bold'),
                 bg=C['bg'], fg=C['text']).pack(anchor='w', pady=(0, 5))

        btn_row = tk.Frame(outer, bg=C['bg'])
        btn_row.pack(fill='x')

        self.topic_btns: list[tk.Button] = []
        for i in range(5):
            b = tk.Button(btn_row,
                          text=f"{i+1}. —",
                          font=('맑은 고딕', 9),
                          bg=C['card'], fg=C['sub'],
                          relief='solid', bd=1,
                          padx=8, pady=7,
                          cursor='hand2',
                          state='disabled',
                          command=lambda idx=i: self._search_topic(idx),
                          wraplength=200, justify='center')
            b.pack(side='left', padx=(0, 8), expand=True, fill='x')
            self.topic_btns.append(b)

    def _build_results(self):
        outer = tk.Frame(self.root, bg=C['bg'])
        outer.pack(fill='both', expand=True, padx=20, pady=(4, 14))

        sources = [
            ('news',    '📰 뉴스',   C['news']),
            ('blog',    '📝 블로그', C['blog']),
            ('youtube', '▶ 유튜브',  C['youtube']),
        ]

        self.panels: dict[str, tk.Text]  = {}
        self.hdrs:   dict[str, tk.Label] = {}

        for i, (key, label, color) in enumerate(sources):
            col = tk.Frame(outer, bg=C['bg'])
            col.grid(row=0, column=i, sticky='nsew',
                     padx=(0, 12) if i < 2 else 0)
            outer.columnconfigure(i, weight=1)
            outer.rowconfigure(0, weight=1)

            hbar = tk.Frame(col, bg=color, height=38)
            hbar.pack(fill='x')
            hbar.pack_propagate(False)

            hdr = tk.Label(hbar, text=f"{label}  TOP 5",
                           font=('맑은 고딕', 10, 'bold'),
                           bg=color, fg='white')
            hdr.pack(side='left', padx=14, pady=9)
            self.hdrs[key] = hdr

            tframe = tk.Frame(col, bg=C['card'], relief='solid', bd=1)
            tframe.pack(fill='both', expand=True)

            sb = tk.Scrollbar(tframe)
            sb.pack(side='right', fill='y')

            txt = tk.Text(
                tframe,
                yscrollcommand=sb.set,
                wrap='word',
                font=('맑은 고딕', 9),
                bg=C['card'], fg=C['text'],
                relief='flat', padx=12, pady=10,
                cursor='arrow',
                state='disabled',
                spacing1=3, spacing2=1, spacing3=3,
            )
            txt.pack(side='left', fill='both', expand=True)
            sb.config(command=txt.yview)

            txt.tag_config('title', font=('맑은 고딕', 9, 'bold'), foreground=color)
            txt.tag_config('meta',  font=('맑은 고딕', 8), foreground=C['sub'])
            txt.tag_config('desc',  font=('맑은 고딕', 8), foreground=C['text'])
            txt.tag_config('sep',   foreground=C['sep'])
            txt.tag_config('hint',  foreground=C['sub'], font=('맑은 고딕', 9))

            self.panels[key] = txt

    def _init_result_panels(self):
        hints = {
            'news':    "\n  인기 주제를 선택하면\n  최신 뉴스 TOP 5가 표시됩니다.",
            'blog':    "\n  인기 주제를 선택하면\n  블로그 글 TOP 5가 표시됩니다.",
            'youtube': "\n  인기 주제를 선택하면\n  유튜브 영상 TOP 5가 표시됩니다.",
        }
        for key, msg in hints.items():
            self._write(key, msg, 'hint')

    # ── Settings dialog ───────────────────────────────────────────────────────

    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("API 키 설정")
        win.geometry("620x380")
        win.configure(bg=C['bg'])
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="API 키 설정",
                 font=('맑은 고딕', 14, 'bold'),
                 bg=C['bg'], fg=C['text']).pack(pady=20)

        frm = tk.Frame(win, bg=C['bg'])
        frm.pack(padx=30, fill='x')

        fields = [
            ("Naver Client ID",     self.sv_naver_id,     False),
            ("Naver Client Secret", self.sv_naver_secret, True),
            ("YouTube API Key",     self.sv_yt_key,       True),
        ]
        for lbl, var, hide in fields:
            r = tk.Frame(frm, bg=C['bg'])
            r.pack(fill='x', pady=7)
            tk.Label(r, text=lbl + ":", width=22, anchor='w',
                     font=('맑은 고딕', 10), bg=C['bg']).pack(side='left')
            tk.Entry(r, textvariable=var, width=38,
                     font=('맑은 고딕', 10),
                     show='*' if hide else '').pack(side='left', fill='x', expand=True)

        info = tk.Frame(win, bg='#e8eaf6', padx=15, pady=10)
        info.pack(fill='x', padx=30, pady=10)
        tk.Label(info,
                 text=("• Naver API: developers.naver.com → 애플리케이션 등록 → 검색 API 선택\n"
                       "• YouTube API: console.cloud.google.com → YouTube Data API v3 → 키 발급"),
                 font=('맑은 고딕', 9), bg='#e8eaf6', fg=C['sub'],
                 justify='left').pack(anchor='w')

        br = tk.Frame(win, bg=C['bg'])
        br.pack(pady=14)

        def save_and_close():
            self._current_config().save()
            messagebox.showinfo("저장 완료", "API 키가 저장되었습니다.", parent=win)
            win.destroy()

        tk.Button(br, text="저장",
                  font=('맑은 고딕', 11), bg=C['header'], fg='white',
                  relief='flat', padx=28, pady=7, cursor='hand2',
                  command=save_and_close).pack(side='left', padx=5)
        tk.Button(br, text="취소",
                  font=('맑은 고딕', 11), bg=C['sep'], fg=C['text'],
                  relief='flat', padx=28, pady=7, cursor='hand2',
                  command=win.destroy).pack(side='left', padx=5)

    # ── Find popular topics ───────────────────────────────────────────────────

    def _start_find_topics(self):
        cfg = self._current_config()
        if not cfg.naver_id or not cfg.naver_secret:
            self._open_settings()
            return

        self.find_btn.config(state='disabled')
        self.status_lbl.config(text="   주제별 검색량 분석 중...")
        self.progress_var.set(0)

        client = SearchClient(cfg.naver_id, cfg.naver_secret)
        threading.Thread(
            target=self._find_topics_worker,
            args=(client,),
            daemon=True
        ).start()

    def _find_topics_worker(self, client: SearchClient):
        try:
            def on_progress(v):
                self.root.after(0, self.progress_var.set, v)

            ranked = client.rank_topics(CANDIDATE_TOPICS, progress_cb=on_progress)
            self.root.after(0, self._apply_topics, ranked[:5])
        except Exception:
            self.root.after(0, self._reset_find_btn, "   오류 발생. 다시 시도하세요.")

    def _reset_find_btn(self, msg: str = ''):
        self.find_btn.config(state='normal')
        self.status_lbl.config(text=msg)
        self.progress_var.set(0)

    def _apply_topics(self, top5: list[tuple[str, int]]):
        self.popular_topics = [t for t, _ in top5]
        for i, (topic, score) in enumerate(top5):
            self.topic_btns[i].config(
                text=f"{i+1}. {topic}\n({score:,}건)",
                state='normal',
                bg=C['card'],
                fg=C['text'],
                font=('맑은 고딕', 9, 'bold'),
            )
        self.find_btn.config(state='normal')
        self.status_lbl.config(text="   ✓ 완료! 주제를 클릭하여 뉴스를 검색하세요.")
        self.progress_var.set(0)

    # ── Search topic ──────────────────────────────────────────────────────────

    def _search_topic(self, idx: int):
        if idx >= len(self.popular_topics):
            return
        topic = self.popular_topics[idx]

        for i, b in enumerate(self.topic_btns):
            b.config(bg=C['accent'] if i == idx else C['card'])
        for key in ('news', 'blog', 'youtube'):
            self._write(key, "\n  검색 중...", 'hint')

        client = self._make_client()
        threading.Thread(
            target=self._search_worker,
            args=(client, topic),
            daemon=True
        ).start()

    def _search_worker(self, client: SearchClient, topic: str):
        news = client.search_news(topic)
        blog = client.search_blog(topic)
        yt   = client.search_youtube(topic)

        self.root.after(0, self._render_results, 'news',    topic, news)
        self.root.after(0, self._render_results, 'blog',    topic, blog)
        self.root.after(0, self._render_results, 'youtube', topic, yt)

    # ── Render (단일 함수 — 뉴스/블로그/유튜브 공통) ──────────────────────────

    _SOURCE_META = {
        'news':    ('📰', '뉴스',   C['news']),
        'blog':    ('📝', '블로그', C['blog']),
        'youtube': ('▶',  '유튜브', C['youtube']),
    }

    def _render_results(self, key: str, topic: str, results: list[SearchResult]):
        icon, label, color = self._SOURCE_META[key]
        self.hdrs[key].config(text=f"{icon} {label}  TOP 5  —  {topic}")

        txt = self.panels[key]
        txt.config(state='normal')
        txt.delete('1.0', 'end')

        if not results:
            msg = ("\n  YouTube API 키가 없습니다.\n\n"
                   "  ⚙ API 설정에서 키를 입력하면\n  유튜브 영상도 검색됩니다."
                   if key == 'youtube' and not self.sv_yt_key.get()
                   else "\n  결과 없음 — API 키를 확인하세요.")
            txt.insert('end', msg, 'hint')
            txt.config(state='disabled')
            return

        for i, result in enumerate(results):
            if i > 0:
                txt.insert('end', "\n" + "─" * 28 + "\n", 'sep')

            tag = f"lnk_{key}_{i}"
            txt.tag_config(tag, foreground=color, underline=True)
            txt.tag_bind(tag, "<Button-1>",
                         lambda e, u=result.url: webbrowser.open(u) if u else None)
            txt.tag_bind(tag, "<Enter>", lambda e: txt.config(cursor="hand2"))
            txt.tag_bind(tag, "<Leave>", lambda e: txt.config(cursor="arrow"))

            txt.insert('end', f"  {result.title}\n", tag)
            txt.insert('end', f"  {result.meta}\n",  'meta')
            if result.desc:
                txt.insert('end',
                           f"  {result.desc}{'…' if len(result.desc) >= 90 else ''}\n",
                           'desc')

        txt.config(state='disabled')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _write(self, key: str, content: str, tag: str = 'hint'):
        txt = self.panels[key]
        txt.config(state='normal')
        txt.delete('1.0', 'end')
        txt.insert('end', content, tag)
        txt.config(state='disabled')


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    NewsFinderApp(root)
    root.mainloop()
