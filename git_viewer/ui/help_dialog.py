"""help_dialog.py —— 「使用说明」（顶部标签分页）+ Git 安装引导。"""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QTabWidget, QTextBrowser, QVBoxLayout)

from .. import APP_NAME, APP_VERSION, i18n

GIT_DOWNLOAD_URL = "https://git-scm.com/download/win"

_QUICK_HTML = """
<div style="font-size:13px; line-height:1.8;">
<h2>🚀 三步上手</h2>
<ol>
<li>点左侧底部的 <b>「➕ 添加仓库」</b>，选中你存放代码项目的文件夹（可按住 Ctrl 一次多选，
也可以直接选某个磁盘整盘扫描）。<b>手边还没有项目？</b>点欢迎页的
「👀 用一个示例项目练手」，软件会生成一个示例项目给你随便点；</li>
<li>等几秒，左侧列表就会列出找到的所有 Git 仓库（找到一个就先显示一个；嫌慢可点左下角
「⏹ 停止扫描」）。可用「↕ 排序」调整顺序、🔍 搜索框筛选，<b>双击</b>卡片打开所在文件夹，
<b>右键</b>卡片有更多操作；</li>
<li>右侧依次看 <b>「基本信息」「提交历史」「版本对比」</b> 三个标签页即可。「提交历史」里那棵<b>思维导图式版本树</b>可以按住空白处拖动、滚轮缩放，点任意节点就在左边看这次的详情。</li>
</ol>

<h3>⌨️ 两个常用快捷键</h3>
<p><b>F5</b>：重新读取当前仓库（换了文件、提交了新版本后想刷新）。
<b>Ctrl + F</b>：直接跳到左上角的搜索框，开始筛选仓库。</p>

<h3>🖱 卡片上能做的事</h3>
<p><b>单击</b>卡片：右边显示这个项目的详细信息。<br>
<b>双击</b>卡片：直接在文件管理器里打开这个项目所在的文件夹。<br>
<b>右键</b>卡片：打开菜单，可以「重新读取信息」「复制文件夹路径」「置顶」「仅从列表移除」。<br>
卡片右侧的 📌：置顶这个仓库，常用的项目就不会被后来扫描到的项目挤走。</p>
</div>
"""

_GLOSSARY_HTML = """
<div style="font-size:13px; line-height:1.75;">
<h2>📖 常见名词（都是大白话）</h2>
<p><b>Git</b>：一款管理文件修改历史的工具，能记住项目的每一步变化，随时可以回看。本软件就是帮你"看"它的。</p>
<p><b>仓库（Repository）</b>：被 Git 管理的项目文件夹。判断标准：文件夹里有个隐藏的 <code>.git</code> 子文件夹。</p>
<p><b>添加仓库（扫描）</b>：本软件自动在你选的文件夹里把所有仓库找出来加入左侧列表，不用你一个一个找；重复扫描只会补充新出现的仓库，已有的不会被移除。</p>
<p><b>扫描深度</b>：添加仓库时往子文件夹里"钻"几层去找。层数越多找得越全，但扫描越慢，默认 5 层。改它的地方在左下角「⚙ 扫描设置」里（平时收起来，不用管）。</p>
<p><b>收藏列表</b>：添加过的仓库会记住（置顶/排序也会记住），下次打开软件直接显示，不用重新扫描。</p>
<p><b>置顶</b>：点仓库卡片右侧的 📌，把它固定在列表最前面；再点一次取消。常用项目再也不用翻着找。</p>
<p><b>排序</b>：列表顶部「↕ 排序」可选按首字母或按更新时间排列、正序/倒序，以及优先显示本地仓库或已关联远程的仓库。</p>
<p><b>批量管理</b>：列表顶部「管理」进入勾选模式，一次选中多个仓库后统一「移除 / 删历史 / 删文件夹 / 置顶」。删除类操作都会先弹确认框，且一律移入回收站（可还原）。</p>
<p><b>远程仓库</b>：放在网上服务器（如 GitHub、Gitee）的仓库副本，用来备份和多人协作。没有远程仓库 = 项目只存在这台电脑上。</p>
<p><b>origin</b>：远程仓库在本地的默认"别名/昵称"，一般不用改它。</p>
<p><b>分支（Branch）</b>：同一个项目里互不干扰的"平行版本线"。主线通常叫 main 或 master。</p>
<p><b>提交（Commit）</b>：一次正式保存的修改记录，相当于游戏里的"存档"，记录了谁在什么时候改了什么。</p>
<p><b>版本号（哈希）</b>：每次提交的唯一编号，像身份证号，用来精确定位某一次保存。</p>
<p><b>提交历史</b>：所有提交按时间从新到旧排成的列表。</p>
<p><b>版本树</b>：提交历史的思维导图——每个提交是一个节点，从新到旧连成一条时间线；分支会另外分出一列（泳道），合并的地方有连线连回去，所以哪条是 main、哪些是分支一眼就能看出来。点任意节点，左边就能看到这次提交的详情。</p>
<p><b>版本对比（差异）</b>：看两个版本之间文件内容哪里变了。在「版本对比」页用两个下拉框选
「版本 A（较早）」和「版本 B（较近）」，下面就会列出全部变化。
<span style="color:#0a6e3c;">🟩 绿色 = 新增的行</span>，
<span style="color:#a40e26;">🟥 红色 = 删除的行</span>。
行首的 <code>+</code> / <code>-</code> 也是"新增/删除"的意思，软件默认会把 <code>@@</code> 之类的
原始信息换成人话；想看 git 原样输出，勾选右上角「显示技术细节」。</p>
<p><b>工作区</b>：你现在正在编辑的项目文件夹本身。"有改动未提交" = 文件改了，但还没拍存档。</p>
<p><b>推送（push）/ 拉取（pull）</b>：把本地的新提交上传到网络仓库 / 把网络仓库的新提交下载到本地。</p>
</div>
"""

_FAQ_HTML = """
<div style="font-size:13px; line-height:1.8;">
<h2>🛟 遇到问题</h2>
<p><b>扫描不到仓库？</b> 试试：① 换成更上一层的文件夹重新扫；② 点左下角「⚙ 扫描设置」把
「扫描深度」调大；③ 上次扫描没扫完时，点列表底部的「⚠ 继续扫描」，软件会自动加大深度再扫一遍；
④ 确认项目文件夹里确实有隐藏的 .git。</p>
<p><b>提示没有 Git 工具？</b> 点软件界面上的「查看安装教程」，按步骤装一下就好（免费，两分钟）。</p>
<p><b>怎么删除仓库内容？</b> 选中仓库后，在「基本信息」页顶部点红色「🗑 删除」，确认框里有三种
选择：<b>删除 Git 历史</b>（只把版本记录 .git 移入回收站，代码保留）、<b>删除整个文件夹</b>
（代码和历史一起进回收站）、<b>仅从列表移除</b>（什么都不删）。三种都会先弹确认框，且都是移入
回收站，可在回收站还原。多个仓库一起删用列表顶部「管理」的批量操作，删除过程有进度框和已用时间，
随时可点「停止」。</p>
<p><b>删除时会卡住吗？</b> 不会。文件是后台搬进回收站的，删除大文件夹时窗口照样能操作，
进度框里的"已用时"会一秒一秒地跳。</p>
<p><b>中文显示乱码？</b> 极少数老仓库的提交说明是用旧编码保存的，属正常现象，不影响其他信息。</p>
<p><b>想换个配色或用英文界面？</b> 点右上角「⚙ 设置」：外观可选浅色 / 深色 / 跟随系统，
语言可选简体中文 / 繁體中文 / English。外观立即生效；语言需要重启软件后生效。</p>
</div>
"""

_QUICK_HTML_EN = """
<div style="font-size:13px; line-height:1.8;">
<h2>🚀 Get started</h2>
<ol>
<li>Click <b>“➕ Add repository”</b> at the bottom left and pick the folder that holds your
code projects (hold Ctrl to pick several, or scan a whole drive). <b>No project yet?</b>
Click “👀 No project yet? Try a sample project” on the welcome page — the app creates one for
you to poke around;</li>
<li>After a few seconds the repositories appear on the left (each one shows up as soon as it is
found; you can stop early with “⏹ Stop scanning”). Use “↕ Sort” to reorder, the 🔍 box to
filter, <b>double-click</b> a card to open its folder, <b>right-click</b> for more actions;</li>
<li>On the right, read the three tabs: <b>Overview</b>, <b>History</b> and
<b>Compare versions</b>. Inside <b>History</b> the version graph is a mind map —
drag empty space to pan, scroll to zoom, click any node to see its details on the left.</li>
</ol>

<h3>⌨️ Two shortcuts worth remembering</h3>
<p><b>F5</b>: reload the current repository (after files changed or you made a new commit).
<b>Ctrl + F</b>: jump straight to the search box on the left.</p>

<h3>🖱 What you can do on a card</h3>
<p><b>Click</b>: show this project on the right.<br>
<b>Double-click</b>: open the project folder in your file manager.<br>
<b>Right-click</b>: “Reload info”, “Copy folder path”, “Pin”, “Remove from list only”.<br>
The 📌 on the right pins the repository so it stays on top.</p>
</div>
"""

_GLOSSARY_HTML_EN = """
<div style="font-size:13px; line-height:1.75;">
<h2>📖 Glossary (plain words)</h2>
<p><b>Git</b>: a tool that remembers every change of your files, so you can look back at any
point. This app is the “viewer” for it.</p>
<p><b>Repository</b>: a project folder managed by Git. Test: the folder contains a hidden
<code>.git</code> subfolder.</p>
<p><b>Add repository (scan)</b>: the app searches the folders you pick and adds every repository
it finds. Scanning again only adds new ones; existing entries stay.</p>
<p><b>Scan depth</b>: how many levels deep the scan looks. More levels find more but are slower.
The setting lives under “⚙ Scan options” at the bottom left (collapsed by default).</p>
<p><b>Saved list</b>: repositories you added are remembered (pins and sorting too), so they show
up next time without scanning.</p>
<p><b>Pin</b>: click the 📌 on a card to keep it at the top; click again to unpin.</p>
<p><b>Sort</b>: “↕ Sort” lets you order by name or by update time, ascending or descending, and
prefer local or remote-backed repositories.</p>
<p><b>Batch manage</b>: “Manage” at the top switches the list into check-box mode; then remove,
delete history, delete folder or pin several at once. Every delete asks first and always goes to
the Recycle Bin (recoverable).</p>
<p><b>Remote</b>: a copy of the repository on a server (GitHub, Gitee…) used for backup and
collaboration. No remote = the project only exists on this computer.</p>
<p><b>origin</b>: the default nickname of that remote; you rarely need to change it.</p>
<p><b>Branch</b>: parallel lines of work inside one project. The main one is usually main or
master.</p>
<p><b>Commit</b>: one saved snapshot — who changed what, and when.</p>
<p><b>Version ID (hash)</b>: the unique ID of a commit, like an ID card number.</p>
<p><b>History</b>: all commits, newest first.</p>
<p><b>Version tree</b>: the graphical form of that list — one node per commit.</p>
<p><b>Compare versions (diff)</b>: pick “Version A (older)” and “Version B (newer)” in the
Compare tab to see what changed.
<span style="color:#0a6e3c;">🟩 green = added lines</span>,
<span style="color:#a40e26;">🟥 red = removed lines</span>.
The <code>+</code> / <code>-</code> at the start mean the same. Raw git headers are hidden by
default; tick “Show raw diff” to see the original output.</p>
<p><b>Working tree</b>: the project folder as it is right now. “Uncommitted changes” = files were
edited but not saved as a commit.</p>
<p><b>Push / Pull</b>: upload local commits to the remote / download remote commits.</p>
</div>
"""

_FAQ_HTML_EN = """
<div style="font-size:13px; line-height:1.8;">
<h2>🛟 Troubleshooting</h2>
<p><b>No repositories found?</b> Try: ① pick a folder one level higher and scan again; ② open
“⚙ Scan options” and raise the depth; ③ if the previous scan was cut short, click
“⚠ Continue scanning”; ④ make sure the folder really contains a hidden .git.</p>
<p><b>It says Git is missing?</b> Click “How to install” in the app and follow the four steps
(free, about two minutes).</p>
<p><b>How do I delete something?</b> Select a repository and click the red “🗑 Delete” at the top
of the Overview tab. You get three choices: <b>delete Git history</b> (only the .git folder moves
to the Recycle Bin, your code stays), <b>delete the whole folder</b> (code and history), or
<b>remove from list only</b> (nothing is deleted). All three ask for confirmation and always go
to the Recycle Bin. For several at once use “Manage”. A progress box shows elapsed time and can
be stopped.</p>
<p><b>Will deleting freeze the window?</b> No. Files are moved in the background, so you can keep
using the app while the counter ticks.</p>
<p><b>Garbled Chinese in old commits?</b> A few old repositories stored messages in a legacy
encoding; it does not affect anything else.</p>
<p><b>Change colours or language?</b> Click “⚙ Settings” at the top right: appearance (Light /
Dark / Follow system) and language (简体中文 / 繁體中文 / English). Appearance applies at once;
the language is applied immediately as well.</p>
</div>
"""

_GUIDE_HTML = """
<div style="font-size:13px; line-height:1.8;">
<p>这台电脑上还没有安装 <b>Git 工具</b>，没有它本软件就读不到仓库信息。按下面四步装好即可（免费，约 2 分钟）：</p>
<ol>
<li>点下方的按钮，打开 Git 官网下载页；</li>
<li>点击页面里的 <b>「64-bit Git for Windows Setup」</b> 下载安装包；</li>
<li>双击下载的安装包，一路点 <b>Next（下一步）</b>，最后点 <b>Install</b>（全部保持默认就行）；</li>
<li>装完后，<b>关闭并重新打开本软件</b>，就能正常使用了。</li>
</ol>
<p style="color:#9ca3af;">提示：公司电脑若无法安装软件，请联系 IT 管理员协助。macOS 用户可在终端执行 <code>xcode-select --install</code> 或从官网下载 mac 版。</p>
</div>
"""

_GUIDE_HTML_EN = """
<div style="font-size:13px; line-height:1.8;">
<p><b>Git</b> is not installed on this computer, so the app cannot read repository information.
Four steps (free, about 2 minutes):</p>
<ol>
<li>Click the button below to open the official Git download page;</li>
<li>Download <b>“64-bit Git for Windows Setup”</b>;</li>
<li>Run the installer and keep clicking <b>Next</b>, then <b>Install</b> (defaults are fine);</li>
<li><b>Close and reopen this app</b> — it will work normally.</li>
</ol>
<p style="color:#9ca3af;">Tip: on a work computer without install rights, ask your IT admin.
macOS users can run <code>xcode-select --install</code> or download the macOS build.</p>
</div>
"""


class HelpDialog(QDialog):
    """使用说明：顶部标签分页（三步上手 / 常见名词 / 遇到问题），底部「我知道了」。"""

    TABS = (
        ("🚀 三步上手", _QUICK_HTML),
        ("📖 常见名词", _GLOSSARY_HTML),
        ("🛟 遇到问题", _FAQ_HTML),
    )

    @staticmethod
    def _tabs():
        """英文界面用英文正文；其余语言用中文正文（繁中靠字符转换，正文较长故保留原文）。"""
        if i18n.current_language() == "en":
            return (
                ("🚀 Get started", _QUICK_HTML_EN),
                ("📖 Glossary", _GLOSSARY_HTML_EN),
                ("🛟 Troubleshooting", _FAQ_HTML_EN),
            )
        return HelpDialog.TABS

    def __init__(self, parent=None, tab=0):
        super().__init__(parent)
        self.setWindowTitle("使用说明")
        self.resize(780, 660)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(10)

        tabs = self._tabs()
        self.tabs = QTabWidget()
        for title, html in tabs:
            view = QTextBrowser()
            view.setOpenExternalLinks(True)
            view.setHtml(html)
            self.tabs.addTab(view, title)
        self.tabs.setCurrentIndex(max(0, min(tab, len(tabs) - 1)))
        v.addWidget(self.tabs, 1)

        foot = QLabel(
            f"{APP_NAME} v{APP_VERSION} · " + i18n.translate(
                "本软件平时只读取信息，不会修改你的代码；"
                "只有你主动删除并确认后，才会把所选内容（.git 或整个文件夹）移入系统回收站（可还原）。"))
        foot.setObjectName("muted2")
        foot.setWordWrap(True)
        v.addWidget(foot)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close = QPushButton("我知道了")
        close.setObjectName("primary")
        close.setDefault(True)
        close.setMinimumWidth(120)
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        v.addLayout(btn_row)


class GitGuideDialog(QDialog):
    """没有检测到 Git 时的安装引导。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("安装 Git 工具教程")
        self.resize(660, 440)
        v = QVBoxLayout(self)
        view = QTextBrowser()
        view.setHtml(_GUIDE_HTML_EN if i18n.current_language() == "en" else _GUIDE_HTML)
        v.addWidget(view, 1)
        btn_row = QHBoxLayout()
        open_btn = QPushButton("🌐 打开 Git 官网下载页")
        open_btn.setObjectName("primary")
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(GIT_DOWNLOAD_URL)))
        close_btn = QPushButton("稍后再说")
        close_btn.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(close_btn)
        v.addLayout(btn_row)
