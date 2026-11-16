"""widgets.py —— 界面里反复用到的小部件。"""
from __future__ import annotations

from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation, Qt)
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPalette, QPen
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from .. import i18n


class ElidedLabel(QLabel):
    """文本太长时自动显示成 "xxx…" 的标签（普通 QLabel 会把布局撑破）。

    里面装的永远是"数据"（路径、仓库名、提交说明），所以标成 raw：
    换语言时不会被翻译，也不会把省略后的文字当原文再翻一遍。
    """

    def __init__(self, text="", mode=Qt.ElideMiddle, parent=None):
        super().__init__(parent)
        self.setProperty("i18nRaw", True)
        self._full = str(text)
        self._mode = mode
        super().setText(self._full)

    def set_text(self, text):
        self._full = str(text)
        self._refresh()

    def full_text(self):
        return self._full

    def resizeEvent(self, event):
        self._refresh()
        super().resizeEvent(event)

    def _refresh(self):
        fm = QFontMetrics(self.font())
        super().setText(fm.elidedText(self._full, self._mode, max(20, self.width() - 4)))


def badge(text, kind="indigo", tooltip="", raw=False):
    """彩色小标签（圆角小胶囊），kind 见 styles.py 里的 badgeKind。

    raw=True 表示内容是一条"数据"（比如分支名），切语言时原样保留。
    """
    if raw:
        lbl = QLabel()
        i18n.set_raw(lbl, str(text))
    else:
        lbl = QLabel(str(text))
    lbl.setProperty("badge", "1")
    lbl.setProperty("badgeKind", kind)
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
    if tooltip:
        lbl.setToolTip(tooltip)
    return lbl


def help_dot(tip_text):
    """标题旁的小圆点"？"，鼠标放上去能看到名词解释。"""
    btn = QPushButton("?")
    btn.setObjectName("helpDot")
    btn.setFixedSize(18, 18)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFocusPolicy(Qt.NoFocus)
    btn.setToolTip(tip_text)
    return btn


def copy_button(text_provider, status_cb=None, label="复制"):
    """点击后把内容复制到剪贴板的小按钮。text_provider 可以是文本或返回文本的函数。"""
    btn = QPushButton(label)
    btn.setObjectName("copyBtn")
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFocusPolicy(Qt.NoFocus)

    def do_copy():
        text = text_provider() if callable(text_provider) else text_provider
        if not text:
            return
        QApplication.clipboard().setText(str(text))
        if status_cb:
            shown = str(text)
            status_cb("已复制：" + (shown[:40] + "…" if len(shown) > 40 else shown))

    btn.clicked.connect(do_copy)
    return btn


class InfoCard(QFrame):
    """详情页里的一张白色圆角卡片：标题 + 名词解释 + 内容。"""

    def __init__(self, title, explain=None, tip=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 10, 16, 12)
        outer.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(6)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        head.addWidget(t)
        if tip:
            head.addWidget(help_dot(tip))
        head.addStretch(1)
        outer.addLayout(head)
        if explain:
            e = QLabel(explain)
            e.setObjectName("muted")
            e.setWordWrap(True)
            outer.addWidget(e)
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        outer.addLayout(self.body)

    def add(self, widget):
        self.body.addWidget(widget)

    def add_layout(self, layout):
        self.body.addLayout(layout)


class KVRow(QHBoxLayout):
    """「标签：值」的一行，值很长时可以带复制按钮。"""

    def __init__(self, key, value_widget=None, value_text="", copy_text=None, status_cb=None,
                 raw=False):
        super().__init__()
        self.setSpacing(8)
        k = QLabel(key)
        k.setObjectName("muted")
        k.setMinimumWidth(88)
        k.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.addWidget(k)
        if value_widget is not None:
            # 胶囊标签这类"固定宽度"的值要贴着标签左边放，否则会被拉伸格子居中到一大片空白中间
            if value_widget.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed:
                self.addWidget(value_widget, 0, Qt.AlignLeft)
                self.addStretch(1)
            else:
                self.addWidget(value_widget, 1)
            text = copy_text
        else:
            v = QLabel()
            if raw:
                # 数据（用户名、邮箱、提交说明……）：换语言时保持原样
                i18n.set_raw(v, value_text)
            else:
                v.setText(value_text)
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.addWidget(v, 1)
            text = value_text if copy_text is None else copy_text
        if text:
            self.addWidget(copy_button(text, status_cb))


class EmptyState(QWidget):
    """没有仓库可选时，中间显示的欢迎/提示大卡片。"""

    def __init__(self, icon="👋", title="", desc="", parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        v.setSpacing(10)
        v.setContentsMargins(30, 60, 30, 20)
        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet("font-size: 46px; border: none;")
        self.title_lbl = QLabel(title)
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #111827; border: none;")
        self.desc_lbl = QLabel()
        self.desc_lbl.setWordWrap(True)
        # 固定一个舒服的宽度：太窄会把一句话拆得七零八落，太宽则不好读
        self.desc_lbl.setFixedWidth(620)
        self.desc_lbl.setStyleSheet("font-size: 13px; color: #6b7280; border: none;")
        self._set_desc(desc)
        v.addWidget(self.icon_lbl)
        v.addWidget(self.title_lbl)
        v.addWidget(self.desc_lbl)
        self.extra = QVBoxLayout()
        self.extra.setAlignment(Qt.AlignHCenter)
        self.extra.setSpacing(8)
        v.addLayout(self.extra)

    def _set_desc(self, desc):
        """多行说明左对齐（①②③ 才排得整齐），单行说明居中更自然。"""
        self.desc_lbl.setText(desc or "")
        self.desc_lbl.setAlignment(Qt.AlignLeft if "\n" in (desc or "") else Qt.AlignCenter)

    def set_message(self, title, desc):
        self.title_lbl.setText(title)
        self._set_desc(desc)

    def add_extra(self, widget):
        self.extra.addWidget(widget)


class Drawer(QWidget):
    """抽屉：点标题按钮后，内容以动画方式向下展开 / 收起。

    header（标题行）里可以再塞标题按钮之外的常驻控件（如统计条）；
    往 self.body_v 里加的内容就是抽屉里可收起的部分。
    """

    def _label(self, expanded):
        """标题按钮的文字：标题和后缀分开翻，切换语言才能整句跟上。"""
        return (i18n.translate(self._title)
                + i18n.translate("（点击收起）" if expanded else "（点击展开）"))

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self._title = title
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        self.toggle = QPushButton(self._label(False))
        self.toggle.setObjectName("ghost")
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.clicked.connect(self.toggle_drawer)
        self.header.addWidget(self.toggle)
        v.addLayout(self.header)
        self.body = QWidget()
        self.body.setVisible(False)
        self.body.setMaximumHeight(0)
        self.body_v = QVBoxLayout(self.body)
        self.body_v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.body)
        self._anim = None  # 持有动画引用，防止动画中途被垃圾回收

    def set_expanded(self, expanded, animate=False):
        """直接设定展开/收起状态（用于"默认展开"这种初始状态）。"""
        if expanded == (self.body.maximumHeight() != 0):
            return
        if not animate:
            if self._anim is not None:
                self._anim.stop()
            if expanded:
                self.body.setVisible(True)
                self.body.setMaximumHeight(16777215)   # QWIDGETSIZE_MAX：交给布局算高度
                self.toggle.setText(self._label(True))
            else:
                self.body.setVisible(False)
                self.body.setMaximumHeight(0)
                self.toggle.setText(self._label(False))
            return
        self.toggle_drawer()

    def toggle_drawer(self):
        collapsed = self.body.maximumHeight() == 0
        if collapsed:
            self.body.setVisible(True)
            target = self.body.sizeHint().height() + 4
            self.toggle.setText(self._label(True))
        else:
            target = 0
            self.toggle.setText(self._label(False))
        anim = QPropertyAnimation(self.body, b"maximumHeight", self)
        anim.setDuration(180)
        # 收起时从"当前实际高度"开始，否则若是 set_expanded 放开的无限高，会有一段无感的动画
        start = self.body.maximumHeight() if collapsed else min(self.body.maximumHeight(),
                                                               self.body.height())
        anim.setStartValue(start)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if not collapsed:
            anim.finished.connect(lambda: self.body.setVisible(False))
        self._anim = anim
        anim.start()


class SoftButton(QPushButton):
    """浅色小按钮：悬停、按下、选中都有渐变色动画。

    「排序」「管理」「扫描设置」以及顶部栏的仓库操作都用它，
    这样几个按钮的点击手感完全一致（换语言时文字照样跟着翻）。
    """

    _instances = []

    def __init__(self, text="", parent=None, checkable=False):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(checkable)
        self.setMinimumHeight(32)
        self.setFocusPolicy(Qt.TabFocus)
        self._bg = QColor(0, 0, 0, 0)
        self._anim = QPropertyAnimation(self, b"bgColor", self)
        self._anim.setDuration(130)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._bg = self._color_for("idle")
        self.toggled.connect(lambda _: self._animate_to("idle"))
        SoftButton._instances.append(self)

    def refresh_theme(self):
        """换主题后重新算一次配色（否则要等鼠标划过才变色）。"""
        self._anim.stop()
        self._bg = self._color_for("hover" if self.underMouse() else "idle")
        self.update()

    # ---- 颜色 ----

    def _is_dark(self):
        return self.palette().color(QPalette.ColorRole.Base).lightness() < 128

    def _color_for(self, state):
        dark = self._is_dark()
        checked = self.isChecked()
        if state == "press":
            return QColor("#dbe7fb") if dark else QColor("#dbe7fb")
        if checked:
            return QColor("#1d3a5f") if dark else QColor("#e8f0fe")
        if state == "hover":
            return QColor("#1e2733") if dark else QColor("#f1f5f9")
        return QColor("#1b222c") if dark else QColor("#ffffff")

    def _border_color(self):
        dark = self._is_dark()
        if self.underMouse() or self.hasFocus():
            return QColor("#3b82f6")
        return QColor("#39424f") if dark else QColor("#d8dee9")

    def _text_color(self):
        dark = self._is_dark()
        if self.isChecked():
            return QColor("#93c5fd") if dark else QColor("#1d4ed8")
        return QColor("#e6e9ef") if dark else QColor("#334155")

    def _animate_to(self, state):
        target = self._color_for(state)
        self._anim.stop()
        self._anim.setStartValue(self._bg)
        self._anim.setEndValue(target)
        self._anim.start()
        self.update()

    def _get_bg(self):
        return self._bg

    def _set_bg(self, color):
        self._bg = color
        self.update()

    bgColor = Property(QColor, _get_bg, _set_bg)

    # ---- 交互 ----

    def enterEvent(self, event):
        self._animate_to("hover")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_to("idle")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._animate_to("press")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._animate_to("hover" if self.underMouse() else "idle")
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        radius = 8.0
        painter.setPen(QPen(self._border_color(), 1.2))
        painter.setBrush(QBrush(self._bg))
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(QPen(self._text_color(), 1))
        font = QFont(self.font())
        if self.isChecked():
            font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect,
                         int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextSingleLine),
                         self.text())
        if not self.isEnabled():
            painter.setBrush(QBrush(QColor(0, 0, 0, 90) if self._is_dark()
                                    else QColor(255, 255, 255, 140)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, radius, radius)


def refresh_soft_buttons():
    """切完主题后调用：让所有 SoftButton 立刻按新主题重画。"""
    alive = []
    for btn in SoftButton._instances:
        try:
            btn.refresh_theme()
        except RuntimeError:      # 控件已被销毁
            continue
        alive.append(btn)
    SoftButton._instances = alive

