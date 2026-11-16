"""info_tab.py —— 「基本信息」标签页。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from .. import git_service as gs
from .. import i18n, utils
from .widgets import ElidedLabel, InfoCard, KVRow, badge, copy_button

REMOTE_TIP = ("远程仓库 = 这份代码在网络上的存放位置（比如 GitHub、Gitee），"
              "用来备份和多人协作。origin 是它的默认别名（昵称）。")
BRANCH_TIP = ("分支 = 项目里相互独立的两条“版本线”，一条线上的修改不会影响另一条。"
              "主线一般叫 main 或 master。")
IDENTITY_TIP = ("署名身份：提交代码时，历史记录里会显示这个名字和邮箱。"
                "只影响署名，不影响查看。")
STATUS_TIP = ("工作区就是你现在正在编辑的项目文件夹。这里提醒你有没有改了文件"
              "但还没生成“提交记录”的情况。")


def _wrap(layout):
    holder = QWidget()
    holder.setLayout(layout)
    return holder


class InfoTab(QWidget):
    def __init__(self, status_cb=None, parent=None):
        super().__init__(parent)
        self._status_cb = status_cb or (lambda s: None)
        self._repo_path = ""

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # 仓库名、位置、刷新/打开/删除这些入口都在主窗口顶部栏上，
        # 这里只放各张信息卡片（可滚动）
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.inner = QWidget()
        self.inner_v = QVBoxLayout(self.inner)
        self.inner_v.setContentsMargins(4, 0, 12, 14)
        self.inner_v.setSpacing(12)
        self.inner_v.addStretch(1)
        self.scroll.setWidget(self.inner)
        v.addWidget(self.scroll, 1)

    def set_repo(self, path):
        """记下当前仓库路径（路径提示已移到主窗口顶部栏）。"""
        self._repo_path = path or ""

    def _clear(self):
        while self.inner_v.count():
            item = self.inner_v.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def show_placeholder(self, text):
        self._clear()
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setObjectName("muted")
        self.inner_v.addWidget(lbl)
        self.inner_v.addStretch(1)

    def set_info(self, info):
        self._clear()
        errors = info.get("errors") or {}
        if len(errors) >= 5:
            card = InfoCard("读取失败", "这个文件夹可能不是有效的 Git 仓库，或仓库数据正被其他程序占用。")
            first_err = next(iter(errors.values()), "")
            card.add_layout(KVRow("详细信息", value_text=str(first_err)[:300]))
            self.inner_v.addWidget(card)
            self.inner_v.addStretch(1)
            return

        # ---- 1. 远程仓库地址 ----
        rc = InfoCard("远程仓库地址",
                      explain="这份代码在网络上（如 GitHub、Gitee）的存放地址。没有则表示这个项目只保存在这台电脑上。",
                      tip=REMOTE_TIP)
        remotes = info.get("remotes") or []
        if remotes:
            for r in remotes:
                row = QHBoxLayout()
                row.setSpacing(8)
                row.addWidget(badge(r["name"], "indigo",
                                    "这是这个远程仓库在本地的别名（昵称），一般叫 origin", raw=True))
                url = ElidedLabel(r["url"], Qt.ElideMiddle)
                url.setToolTip(r["url"])
                row.addWidget(url, 1)
                row.addWidget(_copy(r["url"]))
                rc.add(_wrap(row))
        else:
            none_lbl = QLabel("（无）—— 这个项目只保存在这台电脑上，还没关联网络仓库")
            none_lbl.setObjectName("muted")
            rc.add(none_lbl)
        self.inner_v.addWidget(rc)

        # ---- 2. 分支 ----
        bc = InfoCard("分支（项目的版本线）",
                      explain="当前站在哪条版本线上，以及这个项目里一共有哪几条线。主线一般叫 main 或 master。",
                      tip=BRANCH_TIP)
        cur = info.get("branch")
        if cur:
            bc.add_layout(KVRow("当前分支",
                                value_widget=badge(f"🌿 {cur}", "green",
                                                   "项目现在位于这条版本线上", raw=True)))
        else:
            bc.add_layout(KVRow("当前分支",
                                value_widget=badge("⚠ 不在任何分支上", "amber",
                                                   "正在查看某个历史版本，没有站在分支上（一般不影响查看）")))
        branches = info.get("branches") or []
        chips = [badge(("✓ " + b["name"]) if b.get("current") else b["name"],
                       "green" if b.get("current") else "gray",
                       "当前所在分支" if b.get("current") else "本地分支（版本线）",
                       raw=True)
                 for b in branches]
        if not chips and cur:
            chips = [badge("🌿 " + cur, "green", "新仓库还没有提交记录，所以暂时没有其他分支", raw=True)]
        # 每行最多 4 个，左对齐排列（用 GridLayout 会让胶囊被拉开铺满整行）
        for start in range(0, len(chips), 4):
            row = QHBoxLayout()
            row.setSpacing(6)
            for chip in chips[start:start + 4]:
                row.addWidget(chip)
            row.addStretch(1)
            bc.add_layout(row)
        if len(branches) > 1:
            hint = QLabel("每个胶囊就是一条版本线；带 ✓ 的是这个项目现在站着的那条。")
            hint.setObjectName("muted2")
            hint.setWordWrap(True)
            bc.add(hint)
        self.inner_v.addWidget(bc)

        # ---- 3. 署名 ----
        ic = InfoCard("提交署名（用户名 / 邮箱）",
                      explain="以后提交代码时，历史记录里显示的作者信息。",
                      tip=IDENTITY_TIP)
        for key, data in (("用户名", info.get("user_name")), ("邮箱", info.get("user_email"))):
            data = data or {}
            val = data.get("value")
            scope = data.get("scope")
            scope_name = gs.SCOPE_NAMES.get(scope, "") if scope else ""
            if val:
                text = f"{val}（{i18n.translate(scope_name)}）" if scope_name else val
            else:
                text = "未设置（不影响查看；以后要提交代码时才需要设置）"
            ic.add_layout(KVRow(key, value_text=text, copy_text=val, status_cb=self._status_cb,
                                raw=True))
        self.inner_v.addWidget(ic)

        # ---- 4. 最近一次提交 ----
        lc = info.get("last_commit")
        lcard = InfoCard("最近一次提交（最新的存档记录）",
                         explain="提交 = 给项目当前状态拍的一次“存档”，记录了谁在什么时候改了什么。")
        if lc:
            lcard.add_layout(KVRow("时间",
                                   value_text=f"{utils.fmt_dt(lc['author_date'])}（{utils.rel_time(lc['author_date'])}）",
                                   raw=True))
            lcard.add_layout(KVRow("作者",
                                   value_text=f"{lc['author_name']} <{lc['author_email']}>",
                                   raw=True))
            s = QLabel()
            i18n.set_raw(s, lc["subject"])
            s.setWordWrap(True)
            s.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lcard.add_layout(KVRow("说明", value_widget=s, copy_text=lc["subject"],
                                   status_cb=self._status_cb))
        else:
            empty = QLabel("这个仓库还没有任何提交记录（可能刚刚创建）")
            empty.setObjectName("muted")
            lcard.add(empty)
        if info.get("commit_count"):
            cnt = QLabel(f"这个项目一共保存过 {info['commit_count']} 次（提交）")
            cnt.setObjectName("muted")
            lcard.add(cnt)
        self.inner_v.addWidget(lcard)

        # ---- 5. 工作区状态 ----
        st = info.get("status")
        if st is not None:
            sc = InfoCard("工作区状态",
                          explain="有没有改了文件但还没做“提交”（保存存档记录）。",
                          tip=STATUS_TIP)
            if st["changed"] == 0:
                sc.add_layout(KVRow("当前状态", value_widget=badge("✓ 所有改动都已提交", "green")))
            else:
                sc.add(_wrap(_hstack(badge(f"⚠ 有 {st['changed']} 个文件的改动还没提交", "amber"))))
                note = QLabel("提示：本软件只负责查看，不会帮你提交。想保存这些改动，请在写代码的工具里操作。")
                note.setObjectName("muted")
                note.setWordWrap(True)
                sc.add(note)
            tips = []
            if st.get("no_commits_yet"):
                tips.append("这个分支还没有任何提交记录")
            if st.get("ahead"):
                tips.append(f"本地有 {st['ahead']} 个提交还没同步到网络仓库（术语叫“推送”）")
            if st.get("behind"):
                tips.append(f"网络仓库上有 {st['behind']} 个新提交还没下载到本地（术语叫“拉取”）")
            if tips:
                t2 = QLabel("；".join(tips))
                t2.setObjectName("muted")
                t2.setWordWrap(True)
                sc.add(t2)
            self.inner_v.addWidget(sc)

        self.inner_v.addStretch(1)


def _hstack(*widgets):
    h = QHBoxLayout()
    h.setSpacing(8)
    for w in widgets:
        h.addWidget(w)
    h.addStretch(1)
    return h


def _copy(text):
    from .widgets import copy_button
    return copy_button(text, None)
