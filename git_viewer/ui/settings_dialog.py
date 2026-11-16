"""settings_dialog.py —— 「设置」对话框。

左边一列是分类（通用 / 快捷键 / 关于），右边是对应内容。外观改了会立刻生效，
语言改了也会立刻重刷一遍界面；两者都会记进 QSettings，下次打开软件仍是这个设置。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, APP_VERSION, i18n, settings
from . import styles
from . import widgets as ui_widgets
from .widgets import InfoCard, KVRow, badge

# (设置里存的值, 界面上显示的文字)
THEME_CHOICES = (("system", "跟随系统"), ("light", "浅色"), ("dark", "深色"))
SHORTCUTS = (
    ("刷新当前仓库", "F5"),
    ("搜索仓库 / 提交", "Ctrl + F"),
    ("打开选中仓库的文件夹", "双击卡片"),
    ("更多操作（复制路径、置顶、重读）", "右键卡片"),
    ("关闭对话框", "Esc"),
)


class SettingsDialog(QDialog):
    """设置面板。改完即生效，不需要「应用」按钮。"""

    help_requested = Signal()
    language_changed = Signal()

    def __init__(self, parent=None, git_version: str = ""):
        super().__init__(parent)
        self.git_version = git_version
        self._loading = True
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(680, 480)
        self._build()
        self._load_values()
        self._loading = False

    # ------------------------------------------------------------ 外观搭建
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setFixedWidth(150)
        self.nav.setObjectName("settingsNav")
        for text in ("通用", "快捷键", "关于"):
            self.nav.addItem(QListWidgetItem(text))
        self.nav.currentRowChanged.connect(self._on_nav)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_general())
        self.stack.addWidget(self._page_shortcut())
        self.stack.addWidget(self._page_about())

        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        foot = QHBoxLayout()
        foot.setContentsMargins(16, 10, 16, 12)
        tip = QLabel("改完立刻生效，不用点确定。")
        tip.setObjectName("muted2")
        foot.addWidget(tip)
        foot.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("primary")
        close_btn.setMinimumWidth(110)
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        foot.addWidget(close_btn)
        root.addLayout(foot)

        self.nav.setCurrentRow(0)

    def _on_nav(self, row):
        if row >= 0:
            self.stack.setCurrentIndex(row)

    # ------------------------------------------------------------ 设置行组件
    def _section(self, title):
        """分节标题（像 DeepSeek Harness 设置页那样：小节名 + 下面是若干行）。"""
        lbl = QLabel(title)
        lbl.setObjectName("settingsSection")
        return lbl

    def _divider(self):
        line = QFrame()
        line.setObjectName("settingsDivider")
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        return line

    def _row(self, title, desc, control):
        """一行设置：左边标题+说明，右边控件。"""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 10, 0, 10)
        h.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(3)
        t = QLabel(title)
        t.setObjectName("settingsRowTitle")
        left.addWidget(t)
        if desc:
            d = QLabel(desc)
            d.setObjectName("settingsRowDesc")
            d.setWordWrap(True)
            left.addWidget(d)
        h.addLayout(left, 1)
        control.setMinimumWidth(190)
        h.addWidget(control, 0)
        return w

    def _page_general(self):
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(24, 20, 24, 16)
        v.setSpacing(6)

        v.addWidget(self._section("外观"))
        self.theme_combo = QComboBox()
        self._fill_theme_combo()
        self.theme_combo.currentIndexChanged.connect(self._on_theme_combo)
        v.addWidget(self._row("主题",
                              "「跟随系统」会跟着 Windows 的深浅色自动切换；晚上用深色不刺眼。",
                              self.theme_combo))
        v.addWidget(self._divider())

        v.addSpacing(14)
        v.addWidget(self._section("语言"))
        self.lang_combo = QComboBox()
        for code, name in i18n.LANGUAGES:
            self.lang_combo.addItem(name, code)
        self.lang_combo.currentIndexChanged.connect(self._on_language)
        v.addWidget(self._row("界面语言",
                              "选中后立刻生效。仓库名、提交说明、路径这些是你项目里的真实内容，不会被翻译。",
                              self.lang_combo))
        v.addWidget(self._divider())

        v.addSpacing(14)
        v.addWidget(self._section("显示"))
        self.meta_chk = QCheckBox("在版本对比里显示 git 原始输出")
        self.meta_chk.setChecked(settings.diff_show_meta())
        self.meta_chk.toggled.connect(self._on_meta_toggle)
        v.addWidget(self._row("技术细节",
                              "默认藏起 diff --git、index 这类行，只显示改了哪几行。",
                              self.meta_chk))
        v.addWidget(self._divider())

        v.addStretch(1)
        page.setWidget(inner)
        return page

    def _page_shortcut(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(20, 18, 20, 12)
        v.setSpacing(14)

        card = InfoCard("键盘快捷键", explain="记住两个就够用了：F5 刷新、Ctrl+F 搜索。")
        for name, key in SHORTCUTS:
            card.add_layout(KVRow(name, value_widget=badge(key, "gray")))
        v.addWidget(card)
        v.addStretch(1)
        return page

    def _page_about(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(20, 18, 20, 12)
        v.setSpacing(14)

        card = InfoCard("关于", explain="纯本地小工具：只读取信息，不动你的代码。")
        head = QHBoxLayout()
        name = QLabel(APP_NAME)
        name.setObjectName("bigName")
        head.addWidget(name)
        head.addWidget(badge(f"v{APP_VERSION}", "indigo"))
        head.addStretch(1)
        card.add_layout(head)

        card.add_layout(KVRow("Git 工具", value_text=self.git_version or "未安装"))
        card.add_layout(KVRow("运行方式", value_text="Python + PySide6（Qt 界面）"))
        locations = InfoCard(
            "数据放在哪",
            explain="软件只在这些地方记东西，删掉设置文件就等于恢复出厂设置。",
        )
        locations.add_layout(KVRow("设置与收藏列表", value_text=settings.file_path() or "（未生成）"))
        v.addWidget(card)
        v.addWidget(locations)

        help_btn = QPushButton("📖 打开使用说明")
        help_btn.setObjectName("ghost")
        help_btn.clicked.connect(self.help_requested.emit)
        v.addWidget(help_btn)
        v.addStretch(1)
        return page

    # ---------------------------------------------------------------- 读写
    def _fill_theme_combo(self):
        """下拉框里的「跟随系统 / 浅色 / 深色」是界面文字，换语言要跟着变。"""
        combo = getattr(self, "theme_combo", None)
        if combo is None:
            return
        current = combo.currentData() or settings.theme()
        blocked = combo.blockSignals(True)
        combo.clear()
        for value, text in THEME_CHOICES:
            combo.addItem(i18n.translate(text), value)
        idx = max(0, combo.findData(current))
        combo.setCurrentIndex(idx)
        combo.blockSignals(blocked)

    def _load_values(self):
        # 记住用户选的是「跟随系统」还是具体某一档，而不是当下解析出来的结果
        stored = settings.theme()
        idx = max(0, self.theme_combo.findData(stored))
        self.theme_combo.setCurrentIndex(idx)
        idx = max(0, self.lang_combo.findData(settings.language()))
        self.lang_combo.setCurrentIndex(idx)
        self.meta_chk.setChecked(settings.diff_show_meta())

    def _on_theme_combo(self, _index):
        if self._loading:
            return
        value = self.theme_combo.currentData()
        if not value:
            return
        self._on_theme(value, True)

    def _on_meta_toggle(self, on):
        if self._loading:
            return
        settings.set_diff_show_meta(bool(on))

    def _on_theme(self, value, on):
        if not on or self._loading:
            return
        settings.set_theme(value)
        app = QApplication.instance()
        if app is not None:
            styles.apply_theme(app, value)
            # 自绘按钮的颜色是缓存下来的，必须主动让它按新主题重算
            ui_widgets.refresh_soft_buttons()

    def _on_language(self, _index):
        if self._loading:
            return
        code = self.lang_combo.currentData()
        if not code:
            return
        settings.set_language(code)
        i18n.set_language(code)
        # 立刻把当前窗口和主窗口的文字重刷一遍
        window = self.parent()
        while window is not None and window.parent() is not None:
            window = window.parent()
        if window is not None:
            i18n.retranslate(window)
        i18n.retranslate(self)
        self._fill_theme_combo()
        # 有些文字是"数据 + 界面词"拼出来的（作者：张三、张三（本仓库设置）…），
        # 它们被标成了 raw，重刷文本刷不到，让主窗口重新渲染一遍列表和详情。
        self.language_changed.emit()
