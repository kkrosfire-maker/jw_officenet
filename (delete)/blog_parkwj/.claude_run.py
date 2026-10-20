import subprocess, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
os.chdir(r'C:\Users\JW\Desktop\workspace\blog')
with open('.claude_task.txt', encoding='utf-8') as f:
    msg = f.read()
proc = subprocess.Popen(
    ['claude', '-p', msg],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding='utf-8', errors='replace',
)
for line in proc.stdout:
    print(line, end='', flush=True)
proc.wait()
sys.exit(proc.returncode)
