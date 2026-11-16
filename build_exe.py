"""一键打包脚本：把源码打包成免安装的 exe（结果在 dist 文件夹）。

用法：
    1. 先安装依赖：  pip install -r requirements-dev.txt
    2. 再运行：      python build_exe.py
    3. 完成后去 dist 文件夹拿「Git可视化仓库.exe」

macOS 上同样适用（把 --windowed 的产物当作 .app 使用；
去掉 --onefile 可得到启动更快的文件夹版）。
"""
from __future__ import annotations

import os
import subprocess
import sys


def main():
    # 中文 Windows 的控制台默认是 GBK，打印 ✅/❌ 会直接抛 UnicodeEncodeError，
    # 反而把真正的打包错误盖掉。这里统一按 UTF-8 输出（不支持就退回替换字符）。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    root = os.path.dirname(os.path.abspath(__file__))
    icon = os.path.join("assets", "icon.ico")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", "Git可视化仓库",
        "--add-data", f"{icon}{os.pathsep}assets",
    ]
    if os.path.exists(os.path.join(root, icon)):
        cmd += ["--icon", icon]
    cmd.append(os.path.join(root, "main.py"))

    print("开始打包（大约 2-5 分钟，请耐心等待）…")
    result = subprocess.run(cmd, cwd=root)
    exe = os.path.join(root, "dist", "Git可视化仓库.exe")
    if result.returncode == 0 and os.path.exists(exe):
        size_mb = os.path.getsize(exe) / 1024 / 1024
        print(f"✅ 打包完成！文件位置：{exe}（约 {size_mb:.0f} MB）")
    else:
        print("❌ 打包没有成功，请把上面的报错信息反馈给开发者。")
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
