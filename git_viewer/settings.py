"""settings.py —— 记住用户的使用习惯（上次扫描的文件夹、扫描深度）。

数据保存在系统用户的配置区（Windows 注册表 HKCU），卸载软件也不会影响别的程序。
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

_S = QSettings("GitRepoViewer", "GitRepoViewer")


def last_folder():
    """旧接口：返回单个上次扫描文件夹（取列表第一个）。"""
    folders = last_folders()
    return folders[0] if folders else ""


def last_folders():
    """上次扫描的文件夹列表（支持多个位置/多个磁盘）。"""
    v = _S.value("scan/last_folders", None)
    if v is None:
        old = _S.value("scan/last_folder", "")
        return [str(old)] if old else []
    if isinstance(v, str):
        return [v] if v else []
    return [str(x) for x in v if str(x)]


def set_last_folders(folders):
    _S.setValue("scan/last_folders", [str(f) for f in folders])


def set_last_folder(path):
    _S.setValue("scan/last_folder", path)


def depth():
    try:
        return int(_S.value("scan/depth", 5))
    except (TypeError, ValueError):
        return 5


def set_depth(d):
    _S.setValue("scan/depth", int(d))


def scan_capped():
    """上次扫描是否因达到上限而提前停止（用于界面上的「继续扫描」提示）。"""
    try:
        return bool(_S.value("scan/capped", False, type=bool))
    except Exception:
        return str(_S.value("scan/capped", "false")).lower() in ("1", "true")


def set_scan_capped(b):
    _S.setValue("scan/capped", bool(b))


def repos():
    """收藏的仓库路径列表（展示顺序由界面排序决定，与存储顺序无关）。"""
    v = _S.value("repos/list", None)
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v else []
    return [str(x) for x in v if x]


def set_repos(repos):
    _S.setValue("repos/list", [str(r) for r in repos])


def pinned():
    """被置顶的仓库路径列表。"""
    v = _S.value("ui/pinned", None)
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v else []
    return [str(x) for x in v if x]


def set_pinned(paths):
    _S.setValue("ui/pinned", [str(p) for p in paths])


def sort_key():
    v = str(_S.value("ui/sort_key", "name"))
    return v if v in ("name", "time") else "name"


def set_sort_key(v):
    _S.setValue("ui/sort_key", v)


def sort_priority():
    v = str(_S.value("ui/sort_priority", "none"))
    return v if v in ("none", "local", "remote") else "none"


def set_sort_priority(v):
    _S.setValue("ui/sort_priority", v)


def sort_reverse():
    try:
        return bool(_S.value("ui/sort_reverse", False, type=bool))
    except Exception:
        return str(_S.value("ui/sort_reverse", "false")).lower() in ("1", "true")


def set_sort_reverse(b):
    _S.setValue("ui/sort_reverse", bool(b))


def initialized():
    """是否已经建立过收藏列表（用于老版本升级时的一次性迁移）。"""
    try:
        return bool(_S.value("repos/initialized", False, type=bool))
    except Exception:
        return str(_S.value("repos/initialized", "false")).lower() in ("1", "true")


def set_initialized():
    _S.setValue("repos/initialized", True)


def diff_show_meta():
    """版本对比页是否显示 git 的原始技术行（默认关闭，新手不需要看）。"""
    try:
        return bool(_S.value("ui/diff_show_meta", False, type=bool))
    except Exception:
        return str(_S.value("ui/diff_show_meta", "false")).lower() in ("1", "true")


def set_diff_show_meta(b):
    _S.setValue("ui/diff_show_meta", bool(b))


def theme():
    """外观：light（浅色）/ dark（深色）/ system（跟随系统）。"""
    v = str(_S.value("ui/theme", "system")).lower()
    return v if v in ("light", "dark", "system") else "system"


def set_theme(v):
    _S.setValue("ui/theme", str(v).lower())


def language():
    """界面语言：zh_CN / zh_TW / en。"""
    v = str(_S.value("ui/language", "zh_CN"))
    return v if v in ("zh_CN", "zh_TW", "en") else "zh_CN"


def set_language(v):
    _S.setValue("ui/language", str(v))


def file_path():
    """设置文件（或注册表键）的位置，显示在「关于」里方便排查。"""
    try:
        return _S.fileName()
    except Exception:
        return ""
