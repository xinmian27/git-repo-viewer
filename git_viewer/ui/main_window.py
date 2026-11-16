"""main_window.py —— 主窗口：把所有部件组装起来，并负责后台任务调度。"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QDir, Qt, QStandardPaths, QTimer, Signal, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QMainWindow, QMessageBox, QProgressDialog,
                               QPushButton, QSplitter, QStackedWidget,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import APP_NAME, APP_VERSION
from .. import git_service as gs
from .. import i18n, scanner, selftest, settings, trash, utils
from ..workers import AsyncRunner
from .delete_dialog import DeleteRepoDialog
from .diff_tab import DiffTab
from .help_dialog import GitGuideDialog, HelpDialog
from .history_tab import HistoryTab
from .info_tab import InfoTab
from .repo_list_panel import MAX_DEPTH, RepoListPanel
from .settings_dialog import SettingsDialog
from .widgets import ElidedLabel, EmptyState, SoftButton


class MainWindow(QMainWindow):
    scan_progress = Signal(object)
    batch_progress = Signal(object)   # 批量删除在后台线程执行，进度经此信号回主线程

    def __init__(self, git_ready, git_version, auto_scan=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git可视化仓库")
        # 窗口尺寸跟随屏幕可用区域：既保证抽屉展开后的空间，也不会超出屏幕边界
        self._apply_screen_size()

        self._git_ready = git_ready
        self._git_version = git_version
        self._current_repo = None
        self._repo_cache = {}        # 详情缓存：切换仓库直接秒开，点「刷新」才重新读取
        self._collection_infos = {}  # 收藏列表里每个仓库的简要信息（path -> info）
        self._rendered_order = []    # 当前列表的实际展示顺序
        self._seq = 0
        self._scan_sid = 0     # 扫描会话编号：取消/重开扫描后，旧扫描的进度不再显示
        self._scanning = False
        self._scan_stop = threading.Event()
        self._batch_dlg = None       # 批量删除的进度框（首条进度到达时才创建）
        self._batch_stop = threading.Event()
        self._delete_dlg = None      # 单个仓库删除时的"正在移动"等待框
        self._demo = False

        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(4)
        self.runner_scan = AsyncRunner(self.pool)
        self.runner_collection = AsyncRunner(self.pool)  # 单独一个：读收藏列表不会和扫描互相作废
        self.runner_info = AsyncRunner(self.pool)
        self.runner_card = AsyncRunner(self.pool)  # 单独一个：卡片「重新读取信息」不打断主面板的读取
        self.runner_log = AsyncRunner(self.pool)
        self.runner_diff = AsyncRunner(self.pool)
        self.runner_file = AsyncRunner(self.pool)
        self.runner_batch = AsyncRunner(self.pool)
        self.runner_delete = AsyncRunner(self.pool)  # 单个删除独立：搬大文件夹时后台慢慢做

        self.scan_progress.connect(self._on_scan_progress)
        self.batch_progress.connect(self._on_batch_progress)
        self._build_ui()
        i18n.retranslate(self)  # 构造函数里写死的文字，也按当前语言过一遍

        if not git_ready:
            self.banner.setVisible(True)
            self.statusBar().showMessage("⚠ 还没有安装 Git 工具，暂时读不了仓库信息。点上面的「查看安装教程」。", 0)
        else:
            self.statusBar().showMessage(
                f"Git 工具已就绪（版本 {git_version}）。平时只读取信息，不会改动你的代码；"
                "只有你主动删除 Git 历史时，才会把 .git 文件夹移入回收站（代码不受影响）。", 8000)
            repos = settings.repos()
            if repos:
                # 已有收藏列表：直接读取展示（秒开，无需扫描）
                QTimer.singleShot(200, self._load_collection)
            elif auto_scan:
                locs = [f for f in settings.last_folders() if os.path.isdir(f)]
                if locs and not settings.initialized():
                    # 老版本升级：把上次扫描的位置扫一遍，作为初始收藏列表
                    QTimer.singleShot(200, lambda ls=locs: self.add_repos_from_scan(ls))
                else:
                    # 首次使用：默认扫描常用位置和本机所有固定磁盘，
                    # 把找到的所有仓库直接列出来，不用先手动选择
                    QTimer.singleShot(200, lambda: self.add_repos_from_scan(default_scan_roots()))

    # ---- 界面搭建 ----

    def _apply_screen_size(self):
        """窗口大小跟随屏幕可用区域：不超出屏幕，且给抽屉展开留足空间。"""
        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        max_w = avail.width() - 24 if avail else 1420
        max_h = avail.height() - 24 if avail else 980
        self.resize(min(1420, max(900, max_w)), min(980, max(640, max_h)))
        # 最小尺寸同样不超过屏幕，保证窗口化后仍可自由调整大小
        self.setMinimumSize(min(1320, max(960, max_w - 40)),
                            min(780, max(600, max_h - 40)))

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("root")
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 顶部提醒条（没装 Git 时显示）
        self.banner = QFrame()
        self.banner.setObjectName("bannerWarn")
        self.banner.setVisible(False)
        bv = QHBoxLayout(self.banner)
        bv.setContentsMargins(14, 8, 14, 8)
        bt = QLabel("⚠ 没有检测到 Git 工具 —— 没有它就无法读取仓库信息。")
        bv.addWidget(bt)
        bv.addStretch(1)
        guide_btn = QPushButton("查看安装教程")
        guide_btn.setObjectName("primary")
        guide_btn.clicked.connect(self._show_git_guide)
        bv.addWidget(guide_btn)
        v.addWidget(self.banner)

        # 顶部栏：应用名 + 全局按钮（窗口最上面那一行）
        header = QFrame()
        header.setObjectName("header")
        hv = QVBoxLayout(header)
        hv.setContentsMargins(14, 6, 14, 6)
        hv.setSpacing(0)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        title = QLabel(" Git可视化仓库")
        title.setObjectName("appTitle")
        row1.addWidget(title)
        row1.addStretch(1)

        settings_btn = QPushButton("⚙ 设置")
        settings_btn.setObjectName("ghost")
        settings_btn.setToolTip("外观、语言、快捷键和版本信息")
        settings_btn.clicked.connect(self._show_settings)
        row1.addWidget(settings_btn)

        help_btn = QPushButton("📖 使用说明")
        help_btn.setObjectName("ghost")
        help_btn.setToolTip("三步上手、常见名词、遇到问题怎么办")
        help_btn.clicked.connect(self._show_help)
        row1.addWidget(help_btn)
        hv.addLayout(row1)
        # 标题栏高度约 1cm（96dpi 下 38px），看起来更松弛
        header.setMinimumHeight(38)
        v.addWidget(header)

        # 「当前仓库」信息条：名字 + 位置 + 操作，位于右侧详情区顶部
        self.repo_bar = QFrame()
        self.repo_bar.setObjectName("repoBar")
        rb = QHBoxLayout(self.repo_bar)
        rb.setContentsMargins(0, 0, 0, 8)
        rb.setSpacing(8)
        self.head_name_lbl = QLabel("")
        self.head_name_lbl.setObjectName("repoTitle")
        rb.addWidget(self.head_name_lbl)
        self.head_path_lbl = ElidedLabel("", Qt.ElideMiddle)
        self.head_path_lbl.setObjectName("muted")
        rb.addWidget(self.head_path_lbl, 1)
        self.head_copy_btn = SoftButton("复制路径")
        self.head_copy_btn.setToolTip("把上面这个路径复制到剪贴板")
        self.head_copy_btn.clicked.connect(self._copy_repo_path)
        rb.addWidget(self.head_copy_btn)
        rb.addSpacing(6)
        self.head_refresh_btn = SoftButton("🔄 刷新")
        self.head_refresh_btn.setToolTip("重新读取这个仓库的最新信息（快捷键 F5）")
        self.head_refresh_btn.clicked.connect(self._refresh_current)
        rb.addWidget(self.head_refresh_btn)
        self.head_folder_btn = SoftButton("📂 打开所在文件夹")
        self.head_folder_btn.setToolTip("在文件管理器里打开这个项目所在的文件夹")
        self.head_folder_btn.clicked.connect(self._open_repo_folder)
        rb.addWidget(self.head_folder_btn)
        self.head_delete_btn = SoftButton("🗑 删除")
        self.head_delete_btn.setToolTip("选择删除内容：Git 历史（.git）、整个文件夹，或仅从列表移除")
        self.head_delete_btn.clicked.connect(self._delete_current_repo)
        rb.addWidget(self.head_delete_btn)
        self.repo_bar.setVisible(False)

        # 主体：左列表 + 右详情
        body = QSplitter(Qt.Horizontal)
        self.repo_panel = RepoListPanel()
        self.repo_panel.selected.connect(lambda p: self._load_repo(p))
        self.repo_panel.add_requested.connect(self.pick_and_scan)
        self.repo_panel.continue_scan.connect(self._continue_scan)
        self.repo_panel.cancel_scan.connect(self._cancel_scan)
        self.repo_panel.pin_toggled.connect(self._toggle_pin)
        self.repo_panel.batch_action.connect(self._on_batch_action)
        self.repo_panel.depth_changed.connect(settings.set_depth)
        self.repo_panel.sort_changed.connect(self._render_repo_list)
        self.repo_panel.open_folder.connect(self._open_path_folder)
        self.repo_panel.card_action.connect(self._on_card_action)
        body.addWidget(self.repo_panel)

        self.stack = QStackedWidget()

        self.empty_page = EmptyState(
            "👋", "欢迎使用 Git可视化仓库！",
            "三步就能用起来：\n"
            "① 点左边「➕ 添加仓库」，选一个放着代码的文件夹\n"
            "② 在左边点开任意项目，右边就能看到它的全部信息\n"
            "③ 想知道改了什么，去「提交历史」和「版本对比」看")
        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(8)
        shortcuts.setAlignment(Qt.AlignCenter)
        for name, loc in (("🖥 桌面", QStandardPaths.DesktopLocation),
                          ("📄 文档", QStandardPaths.DocumentsLocation),
                          ("⬇️ 下载", QStandardPaths.DownloadLocation)):
            b = QPushButton(name)
            b.setObjectName("ghost")
            b.setToolTip("扫描该位置，把找到的新仓库加入列表")
            b.clicked.connect(lambda _, l=loc: self._add_std_path(l))
            shortcuts.addWidget(b)
        holder = QWidget()
        holder.setLayout(shortcuts)
        self.empty_page.add_extra(holder)

        # 一键生成示例项目：本机还没有 Git 项目的小白也能马上看到完整效果
        sample_row = QHBoxLayout()
        sample_row.setAlignment(Qt.AlignCenter)
        self.sample_btn = QPushButton("👀 没有现成的项目？用一个示例项目练手")
        self.sample_btn.setObjectName("primary")
        self.sample_btn.setCursor(Qt.PointingHandCursor)
        self.sample_btn.setToolTip("在电脑上生成 3 个很小的示例仓库（不会动你原有的任何文件）")
        self.sample_btn.clicked.connect(self._open_sample_project)
        sample_row.addWidget(self.sample_btn)
        sample_holder = QWidget()
        sample_holder.setLayout(sample_row)
        self.empty_page.add_extra(sample_holder)

        self.last_folder_lbl = QLabel("")
        self.last_folder_lbl.setObjectName("muted")
        self.last_folder_lbl.setWordWrap(True)
        self.last_folder_lbl.setAlignment(Qt.AlignCenter)
        self.empty_page.add_extra(self.last_folder_lbl)
        self._update_last_folder_lbl()
        self.stack.addWidget(self.empty_page)

        detail_page = QWidget()
        dv = QVBoxLayout(detail_page)
        dv.setContentsMargins(14, 12, 14, 12)
        dv.setSpacing(10)
        dv.addWidget(self.repo_bar)

        self.tabs = QTabWidget()
        self.info_tab = InfoTab(status_cb=self._toast)
        self.history_tab = HistoryTab(status_cb=self._toast)
        self.diff_tab = DiffTab(self.runner_diff, self.runner_file, status_cb=self._toast)
        self.tabs.addTab(self.info_tab, "基本信息")
        self.tabs.addTab(self.history_tab, "提交历史")
        self.tabs.addTab(self.diff_tab, "版本对比")
        dv.addWidget(self.tabs, 1)
        self.stack.addWidget(detail_page)

        body.addWidget(self.stack)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setSizes([340, 920])
        v.addWidget(body, 1)
        self.setCentralWidget(central)

        # 状态栏
        self.git_status_lbl = QLabel()
        self.statusBar().addPermanentWidget(self.git_status_lbl)
        self._update_git_status_lbl()

        # 快捷键：F5 重新读取当前仓库、Ctrl+F 直接跳到搜索框
        QShortcut(QKeySequence("F5"), self, self._refresh_current)
        QShortcut(QKeySequence.StandardKey.Find, self, self._focus_search)

    def _focus_search(self):
        self.repo_panel.search.setFocus()
        self.repo_panel.search.selectAll()

    def _update_git_status_lbl(self):
        # 右下角显示软件自己的版本号（与版本树一致），Git 工具信息跟在后面
        if self._git_ready:
            self.git_status_lbl.setText(f"{APP_NAME} v{APP_VERSION}  ·  Git 工具 ✓ v{self._git_version}")
            self.git_status_lbl.setStyleSheet("color: #16a34a;")
        else:
            self.git_status_lbl.setText(f"{APP_NAME} v{APP_VERSION}  ·  Git 工具未安装 ✗")
            self.git_status_lbl.setStyleSheet("color: #dc2626;")

    # ---- 扫描 ----

    def pick_and_scan(self):
        # 扫描进行中也允许重新选择：先取消当前扫描，再挑新位置
        if self._scanning:
            self._scan_stop.set()
        last = settings.last_folders()
        start = last[0] if last else QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
        dirs = []
        try:
            # 非原生对话框才能按住 Ctrl 多选文件夹/磁盘
            dialog = QFileDialog(
                self, "选择要扫描的文件夹（可按住 Ctrl 一次多选；也可以直接选某个磁盘整盘扫描）",
                start)
            dialog.setFileMode(QFileDialog.FileMode.Directory)
            dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            dialog.setSelectionMode(QFileDialog.AbstractItemView.SelectionMode.MultiSelection)
            if dialog.exec():
                dirs = [os.path.normpath(d) for d in dialog.selectedFiles()
                        if d and os.path.isdir(d)]
        except Exception:
            # 多选对话框万一打不开，退回单个文件夹选择，保证按钮永远有响应
            d = QFileDialog.getExistingDirectory(self, "选择要扫描的文件夹", start)
            dirs = [os.path.normpath(d)] if d and os.path.isdir(d) else []
        if dirs:
            self.add_repos_from_scan(dirs)

    def _add_std_path(self, loc):
        path = QStandardPaths.writableLocation(loc)
        if path:
            self.add_repos_from_scan([path])

    def add_repos_from_scan(self, folder):
        """扫描一个或多个文件夹/磁盘，把找到的"新"仓库加入收藏列表。

        folder 可传单个路径字符串或路径列表；已有收藏不会被移除，
        重复扫描同一位置只会补充新出现的仓库。扫描中按钮保持可点，
        再次选择会自动取消当前扫描并重新开始。
        """
        if not gs.is_ready():
            self._show_git_guide()
            return
        folders = [folder] if isinstance(folder, str) else [f for f in folder if f]
        folders = [os.path.normpath(os.path.abspath(f)) for f in folders]
        folders = list(dict.fromkeys(folders))  # 去重，保持先后顺序
        folders = [f for f in folders if os.path.isdir(f)]
        if not folders:
            self._toast("所选的文件夹不存在")
            return
        self._scanning = True
        self._scan_sid += 1
        sid = self._scan_sid
        self._scan_stop = threading.Event()
        self.repo_panel.set_scanning(True)
        settings.set_last_folders(folders)  # 记住扫描位置，下次「添加仓库」默认选中
        self._update_last_folder_lbl()
        depth = settings.depth()
        self.statusBar().showMessage(
            f"正在添加仓库：扫描 {len(folders)} 个位置（往里找 {depth} 层）…"
            "首次扫描可能要几十秒，可以点左下角「停止扫描」随时停下。")

        def progress_cb(payload):
            payload["_sid"] = sid
            self.scan_progress.emit(payload)

        def job():
            paths, stats = scanner.find_repos(
                folders, depth,
                progress=lambda visited, found: progress_cb(
                    {"phase": "find", "visited": visited, "found": found}),
                should_stop=self._scan_stop,
                on_found=lambda p: progress_cb({"phase": "found_one", "path": p}))
            new_paths = sorted(set(paths) - set(self._collection_infos), key=str.lower)
            infos = scanner.gather_quick_infos(
                new_paths,
                progress=lambda i, n: progress_cb({"phase": "read", "i": i, "n": n}),
                should_stop=self._scan_stop)
            return {"folders": folders, "infos": infos, "stats": stats,
                    "total_found": len(paths), "_sid": sid}

        self.runner_scan.run(job, on_ok=self._on_scan_done, on_err=self._on_scan_error)

    def _on_scan_progress(self, payload):
        if payload.get("_sid") != self._scan_sid:
            return  # 已被取消的旧扫描发来的迟到进度，忽略
        phase = payload.get("phase")
        if phase == "find":
            self.statusBar().showMessage(
                f"正在扫描…已检查 {payload['visited']} 个文件夹，发现 {payload['found']} 个仓库")
        elif phase == "found_one":
            self.repo_panel.add_pending(payload["path"])  # 实时上架刚发现的仓库
        elif phase == "read":
            self.statusBar().showMessage(
                f"正在读取仓库信息…{payload['i']}/{payload['n']}")

    def _on_scan_error(self, msg):
        self._scanning = False
        self.repo_panel.set_scanning(False)
        if self._demo:
            print("[demo] scan error:", msg, flush=True)
            QTimer.singleShot(3000, lambda: self.close())
        self.statusBar().showMessage(f"扫描失败：{msg}", 8000)

    def _cancel_scan(self):
        """扫描中的「停止扫描」：已找到的仓库会保留，随时可以再点添加继续。"""
        if not self._scanning:
            return
        self._scan_stop.set()
        self._toast("正在停止扫描…已经找到的仓库会保留下来")

    def _on_scan_done(self, result):
        if result.get("_sid") != self._scan_sid:
            return  # 旧扫描的结果，忽略
        self._scanning = False
        self.repo_panel.set_scanning(False)
        infos = result["infos"]
        folders = result["folders"]
        stats = result["stats"]
        added = 0
        for i in infos:
            if i["path"] not in self._collection_infos:
                self._collection_infos[i["path"]] = i
                added += 1
        repos = settings.repos()
        for i in infos:
            if i["path"] not in repos:
                repos.append(i["path"])
        settings.set_repos(repos)
        settings.set_initialized()
        self._render_repo_list()

        # 扫描被中途取消的不算"扫完"；因达到上限提前停止的，在列表底部给出「继续扫描」入口
        capped = bool(stats.get("capped")) and not stats.get("stopped")
        settings.set_scan_capped(capped)
        self.repo_panel.set_scan_capped(capped)

        where = describe_locations(folders)
        total = len(self._collection_infos)
        cap_note = ("⚠ 已达到扫描上限，部分更深的位置没有检查；"
                    "可点列表底部的「继续扫描」，或到左下角「⚙ 扫描设置」加大深度后再次添加。"
                    if capped else "")
        if stats.get("stopped"):
            self.statusBar().showMessage(
                f"⏹ 扫描已停止（本次新找到 {added} 个仓库，列表共 {total} 个）", 8000)
        elif added:
            self.statusBar().showMessage(
                f"✅ 添加完成：新找到 {added} 个仓库，列表共 {total} 个"
                f"（检查了 {stats['visited']} 个文件夹）。{cap_note}", 12000)
        else:
            self.statusBar().showMessage(
                f"扫描完成：没有发现新的仓库（列表共 {total} 个，"
                f"检查了 {stats['visited']} 个文件夹）。{cap_note}", 12000)

        if not self._collection_infos:
            self.stack.setCurrentWidget(self.empty_page)
            self.empty_page.set_message(
                "这些位置里没有找到 Git 仓库",
                f"已扫描：{where}\n"
                "可以试试：① 选项目的上一层文件夹重新添加；"
                "② 点左下角「⚙ 扫描设置」把深度调大再扫；"
                "③ 确认它是 Git 项目（文件夹里能看到隐藏的 .git）。\n"
                "还是找不到？点上面的示例项目按钮，先看看这个软件能做什么。")
            return

        prev = self._current_repo
        if not (prev and prev in self._collection_infos) and self._rendered_order:
            self.repo_panel.select_path(self._rendered_order[0])

        if self._demo:
            print("[demo] scan done, repos:", added, flush=True)
            QTimer.singleShot(2500, lambda: self.tabs.setCurrentIndex(0))
            QTimer.singleShot(5000, lambda: self.tabs.setCurrentIndex(1))
            QTimer.singleShot(7500, lambda: self.tabs.setCurrentIndex(2))
            QTimer.singleShot(10000, lambda: self.diff_tab.file_list.setCurrentRow(1)
                              if self.diff_tab.file_list.count() > 1 else None)
            QTimer.singleShot(15500, lambda: self.close())
            QTimer.singleShot(18500, lambda: QApplication.instance().quit())

    def _continue_scan(self):
        """上次扫描因上限提前停止：自动加大一层深度，重扫上次的位置补充新仓库。

        添加是增量式的（已有仓库不会被移除/重复），所以直接重扫即可；
        已到最大深度时不再加深，提示改用「➕ 添加仓库」选更具体的位置。
        """
        if self._scanning:
            self._toast("正在扫描中，请等它结束")
            return
        folders = [f for f in settings.last_folders() if os.path.isdir(f)]
        if not folders:
            self._toast("上次的扫描位置已不存在，请用「➕ 添加仓库」重新选择")
            settings.set_scan_capped(False)
            self.repo_panel.set_scan_capped(False)
            return
        depth = settings.depth()
        if depth < MAX_DEPTH:
            depth += 1
            settings.set_depth(depth)
            self.repo_panel.set_depth(depth)
            self._toast(f"已把扫描深度加大到 {depth} 层，继续扫描…")
        else:
            self._toast(f"已是最大扫描深度（{depth} 层），按当前深度重新扫描…")
        self.add_repos_from_scan(folders)

    # ---- 仓库详情 ----

    def _load_repo(self, path, force=False):
        if not path:
            return
        if path == self._current_repo and not force:
            return
        self._current_repo = path
        self._seq += 1
        seq = self._seq
        self.stack.setCurrentIndex(1)
        self._set_header_repo(path)
        cache = self._repo_cache.get(path)
        if cache and not force and "info" in cache and "log" in cache:
            # 之前读取过：直接显示缓存内容，不重复执行 git 命令
            self.info_tab.set_info(cache["info"])
            self._apply_log(cache["log"])
            return
        self.info_tab.show_placeholder("正在读取仓库信息…")
        self.history_tab.set_loading()
        self.diff_tab.set_loading()

        if not gs.is_ready():
            self.info_tab.show_placeholder("还没安装 Git 工具，读不了信息。请点上方「查看安装教程」。")
            return

        def guard(fn):
            def run(*args):
                if seq == self._seq:
                    fn(*args)
            return run

        def on_info(info):
            self._repo_cache.setdefault(path, {})["info"] = info
            self.info_tab.set_info(info)

        def on_log(result):
            self._repo_cache.setdefault(path, {})["log"] = result
            self._apply_log(result)

        self.runner_info.run(
            lambda: gs.get_full_info(path),
            on_ok=guard(on_info),
            on_err=guard(lambda m: self.info_tab.show_placeholder(f"读取失败：{str(m)[:200]}")))
        self.runner_log.run(
            lambda: gs.get_log(path),
            on_ok=guard(on_log),
            on_err=guard(self.history_tab.set_error))

    def _apply_log(self, result):
        """把提交历史结果填到两个标签页（首次读取、刷新、缓存命中共用）。"""
        commits = result["commits"]
        self.history_tab.set_commits(commits,
                                     result.get("version_labels"),
                                     result.get("version_readme_count", 0))
        self.diff_tab.set_repo(self._current_repo)
        self.diff_tab.set_commits(commits)

    def _refresh_current(self):
        if self._current_repo:
            self._load_repo(self._current_repo, force=True)

    def _delete_current_repo(self):
        path = self._current_repo
        if not path:
            return
        if self._scanning:
            self._toast("正在扫描中，请稍等扫描完成后再操作")
            return
        if not os.path.isdir(path):
            self._toast("这个文件夹已经不存在了，请右键这一行选「重新读取信息」更新列表")
            return
        dlg = DeleteRepoDialog(self, path)
        if not dlg.exec():
            return
        self._seq += 1  # 先作废进行中的读取，避免与删除操作打架
        if dlg.action == DeleteRepoDialog.ACTION_TRASH_GIT:
            target = os.path.join(path, ".git")
            if not os.path.exists(target):
                self._toast("这个文件夹已经没有 Git 历史了，现在直接从列表移除")
                self._forget_repo(path)
                return
            what = "Git 历史（.git）"
            ok_text = ("✅ Git 历史已删除（.git 已移入系统回收站，可在回收站还原），"
                       "项目文件全部保留，并已从列表移除。")
        elif dlg.action == DeleteRepoDialog.ACTION_TRASH_FOLDER:
            target = path
            what = "整个项目文件夹"
            ok_text = "✅ 整个项目文件夹已移入系统回收站（可在回收站还原），并已从列表移除。"
        else:
            self.statusBar().showMessage(
                "已从列表移除（没有删除任何文件）。重新扫描后它会再次出现。", 10000)
            self._forget_repo(path)
            return
        # 大文件夹可能在回收站里搬很久，放到后台线程去做，窗口不会假死
        self._run_single_delete(path, target, what, ok_text)

    def _run_single_delete(self, path, target, what, ok_text):
        self._delete_dlg = QProgressDialog(
            f"正在把{what}移入回收站…\n大文件夹会慢一点，请稍等（窗口不会卡住）。",
            None, 0, 0, self)
        self._delete_dlg.setWindowTitle("正在删除")
        self._delete_dlg.setWindowModality(Qt.ApplicationModal)
        self._delete_dlg.setCancelButton(None)
        self._delete_dlg.setMinimumWidth(420)
        self._delete_dlg.setMinimumDuration(0)
        self._delete_dlg.setAutoClose(False)
        self._delete_dlg.setAutoReset(False)
        self._delete_dlg.show()

        def job():
            return trash.move_to_trash(target)

        def done(result):
            self._close_delete_dlg()
            ok, err = result
            if not ok:
                QMessageBox.warning(
                    self, "删除失败",
                    f"没能把{what}移进回收站（{err}）。\n"
                    "可能是它正被其他程序占用，请关掉相关程序后再试。")
                return
            self.statusBar().showMessage(ok_text, 10000)
            self._forget_repo(path)
            self._offer_recycle_bin()

        def failed(msg):
            self._close_delete_dlg()
            QMessageBox.warning(self, "删除失败", str(msg)[:300])

        self.runner_delete.run(job, on_ok=done, on_err=failed)

    def _close_delete_dlg(self):
        dlg, self._delete_dlg = self._delete_dlg, None
        if dlg is not None:
            dlg.close()
            dlg.deleteLater()

    def _offer_recycle_bin(self):
        """删完主动告诉小白"东西没消失，在回收站里"，并给一个直达入口。"""
        box = QMessageBox(self)
        box.setWindowTitle("已放进回收站")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText("删掉的内容已经放进系统回收站，随时可以还原。")
        box.setInformativeText(
            "「回收站」就是 Windows 桌面上的垃圾桶图标。以后想找回，"
            "打开回收站找到它，右键选「还原」就行。")
        open_btn = box.addButton("打开回收站看看", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("知道了", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            self._open_recycle_bin()

    def _open_recycle_bin(self):
        try:
            if sys.platform == "win32":
                os.startfile("shell:RecycleBinFolder")  # noqa: S606 - 打开系统回收站
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.expanduser("~/.Trash")))
        except Exception as e:
            QMessageBox.information(self, "打不开回收站", f"请手动打开回收站：{e}")

    def _set_header_repo(self, path):
        """顶部第二行显示当前仓库的名字、位置和操作按钮。"""
        name = os.path.basename(os.path.normpath(path)) if path else ""
        i18n.set_raw(self.head_name_lbl, name or i18n.translate("（尚未选择仓库）"))
        self.head_path_lbl.set_text(path or "")
        self.head_copy_btn.setEnabled(bool(path))
        self.head_refresh_btn.setEnabled(bool(path))
        self.head_folder_btn.setEnabled(bool(path))
        self.head_delete_btn.setEnabled(bool(path))
        self.repo_bar.setVisible(bool(path))

    def _copy_repo_path(self):
        path = self._current_repo or self.head_path_lbl.full_text()
        if not path:
            return
        QApplication.clipboard().setText(path)
        self._toast(f"已复制路径：{path}")

    def _forget_repo(self, path):
        """把某个仓库从收藏列表里去掉（不删任何文件），列表空了就回到欢迎页。"""
        if path == self._current_repo:
            self._current_repo = None
            self.repo_bar.setVisible(False)
        self._repo_cache.pop(path, None)
        self._collection_infos.pop(path, None)
        settings.set_repos([p for p in settings.repos() if p != path])
        self._render_repo_list()
        if not self._rendered_order:
            self.stack.setCurrentWidget(self.empty_page)
            self.empty_page.set_message(
                "列表空了",
                "点左侧「➕ 添加仓库」可以重新扫描添加。\n"
                "刚才只是把它从列表里拿掉，你的文件一个都没动。")
        elif self._current_repo is None:
            self.repo_panel.select_path(self._rendered_order[0])

    # ---- 收藏列表 ----

    def _load_collection(self):
        """启动时直接读取收藏列表（不扫描，秒开）。"""
        repos = settings.repos()
        if not repos:
            return
        self.statusBar().showMessage(f"正在读取 {len(repos)} 个仓库的信息…")
        # 用独立的 runner：否则同时进行的扫描会把这次读取的令牌作废，列表就「少了一批」
        self.runner_collection.run(
            lambda: scanner.gather_quick_infos(repos),
            on_ok=self._on_collection_loaded,
            on_err=lambda m: self.statusBar().showMessage(f"读取仓库列表失败：{m}", 8000))

    def _on_collection_loaded(self, infos):
        # 合并而不是整体替换：读取期间用户可能已经扫进来了新仓库
        for i in infos:
            self._collection_infos.setdefault(i["path"], i)
        self._render_repo_list()
        if not self._scanning:
            self.statusBar().showMessage(
                f"就绪：共 {len(self._collection_infos)} 个仓库。"
                "点左侧「➕ 添加仓库」可扫描添加新仓库。", 8000)
        if self._rendered_order and not self._current_repo:
            self.repo_panel.select_path(self._rendered_order[0])

    def _render_repo_list(self):
        """按用户的置顶/排序规则重新渲染仓库列表。"""
        infos = sort_repo_infos(
            list(self._collection_infos.values()),
            set(settings.pinned()), settings.sort_key(),
            settings.sort_priority(), settings.sort_reverse())
        self.repo_panel.set_repos(infos)
        self._rendered_order = [i["path"] for i in infos]
        if self._current_repo and self._current_repo not in self._collection_infos:
            # 当前仓库已被移出列表，回到欢迎页
            self._current_repo = None
            self._seq += 1
            self.stack.setCurrentWidget(self.empty_page)
        elif self._current_repo:
            # 重建列表会丢掉选中状态，这里把它恢复回去（不重新读取数据）
            self.repo_panel.select_path(self._current_repo)

    def _toggle_pin(self, path):
        pinned = set(settings.pinned())
        if path in pinned:
            pinned.discard(path)
            self._toast("已取消置顶")
        else:
            pinned.add(path)
            self._toast("已置顶：该仓库将固定在列表最前面")
        settings.set_pinned(sorted(pinned))
        self._render_repo_list()

    def _on_batch_action(self, action):
        paths = self.repo_panel.selected_paths()
        if not paths:
            self._toast("请先勾选要管理的仓库")
            return
        if action == "pin":
            pinned = set(settings.pinned()) | set(paths)
            settings.set_pinned(sorted(pinned))
            self._render_repo_list()
            self._toast(f"已置顶选中的 {len(paths)} 个仓库")
            return
        if action == "delete":
            # 批量删除：和单个仓库删除一样的弹窗，选「删历史 / 删文件夹 / 仅从列表移除」
            dlg = DeleteRepoDialog(self, paths)
            if dlg.exec() != DeleteRepoDialog.DialogCode.Accepted or not dlg.action:
                return
            if dlg.action == DeleteRepoDialog.ACTION_HIDE:
                self._forget_repos(paths)
            elif dlg.action == DeleteRepoDialog.ACTION_TRASH_GIT:
                self._run_batch_delete(paths, "git")
            elif dlg.action == DeleteRepoDialog.ACTION_TRASH_FOLDER:
                self._run_batch_delete(paths, "folder")
            return

    def _forget_repos(self, paths):
        """把一批仓库从列表里拿掉，文件一个都不动。"""
        gone = set(paths)
        for p in paths:
            self._collection_infos.pop(p, None)
            self._repo_cache.pop(p, None)
        settings.set_repos([p for p in settings.repos() if p not in gone])
        if self._current_repo in gone:
            self._current_repo = None
            self.repo_bar.setVisible(False)
            self.stack.setCurrentIndex(0)
        self._render_repo_list()
        self._toast(f"已从列表移除 {len(paths)} 个仓库（文件未动）")

    def _run_batch_delete(self, paths, action):
        """后台逐个执行批量删除：进度框实时反馈、可随时取消，完成后统一更新列表。

        删除改成后台执行是因为选中项多、体积大时，同步循环会把窗口卡到无响应。
        """
        self._seq += 1  # 先作废进行中的详情读取，避免与删除操作打架（同单仓库删除）
        self._batch_stop = threading.Event()
        total = len(paths)
        noun = "Git 历史" if action == "git" else "文件夹"

        def job():
            ok_n, errs, done = 0, [], []
            stop = self._batch_stop
            for idx, p in enumerate(paths):
                if stop.is_set():
                    break
                self.batch_progress.emit({"i": idx, "n": total,
                                          "name": os.path.basename(p)})
                target = os.path.join(p, ".git") if action == "git" else p
                if action == "git" and not os.path.exists(target):
                    errs.append(f"{os.path.basename(p)}：没有 Git 历史")
                    continue
                ok, err = trash.move_to_trash(target)
                if ok:
                    ok_n += 1
                    done.append(p)
                else:
                    errs.append(f"{os.path.basename(p)}：{err}")
            return {"noun": noun, "ok_n": ok_n, "errs": errs, "done": done,
                    "total": total, "stopped": stop.is_set()}

        self.runner_batch.run(job, on_ok=self._on_batch_done,
                              on_err=self._on_batch_error)

    def _on_batch_progress(self, payload):
        if self._batch_dlg is None:
            dlg = QProgressDialog("正在准备…", "停止（当前这个会做完）", 0, payload["n"], self)
            dlg.setWindowTitle("批量删除（移入回收站，可还原）")
            dlg.setWindowModality(Qt.WindowModal)
            dlg.setMinimumWidth(460)
            dlg.setAutoClose(False)
            dlg.setAutoReset(False)
            dlg.setMinimumDuration(0)
            dlg.canceled.connect(self._batch_stop.set)
            self._batch_dlg = dlg
            # 每个仓库都要在回收站里搬一会儿，期间进度条不动会像"卡死了"，
            # 所以拿一个秒表每 0.2 秒刷一次"已用时"，让人看到程序还活着。
            self._batch_started = time.monotonic()
            self._batch_cur = ("", 0, payload["n"])
            self._batch_timer = QTimer(self)
            self._batch_timer.setInterval(200)
            self._batch_timer.timeout.connect(self._tick_batch_elapsed)
            self._batch_timer.start()
        self._batch_cur = (payload["name"], payload["i"] + 1, payload["n"])
        self._batch_dlg.setValue(payload["i"])
        self._tick_batch_elapsed()

    def _tick_batch_elapsed(self):
        dlg = self._batch_dlg
        if dlg is None:
            return
        name, cur, total = getattr(self, "_batch_cur", ("", 0, 0))
        spent = int(time.monotonic() - getattr(self, "_batch_started", time.monotonic()))
        dlg.setLabelText(
            f"正在处理第 {cur}/{total} 个：{name}\n"
            f"已用时 {spent} 秒 —— 正在搬进回收站，窗口可以正常操作，不会卡住。\n"
            "点「停止」会在当前这个处理完后停下，已经删掉的不会回滚（都在回收站里）。")

    def _close_batch_dlg(self):
        timer, self._batch_timer = getattr(self, "_batch_timer", None), None
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        dlg, self._batch_dlg = self._batch_dlg, None
        if dlg is not None:
            dlg.close()
            dlg.deleteLater()

    def _on_batch_done(self, result):
        self._close_batch_dlg()
        for p in result["done"]:
            self._collection_infos.pop(p, None)
            self._repo_cache.pop(p, None)
        settings.set_repos([p for p in settings.repos() if p in self._collection_infos])
        self._render_repo_list()
        noun = result["noun"]
        if result["stopped"]:
            self._toast(f"已取消：本次已删除 {result['ok_n']} 个{noun}（移入回收站，可还原）")
        elif result["errs"]:
            QMessageBox.warning(
                self, f"批量删除{noun}",
                f"已删除 {result['ok_n']} 个；以下 {len(result['errs'])} 个未能删除：\n"
                + "\n".join(result["errs"][:8]))
        else:
            self._toast(f"已删除 {result['ok_n']} 个{noun}（移入回收站，可还原）")

    def _on_batch_error(self, msg):
        self._close_batch_dlg()
        QMessageBox.warning(self, "批量操作失败", str(msg)[:300])

    def _open_repo_folder(self):
        if self._current_repo:
            self._open_path_folder(self._current_repo)

    def _open_path_folder(self, path):
        """打开某个仓库所在的文件夹（「打开所在文件夹」、双击卡片、右键菜单共用）。"""
        if not os.path.isdir(path):
            QMessageBox.information(
                self, "文件夹找不到了",
                f"这个位置现在打不开：\n{path}\n\n它可能已经被移动、改名或删除了。\n"
                "你可以右键这一行选「重新读取信息」，或者把它从列表里移除。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _on_card_action(self, path, action):
        """左侧仓库卡片的双击/右键菜单统一入口。"""
        if action == "open":
            self._open_path_folder(path)
        elif action == "copy":
            QApplication.clipboard().setText(path)
            self._toast(f"已复制文件夹路径：{path}")
        elif action == "pin":
            self._toggle_pin(path)
        elif action == "forget":
            self._forget_repo(path)
            self._toast("已从列表移除，文件夹还在原来的位置")
        elif action == "refresh":
            self._reload_repo_info(path)

    def _reload_repo_info(self, path):
        """重新读取某个仓库的基本信息（右键菜单「重新读取信息」）。"""
        self._repo_cache.pop(path, None)
        if path == self._current_repo:
            self._load_repo(path, force=True)
            return
        self.runner_card.run(
            lambda: gs.quick_info(path),
            on_ok=lambda info: self._merge_repo_info(path, info),
            on_err=lambda m: self._toast(f"读取失败：{m}"))

    def _merge_repo_info(self, path, info):
        cur = self._collection_infos.get(path)
        if cur is None:
            return
        cur.update(info)
        self._render_repo_list()
        self._toast(f"已重新读取：{cur.get('name') or os.path.basename(path)}")

    # ---- 示例项目 ----

    @staticmethod
    def _sample_dir():
        """示例项目固定放在「文档」里，方便用户以后自己找到并删掉。"""
        base = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        if not base or not os.path.isdir(base):
            base = tempfile.gettempdir()
        return os.path.join(base, "Git可视化仓库 示例项目")

    def _open_sample_project(self):
        """给手头没有项目的人造一份示例数据，让软件立刻"有东西可看"。"""
        if not self._git_ready:
            GitGuideDialog(self).exec()
            return
        base = self._sample_dir()
        if os.path.isdir(base) and any(
                os.path.isdir(os.path.join(base, n))
                for n in ("演示项目", "学习笔记", "旧版本备份")):
            self._toast("已经有一份示例项目了，正在添加到列表…")
            self.add_repos_from_scan(base)
            return
        self.statusBar().showMessage("正在准备示例项目…（只需要几秒钟）")

        def job():
            selftest.make_demo_folder(base)
            return base

        self.runner_scan.run(job, on_ok=self._on_sample_ready, on_err=self._on_sample_error)

    def _on_sample_ready(self, base):
        self.statusBar().showMessage(
            f"示例项目已放在「文档\\{os.path.basename(base)}」，用不着时可以整个删掉。", 12000)
        self.add_repos_from_scan(base)

    def _on_sample_error(self, msg):
        QMessageBox.warning(
            self, "示例项目创建失败",
            f"{msg}\n\n你也可以点左侧「➕ 添加仓库」，直接选择自己的项目文件夹。")

    # ---- 其他 ----

    def _toast(self, msg):
        self.statusBar().showMessage(msg, 2500)

    def _update_last_folder_lbl(self):
        fs = settings.last_folders()
        self.last_folder_lbl.setText(describe_locations(fs, with_prefix=True) if fs else "")

    def _show_help(self):
        HelpDialog(self).exec()

    def _show_settings(self):
        dlg = SettingsDialog(self, git_version=self._git_version or "")
        dlg.help_requested.connect(self._show_help)
        dlg.language_changed.connect(self._on_language_changed)
        dlg.exec()
        # 外观可能在设置里改过：按最新设置重刷一遍（含深浅色）
        i18n.retranslate(self)

    def _on_language_changed(self):
        """换语言后，把"数据 + 界面词"拼出来的内容重新渲染一遍。"""
        i18n.retranslate(self)
        self._render_repo_list()
        if self._current_repo:
            self._load_repo(self._current_repo, force=True)
        self.repo_panel.set_scanning(self._scanning)
        # 状态栏上那条提示是换语言之前写的，趁这次清掉，避免新旧语言混在一起
        self.statusBar().clearMessage()
        self._toast(i18n.translate("界面语言已切换。"))

    def _show_git_guide(self):
        GitGuideDialog(self).exec()

    def start_demo(self, folder):
        """开发用：自动扫描并轮流切换标签页，配合外部截图验证界面。"""
        self._demo = True
        print("[demo] start_demo:", folder, flush=True)
        self.showMaximized()
        self.add_repos_from_scan(folder)

    def closeEvent(self, event):
        self._scan_stop.set()
        self._batch_stop.set()
        self.pool.clear()
        super().closeEvent(event)


def default_scan_roots():
    """首次使用（无历史记录）时的默认扫描位置：桌面、文档、下载 + 本机所有固定磁盘。

    只扫固定硬盘（C 盘、D 盘等本地分区）；光驱、U 盘、移动硬盘和网络盘跳过，
    避免首次扫描被慢速介质卡住（用户仍可手动选择它们扫描）。
    """
    roots = []
    for loc in (QStandardPaths.DesktopLocation, QStandardPaths.DocumentsLocation,
                QStandardPaths.DownloadLocation):
        p = QStandardPaths.writableLocation(loc)
        if p and os.path.isdir(p):
            roots.append(p)
    for fi in QDir.drives():
        p = fi.absoluteFilePath()
        if not os.path.isdir(p) or not _is_fixed_drive(p):
            continue
        if p not in roots:
            roots.append(p)
    return roots


def _is_fixed_drive(path):
    """Windows 下判断是否为固定硬盘（DRIVE_FIXED=3）。"""
    try:
        if sys.platform != "win32":
            return True
        code = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(os.path.abspath(path)[:3]))
        return code == 3
    except Exception:
        return True


def describe_location(path):
    """把一个文件夹路径翻译成小白看得懂的说法：桌面 / 文档 / 下载 / C 盘 / 某个文件夹名。

    界面上直接堆 "C:\\Users\\<用户名>\\Desktop" 这种原始路径对新手很不友好，
    所以扫描位置一律用这个函数转成人话。
    """
    try:
        norm = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    except Exception:
        return str(path)
    friendly = ((QStandardPaths.DesktopLocation, "桌面"),
                (QStandardPaths.DocumentsLocation, "文档"),
                (QStandardPaths.DownloadLocation, "下载"))
    for loc, name in friendly:
        p = QStandardPaths.writableLocation(loc)
        if p and os.path.normcase(os.path.normpath(p)) == norm:
            return name
    drive, tail = os.path.splitdrive(norm)
    if drive and tail.strip("\\/") == "":
        return f"{drive[0].upper()} 盘"
    base = os.path.basename(norm.rstrip("\\/"))
    return base or str(path)


def describe_locations(folders, limit=4, with_prefix=False):
    """把多个扫描位置拼成一句人话："桌面、文档、下载、C 盘"；太多时省略后面的。"""
    names = [describe_location(p) for p in folders]
    if not names:
        text = "（还没选过位置）"
    elif len(names) > limit:
        text = "、".join(names[:limit]) + f" 等 {len(names)} 个位置"
    else:
        text = "、".join(names)
    return ("扫描位置：" + text) if with_prefix else text


def sort_repo_infos(infos, pinned, key, priority, reverse):
    """按用户的置顶/排序规则排仓库卡片数据。

    置顶的永远排最前；其次按"优先显示"条件分组（本地优先/远程优先）；
    组内按主键排序：按首字母（正序 A→Z，倒序 Z→A）或按更新时间
    （正序=最近更新的在前，倒序=最旧的在前）。没有更新时间的排最后。
    """
    infos = list(infos)

    def group(i):
        return (0 if i["path"] in pinned else 1,
                1 if ((priority == "local" and i.get("remote_url"))
                      or (priority == "remote" and not i.get("remote_url"))) else 0)

    def by_name(i):
        return i["name"].lower()

    def by_time(i):
        dt = utils.parse_iso(i.get("last_time"))
        return dt.timestamp() if dt else 0

    infos.sort(key=by_name)  # 先按名称，作为同时间的稳定次序
    if key == "time":
        infos.sort(key=by_time, reverse=not reverse)
    else:
        infos.sort(key=by_name, reverse=reverse)
    infos.sort(key=group)  # 稳定排序：置顶/优先组靠前，组内保持上面顺序
    return infos
