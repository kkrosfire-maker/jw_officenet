' 콘솔 창 없이 new_folder.ps1 을 실행한다 (창 스타일 0 = 숨김)
Set fso = CreateObject("Scripting.FileSystemObject")
dir = WScript.Arguments(0)
If Right(dir, 1) = "\" Then dir = dir & "\"
ps1 = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "new_folder.ps1")
CreateObject("WScript.Shell").Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """ """ & dir & """", 0, False
