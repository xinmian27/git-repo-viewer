"""repo_list_panel.py —— 左侧的仓库列表面板。

功能：收藏仓库列表（置顶/排序/搜索）、「➕ 添加仓库」扫描入口、
批量管理模式（勾选多个仓库后批量移除/删历史/删文件夹/置顶）。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QToolButton, QVBoxLayout, QWidget)

from .. import i18n, settings, utils
from .widgets import ElidedLabel, SoftButton, badge

MAX_DEPTH = 6  # 扫描深度下拉框的最大层数（与下方选项保持一致）


class RepoCard(QFrame):
    """仓库列表里的一张卡片：名称/徽章 + 置顶按钮 + 批量勾选框。"""

    pin_clicked = Signal(str)
    select_toggled = Signal(str, bool)
    open_requested = Signal(str)          # 双击卡片：打开所在文件夹
    action_requested = Signal(str, str)   # 右键菜单：(动作, 路径)

    def __init__(self, info, parent=None):
        super().__init__(parent)
        self._path = info["path"]
        self._pinned = bool(info.get("pinned"))
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 8, 8)
        v.setSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.checkbox = QCheckBox()
        self.checkbox.setVisible(False)
        self.checkbox.toggled.connect(self._on_check)
        row1.addWidget(self.checkbox)
        name_lbl = QLabel()
        i18n.set_raw(name_lbl, info["name"])   # 仓库名是数据，换语言不动
        name_lbl.setStyleSheet("font-weight: 700; font-size: 13px; border: none;")
        row1.addWidget(name_lbl)
        row1.addStretch(1)
        if info.get("last_time"):
            t = QLabel(utils.fmt_dt_short(info["last_time"]))
            t.setObjectName("muted2")
            row1.addWidget(t)
        self.pin_btn = QToolButton()
        self.pin_btn.setObjectName("pinBtn")
        self.pin_btn.setText("📌")
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setAutoRaise(True)
        self.pin_btn.clicked.connect(lambda: self.pin_clicked.emit(self._path))
        row1.addWidget(self.pin_btn)
        v.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        if info.get("pending"):
            row2.addWidget(badge("⏳ 读取中…", "amber", "已发现这个仓库，正在读取它的信息"))
        elif info.get("missing"):
            row2.addWidget(badge("❓ 文件夹不存在", "red",
                                 "这个文件夹已经被移动或删除；可勾选后从列表移除"))
        elif b := info.get("branch"):
            row2.addWidget(badge(f"🌿 {b}", "green", "当前所在的分支（版本线）", raw=True))
        else:
            row2.addWidget(badge("❓ 分支未知", "amber"))
        if not info.get("pending") and not info.get("missing"):
            if info.get("remote_url"):
                row2.addWidget(badge("🔗 已关联远程", "indigo",
                                     "这个项目在网络上（GitHub 等）有存放地址"))
            else:
                row2.addWidget(badge("仅本机", "gray",
                                     "这个项目只保存在这台电脑上，没有关联网络仓库"))
        row2.addStretch(1)
        v.addLayout(row2)

        p = ElidedLabel(info["path"], Qt.ElideMiddle)
        p.setObjectName("muted2")
        v.addWidget(p)

        tip = f"{info['name']}\n位置：{info['path']}"
        if info.get("last_subject"):
            tip += f"\n最近提交：{info['last_subject']}"
        tip += "\n\n双击 = 打开这个项目所在的文件夹；右键 = 更多操作"
        self.setToolTip(tip)

        self.set_pinned(self._pinned)

    def _on_check(self, on):
        self.select_toggled.emit(self._path, on)

    def mouseDoubleClickEvent(self, event):
        """双击卡片 = 打开项目所在的文件夹（小白最常用的"我就想看看文件在哪"）。"""
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self._path)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单：常用操作，全部不带破坏性（删除仍然只放在详情页里）。"""
        menu = QMenu(self)
        a_open = menu.addAction("📂 打开所在文件夹")
        a_refresh = menu.addAction("🔄 重新读取信息")
        menu.addSeparator()
        a_copy = menu.addAction("📋 复制文件夹路径")
        a_pin = menu.addAction("取消置顶" if self._pinned else "📌 置顶到最前面")
        menu.addSeparator()
        a_forget = menu.addAction("➖ 仅从列表移除（不删文件）")
        act = menu.exec(event.globalPos())
        name = {a_open: "open", a_refresh: "refresh", a_copy: "copy",
                a_pin: "pin", a_forget: "forget"}.get(act)
        if name:
            self.action_requested.emit(name, self._path)

    def set_pinned(self, on):
        self._pinned = bool(on)
        self.pin_btn.setProperty("on", "1" if on else "0")
        st = self.pin_btn.style()
        st.unpolish(self.pin_btn)
        st.polish(self.pin_btn)
        self.pin_btn.setToolTip("取消置顶" if on else "置顶（固定在列表最前面）")

    def set_batch_mode(self, on):
        self.checkbox.setVisible(on)

    def set_checked(self, on):
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(on)
        self.checkbox.blockSignals(False)


class RepoListPanel(QWidget):
    """左侧面板：标题/排序/管理 + 搜索 + 仓库列表 + 添加仓库入口。"""

    selected = Signal(str)
    pin_toggled = Signal(str)
    batch_action = Signal(str)   # remove / git / folder / pin
    add_requested = Signal()
    continue_scan = Signal()
    cancel_scan = Signal()
    depth_changed = Signal(int)
    sort_changed = Signal()
    open_folder = Signal(str)
    card_action = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(430)
        self._infos = []
        self._selected = set()
        self._batch_mode = False

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 6, 10)
        v.setSpacing(8)

        # ---- 标题行 ----
        head = QHBoxLayout()
        head.setSpacing(6)
        title = QLabel("📦 仓库列表")
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        head.addWidget(title)
        head.addStretch(1)
        self.sort_btn = SoftButton("↕ 排序")
        self.sort_btn.setToolTip("个性化排列：正序/倒序、按首字母或更新时间、优先显示本地或远程仓库")
        self.sort_btn.clicked.connect(self._show_sort_menu)
        head.addWidget(self.sort_btn)
        self.manage_btn = SoftButton("管理")
        self.manage_btn.setToolTip("批量管理：勾选多个仓库后批量移除/删历史/删文件夹/置顶")
        self.manage_btn.clicked.connect(lambda: self.set_batch_mode(not self._batch_mode))
        head.addWidget(self.manage_btn)
        head.addStretch(1)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("muted")
        head.addWidget(self.count_lbl)
        v.addLayout(head)

        # ---- 批量管理条（管理模式下显示） ----
        self.batch_bar = QWidget()
        self.batch_bar.setVisible(False)
        bv = QVBoxLayout(self.batch_bar)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(4)
        br1 = QHBoxLayout()
        br1.setSpacing(6)
        self.chk_all = QCheckBox("全选")
        self.chk_all.toggled.connect(self._toggle_select_all)
        br1.addWidget(self.chk_all)
        self.sel_lbl = QLabel("已选 0 个")
        self.sel_lbl.setObjectName("muted")
        br1.addWidget(self.sel_lbl)
        br1.addStretch(1)
        bv.addLayout(br1)
        br2 = QHBoxLayout()
        br2.setSpacing(6)
        self.batch_pin_btn = SoftButton("📌 置顶")
        self.batch_pin_btn.setToolTip("把勾选的仓库固定到列表最前面")
        self.batch_pin_btn.clicked.connect(lambda: self.batch_action.emit("pin"))
        br2.addWidget(self.batch_pin_btn)
        # 一个「删除」入口，点开后像单个仓库那样选择删除方式
        self.batch_del_btn = SoftButton("🗑 删除")
        self.batch_del_btn.setToolTip("选择删除方式：Git 历史、整个文件夹，或仅从列表移除")
        self.batch_del_btn.clicked.connect(lambda: self.batch_action.emit("delete"))
        br2.addWidget(self.batch_del_btn)
        br2.addStretch(1)
        bv.addLayout(br2)
        v.addWidget(self.batch_bar)

        # ---- 搜索框 ----
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 输入名字，快速筛选仓库…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        v.addWidget(self.search)

        # ---- 列表为空时的提示（小白第一次打开最需要看到的话） ----
        self.empty_hint = QLabel(
            "这里还没有仓库。\n\n"
            "点下面的「➕ 添加仓库」，选一个放着代码项目的文件夹；\n"
            "选中后，右边就能看到它的基本信息、提交历史和版本对比。")
        self.empty_hint.setObjectName("muted2")
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setContentsMargins(6, 18, 6, 18)
        v.addWidget(self.empty_hint)

        # ---- 仓库列表 ----
        self.listw = QListWidget()
        self.listw.setObjectName("repoList")
        self.listw.setSpacing(2)
        self.listw.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.listw.currentRowChanged.connect(self._on_row)
        v.addWidget(self.listw, 1)
        self.empty_hint.setVisible(not self.listw.count())

        # ---- 底部：添加仓库 + 扫描中可停止 + 扫描设置（默认收起） ----
        self.cancel_btn = QPushButton("⏹ 停止扫描")
        self.cancel_btn.setObjectName("warnBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setToolTip("扫描还在进行时点这里可以停下来；已经找到的仓库会保留")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_scan.emit)
        v.addWidget(self.cancel_btn)

        self.add_btn = QPushButton("➕ 添加仓库")
        self.add_btn.setObjectName("primary")
        self.add_btn.setToolTip("扫描一个或多个文件夹/磁盘，把找到的新仓库加入列表")
        self.add_btn.clicked.connect(self.add_requested.emit)

        self.settings_btn = SoftButton("⚙ 扫描设置", checkable=True)
        self.settings_btn.setToolTip(
            "扫描时往子文件夹里钻几层。层数越大找得越全，但耗时也越长；\n"
            "平时用默认的 5 层就够了。")
        self.settings_btn.toggled.connect(self._toggle_settings)

        # 添加仓库 : 扫描设置 ≈ 3 : 1，同一行对齐
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)
        bottom_row.addWidget(self.add_btn, 3)
        bottom_row.addWidget(self.settings_btn, 1)
        v.addLayout(bottom_row)

        self.settings_box = QWidget()
        sbox = QVBoxLayout(self.settings_box)
        sbox.setContentsMargins(0, 0, 0, 0)
        sbox.setSpacing(4)
        depth_row = QHBoxLayout()
        depth_row.setContentsMargins(0, 0, 0, 0)
        depth_row.setSpacing(4)
        dl = QLabel("扫描深度")
        dl.setObjectName("muted2")
        depth_row.addWidget(dl)
        self.depth_combo = QComboBox()
        for n in range(1, MAX_DEPTH + 1):
            self.depth_combo.addItem(f"往里找 {n} 层", n)
        self.depth_combo.setCurrentIndex(min(4, self.depth_combo.count() - 1))
        self.depth_combo.setToolTip("添加仓库时往子文件夹里钻几层去找。层数越多找得越全，但耗时越长。")
        self.depth_combo.currentIndexChanged.connect(
            lambda idx: self.depth_changed.emit(self.depth_combo.itemData(idx)))
        depth_row.addWidget(self.depth_combo)
        depth_row.addStretch(1)
        sbox.addLayout(depth_row)
        depth_tip = QLabel("数字越大，越不容易漏掉藏在深处的项目，但扫描也更慢。一般 5 层够用。")
        depth_tip.setObjectName("muted2")
        depth_tip.setWordWrap(True)
        sbox.addWidget(depth_tip)
        self.settings_box.setVisible(False)
        v.addWidget(self.settings_box)
        self.set_depth(settings.depth())  # 下拉框回读持久化的深度（继续扫描可能调大过）

        # 上次扫描因达到上限提前停止时出现；点一下自动加大深度、重扫上次的位置
        self.continue_btn = QPushButton()
        self.continue_btn.setObjectName("warnBtn")
        self.continue_btn.setCursor(Qt.PointingHandCursor)
        self.continue_btn.setVisible(False)
        self.continue_btn.clicked.connect(self.continue_scan.emit)
        v.addWidget(self.continue_btn)
        self.set_scan_capped(settings.scan_capped())

    # ---- 数据填充 ----

    def set_repos(self, infos):
        """用完整信息重建列表（infos 已按用户的排序规则排好）。"""
        self._infos = list(infos)
        self.listw.clear()
        for info in infos:
            self._add_card(info)
        self.count_lbl.setText(f"共 {len(infos)} 个" if infos else "")
        self.empty_hint.setVisible(not infos)
        self._apply_batch_state()
        self._filter(self.search.text())

    def _add_card(self, info):
        """往列表里放一张卡片，并把卡片上的交互接到面板信号上。"""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, info["path"])
        card = RepoCard(info)
        card.pin_clicked.connect(self.pin_toggled.emit)
        card.select_toggled.connect(self._on_card_select)
        card.open_requested.connect(self.open_folder.emit)
        card.action_requested.connect(self.card_action.emit)
        item.setSizeHint(QSize(0, card.sizeHint().height() + 6))
        self.listw.addItem(item)
        self.listw.setItemWidget(item, card)
        return card

    def add_pending(self, path):
        """扫描过程中实时追加一个"刚发现、还没读取详情"的仓库卡片。"""
        for i in range(self.listw.count()):
            if self.listw.item(i).data(Qt.UserRole) == path:
                return
        info = {"path": path, "name": os.path.basename(os.path.normpath(path)),
                "branch": None, "last_subject": None, "last_time": None,
                "remote_url": "", "pending": True, "error": None}
        self._infos.append(info)
        self._add_card(info)
        self.count_lbl.setText(f"共 {self.listw.count()} 个")
        self.empty_hint.setVisible(False)

    # ---- 选择 / 批量 ----

    def set_batch_mode(self, on):
        self._batch_mode = on
        self.batch_bar.setVisible(on)
        self.manage_btn.setText("完成" if on else "管理")
        if not on:
            self._selected.clear()
        for i in range(self.listw.count()):
            w = self.listw.itemWidget(self.listw.item(i))
            if w is not None:
                w.set_batch_mode(on)
                w.set_checked(on and w._path in self._selected)
        self._update_sel_lbl()

    def _apply_batch_state(self):
        for i in range(self.listw.count()):
            w = self.listw.itemWidget(self.listw.item(i))
            if w is not None:
                w.set_batch_mode(self._batch_mode)
                w.set_checked(self._batch_mode and w._path in self._selected)
        self._update_sel_lbl()

    def _on_card_select(self, path, on):
        if on:
            self._selected.add(path)
        else:
            self._selected.discard(path)
        self._update_sel_lbl()

    def _toggle_select_all(self, on):
        for i in range(self.listw.count()):
            if self.listw.item(i).isHidden():
                continue
            w = self.listw.itemWidget(self.listw.item(i))
            if w is not None:
                w.set_checked(on)

    def _update_sel_lbl(self):
        self.sel_lbl.setText(f"已选 {len(self._selected)} 个")

    def selected_paths(self):
        order = [i["path"] for i in self._infos]
        return [p for p in order if p in self._selected]

    # ---- 排序 ----

    def _show_sort_menu(self):
        menu = QMenu(self)
        a_name = QAction("按首字母排列", menu, checkable=True)
        a_time = QAction("按更新时间排序", menu, checkable=True)
        g1 = QActionGroup(menu)
        g1.setExclusive(True)
        g1.addAction(a_name)
        g1.addAction(a_time)
        a_local = QAction("优先显示本地仓库", menu, checkable=True)
        a_remote = QAction("优先显示已关联远程仓库", menu, checkable=True)
        a_none = QAction("不优先（默认顺序）", menu, checkable=True)
        g2 = QActionGroup(menu)
        g2.setExclusive(True)
        for a in (a_local, a_remote, a_none):
            g2.addAction(a)
        a_rev = QAction("倒序排列", menu, checkable=True)

        key = settings.sort_key()
        pri = settings.sort_priority()
        (a_name if key == "name" else a_time).setChecked(True)
        (a_local if pri == "local" else
         a_remote if pri == "remote" else a_none).setChecked(True)
        a_rev.setChecked(settings.sort_reverse())

        menu.addActions([a_name, a_time])
        menu.addSeparator()
        menu.addActions([a_local, a_remote, a_none])
        menu.addSeparator()
        menu.addAction(a_rev)
        a_name.triggered.connect(lambda: self._set_sort(key="name"))
        a_time.triggered.connect(lambda: self._set_sort(key="time"))
        a_local.triggered.connect(lambda: self._set_sort(priority="local"))
        a_remote.triggered.connect(lambda: self._set_sort(priority="remote"))
        a_none.triggered.connect(lambda: self._set_sort(priority="none"))
        a_rev.toggled.connect(lambda on: self._set_sort(reverse=on))
        menu.exec(self.sort_btn.mapToGlobal(self.sort_btn.rect().bottomLeft()))

    def _set_sort(self, key=None, priority=None, reverse=None):
        if key:
            settings.set_sort_key(key)
        if priority:
            settings.set_sort_priority(priority)
        if reverse is not None:
            settings.set_sort_reverse(reverse)
        self.sort_changed.emit()

    # ---- 其他 ----

    def _toggle_settings(self, on):
        self.settings_box.setVisible(bool(on))
        self.settings_btn.setText("⚙ 收起扫描设置" if on else "⚙ 扫描设置")

    def set_scanning(self, on):
        """扫描进行中：把「添加仓库」变成"换个位置扫描"，并露出「停止扫描」。"""
        self.cancel_btn.setVisible(bool(on))
        if on:
            self.add_btn.setText("➕ 换个位置扫描")
            self.add_btn.setToolTip(
                "正在扫描。想换成别的位置就点这里重新选择（会自动停止当前扫描）")
        else:
            self.add_btn.setText("➕ 添加仓库")
            self.add_btn.setToolTip(
                "扫描一个或多个文件夹/磁盘（可按住 Ctrl 多选），把找到的新仓库加入列表")

    def set_scan_capped(self, capped):
        """上次扫描达到上限时，显示「继续扫描」提示按钮。"""
        self.continue_btn.setVisible(bool(capped))
        if not capped:
            return
        if settings.depth() >= MAX_DEPTH:
            self.continue_btn.setText(
                "⚠ 上次扫描没扫完，且已是最深。可用「➕ 添加仓库」选择更具体的位置")
            self.continue_btn.setToolTip(
                "扫描深度已到最大值；直接选项目的上一层文件夹来添加，比整盘扫描更快更准")
        else:
            self.continue_btn.setText("⚠ 上次扫描没扫完：点这里自动加大深度，继续找漏掉的仓库")
            self.continue_btn.setToolTip(
                "重新扫描上次的位置（已添加的仓库不会重复），并自动把扫描深度加大一层")

    def set_depth(self, n):
        """同步扫描深度下拉框（不触发重复写入）。"""
        i = self.depth_combo.findData(int(n))
        if i >= 0:
            self.depth_combo.blockSignals(True)
            self.depth_combo.setCurrentIndex(i)
            self.depth_combo.blockSignals(False)

    def _filter(self, text):
        text = text.strip().lower()
        for i in range(self.listw.count()):
            item = self.listw.item(i)
            if i < len(self._infos):
                name = self._infos[i]["name"].lower()
                path = self._infos[i]["path"].lower()
            else:
                name = path = ""
            item.setHidden(bool(text) and text not in name and text not in path)

    def _on_row(self, row):
        if row < 0:
            return
        item = self.listw.item(row)
        if item is not None:
            self.selected.emit(item.data(Qt.UserRole))

    def select_path(self, path):
        for i in range(self.listw.count()):
            if self.listw.item(i).data(Qt.UserRole) == path:
                self.listw.setCurrentRow(i)
                return True
        return False

    def count(self):
        return self.listw.count()
