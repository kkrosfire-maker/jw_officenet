# 계약서 docx 3종 -> templates.js (base64, file:// 에서도 로드되도록)
import base64, glob, json, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
m = {}
for f in glob.glob("*.docx"):
    if f.startswith("1."): k = "resident"
    elif "법인" in f: k = "virtual"   # 비상주는 법인 양식 기준
    else: continue
    m[k] = base64.b64encode(open(f, "rb").read()).decode()
open("templates.js", "w", encoding="utf8").write("window.TEMPLATES=" + json.dumps(m) + ";")
print({k: len(v) for k, v in m.items()})
