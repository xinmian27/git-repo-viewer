"""trash.py —— 把文件/文件夹"移入系统回收站"（可还原），而不是永久删除。

这样即使是误删，用户也能在系统回收站里把它还原回来。
Windows 用系统自带的 SHFileOperation（FOF_ALLOWUNDO）；
macOS（将来支持）把目标移动到废纸篓 ~/.Trash。
"""
from __future__ import annotations

import ctypes
import os
import shutil
import sys
import threading


def move_to_trash(path):
    """把 path（文件或文件夹）移入系统回收站。返回 (是否成功, 失败原因)。"""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return False, "路径不存在"
    if sys.platform == "win32":
        return _win_trash(path)
    return _mac_trash(path)


def _win_trash(path):
    """Windows：调用系统 API 把文件夹放进回收站（FOF_ALLOWUNDO 表示可撤销）。

    SHFileOperation 属于外壳（Shell）接口，按 COM 的规矩，调用线程要先初始化
    COM 组件。主界面线程 Qt 已经初始化好了，但我们是放在后台线程里跑的，
    后台线程默认没有初始化 —— 不初始化有时会表现为"卡住几十秒"或直接失败，
    所以这里自己确保一下（已经在别的房间初始化过也没关系，返回失败码忽略即可）。
    """
    _co_init()
    try:
        return _win_trash_impl(path)
    finally:
        _co_uninit()


_COM_READY = threading.local()


def _co_init():
    """在当前线程初始化 COM（单线程套间）。同一线程只做一次。"""
    if getattr(_COM_READY, "done", False):
        return
    try:
        # 0x2 = COINIT_APARTMENTTHREADED；返回 RPC_E_CHANGED_MODE(0x80010106) 也无所谓
        ctypes.windll.ole32.CoInitializeEx(None, 0x2)
    except Exception:
        pass
    _COM_READY.done = True


def _co_uninit():
    try:
        ctypes.windll.ole32.CoUninitialize()
    except Exception:
        pass
    _COM_READY.done = False


def _win_trash_impl(path):

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", ctypes.c_int),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    FO_DELETE = 3
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400

    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = path + "\0"  # 这个 API 要求路径以"两个 \0"结尾
    op.pTo = None
    op.fFlags = FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if code == 0 and not op.fAnyOperationsAborted:
        return True, ""
    reason = f"系统返回码 {code}"
    if op.fAnyOperationsAborted:
        reason += "（操作被系统中止）"
    return False, reason


def _mac_trash(path):
    """macOS：把文件夹移动到废纸篓（~/.Trash），重名时自动加编号。"""
    trash = os.path.expanduser("~/.Trash")
    base = os.path.basename(os.path.normpath(path))
    target = os.path.join(trash, base)
    n = 1
    while os.path.exists(target):
        target = os.path.join(trash, f"{base} {n}")
        n += 1
    shutil.move(path, target)
    return True, ""
