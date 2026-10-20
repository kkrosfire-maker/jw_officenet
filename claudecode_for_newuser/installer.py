"""
Claude Code 새 사용자 설치 도우미 (ClaudeCode_설치.exe 의 본체)

다른 사람 PC에서 실행하면:
  1. 바탕화면\\workspace 폴더 생성
  2. PowerShell 실행 정책 해제 (프로필/claude 명령이 막히지 않게)
  3. Git, Claude Code CLI 설치 (없을 때만)
  4. 내 Claude Code 설정·스킬(/c-push 등)·CLAUDE.md 복사
  5. PowerShell 프로필에 q / ㅂ / cc / ㅊㅊ 단축 명령 추가
  6. 바탕화면 바로가기 (Claude Code, Claude.ai) 생성
  7. 크롬/엣지 즐겨찾기에 claude.ai 추가
  8. Antigravity IDE 설치 + 터미널 설정 (IDE 터미널에서도 q / ㅂ / cc / ㅊㅊ 사용)

내 폴더(프로젝트 파일)·대화 기억은 포함하지 않는다.
번들 내용(payload/)은 build.py 가 이 PC의 현재 설정으로 만든다.

테스트: python installer.py --test-root <폴더> --yes
  → 실제 사용자 폴더 대신 <폴더> 아래에만 파일을 만들고, 프로그램 설치·레지스트리 변경은 건너뛴다.
"""

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import winreg
from pathlib import Path

CLAUDE_URL = "https://claude.ai/"
MARK_BEGIN = "# >>> claudecode_for_newuser >>>"
MARK_END = "# <<< claudecode_for_newuser <<<"

BROWSERS = [
    # (표시 이름, LOCALAPPDATA 기준 User Data 경로, 프로세스 이름)
    ("크롬", Path("Google/Chrome/User Data"), "chrome.exe"),
    ("엣지", Path("Microsoft/Edge/User Data"), "msedge.exe"),
]

# 크롬/엣지 공통 루트 폴더 GUID (Bookmarks 파일을 새로 만들 때만 사용)
ROOT_GUIDS = {
    "bookmark_bar": "0bc5d13f-2cba-5d74-951f-3f233fe6c908",
    "other": "82b081ec-3dd3-529c-8475-ab6c344590dd",
    "synced": "4cf2e351-0e85-532b-bb37-df045d8f8d0f",
}


# ── 출력 ─────────────────────────────────────────────────────────────────────

results = []  # (상태, 메시지)


def ok(msg):
    results.append(("OK", msg))
    print(f"   [완료] {msg}")


def warn(msg):
    results.append(("WARN", msg))
    print(f"   [주의] {msg}")


def info(msg):
    print(f"   {msg}")


def step(n, total, title):
    print(f"\n[{n}/{total}] {title}")


# ── 경로 ─────────────────────────────────────────────────────────────────────

def payload_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "payload"


def known_folder(csidl: int) -> Path:
    # 바탕화면/문서가 OneDrive 로 리디렉션된 PC도 실제 위치를 돌려준다
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return Path(buf.value)


CSIDL_PERSONAL = 0x05          # 문서
CSIDL_DESKTOPDIRECTORY = 0x10  # 바탕화면


class Paths:
    def __init__(self, test_root: str | None):
        if test_root:
            root = Path(test_root).resolve()
            self.home = root / "home"
            self.desktop = self.home / "Desktop"
            self.documents = self.home / "Documents"
            self.localappdata = self.home / "AppData" / "Local"
            self.appdata = self.home / "AppData" / "Roaming"
        else:
            self.home = Path(os.environ["USERPROFILE"])
            self.desktop = known_folder(CSIDL_DESKTOPDIRECTORY)
            self.documents = known_folder(CSIDL_PERSONAL)
            self.localappdata = Path(os.environ["LOCALAPPDATA"])
            self.appdata = Path(os.environ["APPDATA"])
        self.workspace = self.desktop / "workspace"
        self.claude_dir = self.home / ".claude"
        self.claude_bin = self.home / ".local" / "bin"
        self.ide_exe = self.localappdata / "Programs" / "Antigravity IDE" / "Antigravity IDE.exe"
        self.ide_settings = self.appdata / "Antigravity IDE" / "User" / "settings.json"
        self.ps_profiles = [
            self.documents / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
        ]
        # PowerShell 7 이 깔려 있으면 그쪽 프로필에도 넣는다
        if test_root or shutil.which("pwsh"):
            self.ps_profiles.append(self.documents / "PowerShell" / "Microsoft.PowerShell_profile.ps1")


# ── 공용 도우미 ──────────────────────────────────────────────────────────────

def run_ps(command: str, timeout: int | None = None) -> int:
    """PowerShell 명령을 현재 콘솔에 출력을 그대로 보여주며 실행한다."""
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            timeout=timeout,
        ).returncode
    except subprocess.TimeoutExpired:
        return -1


def ps_output(command: str) -> str:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + command],
        capture_output=True,
    ).stdout
    return out.decode("utf-8", errors="replace").strip()


def ps_quote(s) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def refresh_path():
    """winget 등으로 방금 설치한 프로그램을 같은 창에서 바로 찾을 수 있게 PATH 재로딩."""
    parts = []
    for hive, key in [
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, r"Environment"),
    ]:
        try:
            with winreg.OpenKey(hive, key) as k:
                value, _ = winreg.QueryValueEx(k, "Path")
                parts.append(os.path.expandvars(value))
        except OSError:
            pass
    if parts:
        os.environ["PATH"] = ";".join(parts)


def add_to_user_path(folder: Path):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_WRITE) as k:
        try:
            value, kind = winreg.QueryValueEx(k, "Path")
        except OSError:
            value, kind = "", winreg.REG_EXPAND_SZ
        entries = [e for e in value.split(";") if e]
        if any(os.path.normcase(os.path.expandvars(e).rstrip("\\")) ==
               os.path.normcase(str(folder)) for e in entries):
            return False
        winreg.SetValueEx(k, "Path", 0, kind, ";".join([str(folder)] + entries))
    # 열려 있는 탐색기 등에 환경변수 변경 알림
    HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x1A, 0x2
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, None)
    return True


def ask_yes(question: str, auto_yes: bool) -> bool:
    if auto_yes:
        return True
    answer = input(f"   {question} (Y/n): ").strip().lower()
    return answer in ("", "y", "yes", "ㅛ")


def backup(path: Path):
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


# ── 단계별 작업 ──────────────────────────────────────────────────────────────

def make_workspace(p: Paths):
    p.workspace.mkdir(parents=True, exist_ok=True)
    ok(f"작업 폴더: {p.workspace}")


def set_execution_policy(test: bool):
    if test:
        info("(테스트 모드: 건너뜀)")
        return
    policy = ps_output("Get-ExecutionPolicy")
    if policy in ("Restricted", "AllSigned", "Undefined", ""):
        run_ps("Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force")
        policy = ps_output("Get-ExecutionPolicy")
    if policy in ("RemoteSigned", "Unrestricted", "Bypass"):
        ok(f"실행 정책: {policy}")
    else:
        warn(f"실행 정책을 바꾸지 못했습니다({policy}). 회사 PC라면 관리자에게 문의하세요.")


def winget_install(package_id: str, label: str) -> bool:
    if not shutil.which("winget"):
        warn(f"winget 이 없어 {label} 자동 설치를 못 했습니다.")
        return False
    info(f"{label} 설치 중... (몇 분 걸릴 수 있어요)")
    run_ps(f"winget install -e --id {package_id} --silent "
           "--accept-package-agreements --accept-source-agreements")
    refresh_path()
    return True


def install_git(test: bool):
    if test:
        info("(테스트 모드: 건너뜀)")
        return
    refresh_path()
    if shutil.which("git"):
        ok("Git 이미 설치됨")
        return
    winget_install("Git.Git", "Git")
    if shutil.which("git") or Path(r"C:\Program Files\Git\cmd\git.exe").exists():
        ok("Git 설치 완료")
    else:
        warn("Git 설치를 확인하지 못했습니다. https://git-scm.com 에서 직접 설치해 주세요.")


def install_claude(p: Paths, test: bool):
    if test:
        info("(테스트 모드: 건너뜀)")
        return
    refresh_path()
    exe = p.claude_bin / "claude.exe"
    if not (shutil.which("claude") or exe.exists()):
        info("Claude Code 설치 중... (공식 설치 스크립트)")
        run_ps("[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
               "irm https://claude.ai/install.ps1 | iex")
    if exe.exists():
        if add_to_user_path(p.claude_bin):
            info(f"PATH 에 추가: {p.claude_bin}")
        ok("Claude Code 설치됨")
        return
    refresh_path()
    if shutil.which("claude"):
        ok("Claude Code 설치됨")
        return
    # 공식 스크립트가 실패한 경우: Node.js + npm 으로 한 번 더 시도
    info("공식 설치가 실패해 npm 방식으로 다시 시도합니다.")
    if not shutil.which("npm"):
        winget_install("OpenJS.NodeJS.LTS", "Node.js")
    if shutil.which("npm"):
        run_ps("npm install -g @anthropic-ai/claude-code")
        refresh_path()
    if shutil.which("claude"):
        ok("Claude Code 설치됨 (npm)")
    else:
        warn("Claude Code 설치를 확인하지 못했습니다. 설치 프로그램을 한 번 더 실행해 보세요.")


def copy_claude_settings(p: Paths, payload: Path):
    # 전역 settings.json: 기존 값은 살리고 내 설정으로 덮어쓰기
    src = payload / "settings.json"
    if src.exists():
        dest = p.claude_dir / "settings.json"
        merged = {}
        if dest.exists():
            backup(dest)
            try:
                merged = read_json(dest)
            except ValueError:
                merged = {}
        merged.update(read_json(src))
        write_json(dest, merged)
        ok("Claude 전역 설정(settings.json)")

    # 스킬: 어느 폴더에서 claude 를 켜도 쓸 수 있게 전역(~/.claude/skills)에 설치
    skills_src = payload / "skills"
    if skills_src.exists():
        skills_dest = p.claude_dir / "skills"
        skills_dest.mkdir(parents=True, exist_ok=True)
        names = []
        for d in sorted(skills_src.iterdir()):
            if d.is_dir():
                target = skills_dest / d.name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(d, target)
                names.append(d.name)
        ok(f"스킬 {len(names)}개 (/{', /'.join(names[:4])} 등)")


def copy_workspace_files(p: Paths, payload: Path):
    src = payload / "CLAUDE.md"
    if src.exists():
        dest = p.workspace / "CLAUDE.md"
        if dest.exists() and dest.read_bytes() != src.read_bytes():
            backup(dest)
        shutil.copy2(src, dest)
        ok("작업 규칙(CLAUDE.md)")

    src = payload / "settings.local.json"
    if src.exists():
        dest = p.workspace / ".claude" / "settings.local.json"
        mine = read_json(src)
        if dest.exists():
            backup(dest)
            current = read_json(dest)
            allow = current.setdefault("permissions", {}).setdefault("allow", [])
            for rule in mine.get("permissions", {}).get("allow", []):
                if rule not in allow:
                    allow.append(rule)
            mine = current
        write_json(dest, mine)
        ok("허용 명령 목록(.claude/settings.local.json)")


def install_ps_profile(p: Paths, payload: Path):
    template = (payload / "profile_template.ps1").read_text(encoding="utf-8-sig")
    body = template.replace("__WORKSPACE__", str(p.workspace).replace("'", "''"))
    block = f"{MARK_BEGIN}\n{body.rstrip()}\n{MARK_END}\n"

    for profile in p.ps_profiles:
        existing = ""
        if profile.exists():
            raw = profile.read_bytes()
            try:
                existing = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                existing = raw.decode("cp949", errors="replace")
            existing = existing.replace("\r\n", "\n")  # 쓸 때 다시 CRLF 로 바뀌므로 중복 방지
            backup(profile)
            # 재설치 시 이전에 넣은 블록은 교체
            start, end = existing.find(MARK_BEGIN), existing.find(MARK_END)
            if start != -1 and end != -1:
                existing = existing[:start] + existing[end + len(MARK_END):].lstrip("\r\n")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        profile.parent.mkdir(parents=True, exist_ok=True)
        # Windows PowerShell 5.1 은 BOM 없는 UTF-8 의 한글(ㅂ, ㅊㅊ)을 깨뜨리므로 BOM 필수
        profile.write_text(existing + block, encoding="utf-8-sig", newline="\r\n")
        ok(f"PowerShell 단축 명령(q, ㅂ, cc, ㅊㅊ): {profile}")


def upgrade_psreadline(test: bool):
    if test:
        info("(테스트 모드: 건너뜀)")
        return
    info("자동완성 모듈(PSReadLine) 확인 중... (최대 몇 분)")
    code = run_ps(
        "$v = (Get-Module PSReadLine -ListAvailable | Sort-Object Version -Descending | "
        "Select-Object -First 1).Version; "
        "if ($v -and $v -ge [version]'2.2.0') { exit 0 }; "
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
        "Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Scope CurrentUser -Force | Out-Null; "
        "Install-Module PSReadLine -Scope CurrentUser -Force -SkipPublisherCheck -AllowClobber; "
        "exit $(if ($?) {0} else {1})",
        timeout=300,
    )
    if code == 0:
        ok("자동완성 모듈(PSReadLine)")
    else:
        warn("자동완성 모듈 업데이트 실패 — 회색 추천 글씨만 안 나오고 나머지는 정상 동작합니다.")


def make_shortcuts(p: Paths):
    p.desktop.mkdir(parents=True, exist_ok=True)

    url_file = p.desktop / "Claude.ai.url"
    url_file.write_text(f"[InternetShortcut]\nURL={CLAUDE_URL}\n", encoding="ascii", newline="\r\n")
    ok("바탕화면 바로가기: Claude.ai (웹)")

    lnk = p.desktop / "Claude Code.lnk"
    icon = p.claude_bin / "claude.exe"
    script = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$l = $s.CreateShortcut({ps_quote(lnk)}); "
        "$l.TargetPath = \"$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0\\powershell.exe\"; "
        # cc 와 같은 동작. 프로필 함수에 기대지 않고 직접 실행해 프로필이 안 읽혀도 동작하게 함
        "$l.Arguments = '-NoExit -Command claude --dangerously-skip-permissions'; "
        f"$l.WorkingDirectory = {ps_quote(p.workspace)}; "
        "$l.Description = 'workspace 폴더에서 Claude Code 실행 (cc, 권한 확인 없음)'; "
        + (f"$l.IconLocation = {ps_quote(str(icon) + ',0')}; " if icon.exists() else "")
        + "$l.Save()"
    )
    run_ps(script)
    if lnk.exists():
        ok("바탕화면 바로가기: Claude Code (workspace 에서 cc 로 실행)")
    else:
        warn("Claude Code 바로가기를 만들지 못했습니다.")


# ── Antigravity IDE ──────────────────────────────────────────────────────────

# IDE 통합 터미널 설정. 기본 셸을 PowerShell 로 못 박아야 프로필(q/ㅂ/cc/ㅊㅊ)이 읽힌다.
# 스킬은 전역(~/.claude/skills)에 있으므로 IDE 터미널의 claude 에서도 그대로 보인다.
IDE_SETTINGS = {
    "terminal.integrated.defaultProfile.windows": "PowerShell",
    "terminal.integrated.enablePersistentSessions": False,  # 죽은 터미널 세션이 쌓이는 현상 방지
    "terminal.integrated.scrollback": 20000,
    "workbench.secondarySideBar.defaultVisibility": "hidden",  # 시작 시 우측 agent 창 안 띄움
}


def install_ide(p: Paths, test: bool):
    if test:
        info("(테스트 모드: 프로그램 설치 건너뜀)")
    elif p.ide_exe.exists():
        ok("Antigravity IDE 이미 설치됨")
    else:
        winget_install("Google.AntigravityIDE", "Antigravity IDE")
        if p.ide_exe.exists():
            ok("Antigravity IDE 설치 완료")
        else:
            warn("Antigravity IDE 설치를 확인하지 못했습니다. 검색창에 'Antigravity IDE' 로 직접 내려받아 설치해 주세요.")

    # 설정: 기존 값은 살리고 터미널 항목만 덧씌움 (주석이 든 JSONC 라 읽히지 않으면 건드리지 않음)
    current = {}
    if p.ide_settings.exists():
        try:
            current = read_json(p.ide_settings)
        except ValueError:
            warn(f"IDE 설정 파일을 읽지 못해 건드리지 않았습니다. 터미널 기본 셸을 PowerShell 로 직접 지정해 주세요: {p.ide_settings}")
            return
        backup(p.ide_settings)
    current.update(IDE_SETTINGS)
    write_json(p.ide_settings, current)
    ok("Antigravity IDE 터미널 설정 (기본 셸 PowerShell → q, ㅂ, cc, ㅊㅊ 사용 가능)")


def make_ide_shortcut(p: Paths):
    lnk = p.desktop / "Antigravity IDE (workspace).lnk"
    script = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$l = $s.CreateShortcut({ps_quote(lnk)}); "
        f"$l.TargetPath = {ps_quote(p.ide_exe)}; "
        f"$l.Arguments = {ps_quote('\"' + str(p.workspace) + '\"')}; "  # workspace 폴더를 바로 열기
        f"$l.WorkingDirectory = {ps_quote(p.workspace)}; "
        "$l.Description = 'workspace 폴더를 Antigravity IDE 로 열기'; "
        f"$l.IconLocation = {ps_quote(str(p.ide_exe) + ',0')}; "
        "$l.Save()"
    )
    run_ps(script)
    if lnk.exists():
        ok("바탕화면 바로가기: Antigravity IDE (workspace 폴더로 열림)")
    else:
        warn("Antigravity IDE 바로가기를 만들지 못했습니다.")


# ── 즐겨찾기 ─────────────────────────────────────────────────────────────────

def webkit_now() -> str:
    # 크롬 시간 형식: 1601-01-01 부터의 마이크로초
    return str(int((time.time() + 11644473600) * 1_000_000))


def empty_bookmarks() -> dict:
    now = webkit_now()
    roots = {}
    for i, (key, name) in enumerate(
            [("bookmark_bar", "북마크바"), ("other", "기타 북마크"), ("synced", "모바일 북마크")], start=1):
        roots[key] = {"children": [], "date_added": now, "date_modified": "0",
                      "guid": ROOT_GUIDS[key], "id": str(i), "name": name, "type": "folder"}
    return {"roots": roots, "version": 1}


def walk_nodes(node):
    yield node
    for child in node.get("children", []):
        yield from walk_nodes(child)


def add_bookmark(file: Path) -> str:
    data = read_json(file) if file.exists() else empty_bookmarks()
    nodes = [n for root in data["roots"].values() if isinstance(root, dict) for n in walk_nodes(root)]
    if any(n.get("url", "").startswith("https://claude.ai") for n in nodes):
        return "이미 있음"
    max_id = max((int(n["id"]) for n in nodes if str(n.get("id", "")).isdigit()), default=3)
    data["roots"]["bookmark_bar"].setdefault("children", []).insert(0, {
        "date_added": webkit_now(), "date_last_used": "0", "guid": str(uuid.uuid4()),
        "id": str(max_id + 1), "name": "Claude", "type": "url", "url": CLAUDE_URL,
    })
    # checksum 이 남아 있으면 브라우저가 수정된 파일을 의심하므로 제거 (없으면 그냥 받아들인다)
    data.pop("checksum", None)
    if file.exists():
        backup(file)
    write_json(file, data)
    return "추가됨"


def is_running(process: str) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {process}", "/NH"],
                         capture_output=True, text=True, errors="replace").stdout
    return process.lower() in out.lower()


def close_browser(process: str) -> bool:
    subprocess.run(["taskkill", "/IM", process], capture_output=True)
    for _ in range(10):
        time.sleep(0.5)
        if not is_running(process):
            return True
    subprocess.run(["taskkill", "/F", "/IM", process], capture_output=True)
    time.sleep(1)
    return not is_running(process)


def add_favorites(p: Paths, test: bool, auto_yes: bool):
    found = False
    for label, rel, process in BROWSERS:
        user_data = p.localappdata / rel
        profiles = [d for d in [user_data / "Default", *sorted(user_data.glob("Profile *"))] if d.is_dir()]
        if not profiles:
            continue
        found = True
        if not test and is_running(process):
            if not ask_yes(f"{label}이(가) 켜져 있어 즐겨찾기를 추가하려면 잠시 닫아야 합니다. 닫을까요?", auto_yes):
                warn(f"{label} 즐겨찾기 건너뜀 (브라우저에서 직접 추가해 주세요)")
                continue
            if not close_browser(process):
                warn(f"{label}을(를) 닫지 못해 즐겨찾기를 건너뜁니다.")
                continue
        for prof in profiles:
            try:
                result = add_bookmark(prof / "Bookmarks")
                ok(f"{label} 즐겨찾기({prof.name}): claude.ai {result}")
            except Exception as e:  # 손상된 Bookmarks 파일 등
                warn(f"{label} 즐겨찾기({prof.name}) 실패: {e}")
    if not found:
        warn("크롬/엣지 사용 기록이 없어 즐겨찾기는 건너뜁니다. (바탕화면 Claude.ai 바로가기를 사용하세요)")


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-root", help="실제 사용자 폴더 대신 이 폴더 아래에만 설치 (개발용)")
    parser.add_argument("--yes", action="store_true", help="모든 질문에 예 (개발용)")
    args = parser.parse_args()
    test = bool(args.test_root)

    payload = payload_dir()
    p = Paths(args.test_root)

    print("=" * 60)
    print("  Claude Code 설치 도우미")
    print("=" * 60)
    print(f"""
  이 프로그램이 하는 일
   - 바탕화면에 workspace 폴더 만들기 ({p.workspace})
   - Git, Claude Code, Antigravity IDE 설치 (이미 있으면 건너뜀)
   - 설정·스킬(/c-push 등)·단축 명령(q, ㅂ, cc) 적용
   - 바탕화면 바로가기, claude.ai 즐겨찾기 추가
""")
    if test:
        print(f"  ※ 테스트 모드: {Path(args.test_root).resolve()} 아래에만 설치합니다.\n")
    if not args.yes:
        input("  시작하려면 Enter 를 누르세요 (취소: 창 닫기) ")

    steps = [
        ("작업 폴더 만들기", lambda: make_workspace(p)),
        ("PowerShell 실행 정책 설정", lambda: set_execution_policy(test)),
        ("Git 설치 확인", lambda: install_git(test)),
        ("Claude Code 설치 확인", lambda: install_claude(p, test)),
        ("Claude 설정·스킬 복사", lambda: copy_claude_settings(p, payload)),
        ("작업 폴더 규칙 복사", lambda: copy_workspace_files(p, payload)),
        ("PowerShell 단축 명령 설정", lambda: install_ps_profile(p, payload)),
        ("자동완성 모듈 확인", lambda: upgrade_psreadline(test)),
        ("바탕화면 바로가기 만들기", lambda: make_shortcuts(p)),
        ("claude.ai 즐겨찾기 추가", lambda: add_favorites(p, test, args.yes)),
        ("Antigravity IDE 설치·터미널 설정", lambda: install_ide(p, test)),
        ("Antigravity IDE 바로가기 만들기", lambda: make_ide_shortcut(p) if (test or p.ide_exe.exists()) else info("(IDE 미설치: 건너뜀)")),
    ]
    for i, (title, fn) in enumerate(steps, start=1):
        step(i, len(steps), title)
        try:
            fn()
        except Exception as e:
            warn(f"{title} 중 오류: {e}")

    warnings = [m for s, m in results if s == "WARN"]
    print("\n" + "=" * 60)
    print("  설치 완료!" if not warnings else f"  설치 완료 (확인할 항목 {len(warnings)}개)")
    print("=" * 60)
    for m in warnings:
        print(f"   - {m}")
    print("""
  다음 할 일
   1. 바탕화면의 [Claude Code] 아이콘을 더블클릭
   2. 브라우저가 열리면 Claude 계정으로 로그인
   3. 로그인 후 검은 창에서 바로 사용하면 됩니다

  단축 명령 (새로 연 PowerShell 창에서)
   q / ㅂ        workspace 폴더로 이동 (q 폴더명 → 하위 폴더로)
   cc / ㅊㅊ     Claude Code 를 권한 확인 없이 실행
  (Antigravity IDE 의 터미널에서도 동일하게 쓸 수 있습니다)
""")
    if not args.yes:
        input("  Enter 를 누르면 창이 닫힙니다 ")


if __name__ == "__main__":
    main()
