#!/bin/bash
# Claude Code 새 사용자 설치 도우미 (macOS)
#  - 바탕화면/workspace 생성, Homebrew·Git·Claude Code·Antigravity IDE 설치
#  - 설정·스킬 복사, zsh 에 q / ㅂ / cc / ㅊㅊ 추가, 바탕화면 바로가기
#  - Apple Silicon / Intel 자동 판별
# 테스트: bash install.command --test-root <폴더> --yes  (그 폴더 안에만 설치, 프로그램 설치 생략)

HERE="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="$HERE/payload"
MARK_BEGIN="# >>> claudecode_for_newuser >>>"
MARK_END="# <<< claudecode_for_newuser <<<"

TEST_ROOT=""; AUTO_YES=0
while [ $# -gt 0 ]; do
    case "$1" in
        --test-root) TEST_ROOT="$2"; shift ;;
        --yes) AUTO_YES=1 ;;
    esac
    shift
done

if [ -n "$TEST_ROOT" ]; then
    mkdir -p "$TEST_ROOT/home/Desktop"
    HOME_DIR="$(cd "$TEST_ROOT/home" && pwd)"
else
    HOME_DIR="$HOME"
fi
DESKTOP="$HOME_DIR/Desktop"
WORKSPACE="$DESKTOP/workspace"
CLAUDE_DIR="$HOME_DIR/.claude"
IDE_SETTINGS="$HOME_DIR/Library/Application Support/Antigravity IDE/User/settings.json"

WARNINGS=()
ok()   { echo "   [완료] $*"; }
warn() { echo "   [주의] $*"; WARNINGS+=("$*"); }
info() { echo "   $*"; }
step() { echo; echo "[$1/$TOTAL] $2"; }
is_test() { [ -n "$TEST_ROOT" ]; }

backup() { [ -f "$1" ] && cp -p "$1" "$1.bak"; return 0; }

# ── CPU 종류 판별 ────────────────────────────────────────────────────────────
# Rosetta 로 돌아가는 터미널이면 uname 이 x86_64 로 나오므로 sysctl 로 진짜 CPU 를 확인한다.
detect_arch() {
    if [ "$(sysctl -n sysctl.proc_translated 2>/dev/null)" = "1" ] \
       || [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ] \
       || [ "$(uname -m)" = "arm64" ]; then
        ARCH="arm64"; BREW_PREFIX="/opt/homebrew"; ARCH_LABEL="Apple Silicon (M 시리즈)"
    else
        ARCH="x86_64"; BREW_PREFIX="/usr/local"; ARCH_LABEL="Intel"
    fi
}

load_brew() {
    local b
    for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if [ -x "$b" ]; then eval "$("$b" shellenv)"; return 0; fi
    done
    return 1
}

# JSON 병합/BOM 제거는 python3 로 (Xcode 명령줄 도구가 있으면 /usr/bin/python3 사용 가능)
json_merge() {  # json_merge <대상파일> <추가할 JSON 파일>
    /usr/bin/python3 - "$1" "$2" <<'PY'
import json, sys, os
dest, src = sys.argv[1], sys.argv[2]
add = json.load(open(src, encoding="utf-8-sig"))
cur = {}
if os.path.exists(dest):
    try:
        cur = json.load(open(dest, encoding="utf-8-sig"))
    except ValueError:
        sys.exit(3)  # 주석이 든 JSONC 등 → 건드리지 않음
cur.update(add)
os.makedirs(os.path.dirname(dest), exist_ok=True)
json.dump(cur, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
}

# ── 단계 ─────────────────────────────────────────────────────────────────────

make_workspace() {
    mkdir -p "$WORKSPACE" && ok "작업 폴더: $WORKSPACE"
}

install_clt() {
    if is_test; then info "(테스트 모드: 건너뜀)"; return; fi
    if xcode-select -p >/dev/null 2>&1; then ok "Xcode 명령줄 도구(Git 포함) 이미 설치됨"; return; fi
    info "Xcode 명령줄 도구 설치 창이 뜹니다. [설치]를 누르고 끝날 때까지 기다려 주세요."
    xcode-select --install >/dev/null 2>&1
    until xcode-select -p >/dev/null 2>&1; do sleep 5; done
    ok "Xcode 명령줄 도구 설치 완료"
}

install_brew() {
    if is_test; then info "(테스트 모드: 건너뜀)"; return; fi
    if load_brew; then ok "Homebrew 이미 설치됨 ($(brew --prefix))"; return; fi
    info "Homebrew 설치 중... (맥 암호를 물어볼 수 있어요. 입력해도 화면에 안 보이는 게 정상입니다)"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if load_brew; then
        ok "Homebrew 설치 완료"
    else
        warn "Homebrew 설치를 확인하지 못했습니다. https://brew.sh 안내대로 직접 설치한 뒤 이 프로그램을 다시 실행해 주세요."
    fi
}

install_claude() {
    if is_test; then info "(테스트 모드: 건너뜀)"; return; fi
    export PATH="$HOME_DIR/.local/bin:$PATH"
    if ! command -v claude >/dev/null 2>&1; then
        info "Claude Code 설치 중... (공식 설치 스크립트)"
        curl -fsSL https://claude.ai/install.sh | bash
    fi
    if command -v claude >/dev/null 2>&1 || [ -x "$HOME_DIR/.local/bin/claude" ]; then
        ok "Claude Code 설치됨"
    else
        warn "Claude Code 설치를 확인하지 못했습니다. 설치 프로그램을 한 번 더 실행해 보세요."
    fi
}

copy_settings() {
    if [ -f "$PAYLOAD/settings.json" ]; then
        mkdir -p "$CLAUDE_DIR"
        backup "$CLAUDE_DIR/settings.json"
        if json_merge "$CLAUDE_DIR/settings.json" "$PAYLOAD/settings.json"; then
            ok "Claude 전역 설정(settings.json)"
        else
            warn "기존 settings.json 을 읽지 못해 건드리지 않았습니다."
        fi
    fi
    if [ -d "$PAYLOAD/skills" ]; then
        mkdir -p "$CLAUDE_DIR/skills"
        local n=0 d name
        for d in "$PAYLOAD"/skills/*/; do
            name="$(basename "$d")"
            rm -rf "$CLAUDE_DIR/skills/$name"
            cp -R "$d" "$CLAUDE_DIR/skills/$name"
            n=$((n+1))
        done
        ok "스킬 ${n}개 (전역 ~/.claude/skills)"
    fi
}

copy_workspace_files() {
    if [ -f "$PAYLOAD/CLAUDE.md" ]; then
        if [ -f "$WORKSPACE/CLAUDE.md" ] && ! cmp -s "$PAYLOAD/CLAUDE.md" "$WORKSPACE/CLAUDE.md"; then
            backup "$WORKSPACE/CLAUDE.md"
        fi
        cp "$PAYLOAD/CLAUDE.md" "$WORKSPACE/CLAUDE.md" && ok "작업 규칙(CLAUDE.md)"
    fi
}

install_shell_profile() {
    local rc="$HOME_DIR/.zshrc" body tmp
    body="$(sed "s|__WORKSPACE__|$WORKSPACE|g" "$PAYLOAD/profile_template.zsh")"
    touch "$rc"; backup "$rc"
    # 재설치 시 이전에 넣은 블록은 교체
    tmp="$(mktemp)"
    awk -v b="$MARK_BEGIN" -v e="$MARK_END" '
        $0==b {skip=1}
        !skip {print}
        $0==e {skip=0}' "$rc" > "$tmp" && cat "$tmp" > "$rc"
    rm -f "$tmp"
    {
        echo "$MARK_BEGIN"
        echo 'export PATH="$HOME/.local/bin:$PATH"'
        if [ -x "$BREW_PREFIX/bin/brew" ]; then
            echo "eval \"\$($BREW_PREFIX/bin/brew shellenv)\""
        fi
        echo "$body"
        echo "$MARK_END"
    } >> "$rc"
    ok "zsh 단축 명령(q, ㅂ, cc, ㅊㅊ): $rc"
}

install_ide() {
    if is_test; then
        info "(테스트 모드: 프로그램 설치 건너뜀)"
    elif [ -d "/Applications/Antigravity IDE.app" ]; then
        ok "Antigravity IDE 이미 설치됨"
    elif command -v brew >/dev/null 2>&1; then
        info "Antigravity IDE 설치 중... (cask: antigravity-ide, $ARCH_LABEL 용 자동 선택)"
        brew install --cask antigravity-ide
        if [ -d "/Applications/Antigravity IDE.app" ]; then
            ok "Antigravity IDE 설치 완료"
        else
            warn "Antigravity IDE 설치를 확인하지 못했습니다. 터미널에서 'brew install --cask antigravity-ide' 를 직접 실행해 보세요."
        fi
    else
        warn "Homebrew 가 없어 Antigravity IDE 를 설치하지 못했습니다."
    fi

    # IDE 터미널 설정: 기본 셸 zsh 고정 → ~/.zshrc 의 q/ㅂ/cc/ㅊㅊ 사용
    local tmp; tmp="$(mktemp)"
    cat > "$tmp" <<'JSON'
{
  "terminal.integrated.defaultProfile.osx": "zsh",
  "terminal.integrated.enablePersistentSessions": false,
  "terminal.integrated.scrollback": 20000,
  "workbench.secondarySideBar.defaultVisibility": "hidden"
}
JSON
    backup "$IDE_SETTINGS"
    if json_merge "$IDE_SETTINGS" "$tmp"; then
        ok "Antigravity IDE 터미널 설정 (기본 셸 zsh → q, ㅂ, cc, ㅊㅊ 사용 가능)"
    else
        warn "IDE 설정 파일을 읽지 못해 건드리지 않았습니다. 터미널 기본 셸을 zsh 로 직접 지정해 주세요: $IDE_SETTINGS"
    fi
    rm -f "$tmp"
}

make_shortcuts() {
    mkdir -p "$DESKTOP"
    # Claude.ai 웹 바로가기
    cat > "$DESKTOP/Claude.ai.webloc" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>URL</key><string>https://claude.ai/</string></dict></plist>
XML
    ok "바탕화면 바로가기: Claude.ai (웹)"

    # 더블클릭하면 터미널에서 workspace 로 이동해 Claude Code 실행 (cc 와 동일)
    cat > "$DESKTOP/Claude Code.command" <<SH
#!/bin/zsh
export PATH="\$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:\$PATH"
cd "$WORKSPACE" && claude --dangerously-skip-permissions
SH
    chmod +x "$DESKTOP/Claude Code.command"
    ok "바탕화면 바로가기: Claude Code (workspace 에서 cc 로 실행)"

    if is_test || [ -d "/Applications/Antigravity IDE.app" ]; then
        cat > "$DESKTOP/Antigravity IDE (workspace).command" <<SH
#!/bin/zsh
open -a "Antigravity IDE" "$WORKSPACE"
SH
        chmod +x "$DESKTOP/Antigravity IDE (workspace).command"
        ok "바탕화면 바로가기: Antigravity IDE (workspace 폴더로 열림)"
    fi
    # 내려받은 파일에 붙는 '확인되지 않은 개발자' 표시 제거 (실패해도 무방)
    xattr -d com.apple.quarantine "$DESKTOP"/*.command 2>/dev/null
    return 0
}

# ── 메인 ─────────────────────────────────────────────────────────────────────

detect_arch
echo "============================================================"
echo "  Claude Code 설치 도우미 (macOS)"
echo "============================================================"
echo
echo "  감지된 CPU: $ARCH_LABEL  →  Homebrew 위치 $BREW_PREFIX"
echo "  작업 폴더 : $WORKSPACE"
echo
echo "  이 프로그램이 하는 일"
echo "   - Xcode 명령줄 도구(Git), Homebrew, Claude Code, Antigravity IDE 설치 (이미 있으면 건너뜀)"
echo "   - 설정·스킬(/c-push 등)·단축 명령(q, ㅂ, cc, ㅊㅊ) 적용"
echo "   - 바탕화면 바로가기 만들기"
if is_test; then echo; echo "  ※ 테스트 모드: $HOME_DIR 아래에만 설치합니다."; fi
if [ "$AUTO_YES" -ne 1 ]; then
    echo; read -r -p "  시작하려면 Enter 를 누르세요 (취소: 창 닫기) " _
fi

STEPS=(
    "작업 폴더 만들기:make_workspace"
    "Xcode 명령줄 도구(Git) 확인:install_clt"
    "Homebrew 확인:install_brew"
    "Claude Code 설치 확인:install_claude"
    "Claude 설정·스킬 복사:copy_settings"
    "작업 폴더 규칙 복사:copy_workspace_files"
    "zsh 단축 명령 설정:install_shell_profile"
    "Antigravity IDE 설치·터미널 설정:install_ide"
    "바탕화면 바로가기 만들기:make_shortcuts"
)
TOTAL=${#STEPS[@]}
i=0
for s in "${STEPS[@]}"; do
    i=$((i+1)); step "$i" "${s%%:*}"
    "${s##*:}" || warn "${s%%:*} 중 오류"
done

echo; echo "============================================================"
if [ ${#WARNINGS[@]} -eq 0 ]; then echo "  설치 완료!"; else echo "  설치 완료 (확인할 항목 ${#WARNINGS[@]}개)"; fi
echo "============================================================"
for w in "${WARNINGS[@]}"; do echo "   - $w"; done
cat <<'TXT'

  다음 할 일
   1. 바탕화면의 [Claude Code] 아이콘을 더블클릭
   2. 브라우저가 열리면 Claude 계정으로 로그인
   3. 로그인 후 터미널에서 바로 사용하면 됩니다

  단축 명령 (새로 연 터미널 창에서)
   q / ㅂ        workspace 폴더로 이동 (q 폴더명 → 하위 폴더로)
   cc / ㅊㅊ     Claude Code 를 권한 확인 없이 실행
  (Antigravity IDE 의 터미널에서도 동일하게 쓸 수 있습니다)
TXT
if [ "$AUTO_YES" -ne 1 ]; then echo; read -r -p "  Enter 를 누르면 종료합니다 " _; fi
exit 0
