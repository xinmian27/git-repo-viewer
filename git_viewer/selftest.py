"""selftest.py —— 不打开界面的自动化自检。

做法：在临时文件夹里用 git 造一个内容丰富的演示仓库（含中文提交说明、
多分支、重命名、二进制文件、远程地址），然后逐一验证读取功能是否正确。
运行方式：python main.py --selftest
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

from . import APP_NAME, git_service as gs
from . import i18n, scanner, utils
from .ui import styles


def _run_git(args, cwd):
    """造数据用的写操作 git 命令（只在临时演示仓库里执行）。"""
    return gs._exec([gs.git_path(), "-C", cwd, *args])


def _write(path, content, binary=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if binary else "w", encoding=None if binary else "utf-8") as f:
        f.write(content)


def make_demo_repo(base, name="演示项目"):
    """造一个功能完整的演示仓库，供自测和界面演示使用（已存在则先删掉重建）。"""
    repo = os.path.join(base, name)
    shutil.rmtree(repo, ignore_errors=True)
    os.makedirs(repo, exist_ok=True)
    _run_git(["init", "-b", "main"], repo)
    _run_git(["config", "user.name", "张三"], repo)
    _run_git(["config", "user.email", "zhangsan@example.com"], repo)
    _run_git(["remote", "add", "origin", "https://github.com/demo/demo-project.git"], repo)

    _write(os.path.join(repo, "README.md"), "# 演示项目\n\n这是一个用来演示的仓库。\n")
    _run_git(["add", "."], repo)
    _run_git(["commit", "-m", "第一次提交：创建项目"], repo)

    _write(os.path.join(repo, "app.js"), "console.log('hello');\n")
    _write(os.path.join(repo, "src", "main.py"), "print('你好，世界')\n")
    _run_git(["add", "."], repo)
    _run_git(["commit", "-m", "第二次提交：添加功能代码"], repo)

    _run_git(["checkout", "-b", "dev"], repo)
    _write(os.path.join(repo, "dev.txt"), "开发中的内容\n")
    _run_git(["add", "."], repo)
    _run_git(["commit", "-m", "dev 分支：尝试新功能"], repo)
    _run_git(["checkout", "main"], repo)

    _write(os.path.join(repo, "README.md"),
           "# 演示项目\n\n这是一个用来演示的仓库。\n\n## 更新说明\n\n- 修复了若干问题\n")
    _run_git(["add", "."], repo)
    _run_git(["commit", "-m", "第三次提交：完善说明文档"], repo)

    _write(os.path.join(repo, "README.md"),
           "# 演示项目\n\n这是一个用来演示的仓库。\n\n## 更新说明\n\n- 修复了若干问题\n\n"
           "## 版本记录\n\n- v1.1.0 2026-10-24 重命名入口文件并添加图标\n"
           "- v1.0.2 2026-10-23 完善说明文档\n- v1.0.1 2026-10-22 添加功能代码\n"
           "- v1.0.0 2026-10-21 创建项目\n")
    _run_git(["mv", "src/main.py", "src/entry.py"], repo)
    _write(os.path.join(repo, "src", "entry.py"), "print('你好，世界')\nprint('程序启动')\n")
    _write(os.path.join(repo, "logo.png"), bytes([0x89, 0x50, 0x4E, 0x47, 0x00, 0x01, 0xFF, 0x00]), binary=True)
    _run_git(["add", "."], repo)
    _run_git(["commit", "-m", "第四次提交：重命名入口文件并添加图标"], repo)
    return repo


def make_demo_folder(base):
    """造一个"看起来像真实工作区"的演示文件夹：多个仓库、含嵌套。"""
    os.makedirs(base, exist_ok=True)
    make_demo_repo(base, "演示项目")
    make_demo_repo(base, "学习笔记")
    make_demo_repo(os.path.join(base, "旧版本备份"), "2024旧项目")


def run_selftest():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(f"== {APP_NAME} 自动自检 ==")
    path, ver = gs.find_git()
    print(("✓" if path else "✗"), "找到 git：", path, ver)
    if not path:
        print("请先安装 Git 再运行自检。")
        return 1

    checks = []

    def check(name, cond, extra=""):
        checks.append(bool(cond))
        print(("✓" if cond else "✗"), name, ("—— " + str(extra) if (extra and not cond) else ""))

    base = tempfile.mkdtemp(prefix="grv_selftest_")
    repo = make_demo_repo(base)

    info = gs.get_full_info(repo)
    check("识别当前分支 main", info["branch"] == "main", info["branch"])
    check("本地分支包含 main 和 dev",
          {"main", "dev"} <= {b["name"] for b in info["branches"]},
          info["branches"])
    check("读到远程仓库地址",
          bool(info["remotes"]) and info["remotes"][0]["url"].endswith("demo-project.git"),
          info["remotes"])
    check("读到用户名（本仓库设置）",
          info["user_name"]["value"] == "张三" and info["user_name"]["scope"] == "local",
          info["user_name"])
    check("读到邮箱", info["user_email"]["value"] == "zhangsan@example.com", info["user_email"])
    check("最近一次提交说明正确",
          info["last_commit"] and "第四次提交" in info["last_commit"]["subject"],
          info["last_commit"] and info["last_commit"]["subject"])
    check("提交总数 = 4", info["commit_count"] == 4, info["commit_count"])
    st = info["status"]
    check("工作区无未提交改动", st is not None and st["changed"] == 0, st)

    log = gs.get_log(repo)
    check("提交历史条数 = 4", len(log["commits"]) == 4, len(log["commits"]))
    c = log["commits"][0]
    check("历史包含作者/时间/说明",
          c["author_name"] == "张三" and c["author_date"] and c["subject"],
          c)
    check("最新提交带 HEAD 装饰", c["refs"]["head_ref"] == "main", c["refs"])
    labels = log.get("version_labels") or []
    check("版本名取自 README 版本记录",
          labels == ["v1.1.0", "v1.0.2", "v1.0.1", "v1.0.0"], labels)
    check("README 版本记录条数", log.get("version_readme_count") == 4,
          log.get("version_readme_count"))
    vs = gs._parse_readme_versions(
        "# 项目\n\n## 更新日志\n\n- v2.0 2026-01-01 发布\n- 2025-12-31 内部测试\n")
    check("识别更新日志小节且不误认日期", vs == ["2.0"], vs)
    vs2 = gs._parse_readme_versions(
        "# 项目\n\n## 版本记录\n\n## v1.2.0\n\n- 修复若干问题\n\n## v1.1.0\n\n- 首次发布\n")
    check("版本记录小节内支持独立版本标题", vs2 == ["1.2.0", "1.1.0"], vs2)
    vs3 = gs._parse_readme_versions(
        "# 项目\n\n## [1.2.0] - 2026-10-24\n\n- 修复\n\n## [1.1.0] - 2026-10-01\n\n- 发布\n")
    check("无小节标题时按版本标题识别", vs3 == ["1.2.0", "1.1.0"], vs3)
    vs4 = gs._parse_readme_versions("# 项目\n\n## v1.0.0\n\n正文说明，只有一条版本标题不算\n")
    check("单个版本标题不误判为版本记录", vs4 == [], vs4)
    empty_dir = tempfile.mkdtemp(prefix="grv_noreadme_")
    auto_labels, auto_count = gs.assign_version_labels(empty_dir, 4)
    check("无 README 版本记录时自动编号",
          auto_labels == ["v0.4", "v0.3", "v0.2", "v0.1"] and auto_count == 0, auto_labels)
    auto12, auto12_cnt = gs.assign_version_labels(empty_dir, 12)
    check("自动编号超过 9 仍连续递增（不跳主版本号）",
          auto12[:4] == ["v0.12", "v0.11", "v0.10", "v0.9"] and auto12[-1] == "v0.1"
          and auto12_cnt == 0, auto12)
    vs5 = gs._parse_readme_versions(
        "# 项目\n\n## 版本记录\n\n规则：保持条数与提交数一致。\n\n"
        "- v1.2.0（2026-10-25 · abc1234）版本号升至 1.7.0，含 `## v1.2.0` 写法说明\n"
        "- v1.1.0（2026-10-24 · abc1234）初版\n")
    check("条目说明里的其他版本号不误认", vs5 == ["1.2.0", "1.1.0"], vs5)
    lab = gs._labels_from_versions(["1.1.0", "1.0.0"], 4)
    check("部分记录与自动补号拼接后单调有序",
          lab == ["v1.1.0", "v1.0.0", "v0.2", "v0.1"], lab)
    check("记录条数超过提交数则整体弃用",
          gs._labels_from_versions(
              ["0.14", "0.13", "1.7.0", "0.12", "0.11", "1.2.0", "0.10", "0.9",
               "0.8", "0.7", "0.6", "0.5", "0.4", "0.3", "0.2", "0.1"], 14) is None)
    check("记录重号或乱序则弃用",
          gs._labels_from_versions(["1.0.0", "1.0.0"], 2) is None
          and gs._labels_from_versions(["0.2", "0.3"], 2) is None)
    check("自动补号会与记录重叠则弃用", gs._labels_from_versions(["0.2", "0.1"], 4) is None)

    first = log["commits"][-1]["hash"]
    last = log["commits"][0]["hash"]
    files = gs.diff_files(repo, first, last)
    names = {f["path"] for f in files}
    check("diff 文件列表包含 README.md", "README.md" in names, sorted(names))
    # 重命名检测需要新旧两个文件在两个版本里都存在：main.py 是第 2 次提交才加进来的，
    # 所以用"第二次提交 → 最新提交"来验证重命名识别
    second = log["commits"][1]["hash"]
    files2 = gs.diff_files(repo, second, last)
    check("diff 识别重命名（main.py → entry.py）",
          any(f["status"] == "R" and f["path"].endswith("entry.py") for f in files2),
          [(f["status"], f["path"]) for f in files2])
    check("diff 列出新增的图片文件", any(f["path"].endswith("logo.png") for f in files), names)

    ss = gs.diff_shortstat(repo, first, last)
    check("diff 汇总统计", ss["files"] == len(files) and ss["files"] > 0, ss)

    rd = gs.file_diff(repo, first, last, "README.md")
    check("单文件 diff 有新增行",
          any(l.startswith("+") and not l.startswith("+++") for l in rd["text"].splitlines()),
          rd["text"][:200])
    renames = [f for f in files2 if f["status"] == "R"]
    if renames:
        rb = gs.file_diff(repo, second, last, renames[0]["path"], renames[0]["old_path"])
        check("重命名文件的 diff 可读", (not rb["binary"]) and "main.py" in rb["text"],
              rb["text"][:200])
    png = [f for f in files if f["path"].endswith("logo.png")]
    if png:
        bb = gs.file_diff(repo, first, last, png[0]["path"])
        check("二进制文件正确识别", bb["binary"] is True, bb)

    repos, stats = scanner.find_repos(base, max_depth=5)
    check("扫描找到 1 个仓库", len(repos) == 1, stats)
    infos = scanner.gather_quick_infos(repos)
    check("扫描读取仓库信息", bool(infos) and infos[0]["branch"] == "main", infos)

    # 面向普通用户的显示处理：藏掉 git 的原始头部行、把 @@ 换成中文提示
    sample = ("diff --git a/x.txt b/x.txt\nindex 1111111..2222222 100644\n"
              "--- a/x.txt\n+++ b/x.txt\n@@ -3,2 +3,2 @@ 函数名\n-旧的一行\n+新的一行\n")
    clean = utils.strip_diff_meta(sample)
    check("diff 隐藏技术头部", "diff --git" not in clean and "index 1111111" not in clean, clean)
    check("diff 保留正文与分段标记", "@@ -3,2 +3,2 @@" in clean and "+新的一行" in clean, clean)
    check("diff 不误删以 --- 开头的内容行",
          "--- 分隔线" in utils.strip_diff_meta("@@ -1 +1 @@\n---- 分隔线\n"),
          utils.strip_diff_meta("@@ -1 +1 @@\n---- 分隔线\n"))
    friendly = utils.friendly_hunks("@@ -5,3 +5,10 @@ 函数名\n+一行\n")
    check("diff 分段提示讲人话", "@@" not in friendly and "第 5 行" in friendly, friendly)

    # 多语言：繁中走字符级转换，英文走整串词典；路径与代码不应被改
    old_lang = i18n.current_language()
    i18n.set_language("zh_TW")
    tw = i18n.translate("提交历史")
    i18n.set_language("en")
    en = i18n.translate("提交历史")
    path = i18n.translate("D:\\projects\\旧版本备份")
    i18n.set_language(old_lang)
    check("多语言 繁中转换", tw == "提交歷史", tw)
    check("多语言 英文词典", en == "History", en)
    check("多语言 不翻译路径", path == "D:\\projects\\旧版本备份", path)

    # 换语言必须是可逆的：英文再切回中文，原文要一模一样（否则界面会越切越乱）
    zh_src = "提交历史"
    i18n.set_language("en")
    en_again = i18n.translate(zh_src)
    i18n.set_language("zh_CN")
    back = i18n.translate(zh_src)
    check("多语言 切回中文可逆", en_again == "History" and back == zh_src,
          f"{en_again} / {back}")
    # 数据（仓库名等）不该被翻译：它们走 set_raw，translate 也不该改动纯数据串
    data_name = "学习笔记"
    check("多语言 数据保持原样", i18n.translate(data_name) == data_name,
          i18n.translate(data_name))

    # 主题：跟随系统要能解析成实际深浅色，深色版 diff 用暗色底
    resolved = styles.resolved_mode(None, "dark")
    check("主题 深色解析", resolved == "dark", resolved)
    dark_add = utils.diff_to_html("+新增\n-删除\n", dark=True)
    light_add = utils.diff_to_html("+新增\n-删除\n", dark=False)
    check("主题 深色 diff 换配色", dark_add != light_add and "#12291b" in dark_add, dark_add[:120])

    # 版本树泳道：合并提交的第二个父提交要单独占一条分支（否则线会重叠）
    from .ui.version_graph import _assign_lanes
    linear = _assign_lanes([{"hash": "a", "parent_list": ["b"]},
                            {"hash": "b", "parent_list": ["c"]},
                            {"hash": "c", "parent_list": []}])
    check("版本树泳道 线性", linear == [0, 0, 0], str(linear))
    merged = _assign_lanes([
        {"hash": "m", "parent_list": ["b"]},
        {"hash": "b", "parent_list": ["c", "d"]},   # 合并提交：第二个父提交另开一条泳道
        {"hash": "d", "parent_list": ["e"]},        # dev 分支上的提交
        {"hash": "c", "parent_list": ["e"]},        # 主线上的提交
        {"hash": "e", "parent_list": []},
    ])
    check("版本树泳道 合并分出分支", merged == [0, 0, 1, 0, 0], str(merged))

    print()
    failed = checks.count(False)
    print(f"共 {len(checks)} 项检查：" + ("全部通过 ✓" if failed == 0 else f"{failed} 项失败 ✗"))
    return 0 if failed == 0 else 1
