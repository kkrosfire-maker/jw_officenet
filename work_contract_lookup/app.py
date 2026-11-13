import os
import sys
import webview


def resource_path(relative_path):
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, relative_path)


if __name__ == '__main__':
    webview.create_window(
        '계약정보 조회',
        resource_path('www/index.html'),
        width=460,
        height=820,
        resizable=True,
    )
    webview.start()
