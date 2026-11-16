"""git_service.py —— 所有与 Git 打交道的代码都集中在这一个文件里。

它只负责三件事：
1. 找到电脑上的 git 程序（找不到时明确告诉你）；
2. 执行"只读"的 git 命令，把结果解析成好用的字典（dict）；
3. 对界面层提供简单的函数，界面代码完全不需要懂 git 命令。

安全说明：本文件执行的全部是只读命令（log / diff / status / branch /
config / remote 等），不会修改、移动或删除用户的任何文件。

把本模块独立出来、不掺任何界面代码，是为了以后做 macOS 版时可以原样复用。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys


# ---- 对外的异常类型 -------------------------------------------------------

class GitError(Exception):
    """git 命令执行失败。"""


class GitNotFound(GitError):
    """电脑上找不到 git 程序。"""


# ---- 查找并缓存 git 程序位置 ----------------------------------------------

_GIT_PATH: str | None = None
_GIT_VERSION: str | None = None

_WIN_GUESS = [
    r"C:\Program Files\Git\cmd\git.exe",
    r"C:\Program Files (x86)\Git\cmd\git.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
]


def find_git(preferred: str | None = None):
    """找到电脑上的 git，返回 (完整路径, 版本号)；找不到返回 (None, None)。"""
    global _GIT_PATH, _GIT_VERSION
    candidates = [preferred, os.environ.get("GRV_GIT_PATH"), shutil.which("git")]
    if sys.platform == "win32":
        candidates += _WIN_GUESS
    for c in candidates:
        if not c:
            continue
        c = os.path.normpath(c)
        if not os.path.isfile(c):
            continue
        try:
            out = _exec([c, "--version"], timeout=10)
            m = re.search(r"\d+\.\d+(?:\.\d+)?", out)
            _GIT_PATH = c
            _GIT_VERSION = m.group(0) if m else out.strip()
            return _GIT_PATH, _GIT_VERSION
        except Exception:
            continue
    return None, None


def git_path():
    return _GIT_PATH


def git_version():
    return _GIT_VERSION


def is_ready():
    return bool(_GIT_PATH)


def _exec(args, cwd=None, timeout=30):
    """执行外部命令，返回 stdout 文本；失败抛 GitError。"""
    # CREATE_NO_WINDOW：打包成无窗口程序后，防止每个 git 命令都闪一个黑色命令行框
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        p = subprocess.run(
            args, cwd=cwd, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace", creationflags=creationflags,
        )
    except FileNotFoundError:
        raise GitNotFound("找不到 git 程序。")
    except subprocess.TimeoutExpired:
        raise GitError("命令执行超时了（可能仓库特别大，或电脑正忙）。")
    if p.returncode != 0:
        msg = (p.stderr or "").strip() or f"命令执行失败（退出码 {p.returncode}）"
        raise GitError(msg)
    return p.stdout


# core.quotepath=false：中文文件名按原样显示，不转义成 \xxx 编码
# i18n.logoutputencoding=utf-8：让提交说明统一按 UTF-8 输出，避免中文乱码
_GLOBAL_ARGS = ["--no-pager", "-c", "core.quotepath=false", "-c", "i18n.logoutputencoding=utf-8"]


def run_git(repo, args, timeout=30):
    """在仓库 repo 里执行一条只读 git 命令，返回输出文本。"""
    if not _GIT_PATH:
        raise GitNotFound("还没有找到 git 程序，无法读取仓库信息。")
    return _exec([_GIT_PATH, *_GLOBAL_ARGS, "-C", repo, *args], timeout=timeout)


def is_git_repo(path):
    """判断文件夹是不是 Git 仓库（.git 可能是文件夹，也可能是文件）。"""
    return os.path.isdir(path) and os.path.exists(os.path.join(path, ".git"))


# ---- 提交历史的读取与解析 --------------------------------------------------

US = "\x1f"  # 同一条提交里各字段之间的分隔符
RS = "\x1e"  # 不同提交之间的分隔符

_LOG_FIELDS = ["hash", "short_hash", "author_name", "author_email",
               "author_date", "commit_date", "subject", "decoration", "parents", "body"]
_LOG_FMT = "%H" + US + "%h" + US + "%an" + US + "%ae" + US + "%aI" + US + "%cd" + US \
           + "%s" + US + "%d" + US + "%P" + US + "%b" + RS


def _parse_log_output(out):
    commits = []
    for rec in out.split(RS):
        # git 会在两条记录之间插入换行，拆分后每条记录开头可能带着它，要去掉
        rec = rec.strip("\n")
        if not rec:
            continue
        parts = rec.split(US, 9)
        if len(parts) < 10:
            continue
        d = dict(zip(_LOG_FIELDS, parts))
        d["refs"] = parse_decorations(d.get("decoration", ""))
        # 父提交（可能有多个：合并提交）——版本树要靠它画分支线
        d["parent_list"] = [p for p in (d.get("parents") or "").split() if p]
        commits.append(d)
    return commits


def parse_decorations(raw):
    """把 git 的装饰信息，如 " (HEAD -> main, origin/main, tag: v1)" 解析成字典。"""
    result = {"head_ref": None, "tags": [], "origin_refs": [], "others": []}
    raw = (raw or "").strip()
    if not raw:
        return result
    inner = raw.strip("()").strip()
    for tok in (t.strip() for t in inner.split(",")):
        if not tok:
            continue
        if tok.startswith("HEAD -> "):
            result["head_ref"] = tok[len("HEAD -> "):]
        elif tok == "HEAD":
            result["head_ref"] = "HEAD"
        elif tok.startswith("tag: "):
            result["tags"].append(tok[len("tag: "):])
        elif tok.startswith("origin/"):
            result["origin_refs"].append(tok)
        else:
            result["others"].append(tok)
    return result


def get_log(repo, limit=200):
    """读取提交历史（默认最近 200 条），按时间从新到旧。

    同时尝试从 README 的"版本记录"小节读取版本号，作为每个提交的显示名
    （README 里没有记录的更早提交会自动补 v0.x 编号）。
    """
    try:
        out = run_git(repo, ["log", f"--max-count={limit}", "--date=iso-strict-local",
                             "--decorate=short", f"--pretty=format:{_LOG_FMT}"])
    except GitError as e:
        # 新仓库还没有任何提交时，git 会报错，这里转成友好的空结果
        if "does not have any commits" in str(e) or "bad revision" in str(e).lower():
            return {"commits": [], "empty": True, "limit": limit}
        raise
    commits = _parse_log_output(out)
    labels, readme_count = assign_version_labels(repo, len(commits))
    return {"commits": commits, "empty": False, "limit": limit,
            "version_labels": labels, "version_readme_count": readme_count}


# ---- 从 README 的“版本记录”小节识别版本号 ----------------------------------

_README_NAMES = {"readme.md", "readme.txt", "readme.rst", "readme.markdown", "readme"}
_VERSION_SECTION_TITLES = {
    "版本记录", "版本历史", "版本日志", "版本说明",
    "更新记录", "更新日志", "更新历史",
    "changelog", "changelogs", "change log", "change logs", "release notes", "releases",
}
# 版本号：v1.2.0 / 1.2.0 等；不会误认 2026-10-24 这类日期，也不啃「迁移升级 v2」这类裸编号
# （v 前缀后必须跟至少一段点分数字，避免把散文里的 v2/v3 当成版本号）
_VERSION_TOKEN_RE = re.compile(
    r"(?i)(?<![0-9a-z.])(?:v\d{1,3}(?:\.\d{1,3}){1,3}|\d{1,3}(?:\.\d{1,3})+)(?![\d.])")


def _read_readme_text(repo):
    """读仓库根目录的 README 文本（前 200KB）；没有就返回 None。"""
    try:
        names = os.listdir(repo)
    except OSError:
        return None
    for name in names:
        if name.lower() in _README_NAMES and os.path.isfile(os.path.join(repo, name)):
            try:
                with open(os.path.join(repo, name), "rb") as f:
                    return f.read(200_000).decode("utf-8", errors="replace")
            except OSError:
                return None
    return None


_HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*#*$")
# 标题里除版本号/日期外允许出现的修饰符（括号、破折号、星号等）
_HEADING_NOISE_RE = re.compile(r"[\s:：*_\-—=·、，,。.()（）\[\]【】〈〉<>]+")
_HEADING_DATE_RE = re.compile(r"^\d{6,10}$")
# 条目行：版本号必须写在行首（允许 列表/引用/表格/标题/加粗 等装饰前缀），
# 说明散文里提到的版本号（如“版本号升至 1.7.0”）不会被误认成记录
_ENTRY_VER_RE = re.compile(
    r"^[\s#>*\-+·•|]*v?(\d{1,3}(?:\.\d{1,3}){1,3})(?![\d.])", re.IGNORECASE)


def _vkey(v):
    """版本号排序键：补齐到三段数字再比较，避免 (0,1) 与 (0,1,0) 的长度误判。"""
    try:
        parts = [int(x) for x in v.split(".")][:3]
    except ValueError:
        return (0, 0, 0)
    return tuple(parts) + (0,) * (3 - len(parts))


def _heading_version(s):
    """判断一行 Markdown 标题是否本身就是一个版本小节（如 "## v1.2.0"）。

    标题里恰好只有一个版本号、其余部分只有括号/日期等修饰（如
    "## [1.2.0] - 2026-10-24"）才算；是则返回版本号（不带 v 前缀），否则 None。
    """
    m = _HEADING_RE.match(s)
    if not m:
        return None
    title = m.group(2)
    toks = _VERSION_TOKEN_RE.findall(title)
    if len(toks) != 1:
        return None
    rest = _HEADING_NOISE_RE.sub("", _VERSION_TOKEN_RE.sub("", title))
    if rest == "" or _HEADING_DATE_RE.fullmatch(rest):
        return toks[0].lower().lstrip("v")
    return None


def _parse_readme_versions(text):
    """从 README 文本里找“版本记录”小节，按从新到旧返回版本号列表（不带 v 前缀）。

    只认两种写法，其余一律不收（防止把说明文字里提到的版本号当成记录）：
    1. 小节内的条目行：版本号写在行首，允许列表/表格/加粗等装饰前缀，
       如 “- v1.1.0 说明”、“| v1.0.0 | 日期 |”、“v0.9（日期 · hash）说明”；
    2. 独立版本标题：标题本身就是版本号，如 “## v1.2.0”、“## [1.2.0] - 日期”。
    没有「版本记录」小节、但全文有至少两条独立版本标题时，也按版本记录识别；
    若整节是“从旧到新”排列会自动反转。找不到返回空列表。
    """
    if not text:
        return []
    lines = text.splitlines()
    start = None
    level = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        m = _HEADING_RE.match(s)
        if m:
            title = re.sub(r"[\s:：**_\-—]+", "", m.group(2)).lower()
            if title in _VERSION_SECTION_TITLES:
                start, level = i + 1, len(m.group(1))
                break
        else:
            t = re.sub(r"[\s:：**_#>\-—【】\[\]（）()]+", "", s).lower()
            if t in _VERSION_SECTION_TITLES:
                start, level = i + 1, None
                break
    if start is None:
        # 没有小节标题：退一步认“标题即版本号”的小节（Keep a Changelog 常见写法）。
        # 要求至少两条，避免把正文里偶然出现的版本标题当成记录。
        versions = []
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            hv = _heading_version(s)
            if hv and hv not in versions:
                versions.append(hv)
            if len(versions) >= 50:
                break
        return versions if len(versions) >= 2 else []
    versions = []
    for ln in lines[start:]:
        s = ln.strip()
        if not s:
            continue
        if _HEADING_RE.match(s):
            hv = _heading_version(s)
            if hv:
                # 小节里用独立标题逐条记录版本（如 ## v1.2.0），本身即一条版本
                if hv not in versions:
                    versions.append(hv)
                continue
            m = re.match(r"^(#{1,6})(\s|$)", s)
            if m and (level is None or len(m.group(1)) <= level):
                break  # 到了下一个小节，版本记录结束
        m = _ENTRY_VER_RE.match(s)
        if m and m.group(1) not in versions:
            versions.append(m.group(1))
        if len(versions) >= 50:
            break

    if len(versions) >= 2 and _vkey(versions[0]) < _vkey(versions[-1]):
        versions.reverse()  # 文中是从旧到新写的，反成从新到旧
    return versions


def auto_version_label(pos_from_oldest):
    """自动编号：按提交先后连续编为 v0.1、v0.2、v0.3……（最旧 v0.1），永不跳主版本号。

    注意：这是本软件自己排的序号，不是 git 里的版本标签（tag）。
    """
    return f"v0.{pos_from_oldest}"


def _labels_from_versions(versions, n):
    """把 README 版本列表（从新到旧）套到 n 个提交上；记录不可信时返回 None。

    全部满足才采用，确保显示出的版本历史单调有序：
    ① 条数不超过提交数；② 版本号从新到旧严格递减（无重号、无乱序）；
    ③ 若只记录了最近 k 条（k < n），更早提交自动补 v0.x，且要求最老一条
    记录 > v0.(n-k)，避免自动编号与记录重叠。
    """
    if not versions or len(versions) > n:
        return None
    for a, b in zip(versions, versions[1:]):
        if _vkey(a) <= _vkey(b):
            return None
    k = len(versions)
    if k < n and _vkey(versions[-1]) <= _vkey(f"0.{n - k}"):
        return None
    return ["v" + v for v in versions] + [auto_version_label(n - i) for i in range(k, n)]


def assign_version_labels(repo, n):
    """给 n 个提交（从新到旧）分配显示用的版本名。

    优先使用 README“版本记录”里的版本号——但整份记录必须能与提交对上
    （条数兼容、严格递增，允许只记最近几条、更早的自动补 v0.x）才采用；
    记录缺失、条数对不上或有乱序/重号时，一律退回自动编号 v0.1…v0.N，
    保证任何情况下版本历史都单调有序。
    返回 (标签列表, 来自 README 的数量)。
    """
    try:
        versions = _parse_readme_versions(_read_readme_text(repo))
    except Exception:
        versions = []
    labels = _labels_from_versions(versions, n)
    if labels is not None:
        return labels, len(versions)
    return [auto_version_label(n - i) for i in range(n)], 0


def get_last_commit(repo):
    try:
        out = run_git(repo, ["log", "-1", "--date=iso-strict-local",
                             f"--pretty=format:{_LOG_FMT}"])
    except GitError:
        return None
    commits = _parse_log_output(out)
    return commits[0] if commits else None


# ---- 分支 / 远程 / 署名 / 状态 ---------------------------------------------

def _current_branch(repo):
    """当前分支名；处于"分离头指针"状态（不在任何分支上）时返回 None。"""
    # symbolic-ref 在"还没有任何提交"的新仓库里也能用，所以放在前面
    try:
        return run_git(repo, ["symbolic-ref", "--short", "HEAD"]).strip() or None
    except GitError:
        pass
    try:
        ref = run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        return None if ref == "HEAD" else ref
    except GitError:
        return None


def _remotes(repo):
    """远程仓库列表：[{name, url}]（取 fetch 地址）。"""
    out = run_git(repo, ["remote", "-v"])
    items, seen = [], set()
    for line in out.splitlines():
        line = line.rstrip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2 or not parts[1].endswith("(fetch)"):
            continue
        name = parts[0]
        url = parts[1][:-len("(fetch)")].strip()
        if name not in seen:
            seen.add(name)
            items.append({"name": name, "url": url})
    return items


def _branches(repo):
    fmt = "%(HEAD)\t%(refname:short)\t%(objectname:short)\t%(committerdate:unix)"
    out = run_git(repo, ["branch", "--list", "--format", fmt])
    result = []
    for line in out.splitlines():
        f = line.split("\t")
        if len(f) < 4:
            continue
        result.append({
            "name": f[1].strip(),
            "short_hash": f[2].strip(),
            "time": f[3].strip(),
            "current": f[0].strip() == "*",
        })
    return result


def _identity(repo, key):
    """读取 user.name / user.email，并标明设置来源（本仓库还是电脑全局）。"""
    try:
        out = run_git(repo, ["config", "--show-scope", "--get", key]).strip()
    except GitError:
        return {"value": None, "scope": None}
    if not out:
        return {"value": None, "scope": None}
    scope, _, value = out.partition("\t")
    return {"value": value.strip() or None, "scope": scope.strip() or None}


SCOPE_NAMES = {
    "local": "本仓库设置",
    "worktree": "本工作区设置",
    "global": "电脑通用设置",
    "system": "Git 安装时的默认设置",
    "command": "命令行临时设置",
}


def get_status(repo):
    """工作区状态摘要：有没有改了但还没提交的文件、和远程相比多了/少了几个提交。"""
    out = run_git(repo, ["status", "--porcelain=v1", "-b", "-z"])
    recs = [r for r in out.split("\0") if r.strip()]
    branch_line = ""
    if recs and recs[0].startswith("## "):
        branch_line = recs[0][3:].strip()
        recs = recs[1:]
    # 重命名条目在 -z 模式下会多出一段"旧路径"，用状态字母前缀把它区分开
    changed = sum(1 for r in recs if re.match(r"^[MADRCUT?!?]{1,2}\s", r))
    untracked = sum(1 for r in recs if r.startswith("??"))
    result = {"branch": None, "upstream": None, "ahead": 0, "behind": 0,
              "changed": changed, "untracked": untracked, "no_commits_yet": False}
    if branch_line.startswith("No commits yet on "):
        result["branch"] = branch_line.replace("No commits yet on ", "").strip()
        result["no_commits_yet"] = True
    elif branch_line.startswith("HEAD (no branch)"):
        result["branch"] = None
    else:
        m = re.match(r"^(.*?)\.\.\.(\S+)(?:\s+\[(.+)\])?$", branch_line)
        if m:
            result["branch"] = m.group(1).strip()
            result["upstream"] = m.group(2)
            flags = m.group(3) or ""
            a = re.search(r"ahead (\d+)", flags)
            b = re.search(r"behind (\d+)", flags)
            result["ahead"] = int(a.group(1)) if a else 0
            result["behind"] = int(b.group(1)) if b else 0
        elif branch_line:
            result["branch"] = branch_line
    return result


# ---- 版本对比（diff） ------------------------------------------------------

def diff_files(repo, a, b):
    """列出从版本 a 变到版本 b 时，所有发生变化的文件。"""
    out = run_git(repo, ["diff", "--name-status", "-M", "--no-color", "-z", a, b])
    files = []
    toks = out.split("\0")
    i = 0
    while i < len(toks):
        t = toks[i].strip()
        if not t:
            i += 1
            continue
        m = re.match(r"^([A-Z])(\d*)$", t)
        if not m:
            i += 1
            continue
        letter, i = m.group(1), i + 1
        if letter in ("R", "C") and i + 1 < len(toks):
            files.append({"status": letter, "code": t, "old_path": toks[i], "path": toks[i + 1]})
            i += 2
        elif i < len(toks):
            files.append({"status": letter, "code": t, "old_path": None, "path": toks[i]})
            i += 1
    return files


def diff_shortstat(repo, a, b):
    """汇总统计：几个文件有改动、新增几行、删除几行。"""
    out = run_git(repo, ["diff", "--shortstat", "-M", "--no-color", a, b]).strip()
    if not out:
        return {"files": 0, "insertions": 0, "deletions": 0}

    def num(pat):
        m = re.search(pat, out)
        return int(m.group(1)) if m else 0

    return {"files": num(r"(\d+) files? changed"),
            "insertions": num(r"(\d+) insertions?"),
            "deletions": num(r"(\d+) deletions?")}


MAX_DIFF_CHARS = 400_000  # 单个文件的差异内容上限，防止超大文件把界面卡死


def file_diff(repo, a, b, path, old_path=None):
    """读取单个文件在两个版本之间的具体差异文本。"""
    paths = list(dict.fromkeys([p for p in (old_path, path) if p]))
    ns = run_git(repo, ["diff", "--numstat", "-M", "--no-color", "-z", a, b, "--", *paths])
    toks = [t for t in ns.split("\0") if t.strip()]
    first = toks[0].split("\t") if toks else []
    added = first[0] if len(first) >= 2 else "0"
    deleted = first[1] if len(first) >= 2 else "0"
    if added == "-" or deleted == "-":
        # numstat 里出现 "-" 表示这是二进制文件（图片、压缩包等），无法逐行对比
        return {"binary": True, "text": "", "truncated": False, "added": None, "deleted": None}
    text = run_git(repo, ["diff", "--no-color", "-M", a, b, "--", *paths], timeout=60)
    truncated = len(text) > MAX_DIFF_CHARS
    if truncated:
        text = text[:MAX_DIFF_CHARS] + "\n……（差异内容太长，后面部分省略不显示）"
    return {"binary": False, "text": text, "truncated": truncated,
            "added": added, "deleted": deleted}


# ---- 面向界面的汇总接口 ----------------------------------------------------

def quick_info(repo):
    """仓库列表里每张卡片需要的少量信息（扫描时批量获取）。"""
    name = os.path.basename(os.path.normpath(repo))
    info = {"path": repo, "name": name, "branch": None,
            "last_subject": None, "last_time": None, "remote_url": "", "error": None}
    if not os.path.isdir(repo):
        info["missing"] = True
        info["error"] = "文件夹不存在"
        return info
    if not is_ready():
        info["error"] = "git-unavailable"
        return info
    try:
        info["branch"] = _current_branch(repo)
    except GitError as e:
        info["error"] = str(e)
    try:
        lc = get_last_commit(repo)
        if lc:
            info["last_subject"] = lc["subject"]
            info["last_time"] = lc["author_date"]
    except GitError:
        pass
    try:
        rs = _remotes(repo)
        info["remote_url"] = rs[0]["url"] if rs else ""
    except GitError:
        pass
    return info


def get_full_info(repo):
    """详情页需要的完整信息。某一部分失败不影响其他部分。"""
    info = {"path": repo, "name": os.path.basename(os.path.normpath(repo)), "errors": {}}

    def safe(key, fn, default):
        try:
            info[key] = fn()
        except GitError as e:
            info[key] = default
            info["errors"][key] = str(e)

    safe("branch", lambda: _current_branch(repo), None)
    safe("remotes", lambda: _remotes(repo), [])
    safe("branches", lambda: _branches(repo), [])
    safe("user_name", lambda: _identity(repo, "user.name"), {"value": None, "scope": None})
    safe("user_email", lambda: _identity(repo, "user.email"), {"value": None, "scope": None})
    safe("last_commit", lambda: get_last_commit(repo), None)
    safe("status", lambda: get_status(repo), None)
    safe("commit_count", lambda: int(run_git(repo, ["rev-list", "--count", "HEAD"]).strip() or 0), 0)
    return info
