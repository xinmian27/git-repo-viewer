"""styles.py —— 全局界面样式（QSS，类似网页的 CSS）。

整体为扁平风格：白色背景，各区块之间用实线分隔，不再使用圆角卡片。
提供两套主题（浅色 / 深色）与 apply_theme(app, mode)：统一样式、
调色板、中文字体，并返回实际生效的是浅色还是深色。
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette

QSS = """
* { font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif; outline: none; }
QMainWindow, QDialog, #root { background: #ffffff; }
QWidget { color: #1f2937; }
QLabel { background: transparent; }

QLabel#appTitle { font-size: 16px; font-weight: 700; color: #111827; }
QLabel#muted  { color: #6b7280; font-size: 12px; }
QLabel#muted2 { color: #9ca3af; font-size: 11px; }
QLabel#cardTitle { font-size: 14px; font-weight: 700; color: #111827; }
QLabel#bigName { font-size: 17px; font-weight: 700; color: #111827; }
QLabel#mono { font-family: Consolas, "Courier New", monospace; color: #6b7280; font-size: 11px; }

/* 区块容器：无底色无边框，仅用一条实线与下一个区块分隔 */
QFrame#card { background: transparent; border: none; border-bottom: 1px solid #e5e9f0; border-radius: 0; }
QFrame#sectionTop { background: transparent; border: none; border-top: 1px solid #e5e9f0; border-radius: 0; }
QFrame#bannerWarn { background: #fff7ed; border: none; border-bottom: 1px solid #fed7aa; border-radius: 0; }

QToolBar { background: #ffffff; border: none; border-bottom: 1px solid #e5e9f0; padding: 8px 12px; spacing: 8px; }
QFrame#header { background: #ffffff; border: none; border-bottom: 1px solid #e5e9f0; }
QLabel#repoTitle { font-size: 15px; font-weight: 700; color: #111827; }

QPushButton#primary { background: #2563eb; color: #ffffff; border: none; border-radius: 4px; padding: 8px 16px; font-weight: 600; font-size: 13px; }
QPushButton#primary:hover { background: #1d4ed8; }
QPushButton#primary:disabled { background: #a5c3fa; }
QPushButton#ghost { background: #ffffff; color: #374151; border: 1px solid #d7dce5; border-radius: 4px; padding: 7px 14px; }
QPushButton#ghost:hover { border-color: #2563eb; color: #2563eb; }
QPushButton#danger { background: #ffffff; color: #dc2626; border: 1px solid #fca5a5; border-radius: 4px; padding: 7px 14px; }
QPushButton#danger:hover { background: #fef2f2; border-color: #dc2626; }
QPushButton#dangerPrimary { background: #dc2626; color: #ffffff; border: none; border-radius: 4px; padding: 8px 16px; font-weight: 600; font-size: 13px; }
QPushButton#dangerPrimary:hover { background: #b91c1c; }
QPushButton#helpDot { background: #eef2ff; color: #4f46e5; border: none; border-radius: 9px; font-weight: 700; font-size: 11px; padding: 0; }
QPushButton#helpDot:hover { background: #e0e7ff; }
QPushButton#copyBtn { background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb; border-radius: 4px; padding: 2px 10px; font-size: 11px; }
QPushButton#copyBtn:hover { color: #2563eb; border-color: #bfdbfe; background: #eff6ff; }
QPushButton#warnBtn { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; border-radius: 4px; padding: 8px 10px; font-size: 12px; }
QPushButton#warnBtn:hover { background: #fef3c7; border-color: #f59e0b; }

/* 彩色小标签：改为方正的小色块 */
QLabel[badge="1"] { border-radius: 3px; padding: 1px 8px; font-size: 11px; font-weight: 600; }
QLabel[badgeKind="indigo"] { background: #eef2ff; color: #4f46e5; }
QLabel[badgeKind="green"]  { background: #ecfdf5; color: #047857; }
QLabel[badgeKind="amber"]  { background: #fffbeb; color: #b45309; }
QLabel[badgeKind="gray"]   { background: #f3f4f6; color: #4b5563; }
QLabel[badgeKind="red"]    { background: #fef2f2; color: #b91c1c; }
QLabel[badgeKind="blue"]   { background: #eff6ff; color: #1d4ed8; }
QLabel[badgeKind="purple"] { background: #faf5ff; color: #7e22ce; }

/* 列表：每行之间用一条浅色实线分隔 */
QListWidget { background: transparent; border: none; }
QListWidget::item { border-radius: 0; margin: 0; border-bottom: 1px solid #eef1f5; }
QListWidget::item:hover { background: #f3f6fa; }
QListWidget::item:selected { background: #e8f0fe; }

/* 仓库列表：保留圆角卡片样式 */
QListWidget#repoList::item { border-radius: 8px; margin: 2px 4px; border-bottom: none; }
QListWidget#repoList::item:hover { background: #e9edf4; }
QListWidget#repoList::item:selected { background: #dbeafe; }

/* 版本树里的版本按钮 */
QPushButton#versionBtn { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 4px; padding: 4px 12px; font-weight: 700; font-size: 13px; }
QPushButton#versionBtn:hover { background: #dbeafe; border-color: #93c5fd; }
QPushButton#versionBtn[on="1"] { background: #2563eb; color: #ffffff; border-color: #2563eb; }

/* 删除确认框里的可选操作行 */
QFrame#optionRow { background: #f8fafc; border: 1px solid #e5e9f0; border-radius: 4px; }
QFrame#optionRow:hover { background: #eff6ff; border-color: #93c5fd; }
QFrame#optionRow[danger="1"]:hover { background: #fef2f2; border-color: #fca5a5; }

QLineEdit { background: #ffffff; border: 1px solid #e0e4eb; border-radius: 4px; padding: 7px 10px; }
QLineEdit:focus { border-color: #93c5fd; }

QComboBox { background: #ffffff; border: 1px solid #d7dce5; border-radius: 4px; padding: 5px 10px; }
QComboBox:hover { border-color: #93c5fd; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #e5e9f0; selection-background-color: #e8f0fe; selection-color: #1f2937; }

QTabWidget { background: transparent; }
QTabWidget::pane { border: none; background: #ffffff; top: 0; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: #6b7280; padding: 9px 16px; margin-right: 4px; border: none; font-size: 14px; }
QTabBar::tab:selected { color: #2563eb; font-weight: 700; border-bottom: 3px solid #2563eb; }
QTabBar::tab:hover:!selected { color: #374151; }

QScrollArea { border: none; background: transparent; }
QTabWidget { background: transparent; }
/* 让滚动区的内容层保持透明，避免系统深色模式的黑底透出来 */
QScrollArea > QWidget > QWidget { background: transparent; }
QTextEdit, QTextBrowser, QPlainTextEdit { background: #ffffff; color: #1f2937; border: none; }

/* 左右分栏、文件列表/差异内容之间用一条实线分隔 */
QSplitter::handle { background: #e5e9f0; width: 1px; }

QStatusBar { background: transparent; color: #6b7280; font-size: 12px; border-top: 1px solid #e5e9f0; }
QStatusBar::item { border: none; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #d1d5db; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #9ca3af; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #d1d5db; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip { background: #111827; color: #f9fafb; border: none; padding: 6px 8px; font-size: 12px; }

/* 勾选框：显式画出来，避免跟随系统深色模式变成看不清的色块 */
QCheckBox { color: #1f2937; font-size: 12px; spacing: 6px; background: transparent; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #cbd5e1; border-radius: 3px; background: #ffffff; }
QCheckBox::indicator:hover { border-color: #2563eb; }
QCheckBox::indicator:checked { background: #2563eb; border-color: #2563eb; }
QCheckBox::indicator:disabled { background: #f3f4f6; border-color: #e5e7eb; }

/* 下拉框弹出的列表、菜单也一起调成浅色 */
QComboBox QAbstractItemView { background: #ffffff; color: #1f2937; border: 1px solid #d7dce5; selection-background-color: #eff6ff; selection-color: #1d4ed8; }
QMenu { background: #ffffff; border: 1px solid #d7dce5; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: #eff6ff; color: #1d4ed8; }
QMenu::separator { height: 1px; background: #e5e9f0; margin: 4px 8px; }

/* 设置对话框左栏 */
QListWidget#settingsNav { background: #f8fafc; border: none; border-right: 1px solid #e5e9f0; padding: 8px 6px; }
QListWidget#settingsNav::item { border: none; border-radius: 6px; padding: 9px 10px; margin: 2px 0; }
QListWidget#settingsNav::item:hover { background: #eef2f7; }
QListWidget#settingsNav::item:selected { background: #e8f0fe; color: #1d4ed8; }
/* 设置页里的"设置行"：小节名 + 标题/说明 + 右侧控件 + 细分隔线 */
QLabel#settingsSection { color: #6b7280; font-size: 12px; font-weight: 700; }
QLabel#settingsRowTitle { color: #1f2937; font-size: 13px; font-weight: 600; }
QLabel#settingsRowDesc { color: #6b7280; font-size: 12px; }
QFrame#settingsDivider { background: #edf0f5; border: none; }
"""

# 深色主题：只覆盖需要换色的选择器，追加在 QSS 后面（后写优先）
DARK_QSS = """
QMainWindow, QDialog, #root { background: #151a21; }
QWidget { color: #e6e9ef; }

QLabel#appTitle { color: #f3f4f6; }
QLabel#muted  { color: #9aa4b2; }
QLabel#muted2 { color: #7c8696; }
QLabel#cardTitle { color: #f3f4f6; }
QLabel#bigName { color: #f3f4f6; }
QLabel#mono { color: #9aa4b2; }

QFrame#card { border-bottom: 1px solid #2a3341; }
QFrame#sectionTop { border-top: 1px solid #2a3341; }
QFrame#bannerWarn { background: #3a2a12; border-bottom: 1px solid #7c5c1d; }

QToolBar { background: #151a21; border-bottom: 1px solid #2a3341; }
QFrame#header { background: #151a21; border-bottom: 1px solid #2a3341; }
QLabel#repoTitle { color: #f3f4f6; }

QPushButton#primary { background: #3b82f6; color: #ffffff; }
QPushButton#primary:hover { background: #2563eb; }
QPushButton#primary:disabled { background: #2b4a80; }
QPushButton#ghost { background: #1c232d; color: #d7dde6; border: 1px solid #39424f; }
QPushButton#ghost:hover { border-color: #3b82f6; color: #93c5fd; }
QPushButton#danger { background: #1c232d; color: #f87171; border: 1px solid #7f3230; }
QPushButton#danger:hover { background: #2a1b1b; border-color: #f87171; }
QPushButton#dangerPrimary { background: #dc2626; color: #ffffff; }
QPushButton#dangerPrimary:hover { background: #b91c1c; }
QPushButton#helpDot { background: #26304a; color: #a5b4fc; }
QPushButton#helpDot:hover { background: #303c5c; }
QPushButton#copyBtn { background: #232a36; color: #d7dde6; border: 1px solid #39424f; }
QPushButton#copyBtn:hover { color: #93c5fd; border-color: #3b82f6; background: #1e2836; }
QPushButton#warnBtn { background: #3a2a12; color: #fbbf24; border: 1px solid #7c5c1d; }
QPushButton#warnBtn:hover { background: #4a3517; border-color: #b45309; }

QLabel[badgeKind="indigo"] { background: #26304a; color: #a5b4fc; }
QLabel[badgeKind="green"]  { background: #12352a; color: #6ee7b7; }
QLabel[badgeKind="amber"]  { background: #3a2a12; color: #fcd34d; }
QLabel[badgeKind="gray"]   { background: #232a36; color: #cbd5e1; }
QLabel[badgeKind="red"]    { background: #3a1a1a; color: #fca5a5; }
QLabel[badgeKind="blue"]   { background: #1b2c46; color: #93c5fd; }
QLabel[badgeKind="purple"] { background: #2e1f3d; color: #d8b4fe; }

QListWidget::item { border-bottom: 1px solid #232b37; }
QListWidget::item:hover { background: #1e2733; }
QListWidget::item:selected { background: #1e3a5f; }
QListWidget#repoList::item:hover { background: #1e2733; }
QListWidget#repoList::item:selected { background: #1e3a5f; }

QPushButton#versionBtn { background: #1b2c46; color: #93c5fd; border: 1px solid #2f4a70; }
QPushButton#versionBtn:hover { background: #1e3a5f; border-color: #3b82f6; }
QPushButton#versionBtn[on="1"] { background: #3b82f6; color: #ffffff; border-color: #3b82f6; }

QFrame#optionRow { background: #1b222c; border: 1px solid #2a3341; }
QFrame#optionRow:hover { background: #1e2836; border-color: #3b82f6; }
QFrame#optionRow[danger="1"]:hover { background: #2a1b1b; border-color: #f87171; }

QLineEdit { background: #1b222c; color: #e6e9ef; border: 1px solid #39424f; }
QLineEdit:focus { border-color: #3b82f6; }

QComboBox { background: #1b222c; color: #e6e9ef; border: 1px solid #39424f; }
QComboBox:hover { border-color: #3b82f6; }
QComboBox QAbstractItemView { background: #1b222c; color: #e6e9ef; border: 1px solid #39424f; selection-background-color: #1e3a5f; selection-color: #e6e9ef; }

QTabWidget::pane { background: #151a21; }
QTabBar::tab { color: #9aa4b2; }
QTabBar::tab:selected { color: #60a5fa; border-bottom: 3px solid #3b82f6; }
QTabBar::tab:hover:!selected { color: #d7dde6; }

QScrollArea > QWidget > QWidget { background: transparent; }
QTextEdit, QTextBrowser, QPlainTextEdit { background: #151a21; color: #e6e9ef; }

QSplitter::handle { background: #2a3341; }

QStatusBar { color: #9aa4b2; border-top: 1px solid #2a3341; }

QScrollBar::handle:vertical { background: #39424f; }
QScrollBar::handle:vertical:hover { background: #4c5765; }
QScrollBar::handle:horizontal { background: #39424f; }

QToolTip { background: #0b0f14; color: #f3f4f6; }

QCheckBox { color: #e6e9ef; }
QCheckBox::indicator { background: #1b222c; border: 1px solid #4c5765; }
QCheckBox::indicator:hover { border-color: #3b82f6; }
QCheckBox::indicator:checked { background: #3b82f6; border-color: #3b82f6; }
QCheckBox::indicator:disabled { background: #232a36; border-color: #39424f; }

QMenu { background: #1b222c; border: 1px solid #39424f; }
QMenu::item { color: #e6e9ef; }
QMenu::item:selected { background: #1e3a5f; color: #93c5fd; }
QMenu::separator { background: #2a3341; }

QProgressDialog { background: #151a21; }
QProgressBar { background: #1b222c; border: 1px solid #39424f; border-radius: 4px; text-align: center; color: #e6e9ef; }
QProgressBar::chunk { background: #3b82f6; border-radius: 3px; }

QListWidget#settingsNav { background: #12161d; border-right: 1px solid #2a3341; }
QListWidget#settingsNav::item:hover { background: #1e2733; }
QListWidget#settingsNav::item:selected { background: #1e3a5f; color: #93c5fd; }
QLabel#settingsSection { color: #9aa4b2; }
QLabel#settingsRowTitle { color: #e6e9ef; }
QLabel#settingsRowDesc { color: #9aa4b2; }
QFrame#settingsDivider { background: #2a3341; }
"""

THEMES = (("light", "浅色"), ("dark", "深色"), ("system", "跟随系统"))


def _light_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#1f2937"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#f7f9fc"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#1f2937"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#f3f4f6"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#1f2937"))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#dc2626"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#111827"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#f9fafb"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#9ca3af"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#9ca3af"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#9ca3af"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#9ca3af"))
    return pal


def _dark_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#151a21"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#e6e9ef"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#1b222c"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#1e2733"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#e6e9ef"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#232a36"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#e6e9ef"))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#f87171"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#3b82f6"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#0b0f14"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#f3f4f6"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#7c8696"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#6b7686"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#6b7686"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#6b7686"))
    return pal


def system_is_dark(app) -> bool:
    """系统当前是不是深色模式（优先问 Qt，问不到就按调色板亮度猜）。"""
    hints = getattr(app, "styleHints", None)
    if callable(hints):
        try:
            scheme = hints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        except Exception:
            pass
    try:
        return app.palette().color(QPalette.ColorRole.Window).lightness() < 128
    except Exception:
        return False


def resolved_mode(app, mode=None) -> str:
    """把 light/dark/system 收敛成真正要用的 light 或 dark。"""
    if mode is None:
        from .. import settings as app_settings

        mode = app_settings.theme()
    mode = (mode or "system").lower()
    if mode == "system":
        return "dark" if system_is_dark(app) else "light"
    return mode if mode in ("light", "dark") else "light"


def apply_theme(app, mode=None) -> str:
    """统一外观：Fusion 风格 + 调色板 + 中文字体 + QSS；返回实际生效的 light/dark。

    为什么还要调色板：QSS 只覆盖了程序自己画的部分，勾选框、下拉弹层、
    消息框里的图标等仍由系统调色板决定。系统开了深色模式时这些地方会和
    界面割裂，所以两套主题都显式给一套配色。
    """
    from .. import i18n

    mode = resolved_mode(app, mode)
    dark = mode == "dark"
    app.setStyle("Fusion")
    app.setPalette(_dark_palette() if dark else _light_palette())
    if i18n.current_language() == "zh_TW":
        prefer = ("Microsoft JhengHei", "PingFang TC")
    else:
        prefer = ("Microsoft YaHei", "PingFang SC")
    family = prefer[0] if app.platformName() == "windows" else prefer[1]
    app.setFont(QFont(family, 10) if family else QFont(QFont().family(), 10))
    app.setStyleSheet(QSS + (DARK_QSS if dark else ""))
    return mode
