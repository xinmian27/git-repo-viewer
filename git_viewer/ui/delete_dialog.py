"""delete_dialog.py —— 删除前的确认对话框。

三种可选操作（都以"移入系统回收站"为准，不永久删除）：
1. 删除 Git 历史 —— 只删 .git，代码文件全部保留；
2. 删除整个文件夹 —— 代码和 Git 历史一起进回收站；
3. 仅从列表移除 —— 什么都不删。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout)

from .widgets import ElidedLabel, copy_button


class _OptionRow(QFrame):
    """一行可点击的操作选项（悬停高亮）。"""

    clicked = Signal()

    def __init__(self, icon, title, desc, danger=False, parent=None):
        super().__init__(parent)
        self.setObjectName("optionRow")
        self.setProperty("danger", "1" if danger else "0")
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 9, 12, 9)
        h.setSpacing(10)
        ic = QLabel(icon)
        ic.setStyleSheet("font-size: 18px; border: none; background: transparent;")
        h.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(1)
        t = QLabel(title)
        t.setStyleSheet("font-weight: 700; font-size: 13px; border: none; background: transparent;")
        col.addWidget(t)
        d = QLabel(desc)
        d.setObjectName("muted")
        d.setWordWrap(True)
        col.addWidget(d)
        h.addLayout(col, 1)
        arrow = QLabel("›")
        arrow.setStyleSheet("color: #9ca3af; font-size: 16px; border: none; background: transparent;")
        h.addWidget(arrow)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class DeleteRepoDialog(QDialog):
    """删除确认框。exec() 返回 Accepted 后，通过 self.action 读取用户的选择。

    repo_path 传一个路径 = 删单个仓库；传路径列表 = 批量删这几个仓库，
    两种情况的界面与交互完全一样，只是标题和说明会带上数量。
    """

    ACTION_TRASH_GIT = "trash_git"        # 删除 .git（进回收站）并从列表移除
    ACTION_TRASH_FOLDER = "trash_folder"  # 删除整个文件夹（进回收站）并从列表移除
    ACTION_HIDE = "hide"                  # 仅从列表移除，什么都不删

    def __init__(self, parent, repo_path):
        super().__init__(parent)
        self.action = None
        paths = [repo_path] if isinstance(repo_path, str) else [p for p in repo_path if p]
        self.paths = paths
        many = len(paths) > 1
        first = paths[0] if paths else ""
        name = os.path.basename(os.path.normpath(first)) if first else ""
        word = f"选中的 {len(paths)} 个仓库" if many else f"「{name}」"
        self.setWindowTitle(f"删除 {len(paths)} 个仓库" if many else "删除")
        self.setMinimumWidth(640)

        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 16)
        v.setSpacing(10)

        head = QHBoxLayout()
        icon = QLabel("⚠️")
        icon.setStyleSheet("font-size: 30px; border: none;")
        head.addWidget(icon)
        t = QLabel(f"要{word}做什么？")
        t.setStyleSheet("font-size: 16px; font-weight: 700; border: none;")
        head.addWidget(t)
        head.addStretch(1)
        v.addLayout(head)

        card = QFrame()
        card.setObjectName("card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(14, 10, 14, 12)
        cv.setSpacing(6)
        prow = QHBoxLayout()
        pl = QLabel("位置" if not many else "其中第一个")
        pl.setObjectName("muted")
        prow.addWidget(pl)
        p = ElidedLabel(first, Qt.ElideMiddle)
        p.setObjectName("muted")
        prow.addWidget(p, 1)
        prow.addWidget(copy_button(first, None, label="复制路径"))
        cv.addLayout(prow)
        if many:
            names = "、".join(os.path.basename(os.path.normpath(x)) for x in paths[:6])
            if len(paths) > 6:
                names += f" 等 {len(paths)} 个"
            lst = QLabel(names)
            lst.setObjectName("muted")
            lst.setWordWrap(True)
            cv.addWidget(lst)
        v.addWidget(card)

        note = QLabel("下面所有操作都只是把内容移入系统回收站（不是永久删除），"
                      "随时可以在回收站里还原；但在本软件里无法撤销。")
        note.setWordWrap(True)
        note.setObjectName("muted")
        v.addWidget(note)

        row_git = _OptionRow(
            "🗂", "删除 Git 历史",
            "把版本记录文件夹（.git）移入回收站：代码文件全部保留，"
            "此文件夹不再受 Git 管理，并从列表移除。" if not many else
            f"把这 {len(paths)} 个仓库的版本记录文件夹（.git）逐个移入回收站：代码文件全部保留，"
            "并从列表移除。")
        row_git.clicked.connect(lambda: self._confirm_and_done(
            "删除 Git 历史",
            "会把该项目的版本记录（.git）移入回收站：代码文件全部保留，可随时在回收站还原。"
            if not many else
            f"会把这 {len(paths)} 个仓库的版本记录（.git）逐个移入回收站：代码文件全部保留，"
            "可随时在回收站还原。",
            self.ACTION_TRASH_GIT))
        v.addWidget(row_git)

        row_folder = _OptionRow(
            "📁", "删除整个文件夹",
            "把整个项目文件夹（代码 + Git 历史）移入回收站：内容较多时耗时稍长。"
            if not many else
            f"把这 {len(paths)} 个项目文件夹（代码 + Git 历史）逐个移入回收站：内容较多时耗时稍长。",
            danger=True)
        row_folder.clicked.connect(lambda: self._confirm_and_done(
            "删除整个文件夹",
            "会把整个项目文件夹（代码 + Git 历史）移入回收站：内容较多时耗时稍长，"
            "可随时在回收站还原。" if not many else
            f"会把这 {len(paths)} 个项目文件夹（代码 + Git 历史）逐个移入回收站："
            "内容较多时耗时稍长，可随时在回收站还原。",
            self.ACTION_TRASH_FOLDER))
        v.addWidget(row_folder)

        row_hide = _OptionRow(
            "📋", "仅从列表移除",
            "什么都不删，只是列表里不再显示；重新扫描后它会再次出现。" if not many else
            "什么都不删，只是这些仓库不再出现在列表里；重新扫描后它们会再次出现。")
        row_hide.clicked.connect(lambda: self._confirm_and_done(
            "仅从列表移除",
            "不会删除任何文件，只是列表里不再显示，重新扫描后它会再次出现。" if not many else
            "不会删除任何文件，只是这些仓库不再出现在列表里，重新扫描后它们会再次出现。",
            self.ACTION_HIDE))
        v.addWidget(row_hide)

        v.addStretch(1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("ghost")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        v.addLayout(btns)

    def _confirm_and_done(self, title, extra, action):
        """每个操作行都要再过一次确认框，防止手滑点错。"""
        box = QMessageBox(self)
        box.setWindowTitle("再确认一下")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"确定要「{title}」吗？")
        box.setInformativeText(extra)
        yes = box.addButton("确定", QMessageBox.ButtonRole.YesRole)
        box.addButton("再想想", QMessageBox.ButtonRole.NoRole)
        box.exec()
        if box.clickedButton() is yes:
            self._done(action)

    def _done(self, action):
        self.action = action
        self.accept()
