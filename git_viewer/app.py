"""app.py —— 程序入口：创建应用、加载样式、打开主窗口。"""
from __future__ import annotations

import os
import sys
import tempfile

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import APP_NAME, APP_VERSION, git_service, i18n, settings
from .ui import styles
from .ui.main_window import MainWindow


def resource_path(rel):
    """取资源文件路径：开发时在项目目录，打包后在解包临时目录（sys._MEIPASS）。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, rel.replace("/", os.sep))


def main():
    args = sys.argv[1:]

    if "--selftest" in args:
        from .selftest import run_selftest
        sys.exit(run_selftest())

    if "--make-fixture" in args:
        from .selftest import make_demo_folder
        if not git_service.find_git()[0]:
            print("没有找到 git，无法生成演示数据。请先安装 Git。")
            sys.exit(1)
        i = args.index("--make-fixture")
        target = args[i + 1] if len(args) > i + 1 else tempfile.mkdtemp(prefix="grv_fixture_")
        make_demo_folder(target)
        print("演示文件夹已生成（用完可以直接整个删掉）：", os.path.abspath(target))
        return

    demo_folder = None
    if "--autotest-demo" in args:
        i = args.index("--autotest-demo")
        demo_folder = args[i + 1] if len(args) > i + 1 else None

    app = QApplication([sys.argv[0]])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    # 语言要先定下来：界面上所有文字都会经过 i18n.translate() 再落到控件上
    i18n.set_language(settings.language())
    i18n.install()
    styles.apply_theme(app, settings.theme())

    icon_file = resource_path("assets/icon.ico")
    if os.path.exists(icon_file):
        app.setWindowIcon(QIcon(icon_file))

    git_path, git_version = git_service.find_git()
    win = MainWindow(git_ready=bool(git_path), git_version=git_version,
                     auto_scan="--fresh" not in args)
    win.show()

    if demo_folder:
        win.start_demo(demo_folder)

    sys.exit(app.exec())
