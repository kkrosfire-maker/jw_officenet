"""콘솔 창 없이 실행하는 런처 (.pyw = pythonw.exe로 실행됨)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from main import App
App().mainloop()
