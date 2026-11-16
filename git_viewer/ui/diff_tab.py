"""diff_tab.py —— 「版本对比」标签页。"""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QPushButton, QSplitter, QTextEdit,
                               QVBoxLayout, QWidget)

from .. import git_service as gs
from .. import settings, utils
from .widgets import Drawer, ElidedLabel, badge
from ..workers import AsyncRunner


class FileRow(QWidget):
    """左侧文件列表里的一行：变化类型徽章 + 文件路径。"""

    def __init__(self, f, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 10, 6)
        h.setSpacing(8)
        name = utils.status_name(f["status"])
        kind = {"新增": "green", "修改": "blue", "删除": "red", "重命名": "purple"}.get(name, "gray")
        h.addWidget(badge(name, kind))
        p = ElidedLabel(f["path"], Qt.ElideMiddle)
        h.addWidget(p, 1)
        if f.get("old_path"):
            old = QLabel(f"（原名：{f['old_path']}）")
            old.setObjectName("muted2")
            h.addWidget(old)
        tip = f["path"] if not f.get("old_path") else f"{f['old_path']}  →  {f['path']}"
        self.setToolTip(tip)


class DiffTab(QWidget):
    """顶部选两个版本，下面左边列文件、右边看具体差异。"""

    def __init__(self, diff_runner: AsyncRunner, file_runner: AsyncRunner,
                 status_cb=None, parent=None):
        super().__init__(parent)
        self._diff_runner = diff_runner
        self._file_runner = file_runner
        self._status_cb = status_cb or (lambda s: None)
        self._repo = None
        self._files = []
        self._a = None
        self._b = None
        self._last_diff = None   # 记住最近一次读到的差异，供「显示技术细节」开关重绘

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # ---- 顶部：选版本区（这里是全软件唯一的对比入口，默认展开） ----
        self.drawer = Drawer("⚖️ 选两个版本对比")
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.combo_a = QComboBox()
        self.combo_a.setMinimumWidth(220)
        self.combo_b = QComboBox()
        self.combo_b.setMinimumWidth(220)
        self.combo_a.currentIndexChanged.connect(self.load_diff)
        self.combo_b.currentIndexChanged.connect(self.load_diff)
        self.swap_btn = QPushButton("⇅ 交换方向")
        self.swap_btn.setObjectName("ghost")
        self.swap_btn.setToolTip("把对比方向反过来：从“版本 B”变成“版本 A”")
        self.swap_btn.clicked.connect(self._swap)
        la = QLabel("版本 A（较早）")
        lb = QLabel("版本 B（较近）")
        la.setObjectName("muted")
        lb.setObjectName("muted")
        row2.addWidget(la)
        row2.addWidget(self.combo_a)
        row2.addWidget(lb)
        row2.addWidget(self.combo_b, 1)
        row2.addWidget(self.swap_btn)
        self.drawer.body_v.addLayout(row2)

        self.hint = QLabel(
            "默认已经选好「上一次」和「最新」，下面直接显示这两个版本之间改了什么。\n"
            "想比别的版本，改上面两个下拉框即可；🟩 绿色 = 新加的行，🟥 红色 = 删掉的行。")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        self.drawer.body_v.addWidget(self.hint)

        self.summary = QHBoxLayout()
        self.summary.setSpacing(6)
        self.drawer.header.addStretch(1)
        self.drawer.header.addLayout(self.summary)
        v.addWidget(self.drawer)
        self.drawer.set_expanded(True)

        # ---- 主体：左文件列表 + 右差异内容 ----
        split = QSplitter(Qt.Horizontal)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(4)
        lt = QLabel("有变化的文件")
        lt.setObjectName("muted")
        lv.addWidget(lt)
        self.file_list = QListWidget()
        self.file_list.setSpacing(0)
        self.file_list.currentRowChanged.connect(self._on_file)
        lv.addWidget(self.file_list, 1)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(4)
        rhead = QHBoxLayout()
        rt = QLabel("文件内容变化明细")
        rt.setObjectName("muted")
        rhead.addWidget(rt)
        rhead.addStretch(1)
        self.meta_chk = QCheckBox("显示技术细节")
        self.meta_chk.setObjectName("muted2")
        self.meta_chk.setToolTip(
            "默认帮你把 git 的原始信息行（如 diff --git、index、---/+++）藏起来。\n"
            "只有排查问题或想看清楚文件路径时才需要勾上。")
        self.meta_chk.setChecked(settings.diff_show_meta())
        self.meta_chk.toggled.connect(self._on_meta_toggled)
        rhead.addWidget(self.meta_chk)
        legend = QLabel("🟩 新增的行　🟥 删除的行")
        legend.setObjectName("muted2")
        rhead.addWidget(legend)
        rv.addLayout(rhead)
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        rv.addWidget(self.diff_view, 1)
        split.addWidget(right)

        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([360, 760])
        v.addWidget(split, 1)

        # 底部指路：从「提交历史」点某个版本过来时，这里告诉你怎么换成别的版本再比
        self.compare_hint = QLabel(
            "想比较别的两个版本？用上面的「版本 A」「版本 B」选一下就行；"
            "选好后下面会自动列出它们之间改了哪些文件、改了哪几行。")
        self.compare_hint.setObjectName("muted2")
        self.compare_hint.setWordWrap(True)
        v.addWidget(self.compare_hint)

    # ---- 对外接口 ----

    def set_repo(self, repo):
        self._repo = repo

    def set_loading(self):
        self._files = []
        self._last_diff = None
        self.file_list.clear()
        self._clear_summary()
        for combo in (self.combo_a, self.combo_b):
            combo.clear()
        self.diff_view.setHtml("<div style='color:#9ca3af;padding:20px;'>正在读取…</div>")

    def set_commits(self, commits):
        for combo, idx in ((self.combo_a, 1), (self.combo_b, 0)):
            combo.blockSignals(True)
            combo.clear()
            for c in commits:
                combo.addItem(
                    f"{utils.fmt_dt_short(c['commit_date'])}  {c['subject'][:16]}",
                    c["hash"],
                )
                combo.setItemData(combo.count() - 1,
                                  f"{utils.fmt_dt(c['commit_date'])}  {c['subject']}（{c['short_hash']}）",
                                  Qt.ToolTipRole)
            if len(commits) >= 2:
                combo.setCurrentIndex(min(idx, len(commits) - 1))
            combo.blockSignals(False)
        self.load_diff()

    def set_selection(self, a, b):
        changed = False
        for combo, h in ((self.combo_a, a), (self.combo_b, b)):
            i = combo.findData(h)
            if i >= 0 and combo.currentData() != h:
                combo.blockSignals(True)
                combo.setCurrentIndex(i)
                combo.blockSignals(False)
                changed = True
        self.load_diff()

    # ---- 内部逻辑 ----

    def _swap(self):
        for combo in (self.combo_a, self.combo_b):
            combo.blockSignals(True)
        ia, ib = self.combo_a.currentIndex(), self.combo_b.currentIndex()
        self.combo_a.setCurrentIndex(ib)
        self.combo_b.setCurrentIndex(ia)
        for combo in (self.combo_a, self.combo_b):
            combo.blockSignals(False)
        self.load_diff()

    def load_diff(self):
        a, b = self.combo_a.currentData(), self.combo_b.currentData()
        self._clear_files()
        if not self._repo or not a or not b:
            self._show_message("在上面选择两个版本后，这里会显示它们之间的文件变化。")
            return
        if a == b:
            self._show_message("这两个是同一个版本，没有可对比的内容。")
            return
        self._a, self._b = a, b
        repo, a_, b_ = self._repo, a, b
        self._show_message("正在读取文件变化列表…")
        self._diff_runner.run(
            lambda: (gs.diff_files(repo, a_, b_), gs.diff_shortstat(repo, a_, b_)),
            on_ok=self._show_files,
            on_err=self._show_error,
        )

    def _clear_files(self):
        self._files = []
        self.file_list.clear()
        self._clear_summary()

    def _clear_summary(self):
        while self.summary.count():
            it = self.summary.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
            elif it.spacerItem() is not None:
                self.summary.removeItem(it)

    def _chip(self, text, kind):
        self.summary.addWidget(badge(text, kind))

    def _show_message(self, text):
        self.diff_view.setHtml(f"<div style='color:#6b7280;padding:20px;font-size:13px;'>{utils.esc(text)}</div>")

    def _show_error(self, msg):
        self.diff_view.setHtml(f"<div style='color:#b91c1c;padding:20px;'>读取差异失败：{utils.esc(str(msg)[:400])}</div>")

    def _show_files(self, result):
        files, stats = result
        self._files = files
        self._clear_summary()
        if not files:
            self._show_message("这两个版本的内容完全一样（没有文件变化）。")
            return
        cnt = Counter(f["status"] for f in files)
        self._chip(f"共 {len(files)} 个文件有变化", "indigo")
        for s in ("A", "M", "D", "R", "C", "T"):
            if cnt.get(s):
                kind = {"A": "green", "M": "blue", "D": "red", "R": "purple"}.get(s, "gray")
                self._chip(f"{utils.status_name(s)} {cnt[s]} 个", kind)
        if stats and (stats["insertions"] or stats["deletions"]):
            self._chip(f"内容上新增 {stats['insertions']} 行、删除 {stats['deletions']} 行", "amber")
        self.summary.addStretch(1)

        for f in files:
            item = QListWidgetItem()
            row = FileRow(f)
            item.setSizeHint(QSize(0, row.sizeHint().height() + 4))
            item.setData(Qt.UserRole, f["path"])
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, row)
        self.file_list.setCurrentRow(0)

    def _on_file(self, row):
        if row < 0 or row >= len(self._files):
            return
        f = self._files[row]
        if not self._repo or not self._a:
            return
        repo, a, b = self._repo, self._a, self._b
        self._last_diff = None
        self.diff_view.setHtml("<div style='color:#9ca3af;padding:20px;'>正在读取这个文件的具体变化…</div>")
        self._file_runner.run(
            lambda: gs.file_diff(repo, a, b, f["path"], f.get("old_path")),
            on_ok=self._show_file_diff,
            on_err=self._show_error,
        )

    def _is_dark(self):
        """深色主题下 diff 要用另一套配色，否则亮绿/亮红底会非常刺眼。"""
        from PySide6.QtGui import QPalette
        return self.palette().color(QPalette.ColorRole.Base).lightness() < 128

    def _show_file_diff(self, d):
        self._last_diff = d
        if d.get("binary"):
            self.diff_view.setHtml(
                "<div style='color:#6b7280;padding:24px;font-size:13px;'>"
                "这是一个<b>二进制文件</b>（比如图片、压缩包、音频），内容不是普通文字，所以无法逐行对比。<br><br>"
                "不过在上面的列表里仍然能看到它是“新增 / 删除”了，这已经足够了解变化。</div>")
            return
        note = ("<div style='color:#d97706;font-size:12px;'>（内容太长，只显示前面一部分）</div>"
                if d.get("truncated") else "")
        text = d["text"]
        if not settings.diff_show_meta():
            text = utils.friendly_hunks(utils.strip_diff_meta(text))
        if not text.strip():
            # 只剩头部信息 = 只是改名/改权限，内容本身没动
            self.diff_view.setHtml(
                note + "<div style='color:#6b7280;padding:24px;font-size:13px;'>"
                       "这个文件只是<b>改了名字或改动了文件属性</b>，内容本身没有增加或删除任何一行。<br><br>"
                       "想看 git 记录的原始信息，勾选右上角的「显示技术细节」。</div>")
            return
        self.diff_view.setHtml(note + utils.diff_to_html(text, dark=self._is_dark()))
        self.diff_view.verticalScrollBar().setValue(0)

    def _on_meta_toggled(self, on):
        settings.set_diff_show_meta(bool(on))
        if self._last_diff:
            self._show_file_diff(self._last_diff)
