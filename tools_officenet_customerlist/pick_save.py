# 저장 위치 선택 창(기본 바탕화면). 인자: 기본폴더 파일명 종류(pdf|docx). 선택한 경로를 stdout 으로 출력, 취소하면 빈 출력.
import sys, os
import tkinter as tk
from tkinter import filedialog
folder, name, kind = sys.argv[1], sys.argv[2], sys.argv[3]
root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
ext, label = (".pdf", "PDF 파일") if kind == "pdf" else (".docx", "Word 파일")
p = filedialog.asksaveasfilename(parent=root, title="저장할 위치와 파일 이름", initialdir=folder, initialfile=name + ext,
                                 defaultextension=ext, filetypes=[(label, "*" + ext)])
root.destroy()
sys.stdout.buffer.write((os.path.normpath(p) if p else "").encode("utf-8"))
