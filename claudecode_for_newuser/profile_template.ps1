# --- PSReadLine: 인라인 자동완성(고스트 텍스트) ---
# 설치된 PSReadLine 버전이 지원하지 않으면 조용히 건너뛴다 (q/ㅂ/cc 는 그대로 동작)
try {
    Import-Module PSReadLine -ErrorAction Stop
    if ($PSVersionTable.PSVersion -ge [version]"7.2") {
        Set-PSReadLineOption -PredictionSource HistoryAndPlugin -ErrorAction Stop
    } else {
        Set-PSReadLineOption -PredictionSource History -ErrorAction Stop
    }
    Set-PSReadLineOption -PredictionViewStyle InlineView -ErrorAction Stop
} catch {}

# --- 단축 명령 설정 ---

# cc: claude --dangerously-skip-permissions 실행
function cc {
    claude --dangerously-skip-permissions
}

# ㅊㅊ: 한글 입력 상태에서 실수로 cc 대신 친 경우를 위한 별칭
function ㅊㅊ {
    cc
}

# q: 기본 작업 폴더로 이동 / q [폴더명]: 하위 폴더로 이동
function q {
    param([string]$sub = "")
    $base = '__WORKSPACE__'
    if ($sub -eq "") {
        Set-Location $base
    } elseif ([System.IO.Path]::IsPathRooted($sub)) {
        Set-Location $sub
    } else {
        Set-Location "$base\$sub"
    }
}

# ㅂ: 한글 입력 상태에서 실수로 q 대신 친 경우를 위한 별칭
function ㅂ {
    param([string]$sub = "")
    q $sub
}

# q 뒤에 workspace 하위 폴더 이름 일부를 치고 Tab(순환 완성) 또는
# 오른쪽 방향키/End(고스트 텍스트 수락)로 선택할 수 있도록 자동완성 등록
Register-ArgumentCompleter -CommandName q, ㅂ -ParameterName sub -ScriptBlock {
    param($commandName, $parameterName, $wordToComplete, $commandAst, $fakeBoundParameters)
    $base = '__WORKSPACE__'
    Get-ChildItem -Path $base -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "$wordToComplete*" } |
        Sort-Object Name |
        ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_.Name, $_.Name, 'ParameterValue', $_.Name)
        }
}
