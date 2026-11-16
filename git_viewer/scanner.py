"""scanner.py —— 在指定文件夹里找出所有 Git 仓库。

找法：从用户选的文件夹出发，一层层往下看，凡是里面带 .git 的文件夹
就是一个 Git 仓库。为了不把电脑扫卡，会跳过 node_modules 之类的
"几乎不可能放仓库"的文件夹，并限制扫描层数和数量上限；
多个磁盘会并行扫描，找到的仓库通过 on_found 实时上报。
"""
from __future__ import annotations

import os
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

# 这些文件夹里几乎不会有用户自己的 Git 仓库，跳过可以大大加快扫描
SKIP_DIRS = {
    "node_modules", "__pycache__", "venv", "env", "site-packages",
    "$recycle.bin", "system volume information",
    "windows", "program files", "program files (x86)", "programdata", "appdata",
    "application data", "local settings", "my documents",
    "recovery", "perflogs",
}

MAX_REPOS = 1000        # 最多记录这么多仓库，防止极端情况扫出上千个
MAX_VISITED = 600_000   # 最多检查这么多文件夹


def find_repos(root, max_depth=5, progress=None, should_stop=None, on_found=None):
    """扫描 root 及其子文件夹（最多 max_depth 层）。

    root 可以是单个文件夹路径，也可以是文件夹路径列表（实现多个文件夹、
    多个磁盘一起扫描）；多个磁盘并行扫描，重叠的扫描范围由调用方去重。
    每发现一个仓库会立即调用 on_found(路径)，方便界面实时展示。
    返回 (仓库路径列表, 统计信息)；stats 里 capped=True 表示达到了上限、
    还有位置没扫完（可加大深度或分批扫描）。progress(已检查数, 已发现数)
    用来汇报进度；should_stop 是 threading.Event，set() 可随时中止扫描。
    """
    roots = [root] if isinstance(root, str) else [r for r in root if r]
    max_depth = max(1, int(max_depth))
    repos, visited = [], 0
    capped, stopped = False, False
    lock = threading.Lock()

    def scan_one(root_path):
        nonlocal visited, capped, stopped
        queue = deque([(root_path, 0)])
        while queue:
            if should_stop is not None and should_stop.is_set():
                stopped = True
                return
            with lock:
                if visited >= MAX_VISITED or len(repos) >= MAX_REPOS:
                    capped = True
                    return
            d, depth = queue.popleft()
            with lock:
                visited += 1
                v = visited
            if progress is not None and v % 40 == 0:
                with lock:
                    progress(v, len(repos))
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue  # 没权限或被占用的文件夹直接跳过
            for e in entries:
                if e.name.lower() != ".git":
                    continue
                with lock:
                    repos.append(d)
                    full = len(repos) >= MAX_REPOS
                if on_found is not None:
                    on_found(d)
                if full:
                    capped = True
                    return
                break
            if depth >= max_depth:
                continue
            for e in entries:
                try:
                    if not e.is_dir(follow_symlinks=False):
                        continue
                    # junction（Windows 的目录联接）可能造成死循环，一律不进入
                    if getattr(e, "is_junction", lambda: False)():
                        continue
                except OSError:
                    continue
                low = e.name.lower()
                if low.startswith(".") or low in SKIP_DIRS:
                    continue
                queue.append((e.path, depth + 1))

    if len(roots) == 1:
        scan_one(roots[0])
    elif roots:
        with ThreadPoolExecutor(max_workers=min(4, len(roots))) as ex:
            list(ex.map(scan_one, roots))

    repos.sort(key=lambda p: p.lower())
    return repos, {"visited": visited, "found": len(repos),
                   "stopped": stopped, "capped": capped}


def gather_quick_infos(paths, progress=None, should_stop=None, workers=8):
    """并行读取每个仓库的简要信息（仓库列表卡片用）。"""
    from . import git_service

    infos = []
    total = len(paths)
    if total == 0:
        return infos
    with ThreadPoolExecutor(max_workers=min(workers, total)) as ex:
        futs = {ex.submit(git_service.quick_info, p): p for p in paths}
        done = 0
        for fut in as_completed(futs):
            if should_stop is not None and should_stop.is_set():
                break
            p = futs[fut]
            try:
                infos.append(fut.result())
            except Exception:
                infos.append({"path": p, "name": os.path.basename(os.path.normpath(p)),
                              "branch": None, "last_subject": None, "last_time": None,
                              "remote_url": "", "error": "读取失败"})
            done += 1
            if progress is not None:
                progress(done, total)
    infos.sort(key=lambda x: x["name"].lower())
    return infos
