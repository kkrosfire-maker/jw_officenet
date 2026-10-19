# cc: claude --dangerously-skip-permissions 실행
function cc {
    claude --dangerously-skip-permissions "$@"
}

# ㅊㅊ: 한글 입력 상태에서 실수로 cc 대신 친 경우를 위한 별칭
function ㅊㅊ {
    cc "$@"
}

# q: 기본 작업 폴더로 이동 / q [폴더명]: 하위 폴더로 이동
function q {
    local base='__WORKSPACE__'
    if [[ -z "$1" ]]; then
        cd "$base"
    elif [[ "$1" = /* ]]; then
        cd "$1"
    else
        cd "$base/$1"
    fi
}

# ㅂ: 한글 입력 상태에서 실수로 q 대신 친 경우를 위한 별칭
function ㅂ {
    q "$@"
}

# q / ㅂ 뒤에서 Tab 으로 workspace 하위 폴더 이름 자동완성
function _q_complete {
    local base='__WORKSPACE__'
    local -a dirs
    dirs=("$base"/*(/N:t))
    compadd -a dirs
}
autoload -Uz compinit 2>/dev/null
(( $+functions[compdef] )) || compinit -u 2>/dev/null
(( $+functions[compdef] )) && compdef _q_complete q ㅂ
