"""history_tab.py —— 「提交历史」标签页。

右侧是「版本树」：思维导图式的画布，主线在最左，分出去的分支排在右边，
每个版本是一个可点的方块。版本名优先取自项目 README 的"版本记录"小节
（如 v1.1.0）；README 记录能与提交一一对上时才采用，对不上或没有记录时
按提交先后自动连续编号 v0.1、v0.2……。点击节点左侧立即显示该版本详情。

画布交互：左键拖空白处平移、滚轮缩放（以鼠标为中心）、双击空白复位。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QSplitter,
                               QTextBrowser, QVBoxLayout, QWidget)

from .. import i18n, utils
from ..git_service import auto_version_label
from .version_graph import VersionGraph
from .widgets import badge, copy_button


def _esc(s):
    return utils.esc(s)


def version_label(index_from_new, total):
    """给提交排一个好记的序号：最早的是 v0.1，往后 v0.2、v0.3……连续递增。

    注意：这是本软件自己排的序号，不是 git 里的版本标签（tag）。
    """
    return auto_version_label(total - index_from_new)


class HistoryTab(QWidget):
    """左侧版本详情 + 右侧版本树。

    选两个版本对比的入口统一放在「版本对比」标签页，本页只负责看历史。
    """

    def __init__(self, status_cb=None, parent=None):
        super().__init__(parent)
        self._status_cb = status_cb or (lambda s: None)
        self._commits = []
        self._search_blobs = []   # 每行的可搜索文本（说明+作者+版本号+时间）
        self._current_hash = None

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # ---- 主体：左详情 + 右版本树 ----
        split = QSplitter(Qt.Horizontal)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 12, 0)
        lv.setSpacing(8)
        lt = QLabel("版本详情")
        lt.setStyleSheet("font-weight: 700;")
        lv.addWidget(lt)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.detail_vlabel = badge("", "indigo", "本软件为这次提交排的序号")
        title_row.addWidget(self.detail_vlabel)
        self.detail_subject = QLabel("")
        self.detail_subject.setStyleSheet("font-size: 15px; font-weight: 700; border: none;")
        self.detail_subject.setWordWrap(True)
        # 垂直方向给 Minimum：窗口不高时宁可让下面的正文变矮，
        # 也不要把两行的说明挤成一行（那会看起来像文字被截断/重叠）。
        self.detail_subject.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        title_row.addWidget(self.detail_subject, 1)
        lv.addLayout(title_row)

        self.detail_badges = QHBoxLayout()
        self.detail_badges.setSpacing(6)
        holder = QWidget()
        holder.setLayout(self.detail_badges)
        lv.addWidget(holder)

        self.detail_author = QLabel("")
        self.detail_author.setObjectName("muted")
        self.detail_author.setWordWrap(True)
        lv.addWidget(self.detail_author)
        self.detail_time = QLabel("")
        self.detail_time.setObjectName("muted")
        lv.addWidget(self.detail_time)

        # 版本号很长（40 位），单独给一行；复制按钮放下一行右对齐，
        # 否则窄窗口下 40 位哈希会被截掉。
        hash_box = QVBoxLayout()
        hash_box.setSpacing(4)
        hash_row = QHBoxLayout()
        hash_row.setSpacing(8)
        hl = QLabel("完整版本号")
        hl.setObjectName("muted")
        hash_row.addWidget(hl)
        self.detail_hash = QLabel("")
        self.detail_hash.setObjectName("mono")
        self.detail_hash.setTextInteractionFlags(Qt.TextSelectableByMouse)
        hash_row.addWidget(self.detail_hash, 1)
        hash_box.addLayout(hash_row)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(copy_button(lambda: self._current_hash or "",
                                      self._status_cb, label="复制完整版本号"))
        hash_box.addLayout(btn_row)
        hv_holder = QWidget()
        hv_holder.setLayout(hash_box)
        lv.addWidget(hv_holder)

        self.detail_body = QTextBrowser()
        self.detail_body.setOpenExternalLinks(False)
        self.detail_body.setStyleSheet("border: none; background: transparent;")
        lv.addWidget(self.detail_body, 1)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 0, 0, 0)
        rv.setSpacing(4)
        rhead = QHBoxLayout()
        rhead.setSpacing(8)
        rt = QLabel("版本树 · 点节点看详情，拖空白处平移，滚轮缩放")
        rt.setObjectName("muted")
        rhead.addWidget(rt)
        rhead.addStretch(1)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("muted2")
        rhead.addWidget(self.count_lbl)
        rv.addLayout(rhead)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 找某一次的说明、作者名或版本号…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        rv.addWidget(self.search)
        self.graph = VersionGraph()
        self.graph.node_clicked.connect(self._on_node)
        rv.addWidget(self.graph, 1)
        split.addWidget(right)

        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)
        split.setSizes([640, 460])
        v.addWidget(split, 1)

        self._show_detail(None)

    # ---- 对外接口（MainWindow 调用） ----

    def set_loading(self):
        self._commits = []
        self._search_blobs = []
        self.graph.clear_data()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.count_lbl.setText("")
        self._show_detail(None)
        self._set_detail_placeholder("正在读取提交历史…")

    def set_error(self, msg):
        self._commits = []
        self._search_blobs = []
        self.graph.clear_data()
        self.count_lbl.setText("")
        self._show_detail(None)
        self._set_detail_placeholder(f"读取提交历史失败：{_esc(str(msg)[:200])}")

    def set_commits(self, commits, version_labels=None, readme_count=0):
        self._commits = commits
        n = len(commits)
        # 版本名：优先来自 README 版本记录；不够的（更早提交）用自动编号补齐
        provided = list(version_labels or [])
        if len(provided) < n:
            provided += [version_label(i, n) for i in range(len(provided), n)]
        self._version_labels = provided
        self._readme_count = readme_count
        self._search_blobs = [
            " ".join([provided[i], c["subject"], c["author_name"], c["short_hash"],
                      utils.fmt_dt(c["commit_date"])]).lower()
            for i, c in enumerate(commits)
        ]
        self.graph.set_data(commits, provided)
        self.graph.set_blobs(self._search_blobs)

        self._apply_filter(self.search.text())
        first = self.graph.first_visible()
        if first >= 0:
            self.graph.select(first)
            self._current_hash = commits[first]["hash"]
            self._show_detail(first, commits[first])
        elif not commits:
            self._show_detail(None)
            self._set_detail_placeholder("这个仓库还没有任何提交记录。等有了提交，右侧会出现版本树。")

    # ---- 内部逻辑 ----

    def _update_count(self, shown=None):
        n = len(self._commits)
        if not n:
            self.count_lbl.setText("")
            return
        parts = [f"显示 {shown} / 共 {n} 次" if shown is not None and shown != n
                 else f"共 {n} 次"]
        if n >= 200:
            parts.append("只读取了最近 200 次")
        self.count_lbl.setText(" · ".join(parts))

    def _apply_filter(self, text):
        """在版本树里按关键词过滤：提交说明、作者名、版本号、日期都能搜。"""
        needle = (text or "").strip().lower()
        shown = self.graph.set_filter(needle)
        self._update_count(shown if needle else None)
        if needle and shown == 0 and self._commits:
            self._set_detail_placeholder(
                "没有找到符合条件的记录。换个关键词试试：可以搜提交说明里的字、作者名，"
                "也可以搜 v1.2 这样的版本号。")
        elif needle and shown:
            first = self.graph.first_visible()
            if first >= 0:
                self.graph.select(first, notify=True)

    def _on_node(self, index):
        if index < 0 or index >= len(self._commits):
            self._current_hash = None
            self._show_detail(None)
            return
        self.graph.select(index)
        self._current_hash = self._commits[index]["hash"]
        self._show_detail(index, self._commits[index])

    def _show_detail(self, index, c=None):
        if c is None:
            self.detail_vlabel.setText("")
            self.detail_vlabel.setVisible(False)
            self.detail_subject.setText("（尚未选择版本）")
            self._set_detail_badges(None)
            self.detail_author.setText("")
            self.detail_time.setText("")
            self.detail_hash.setText("")
            return
        vlabel = self._version_labels[index]
        from_readme = index < self._readme_count
        self.detail_vlabel.setVisible(True)
        i18n.set_raw(self.detail_vlabel, vlabel)
        self.detail_vlabel.setToolTip(
            "版本名来自项目 README 的版本记录" if from_readme
            else "README 版本记录里没有对应的条目，这个版本名是本软件自动编排的")
        self.detail_subject.setText(c["subject"])
        # 说明可能是两行：先把高度按新文字重算一遍再让父布局立刻重排，
        # 否则下一帧才更新，看起来像文字被截断/压在下一行上。
        self.detail_subject.updateGeometry()
        parent_layout = self.detail_subject.parentWidget().layout()
        if parent_layout is not None:
            parent_layout.activate()
        self._set_detail_badges(c.get("refs") or {})
        i18n.set_raw(self.detail_author,
                     f"{i18n.translate('作者：')}{c['author_name']}（{c['author_email']}）")
        i18n.set_raw(self.detail_time,
                     f"{i18n.translate('时间：')}{utils.fmt_dt(c['author_date'], True)}")
        self.detail_hash.setText(c["hash"])
        body = (c.get("body") or "").strip()
        body_html = _esc(body).replace("\n", "<br>")
        self.detail_body.setHtml(
            (body_html if body_html else "<span style='color:#9ca3af;'>（这条提交没有填写详细说明）</span>"))

    def _set_detail_placeholder(self, text):
        self.detail_body.setHtml(f"<div style='color:#9ca3af;'>{text}</div>")

    def _set_detail_badges(self, refs):
        while self.detail_badges.count():
            it = self.detail_badges.takeAt(0)
            w = it.widget()
            if w is not None:
                # 只 deleteLater 的话，控件在事件循环真正删除前还会画在原位置，
                # 于是切到别的版本时能看到上一次的「最新」徽章残留。
                w.setParent(None)
                w.deleteLater()
        if not refs:
            return
        if refs.get("head_ref"):
            self.detail_badges.addWidget(badge("⭐ 最新（当前分支）", "green",
                                               "这是项目现在所处的最新版本"))
        for tag in (refs.get("tags") or []):
            self.detail_badges.addWidget(
                badge(f"🏷 {tag}", "purple", "标签：给某个版本起的有意义的名字", raw=True))
        if refs.get("origin_refs"):
            self.detail_badges.addWidget(badge("☁ 已同步远程", "blue", "这个版本已经上传到网络仓库了"))
