#!/usr/bin/env python3
"""Git可视化仓库 —— 启动入口。

普通使用：    python main.py
自动化自检：  python main.py --selftest          （不打开窗口，验证读取功能）
生成演示数据：python main.py --make-fixture <文件夹路径>
界面自动演示：python main.py --autotest-demo <演示文件夹路径>   （开发调试用）
跳过自动扫描：python main.py --fresh              （开发调试用）
"""
from git_viewer.app import main

if __name__ == "__main__":
    main()
