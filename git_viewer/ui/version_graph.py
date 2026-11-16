"""version_graph.py —— 「提交历史」里的版本树（思维导图样式）。

为什么不用列表：一长串提交看不出哪条是主线、哪里分出了分支。这里把每个提交
画成一个可点的方块，用曲线把"子提交 → 父提交"连起来，同一个分支排在同一列
（lane），主线默认在最左边。

交互：
* 左键点节点  = 选中并在左侧显示这个版本的详情（和原来的行为一致）
* 左键拖空白  = 平移画布（不会拖出边框外）
* 滚轮        = 以鼠标位置为中心缩放（Shift + 滚轮上下滚动）
* 双击空白    = 缩放和位置复位
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath,
                           QPen)
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsPathItem, QGraphicsScene,
                               QGraphicsView)

from .. import i18n, utils

# 每个分支（lane）一种颜色，深浅主题各一套
LANE_COLORS_LIGHT = ("#2563eb", "#0d9488", "#7c3aed", "#ea580c", "#059669",
                     "#e11d48", "#0891b2", "#a16207")
LANE_COLORS_DARK = ("#60a5fa", "#2dd4bf", "#a78bfa", "#fb923c", "#34d399",
                    "#fb7185", "#22d3ee", "#facc15")

NODE_W = 176
NODE_H = 50
LANE_GAP = 210
ROW_GAP = 78
PAD = 30          # 内容四周留白
EXTRA = 260       # 内容外还能拖多远（比原来大一截，拖起来更自由）


class _NodeItem(QGraphicsItem):
    """一个版本方块。自己画，点击/悬停都在这层处理。"""

    def __init__(self, view: "VersionGraph", index: int):
        super().__init__()
        self._view = view
        self.index = index
        self.label = ""
        self.subject = ""
        self.is_head = False
        self.lane = 0
        self.selected = False
        self.matched = True
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setZValue(2)
        self._hover = False

    # ---- 绘制 ----
    def boundingRect(self):
        return QRectF(-2, -2, NODE_W + 4, NODE_H + 4)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        dark = self._view.is_dark()
        color = QColor(self._view.lane_color(self.lane))
        rect = QRectF(0, 0, NODE_W, NODE_H)

        if self.selected:
            fill = QBrush(color)
            pen = QPen(color, 1.5)
        elif self.is_head:
            fill = QBrush(QColor("#16233a") if dark else QColor("#eff6ff"))
            pen = QPen(color, 2.0)
        else:
            fill = QBrush(QColor("#1b222c") if dark else QColor("#ffffff"))
            pen = QPen(color, 1.4)
        if self._hover and not self.selected:
            fill = QBrush(QColor("#22303f") if dark else QColor("#f5f8ff"))

        painter.setBrush(fill)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 10, 10)

        # 左边一条同色竖条，方便一眼看出属于哪个分支
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(QRectF(0, 8, 4, NODE_H - 16), 2, 2)

        text_color = QColor("#ffffff") if self.selected else (
            QColor("#e6e9ef") if dark else QColor("#1f2937"))
        sub_color = QColor("#dbeafe") if self.selected else (
            QColor("#9aa4b2") if dark else QColor("#6b7280"))

        f1 = QFont(painter.font())
        f1.setPointSizeF(max(8.5, f1.pointSizeF()))
        f1.setBold(True)
        painter.setFont(f1)
        painter.setPen(QPen(text_color))
        label = QFontMetricsF(f1).elidedText(self.label, Qt.ElideRight, NODE_W - 26)
        painter.drawText(QRectF(14, 6, NODE_W - 24, 20), Qt.AlignLeft | Qt.AlignVCenter, label)

        f2 = QFont(painter.font())
        f2.setBold(False)
        f2.setPointSizeF(max(8.0, f1.pointSizeF() - 1.0))
        painter.setFont(f2)
        painter.setPen(QPen(sub_color))
        subject = QFontMetricsF(f2).elidedText(self.subject, Qt.ElideRight, NODE_W - 26)
        painter.drawText(QRectF(14, 26, NODE_W - 24, 18), Qt.AlignLeft | Qt.AlignVCenter, subject)

        if not self.matched:
            painter.setBrush(QBrush(QColor(21, 26, 33, 190) if dark else QColor(255, 255, 255, 190)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 10, 10)

    # ---- 交互 ----
    def hoverEnterEvent(self, event):
        self._hover = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        # 吃掉按下事件，避免被画布的"拖拽平移"逻辑抢走
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._view.node_clicked.emit(self.index)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class VersionGraph(QGraphicsView):
    """版本树画布：节点 + 连线 + 自适应边框，可平移、可缩放。"""

    node_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setObjectName("versionGraph")
        self.setMinimumHeight(220)

        self._nodes = []
        self._edges = []
        self._border = None
        self._selected = -1
        self._panning = False
        self._pan_pos = QPointF()
        self._zoom = 1.0

    # ---- 主题 ----
    def is_dark(self):
        return self.palette().color(self.palette().ColorRole.Base).lightness() < 128

    def lane_color(self, lane):
        palette = LANE_COLORS_DARK if self.is_dark() else LANE_COLORS_LIGHT
        return palette[lane % len(palette)]

    # ---- 数据 ----
    def clear_data(self):
        self._scene.clear()
        self._nodes = []
        self._edges = []
        self._border = None
        self._selected = -1
        self.resetTransform()
        self._zoom = 1.0

    def set_data(self, commits, labels):
        """commits 已按从新到旧排好；labels 与之一一对应。"""
        self.clear_data()
        if not commits:
            return
        lanes = _assign_lanes(commits)
        count = len(commits)
        self._nodes = []
        for i, c in enumerate(commits):
            node = _NodeItem(self, i)
            node.label = labels[i]
            node.subject = c.get("subject") or ""
            node.is_head = bool((c.get("refs") or {}).get("head_ref"))
            node.lane = lanes[i]
            node.setPos(PAD + lanes[i] * LANE_GAP, PAD + i * ROW_GAP)
            node.setToolTip(
                f"{labels[i]}  {utils.fmt_dt(c.get('commit_date'), True)}\n"
                f"{c.get('subject') or ''}\n{i18n.translate('完整版本号')}：{c.get('hash')}")
            self._scene.addItem(node)
            self._nodes.append(node)

        index_of = {c["hash"]: i for i, c in enumerate(commits)}
        for i, c in enumerate(commits):
            color = QColor(self.lane_color(lanes[i]))
            for parent in (c.get("parent_list") or []):
                j = index_of.get(parent)
                if j is None:
                    continue
                color = QColor(self.lane_color(lanes[j]))
                self._add_edge(i, j, color)

        self._update_border()
        self._fit_scene()

    def _add_edge(self, child, parent, color):
        a = self._nodes[child]
        b = self._nodes[parent]
        # 竖线落在节点正中间，两条连线才不会看着偏一边
        x1 = a.pos().x() + NODE_W / 2.0
        y1 = a.pos().y() + NODE_H
        x2 = b.pos().x() + NODE_W / 2.0
        y2 = b.pos().y()
        path = QPainterPath(QPointF(x1, y1))
        if abs(x1 - x2) < 0.5:
            path.lineTo(x2, y2)
        else:
            mid = (y1 + y2) / 2.0
            path.cubicTo(QPointF(x1, mid), QPointF(x2, mid), QPointF(x2, y2))
        item = QGraphicsPathItem(path)
        pen = QPen(color, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        item.setPen(pen)
        item.setZValue(0)
        self._scene.addItem(item)
        item.setData(0, (child, parent))
        self._edges.append(item)

    def _update_border(self):
        """算出内容范围（画布可拖动范围就按它来），不再画虚线边框。"""
        if not self._nodes:
            return
        if self._border is not None:
            self._scene.removeItem(self._border)
            self._border = None
        rect = self._nodes[0].sceneBoundingRect()
        for node in self._nodes[1:]:
            rect = rect.united(node.sceneBoundingRect())
        self._content_rect = rect.adjusted(-PAD, -PAD, PAD, PAD)
        # 画布范围比内容大一圈：留足拖动余量，又不至于能拖到无穷远
        self.setSceneRect(self._content_rect.adjusted(-EXTRA, -EXTRA, EXTRA, EXTRA))

    def _fit_scene(self):
        """内容比视口小就居中，比视口大就从左上角看起。"""
        if not self._nodes:
            return
        self.centerOn(self._content_rect.center())

    # ---- 过滤 ----
    def set_filter(self, needle):
        needle = (needle or "").strip().lower()
        shown = 0
        for node in self._nodes:
            blob = getattr(node, "blob", "")
            hit = (not needle) or (needle in blob)
            node.matched = hit
            node.update()
            if hit:
                shown += 1
        for edge in self._edges:
            data = edge.data(0)
            if not data:
                continue
            child, parent = data
            edge.setVisible(self._nodes[child].matched or self._nodes[parent].matched)
        return shown

    def set_blobs(self, blobs):
        for node, blob in zip(self._nodes, blobs):
            node.blob = blob

    # ---- 选中 ----
    def select(self, index, notify=False):
        if index == self._selected:
            return
        if 0 <= self._selected < len(self._nodes):
            self._nodes[self._selected].selected = False
            self._nodes[self._selected].update()
        self._selected = index
        if 0 <= index < len(self._nodes):
            node = self._nodes[index]
            node.selected = True
            node.update()
            self.ensureVisible(node, 40, 40)
        if notify and index >= 0:
            self.node_clicked.emit(index)

    def first_visible(self):
        for i, node in enumerate(self._nodes):
            if node.matched:
                return i
        return -1

    def zoom_reset(self):
        self.resetTransform()
        self._zoom = 1.0
        self._fit_scene()

    # ---- 视图交互 ----
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ShiftModifier:
            super().wheelEvent(event)
            return
        step = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        target = self._zoom * step
        if target < 0.4 or target > 2.5:
            event.accept()
            return
        self._zoom = target
        self.scale(step, step)
        event.accept()

    def mousePressEvent(self, event):
        # 除了按在版本节点上（那是"按钮"），其余任何地方都能拖着平移：
        # 空白处、连线、边距都算，手感才顺。
        item = self.itemAt(event.pos())
        if event.button() == Qt.LeftButton and not isinstance(item, _NodeItem):
            self._panning = True
            self._pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_pos
            self._pan_pos = event.pos()
            h, v = self.horizontalScrollBar(), self.verticalScrollBar()
            h.setValue(h.value() - int(delta.x()))
            v.setValue(v.value() - int(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.itemAt(event.pos()) is None:
            self.zoom_reset()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


def _assign_lanes(commits):
    """给每个提交分一条"泳道"：主线在 0，分出去的分支排到右边。

    做法是模拟 gitk：从最新的提交往下走，每条泳道记着"下一个应该出现的提交"。
    遇到没被预期到的提交（分支的起点、或者没连上的历史）就找一条空泳道。
    合并提交的第二个及以后的父提交，各自占一条新泳道，分支线就看出来了。
    """
    expect = []      # 每条泳道当前等待的提交哈希
    lanes = []
    for c in commits:
        h = c["hash"]
        if h in expect:
            lane = expect.index(h)
        else:
            lane = None
            for i, pending in enumerate(expect):
                if pending is None:
                    lane = i
                    break
            if lane is None:
                lane = len(expect)
                expect.append(None)
        lanes.append(lane)
        parents = c.get("parent_list") or []
        expect[lane] = parents[0] if parents else None
        for extra in parents[1:]:
            if extra in expect:
                continue
            slot = None
            for i in range(lane + 1, len(expect)):
                if expect[i] is None:
                    slot = i
                    break
            if slot is None:
                slot = len(expect)
                expect.append(None)
            expect[slot] = extra
    return lanes
