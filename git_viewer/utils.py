"""utils.py —— 把"机器信息"变成人话的小工具函数。"""
from __future__ import annotations

import html as _html
import re
from datetime import datetime

# diff 文件变化类型的中文说法和颜色
DIFF_STATUS_NAMES = {"A": "新增", "M": "修改", "D": "删除", "R": "重命名",
                     "C": "复制", "T": "类型变更", "U": "冲突"}
DIFF_STATUS_COLORS = {"A": "#16a34a", "M": "#2563eb", "D": "#dc2626", "R": "#9333ea",
                      "C": "#0891b2", "T": "#d97706", "U": "#d97706"}


def status_name(code):
    return DIFF_STATUS_NAMES.get((code or "")[:1].upper(), "变化")


def status_color(code):
    return DIFF_STATUS_COLORS.get((code or "")[:1].upper(), "#6b7280")


def parse_iso(value):
    """把 git 返回的时间字符串（ISO 格式或 unix 秒）变成 datetime。"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.fromtimestamp(int(s))
        except (ValueError, OSError):
            return None


def fmt_dt(value, with_seconds=False):
    """2026-10-24T14:30:05+08:00 -> 2026-10-24 14:30"""
    dt = parse_iso(value)
    if dt is None:
        return str(value or "")
    return dt.strftime("%Y-%m-%d %H:%M:%S" if with_seconds else "%Y-%m-%d %H:%M")


def fmt_dt_short(value):
    """列表里用的短时间：今年显示 10-24 14:30，往年显示 2025-10-24。"""
    dt = parse_iso(value)
    if dt is None:
        return str(value or "")
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    if dt.year == now.year:
        return dt.strftime("%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d")


def rel_time(value):
    """相对时间：刚刚 / 5 分钟前 / 3 天前 / 2 个月前。"""
    dt = parse_iso(value)
    if dt is None:
        return ""
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    sec = (now - dt).total_seconds()
    if sec < 60:
        return "刚刚"
    if sec < 3600:
        return f"{int(sec // 60)} 分钟前"
    if sec < 86400:
        return f"{int(sec // 3600)} 小时前"
    days = int(sec // 86400)
    if days < 30:
        return f"{days} 天前"
    if days < 365:
        return f"{days // 30} 个月前"
    return f"{days // 365} 年前"


def esc(s):
    """把文本转成能安全放进 HTML 的形式。"""
    return _html.escape(str(s or ""))


# diff 输出里每一行的配色：(背景色, 文字色)
_DIFF_STYLES = {
    "meta": (None, "#8a94a6"),   # diff --git / index 等头部信息
    "hunk": (None, "#0550ae"),   # @@ 行号定位
    "add":  ("#e6ffec", "#0a6e3c"),  # 新增的行：绿
    "del":  ("#ffebe9", "#a40e26"),  # 删除的行：红
    "note": (None, "#9aa4b2"),   # \ No newline 之类的提示
    "ctx":  (None, "#24292f"),   # 没变化的上下文行
}

# 深色界面（深色主题）下同一批行的配色：亮底会刺眼，文字也得反过来
_DIFF_STYLES_DARK = {
    "meta": (None, "#8b95a7"),
    "hunk": (None, "#7ec3ff"),
    "add":  ("#12291b", "#7ee2a8"),
    "del":  ("#331a1c", "#ff9b9b"),
    "note": (None, "#7c8696"),
    "ctx":  (None, "#dbe2ea"),
}


def diff_to_html(text, dark=False):
    """把 git diff 文本变成带颜色的 HTML（QTextEdit 可以直接显示）。

    dark=True 时用深色配色（深色主题下亮绿/亮红底会非常刺眼）。
    """
    styles = _DIFF_STYLES_DARK if dark else _DIFF_STYLES
    out = []
    for ln in text.splitlines():
        if ln.startswith(("diff --git ", "index ", "+++ ", "--- ", "rename ", "similarity ",
                          "old mode", "new mode", "new file", "deleted file", "Binary")):
            kind = "meta"
        elif ln.startswith("⋯ "):
            kind = "note"      # friendly_hunks() 生成的分段提示
        elif ln.startswith("@@"):
            kind = "hunk"
        elif ln.startswith("\\"):
            kind = "note"
        elif ln.startswith("+"):
            kind = "add"
        elif ln.startswith("-"):
            kind = "del"
        else:
            kind = "ctx"
        bg, fg = styles[kind]
        e = esc(ln) or "&nbsp;"
        if not e.strip():
            e = "&nbsp;"
        style = f"color:{fg};"
        if bg:
            style += f"background-color:{bg};"
        out.append('<div style="{}white-space:pre-wrap;'
                   "font-family:Consolas,'Courier New',monospace;"
                   'font-size:12px;margin:0;">{}</div>'.format(style, e))
    return "".join(out)


# diff 里只对程序员有意义的技术头行：默认不展示给小白看
_DIFF_META_PREFIXES = (
    "diff --git ", "diff --cc ", "diff --combined ", "index ",
    "--- ", "+++ ", "old mode ", "new mode ",
    "new file mode ", "deleted file mode ",
    "similarity index ", "dissimilarity index ",
    "rename from ", "rename to ", "copy from ", "copy to ",
    "Binary files ", "GIT binary patch", "literal ", "delta ",
)


def strip_diff_meta(text):
    """去掉 diff 里给程序员看的原始头部行（diff --git / index / --- / +++ 等）。

    小白只需要看「哪些行加了、哪些行删了」。界面上的「显示技术细节」开关
    打开后就不会调用这个过滤，可以看到 git 的原样输出。

    注意：只在第一个 @@ 段落标记之前过滤头部行。之后的内容行虽然也可能
    以 "---" 开头（比如被删掉的 Markdown 分隔线），但那是真正的文件内容，
    不能误删。
    """
    keep = []
    in_body = False
    for ln in (text or "").splitlines():
        if ln.startswith("@@"):
            in_body = True
        elif not in_body and ln.startswith(_DIFF_META_PREFIXES):
            continue
        if ln.startswith("\\ No newline"):
            continue
        keep.append(ln)
    while keep and not keep[0].strip():
        keep.pop(0)
    return "\n".join(keep)


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@ *(.*)$")


def friendly_hunks(text):
    """把 "@@ -5,3 +5,10 @@" 换成人话，例如 "⋯ 从第 5 行附近开始的一段改动 ⋯"。

    普通用户看不懂 @@ 里的数字含义；保留它只会让人以为显示坏了。
    """
    out = []
    for ln in (text or "").splitlines():
        m = _HUNK_RE.match(ln)
        if m:
            out.append(f"⋯ 从第 {m.group(2)} 行附近开始的一段改动 ⋯")
        else:
            out.append(ln)
    return "\n".join(out)
