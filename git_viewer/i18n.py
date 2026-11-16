"""界面多语言支持（简体中文 / 繁體中文 / English）。

设计思路：不给每个控件逐条包一层 tr()，而是在「文字写进控件」的那一层统一翻译。
`install()` 会给 Qt 的文字 setter 打补丁，任何界面文字在落到控件之前都会先过
`translate()`；`retranslate(widget)` 再补一遍「构造函数里就带文字」的控件。这样：

* 繁體中文：走字符级简→繁转换，界面文字全覆盖，以后新加的文案也自动生效；
* English：走整串词典 `_EN` + 正则模板 `_EN_PATTERNS`，没收录的句子原样回退中文；
* 目标语言就是当前文字时原样返回，天然幂等，可以反复调用。

主界面、左侧仓库列表、三个详情页的标题/按钮/提示、设置与使用说明对话框都收录在
词典里；少数很长的说明文字（每张信息卡下面的灰色解释）暂时仍是中文，需要时往
`_EN` 里加一条即可。
"""

from __future__ import annotations

import re

LANGUAGES = [
    ("zh_CN", "简体中文"),
    ("zh_TW", "繁體中文"),
    ("en", "English"),
]
DEFAULT_LANGUAGE = "zh_CN"

_lang = DEFAULT_LANGUAGE


def current_language() -> str:
    return _lang


def language_name(code: str = None) -> str:
    code = code or _lang
    for key, name in LANGUAGES:
        if key == code:
            return name
    return code


def set_language(code: str) -> None:
    """设置当前界面语言；不认识的值回退到简体中文。"""
    global _lang
    _lang = code if any(code == k for k, _ in LANGUAGES) else DEFAULT_LANGUAGE


# --------------------------------------------------------------- 简体 -> 繁體
# 只收「一字对一字且不会误伤」的字。一字多义的（系/台/干/只/发…）交给
# `_S2T_WORDS` 按词处理。
_S2T = {
    "个": "個", "仓": "倉", "库": "庫", "这": "這", "说": "說", "动": "動",
    "删": "刪", "历": "歷", "时": "時", "间": "間", "开": "開", "关": "關",
    "设": "設", "显": "顯", "项": "項", "览": "覽", "选": "選", "择": "擇",
    "顶": "頂", "顺": "順", "录": "錄", "贴": "貼", "图": "圖", "标": "標",
    "数": "數", "据": "據", "转": "轉", "换": "換", "读": "讀", "写": "寫",
    "单": "單", "双": "雙", "击": "擊", "键": "鍵", "盘": "盤", "径": "徑",
    "缓": "緩", "载": "載", "内": "內", "长": "長", "缩": "縮", "详": "詳",
    "细": "細", "节": "節", "条": "條", "统": "統", "计": "計", "语": "語",
    "实": "實", "现": "現", "电": "電", "脑": "腦", "软": "軟", "应": "應",
    "该": "該", "让": "讓", "觉": "覺", "认": "認", "识": "識", "简": "簡",
    "体": "體", "习": "習", "惯": "慣", "帮": "幫", "处": "處", "网": "網",
    "络": "絡", "连": "連", "远": "遠", "联": "聯", "后": "後", "线": "線",
    "义": "義", "务": "務", "备": "備", "树": "樹", "术": "術", "头": "頭",
    "类": "類", "变": "變", "记": "記", "档": "檔", "户": "戶", "号": "號",
    "码": "碼", "邮": "郵", "签": "簽", "链": "鏈", "压": "壓", "频": "頻",
    "视": "視", "进": "進", "装": "裝", "费": "費", "广": "廣", "访": "訪",
    "问": "問", "赚": "賺", "钱": "錢", "银": "銀", "仅": "僅", "从": "從",
    "会": "會", "传": "傳", "伪": "偽", "确": "確", "词": "詞", "讲": "講",
    "试": "試", "验": "驗", "测": "測", "对": "對", "将": "將", "属": "屬",
    "带": "帶", "锁": "鎖", "忆": "憶", "储": "儲", "占": "佔", "优": "優",
    "势": "勢", "创": "創", "杂": "雜", "难": "難", "题": "題", "报": "報",
    "错": "錯", "误": "誤", "败": "敗", "环": "環", "还": "還", "边": "邊",
    "过": "過", "独": "獨", "获": "獲", "启": "啟", "轮": "輪", "拟": "擬",
    "围": "圍", "闭": "閉", "净": "淨", "减": "減", "冲": "衝", "决": "決",
    "况": "況", "园": "園", "坏": "壞", "坚": "堅", "场": "場", "块": "塊",
    "够": "夠", "夹": "夾", "夺": "奪", "奋": "奮", "奖": "獎", "妆": "妝",
    "妇": "婦", "妈": "媽", "娱": "娛", "婴": "嬰", "孙": "孫", "宁": "寧",
    "宝": "寶", "审": "審", "宠": "寵", "宪": "憲", "宽": "寬", "宾": "賓",
    "导": "導", "寿": "壽", "尔": "爾", "尽": "盡", "层": "層", "岁": "歲",
    "币": "幣", "师": "師", "帐": "帳", "庆": "慶", "废": "廢", "弃": "棄",
    "张": "張", "强": "強", "归": "歸", "当": "當", "彻": "徹", "征": "徵",
    "怀": "懷", "态": "態", "总": "總", "恋": "戀", "恳": "懇", "恼": "惱",
    "悦": "悅", "悬": "懸", "惊": "驚", "惧": "懼", "愤": "憤", "愿": "願",
    "战": "戰", "扑": "撲", "执": "執", "扩": "擴", "扫": "掃", "扬": "揚",
    "扰": "擾", "抚": "撫", "抛": "拋", "护": "護", "拥": "擁", "拨": "撥",
    "挂": "掛", "挤": "擠", "挥": "揮", "损": "損", "摆": "擺", "携": "攜",
    "摊": "攤", "撑": "撐", "摇": "搖", "断": "斷", "无": "無", "旧": "舊",
    "晒": "曬", "晓": "曉", "极": "極", "构": "構", "枪": "槍", "样": "樣",
    "检": "檢", "楼": "樓", "欢": "歡", "欧": "歐", "残": "殘", "汉": "漢",
    "汤": "湯", "沟": "溝", "没": "沒", "泼": "潑", "济": "濟", "浅": "淺",
    "浆": "漿", "浇": "澆", "润": "潤", "涨": "漲", "渐": "漸", "渔": "漁",
    "温": "溫", "湾": "灣", "满": "滿", "滤": "濾", "滨": "濱", "滚": "滾",
    "点": "點", "炼": "煉", "烂": "爛", "热": "熱", "爱": "愛", "爷": "爺",
    "牵": "牽", "牺": "犧", "状": "狀", "犹": "猶", "狭": "狹", "狱": "獄",
    "猎": "獵", "献": "獻", "画": "畫", "畅": "暢", "疗": "療", "疯": "瘋",
    "痒": "癢", "皱": "皺", "盗": "盜", "监": "監", "盖": "蓋", "睁": "睜",
    "瞒": "瞞", "础": "礎", "硕": "碩", "碍": "礙", "礼": "禮", "祸": "禍",
    "离": "離", "种": "種", "积": "積", "称": "稱", "稳": "穩", "穷": "窮",
    "窃": "竊", "竞": "競", "竖": "豎", "笔": "筆", "粮": "糧", "紧": "緊",
    "纠": "糾", "红": "紅", "级": "級", "纪": "紀", "纯": "純", "纳": "納",
    "纵": "縱", "纷": "紛", "纸": "紙", "练": "練", "组": "組", "织": "織",
    "终": "終", "绍": "紹", "经": "經", "结": "結", "绘": "繪", "给": "給",
    "绝": "絕", "继": "繼", "绩": "績", "维": "維", "绵": "綿", "综": "綜",
    "绿": "綠", "编": "編", "缘": "緣", "缴": "繳", "罗": "羅", "罚": "罰",
    "罢": "罷", "职": "職", "肃": "肅", "肠": "腸", "肤": "膚", "胜": "勝",
    "胁": "脅", "胶": "膠", "脉": "脈", "脸": "臉", "腊": "臘", "腾": "騰",
    "舰": "艦", "舱": "艙", "艰": "艱", "苏": "蘇", "范": "範", "荐": "薦",
    "荡": "蕩", "药": "藥", "营": "營", "萧": "蕭", "萨": "薩", "蓝": "藍",
    "蕴": "蘊", "虏": "虜", "虑": "慮", "虫": "蟲", "虽": "雖", "蚀": "蝕",
    "蚁": "蟻", "蛮": "蠻", "补": "補", "裤": "褲", "见": "見", "观": "觀",
    "规": "規", "订": "訂", "讨": "討", "训": "訓", "议": "議", "讯": "訊",
    "讳": "諱", "讶": "訝", "许": "許", "论": "論", "证": "證", "评": "評",
    "诉": "訴", "诊": "診", "译": "譯", "诗": "詩", "诚": "誠", "话": "話",
    "询": "詢", "请": "請", "诸": "諸", "课": "課", "谁": "誰", "调": "調",
    "谈": "談", "谋": "謀", "谎": "謊", "谐": "諧", "谜": "謎", "谢": "謝",
    "谨": "謹", "谱": "譜", "谷": "穀", "贝": "貝", "负": "負", "贡": "貢",
    "财": "財", "责": "責", "贤": "賢", "货": "貨", "质": "質", "贩": "販",
    "贪": "貪", "贫": "貧", "购": "購", "贮": "貯", "贯": "貫", "贱": "賤",
    "贵": "貴", "贷": "貸", "贸": "貿", "贺": "賀", "资": "資", "赋": "賦",
    "赌": "賭", "赏": "賞", "赔": "賠", "赖": "賴", "赛": "賽", "赞": "讚",
    "赠": "贈", "赢": "贏", "赵": "趙", "趋": "趨", "赶": "趕", "跃": "躍",
    "践": "踐", "踪": "蹤", "车": "車", "轨": "軌", "轻": "輕", "较": "較",
    "辅": "輔", "辆": "輛", "辈": "輩", "辉": "輝", "辑": "輯", "输": "輸",
    "辙": "轍", "辞": "辭", "辩": "辯", "辽": "遼", "达": "達", "迁": "遷",
    "迈": "邁", "运": "運", "违": "違", "迟": "遲", "适": "適", "逊": "遜",
    "递": "遞", "逻": "邏", "遗": "遺", "邻": "鄰", "郁": "鬱", "郑": "鄭",
    "释": "釋", "针": "針", "钉": "釘", "钓": "釣", "钙": "鈣", "钝": "鈍",
    "钟": "鐘", "钠": "鈉", "钢": "鋼", "钥": "鑰", "钦": "欽", "钳": "鉗",
    "钻": "鑽", "铁": "鐵", "铃": "鈴", "铅": "鉛", "铜": "銅", "铝": "鋁",
    "铭": "銘", "铺": "鋪", "销": "銷", "锅": "鍋", "锋": "鋒", "锡": "錫",
    "锤": "錘", "锦": "錦", "锯": "鋸", "锻": "鍛", "镀": "鍍", "镇": "鎮",
    "镜": "鏡", "镰": "鐮", "镶": "鑲", "门": "門", "闪": "閃", "闯": "闖",
    "闷": "悶", "闸": "閘", "闹": "鬧", "闻": "聞", "阀": "閥", "阁": "閣",
    "阅": "閱", "阔": "闊", "队": "隊", "阳": "陽", "阴": "陰", "阵": "陣",
    "阶": "階", "际": "際", "陆": "陸", "陈": "陳", "险": "險", "随": "隨",
    "隐": "隱", "雏": "雛", "雾": "霧", "灵": "靈", "静": "靜", "页": "頁",
    "须": "須", "顾": "顧", "顿": "頓", "颁": "頒", "预": "預", "领": "領",
    "颇": "頗", "颗": "顆", "颜": "顏", "额": "額", "风": "風", "飘": "飄",
    "飞": "飛", "饭": "飯", "饮": "飲", "饰": "飾", "饱": "飽", "饲": "飼",
    "饼": "餅", "馆": "館", "鱼": "魚", "鲜": "鮮", "鸟": "鳥", "鸡": "雞",
    "鸣": "鳴", "鸭": "鴨", "鹅": "鵝", "鹰": "鷹", "麦": "麥", "黄": "黃",
    "齐": "齊", "齿": "齒", "龄": "齡", "龙": "龍", "龟": "龜", "丛": "叢",
    "东": "東", "丝": "絲", "两": "兩", "严": "嚴", "丧": "喪", "临": "臨",
    "为": "為", "丽": "麗", "举": "舉", "么": "麼", "乡": "鄉", "书": "書",
    "买": "買", "乱": "亂", "争": "爭", "于": "於", "亏": "虧", "产": "產",
    "亩": "畝", "亲": "親", "价": "價", "众": "眾", "伙": "夥", "伤": "傷",
    "伦": "倫", "伟": "偉", "伞": "傘", "侧": "側", "侨": "僑", "俭": "儉",
    "债": "債", "倾": "傾", "偿": "償", "儿": "兒", "党": "黨", "兰": "蘭",
    "兴": "興", "养": "養", "兽": "獸", "冈": "岡", "册": "冊", "军": "軍",
    "农": "農", "冯": "馮", "冻": "凍", "凑": "湊", "几": "幾", "凤": "鳳",
    "凭": "憑", "凯": "凱", "凿": "鑿", "划": "劃", "刘": "劉", "则": "則",
    "刚": "剛", "别": "別", "剂": "劑", "剑": "劍", "剧": "劇", "劝": "勸",
    "办": "辦", "勋": "勳", "劳": "勞", "励": "勵", "劲": "勁", "匀": "勻",
    "区": "區", "医": "醫", "华": "華", "协": "協", "卖": "賣", "卢": "盧",
    "卫": "衛", "却": "卻", "厂": "廠", "厅": "廳", "厉": "厲", "厌": "厭",
    "厕": "廁", "厢": "廂", "厦": "廈", "县": "縣", "参": "參", "叙": "敘",
    "叠": "疊", "叹": "嘆", "叽": "嘰", "吓": "嚇", "吕": "呂", "吗": "嗎",
    "吨": "噸", "听": "聽", "吴": "吳", "呐": "吶", "呕": "嘔", "员": "員",
    "呛": "嗆", "呜": "嗚", "咏": "詠", "响": "響", "哑": "啞", "唤": "喚",
    "啸": "嘯", "喷": "噴", "嘱": "囑", "团": "團", "圆": "圓", "圣": "聖",
    "坛": "壇", "坞": "塢", "坟": "墳", "坠": "墜", "垒": "壘", "垦": "墾",
    "垫": "墊", "涂": "塗", "墙": "牆", "壮": "壯", "声": "聲", "壶": "壺",
}

# 一字多义、不能按单字替换的，先整词替换再逐字替换
_S2T_WORDS = {
    "关系": "關係",
    "联系": "聯繫",
    "仔细": "仔細",
    "里面": "裡面",
    "这里": "這裡",
    "哪里": "哪裡",
    "后台": "後臺",
    "复制": "複製",
    "恢复": "恢復",
    "复杂": "複雜",
    "重复": "重複",
    "头发": "頭髮",
    "干活": "幹活",
    "干净": "乾淨",
    "一只": "一隻",
    # 台湾常用说法（和大陆用词不同，不是简繁差异）
    "软件": "軟體",
    "硬件": "硬體",
    "网络": "網路",
    "默认": "預設",
    "屏幕": "螢幕",
    "鼠标": "滑鼠",
    "信息": "資訊",
    "文件夹": "資料夾",
    "打印": "列印",
    "视频": "影片",
    "程序": "程式",
    "缓存": "快取",
}


def to_traditional(text: str) -> str:
    for src, dst in _S2T_WORDS.items():
        if src in text:
            text = text.replace(src, dst)
    return "".join(_S2T.get(ch, ch) for ch in text)


# ------------------------------------------------------------------ English
_EN = {
    # 窗口 / 工具栏
    "Git可视化仓库": "Git Repository Viewer",
    " Git可视化仓库": " Git Repository Viewer",
    "📦 仓库列表": "📦 Repos",
    "🔗 已关联远程": "🔗 Has remote",
    "仅本机": "Local only",
    "本仓库设置": "set in this repo",
    "本工作区设置": "set in this worktree",
    "电脑通用设置": "set for this computer",
    "Git 安装时的默认设置": "Git default",
    "命令行临时设置": "temporary",
    "📖 名词小词典": "📖 Help",
    "📖 使用说明": "📖 Help",
    "⚙ 设置": "⚙ Settings",
    "设置": "Settings",
    "使用说明": "Help",
    "知道了": "OK",
    "我知道了": "Got it",
    # 左侧列表
    "📦 仓库列表": "📦 Repos",
    "仓库列表": "Repositories",
    "↕ 排序": "↕ Sort",
    "管理": "Manage",
    "完成": "Done",
    "全选": "Select all",
    "移除": "Remove",
    "删历史": "Delete history",
    "删文件夹": "Delete folder",
    "置顶": "Pin",
    "取消置顶": "Unpin",
    "没找到": "",
    "➕ 添加仓库": "➕ Add repository",
    "➕ 换个位置扫描": "➕ Scan elsewhere",
    "⏹ 停止扫描": "⏹ Stop scanning",
    "⚙ 扫描设置": "⚙ Scan options",
    "⚙ 收起扫描设置": "⚙ Hide scan options",
    "扫描深度": "Scan depth",
    "🔍 输入名字，快速筛选仓库…": "🔍 Filter repositories by name…",
    "这里还没有仓库。": "No repositories yet.",
    "这里还没有仓库。\n\n点下面的「➕ 添加仓库」，选一个放着代码项目的文件夹；\n选中后，右边就能看到它的基本信息、提交历史和版本对比。":
        "No repositories yet.\n\nClick “➕ Add repository” below and pick a folder with code;\n"
        "once it is selected, its details, history and version comparison show up on the right.",
    "按名字排序": "Sort by name",
    "按更新时间": "Sort by updated time",
    "置顶的放最前面": "Pinned first",
    "倒序": "Reverse order",
    # 三个标签页
    "基本信息": "Overview",
    "提交历史": "History",
    "版本对比": "Compare",
    "🔄 刷新": "🔄 Refresh",
    "刷新": "Refresh",
    "📂 打开所在文件夹": "📂 Open folder",
    "🗑 删除": "🗑 Delete",
    "复制路径": "Copy path",
    "复制": "Copy",
    "把上面这个路径复制到剪贴板": "Copy the path above to the clipboard",
    "重新读取这个仓库的最新信息（快捷键 F5）": "Reload this repository (shortcut F5)",
    "在文件管理器里打开这个项目所在的文件夹": "Open this project's folder in your file manager",
    "版本树 · 点节点看详情，拖空白处平移，滚轮缩放":
        "Version graph · click a node for details, drag to pan, scroll to zoom",
    "点节点看详情": "click a node for details",
    "拖空白处平移": "drag empty space to pan",
    "滚轮缩放": "scroll to zoom",
    "查一查哪次改了": "find a change",
    "复制完整版本号": "Copy full version ID",
    "位置": "Location",
    "远程仓库地址": "Remote repository",
    "分支（项目的版本线）": "Branches (version lines)",
    "提交署名（用户名 / 邮箱）": "Commit author (name / email)",
    "最近一次提交（最新的存档记录）": "Latest commit",
    "工作区状态": "Working tree status",
    "用户名": "Name",
    "邮箱": "Email",
    "当前分支": "Current branch",
    "版本详情": "Version details",
    "作者：": "Author: ",
    "时间：": "Time: ",
    "完整版本号": "Full version ID",
    "有变化的文件": "Changed files",
    "文件内容变化明细": "Line-by-line changes",
    "显示技术细节": "Show raw diff",
    "版本对比": "Compare versions",
    "⚖️ 选两个版本对比": "⚖️ Compare two versions",
    "⇅ 交换方向": "⇅ Swap",
    "对比这两个版本 →": "Compare these two →",
    "版本 A（较早）": "Version A (older)",
    "版本 B（较近）": "Version B (newer)",
    "版本 A": "Version A",
    "版本 B": "Version B",
    "（点击展开）": " (click to expand)",
    "（点击收起）": " (click to collapse)",
    # 欢迎页
    "欢迎使用 Git可视化仓库！": "Welcome to Git Repository Viewer!",
    "三步就能用起来：": "Three steps to get started:",
    "👀 没有现成的项目？用一个示例项目练手": "👀 No project yet? Try a sample project",
    "桌面": "Desktop",
    "文档": "Documents",
    "下载": "Downloads",
    "🖥 桌面": "🖥 Desktop",
    "📄 文档": "📄 Documents",
    "⬇️ 下载": "⬇️ Downloads",
    "⏳ 读取中…": "⏳ Reading…",
    "❓ 文件夹不存在": "❓ Folder missing",
    "❓ 分支未知": "❓ Branch unknown",
    "扫描位置：": "Scanning: ",
    "已扫描：": "Scanned: ",
    # 通用按钮
    "确定": "OK",
    "取消": "Cancel",
    "再想想": "Not now",
    "关闭": "Close",
    "是": "Yes",
    "否": "No",
    "稍后再说": "Later",
    "打开回收站看看": "Open Recycle Bin",
    "知道了，谢谢": "OK, thanks",
    # 设置对话框
    "通用": "General",
    "快捷键": "Shortcuts",
    "关于": "About",
    "外观": "Appearance",
    "浅色": "Light",
    "深色": "Dark",
    "跟随系统": "Follow system",
    "语言": "Language",
    "显示": "Display",
    "主题": "Theme",
    "界面语言": "Interface language",
    "界面语言已切换。": "Interface language changed.",
    "本软件平时只读取信息，不会修改你的代码；只有你主动删除并确认后，才会把所选内容（.git 或整个文件夹）移入系统回收站（可还原）。":
        "This app only reads information and never changes your code. Only when you delete "
        "something yourself — and confirm — is the selected content (.git or a whole folder) "
        "moved to the Recycle Bin (recoverable).",
    "作者：": "Author: ",
    "时间：": "Time: ",
    "技术细节": "Raw diff",
    "在版本对比里显示 git 原始输出": "Show raw git output in Compare versions",
    "「跟随系统」会跟着 Windows 的深浅色自动切换；晚上用深色不刺眼。":
        "“Follow system” tracks your Windows light/dark setting; dark is easier at night.",
    "选中后立刻生效。仓库名、提交说明、路径这些是你项目里的真实内容，不会被翻译。":
        "Applies immediately. Repository names, commit messages and paths are your own "
        "content and are never translated.",
    "默认藏起 diff --git、index 这类行，只显示改了哪几行。":
        "Hides lines like diff --git and index; only the changed lines are shown.",
    "语言（重启后生效）": "Language (takes effect after restart)",
    "界面语言改成": "Interface language set to",
    "重启软件后生效。": "Restart the app to apply.",
    "时间": "Time",
    "作者": "Author",
    "说明": "Message",
    "功能": "Action",
    "按键": "Shortcut",
    "版本": "Version",
    "「跟随系统」会跟着 Windows 的深浅色自动换；晚上用深色不刺眼。":
        "“Follow system” tracks your Windows light/dark setting; dark is easier at night.",
    "切换后界面会立刻换成所选语言；个别正在显示的状态提示要等下一次刷新才更新。":
        "The interface switches right away; a few status messages update on the next refresh.",
    "改完立刻生效，不用点确定。": "Changes apply immediately — no OK button needed.",
    "外观、语言、快捷键和版本信息": "Appearance, language, shortcuts and version info",
    "键盘快捷键": "Keyboard shortcuts",
    "刷新当前仓库": "Refresh current repository",
    "搜索仓库 / 提交": "Search repositories / commits",
    "更多操作（复制路径、置顶、重读）": "More actions (copy path, pin, reload)",
    "双击卡片": "double-click a card",
    "右键卡片": "right-click a card",
    "打开选中仓库的文件夹": "Open the selected repository's folder",
    "更多操作": "More actions",
    "关闭对话框": "Close a dialog",
    "数据放在哪": "Where data is stored",
    "软件只在这些地方记东西，删掉设置文件就等于恢复出厂设置。":
        "The app only stores data here. Deleting the settings file resets everything.",
    "设置与收藏列表": "Settings & repository list",
    "运行方式": "Built with",
    "未安装": "not installed",
    "📖 打开使用说明": "📖 Open the help",
    "🚀 三步上手": "🚀 Get started",
    "📖 常见名词": "📖 Glossary",
    "🛟 遇到问题": "🛟 Troubleshooting",
    "我知道了，谢谢": "Got it, thanks",
    # ---- 基本信息页的说明文字 ----
    "（尚未选择仓库）": "(no repository selected)",
    "重新读取这个仓库的最新信息": "Reload the latest info for this repository",
    "选择删除内容：Git 历史（.git）、整个文件夹，或仅从列表移除":
        "What to delete: Git history (.git), the whole folder, or just remove it from the list",
    "这个文件夹可能不是有效的 Git 仓库，或仓库数据正被其他程序占用。":
        "This folder may not be a valid Git repository, or its data is in use by another program.",
    "这份代码在网络上（如 GitHub、Gitee）的存放地址。没有则表示这个项目只保存在这台电脑上。":
        "Where this code lives online (GitHub, Gitee, …). If empty, the project only exists on this computer.",
    "（无）—— 这个项目只保存在这台电脑上，还没关联网络仓库":
        "(none) — this project only exists on this computer",
    "当前站在哪条版本线上，以及这个项目里一共有哪几条线。主线一般叫 main 或 master。":
        "Which line of work you are on, and how many lines this project has. The main one is usually main or master.",
    "项目现在位于这条版本线上": "The project is currently on this branch",
    "⚠ 不在任何分支上": "⚠ Not on any branch",
    "正在查看某个历史版本，没有站在分支上（一般不影响查看）":
        "Looking at an old snapshot instead of a branch (usually harmless)",
    "当前所在分支": "Current branch",
    "本地分支（版本线）": "Local branches",
    "新仓库还没有提交记录，所以暂时没有其他分支":
        "A brand new repository has no commits yet, so there are no other branches.",
    "每个胶囊就是一条版本线；带 ✓ 的是这个项目现在站着的那条。":
        "Each pill is one version line; the ✓ one is where the project stands now.",
    "以后提交代码时，历史记录里显示的作者信息。":
        "The name and email shown in history when you save (commit) changes.",
    "未设置（不影响查看；以后要提交代码时才需要设置）":
        "Not set (reading works fine; you only need this to save changes)",
    "提交 = 给项目当前状态拍的一次“存档”，记录了谁在什么时候改了什么。":
        "A commit is a snapshot of the project: who changed what, and when.",
    "这个仓库还没有任何提交记录（可能刚刚创建）":
        "This repository has no commits yet (it may have just been created)",
    "有没有改了文件但还没做“提交”（保存存档记录）。":
        "Whether you changed files without saving a commit yet.",
    "当前状态": "Status",
    "✓ 所有改动都已提交": "✓ Everything is committed",
    "提示：本软件只负责查看，不会帮你提交。想保存这些改动，请在写代码的工具里操作。":
        "Note: this app only reads. To save these changes, commit them in your editor.",
    "这个分支还没有任何提交记录": "This branch has no commits yet",
    "未设置": "Not set",
    # ---- 提交历史页 ----
    "版本记录": "Version history",
    "⭐ 最新": "⭐ Latest",
    "⭐ 最新（当前分支）": "⭐ Latest (current branch)",
    "这是项目现在所处的最新版本": "The newest version of this project",
    "复制完整版本号": "Copy full version ID",
    "想比较两个版本之间改了什么？到「版本对比」页，选好「版本 A」和「版本 B」就能看。":
        "Want to compare two versions? Open the Compare tab and pick Version A and Version B.",
    "版本树 · 从新到旧（点击版本按钮查看左侧详情）":
        "Version tree · newest first",
    "🔍 找某一次的说明、作者名或版本号…": "🔍 Search message, author or version…",
    "正在读取提交历史…": "Reading commit history…",
    "这个仓库还没有任何提交记录。等有了提交，右侧会出现版本树。":
        "No commits yet. Once you commit, the version tree appears here.",
    "只读取了最近 200 次": "only the latest 200 commits are loaded",
    "在版本树里按关键词过滤：提交说明、作者名、版本号、日期都能搜。":
        "Filter the tree by message, author, version or date.",
    "（尚未选择版本）": "(no version selected)",
    "版本名来自项目 README 的版本记录": "Version name comes from the README version list",
    "README 版本记录里没有对应的条目，这个版本名是本软件自动编排的":
        "The README has no entry for this commit, so the version name was assigned automatically",
    "标签：给某个版本起的有意义的名字": "Tag: a meaningful name given to a version",
    "☁ 已同步远程": "☁ Pushed",
    "这个版本已经上传到网络仓库了": "This version is already on the remote repository",
    # ---- 版本对比页 ----
    "顶部选两个版本，下面左边列文件、右边看具体差异。":
        "Pick two versions on top: files on the left, line-by-line changes on the right.",
    "把对比方向反过来：从“版本 B”变成“版本 A”": "Flip the direction: from B to A",
    "🟩 新增的行　🟥 删除的行": "🟩 added lines　🟥 removed lines",
    "在上面选择两个版本后，这里会显示它们之间的文件变化。":
        "Pick two versions above to see what changed between them.",
    "这两个是同一个版本，没有可对比的内容。": "Both sides are the same version — nothing to compare.",
    "正在读取文件变化列表…": "Reading the list of changed files…",
    "这两个版本的内容完全一样（没有文件变化）。":
        "These two versions are identical (no file changed).",
    "新增": "Added",
    "修改": "Modified",
    "重命名": "Renamed",
    "默认已经选好「上一次」和「最新」，下面直接显示这两个版本之间改了什么。\n"
    "想比别的版本，改上面两个下拉框即可；🟩 绿色 = 新加的行，🟥 红色 = 删掉的行。":
        "The previous and the latest version are pre-selected, so the changes show up right away.\n"
        "Pick other versions in the boxes above; 🟩 green = added, 🟥 red = removed.",
    "默认帮你把 git 的原始信息行（如 diff --git、index、---/+++）藏起来。\n"
    "只有排查问题或想看清楚文件路径时才需要勾上。":
        "Hides raw git header lines (diff --git, index, ---/+++) by default.\n"
        "Tick it only when troubleshooting or when you need the exact paths.",
    "这是一个<b>二进制文件</b>（比如图片、压缩包、音频），内容不是普通文字，所以无法逐行对比。<br><br>"
    "不过在上面的列表里仍然能看到它是“新增 / 删除”了，这已经足够了解变化。</div>":
        "This is a <b>binary file</b> (image, archive, audio…), so it cannot be compared line by line.<br><br>"
        "The list above still tells you whether it was added or deleted.</div>",
    "这个文件只是<b>改了名字或改动了文件属性</b>，内容本身没有增加或删除任何一行。<br><br>"
    "想看 git 记录的原始信息，勾选右上角的「显示技术细节」。</div>":
        "This file was only <b>renamed or its attributes changed</b> — no line was added or removed.<br><br>"
        "Tick “Show raw diff” at the top right to see the raw git output.</div>",
    # ---- 欢迎页 / 扫描相关 ----
    "三步就能用起来：\n① 点左边「➕ 添加仓库」，选一个放着代码的文件夹\n"
    "② 在左边点开任意项目，右边就能看到它的全部信息\n"
    "③ 想知道改了什么，去「提交历史」和「版本对比」看":
        "Three steps:\n① Click “➕ Add repository” on the left and pick a folder with code\n"
        "② Click any project on the left — everything shows up on the right\n"
        "③ To see what changed, open History and Compare",
    "在电脑上生成 3 个很小的示例仓库（不会动你原有的任何文件）":
        "Creates 3 tiny sample repositories (your own files are never touched)",
    "数字越大，越不容易漏掉藏在深处的项目，但扫描也更慢。一般 5 层够用。":
        "The bigger the number, the deeper it looks — slower, but less likely to miss "
        "something buried. 5 levels is usually enough.",
    "扫描该位置，把找到的新仓库加入列表": "Scan here and add any new repositories to the list",
    "选择要扫描的文件夹（可按住 Ctrl 一次多选；也可以直接选某个磁盘整盘扫描）":
        "Choose folders to scan (hold Ctrl to pick several, or pick a whole drive)",
    "选择要扫描的文件夹": "Choose folders to scan",
    "⚠ 还没有安装 Git 工具，暂时读不了仓库信息。点上面的「查看安装教程」。":
        "⚠ Git is not installed, so repository info cannot be read. Click “How to install”.",
    "⚠ 没有检测到 Git 工具 —— 没有它就无法读取仓库信息。":
        "⚠ Git was not found — without it, repository info cannot be read.",
    "查看安装教程": "How to install",
    "正在扫描中，请等它结束": "Scanning is running — please wait",
    "正在读取仓库信息…": "Reading repository info…",
    "还没安装 Git 工具，读不了信息。请点上方「查看安装教程」。":
        "Git is not installed. Click “How to install” at the top.",
    "这些位置里没有找到 Git 仓库": "No Git repositories found in those places",
    "列表空了": "The list is empty",
    "删完主动告诉小白": "Tell the user after deleting",
    "已放进回收站": "Moved to the Recycle Bin",
    "打不开回收站": "Cannot open the Recycle Bin",
    "正在删除": "Deleting",
    "删除失败": "Delete failed",
    "Git 历史（.git）": "Git history (.git)",
    "整个项目文件夹": "the whole project folder",
    "批量移除": "Remove selected",
    "批量删除 Git 历史": "Delete Git history",
    "批量删除文件夹": "Delete folders",
    "Git 历史": "Git history",
    "文件夹": "Folder",
    "正在准备…": "Preparing…",
    "批量删除（移入回收站，可还原）": "Bulk delete (moved to the Recycle Bin, restorable)",
    "请先勾选要管理的仓库": "Select some repositories first",
    "卡死了": "Frozen",
    "已用时": "Elapsed",
    "扫完": "Done",
    "把勾选的仓库固定到列表最前面": "Pin the selected repositories to the top",
    "选择删除方式：Git 历史、整个文件夹，或仅从列表移除":
        "Choose what to delete: Git history, the whole folder, or remove from list only",
    "扫描一个或多个文件夹/磁盘，把找到的新仓库加入列表":
        "Scan one or more folders or a whole drive, and add the repositories found",
    "其中第一个": "First one",
    "什么都不删，只是这些仓库不再出现在列表里；重新扫描后它们会再次出现。":
        "Nothing is deleted — they just disappear from this list and come back after a rescan.",
    "不会删除任何文件，只是这些仓库不再出现在列表里，重新扫描后它们会再次出现。":
        "No files are deleted. They only leave this list and will come back after a rescan.",
    "想比较别的两个版本？用上面的「版本 A」「版本 B」选一下就行；"
    "选好后下面会自动列出它们之间改了哪些文件、改了哪几行。":
        "Want to compare other versions? Pick them in “Version A” and “Version B” above; "
        "the changed files and lines show up below automatically.",
}

_EN_PATTERNS = [
    (re.compile(r"^共 (\d+) 个$"), r"\1 repositories"),
    (re.compile(r"^共 (\d+) 次$"), r"\1 commits"),
    (re.compile(r"^显示 (\d+) / 共 (\d+) 次$"), r"Showing \1 of \2 commits"),
    (re.compile(r"^往里找 (\d+) 层$"), r"Search \1 levels deep"),
    (re.compile(r"^已选 (\d+) 个$"), r"\1 selected"),
    (re.compile(r"^Git 工具 ✓ v(.+)$"), r"Git ✓ v\1"),
    (re.compile(r"^Git 工具未安装 ✗$"), r"Git not installed ✗"),
    (re.compile(r"^Git可视化仓库 v(.+)  ·  Git 工具 ✓ v(.+)$"),
     r"Git Repository Viewer v\1  ·  Git \2 ready"),
    (re.compile(r"^Git可视化仓库 v(.+)  ·  Git 工具未安装 ✗$"),
     r"Git Repository Viewer v\1  ·  Git not installed"),
    (re.compile(r"^要「(.+)」做什么？$"), r"What do you want to do with “\1”?"),
    (re.compile(r"^要选中的 (\d+) 个仓库做什么？$"),
     r"What do you want to do with the \1 selected repositories?"),
    (re.compile(r"^删除 (\d+) 个仓库$"), r"Delete \1 repositories"),
    (re.compile(r"^把这 (\d+) 个仓库的版本记录文件夹（\.git）逐个移入回收站：代码文件全部保留，并从列表移除。$"),
     r"Move each of these \1 .git folders to the Recycle Bin: code files stay untouched, "
     r"and they are removed from the list."),
    (re.compile(r"^把这 (\d+) 个项目文件夹（代码 \+ Git 历史）逐个移入回收站：内容较多时耗时稍长。$"),
     r"Move all \1 project folders (code + Git history) to the Recycle Bin: "
     r"large folders take a bit longer."),
    (re.compile(r"^会把这 (\d+) 个仓库的版本记录（\.git）逐个移入回收站：代码文件全部保留，可随时在回收站还原。$"),
     r"The .git folder of each of these \1 repositories will be moved to the Recycle Bin. "
     r"Code files are kept; you can restore them any time."),
    (re.compile(r"^会把这 (\d+) 个项目文件夹（代码 \+ Git 历史）逐个移入回收站：内容较多时耗时稍长，可随时在回收站还原。$"),
     r"All \1 project folders (code + Git history) will be moved to the Recycle Bin, "
     r"which may take a while for big folders. You can restore them any time."),
    # 带数字的动态句子
    (re.compile(r"^共 (\d+) 个文件有变化$"), r"\1 files changed"),
    (re.compile(r"^内容上新增 (\d+) 行、删除 (\d+) 行$"), r"+\1 / −\2 lines"),
    (re.compile(r"^新增 (\d+) 个$"), r"\1 added"),
    (re.compile(r"^修改 (\d+) 个$"), r"\1 modified"),
    (re.compile(r"^删除 (\d+) 个$"), r"\1 deleted"),
    (re.compile(r"^重命名 (\d+) 个$"), r"\1 renamed"),
    (re.compile(r"^复制 (\d+) 个$"), r"\1 copied"),
    (re.compile(r"^类型变更 (\d+) 个$"), r"\1 type-changed"),
    (re.compile(r"^冲突 (\d+) 个$"), r"\1 conflicted"),
    (re.compile(r"^(\S+) (\d+) 个$"), r"\2 \1"),
    (re.compile(r"^<span style='color:#9ca3af;'>（这条提交没有填写详细说明）</span>$"),
     "<span style='color:#9ca3af;'>(no detailed message for this commit)</span>"),
    (re.compile(r"^正在读取仓库信息…(\d+)/(\d+)$"), r"Reading repositories… \1/\2"),
    (re.compile(r"^正在读取 (\d+) 个仓库的信息…$"), r"Reading \1 repositories…"),
    (re.compile(r"^正在扫描…已检查 (\d+) 个文件夹，发现 (\d+) 个仓库$"),
     r"Scanning… \1 folders checked, \2 repositories found"),
    (re.compile(r"^✅ 添加完成：新找到 (\d+) 个仓库，列表共 (\d+) 个$"),
     r"✅ Done: \1 new repositories, \2 in the list"),
    (re.compile(r"^⏹ 扫描已停止（本次新找到 (\d+) 个仓库，列表共 (\d+) 个）$"),
     r"⏹ Scan stopped (\1 new, \2 in the list)"),
    (re.compile(r"^作者：(.+)$"), r"Author: \1"),
    (re.compile(r"^时间：(.+)$"), r"Time: \1"),
    (re.compile(r"^（原名：(.+)）$"), r"(was: \1)"),
    (re.compile(r"^已置顶选中的 (\d+) 个仓库$"), r"Pinned \1 repositories"),
    (re.compile(r"^已从列表移除 (\d+) 个仓库（文件未动）$"), r"Removed \1 repositories (files untouched)"),
    (re.compile(r"^这个项目一共保存过 (\d+) 次（提交）$"), r"\1 commits in total"),
    (re.compile(r"^⚠ 有 (\d+) 个文件的改动还没提交$"), r"⚠ \1 changed files not committed yet"),
    (re.compile(r"^读取失败：(.+)$"), r"Read failed: \1"),
    (re.compile(r"^扫描失败：(.+)$"), r"Scan failed: \1"),
    (re.compile(r"^正在把(.+)移入回收站…"), r"Moving \1 to the Recycle Bin…"),
    (re.compile(r"^正在处理第 (\d+)/(\d+) 个：(.+)$"), r"Processing \1/\2: \3"),
    (re.compile(r"^已用时 (\d+) 秒"), r"Elapsed \1 s"),
    (re.compile(r"^就绪：共 (\d+) 个仓库。$"), r"Ready: \1 repositories."),
    (re.compile(r"^Git 工具已就绪（版本 (.+)）。平时只读取信息，不会改动你的代码；"
                r"只有你主动删除 Git 历史时，才会把 \.git 文件夹移入回收站（代码不受影响）。$"),
     r"Git \1 is ready. This app only reads — it never changes your code; "
     r"only when you delete Git history yourself does it move the .git folder "
     r"to the Recycle Bin (your code is untouched)."),
    (re.compile(r"^已扫描：(.+)$"), r"Scanned: \1"),
    (re.compile(r"^✅ 添加完成：新找到 (\d+) 个仓库，列表共 (\d+) 个（检查了 (\d+) 个文件夹）。$"),
     r"✅ Done: \1 new repositories, \2 in the list (\3 folders checked)"),
    (re.compile(r"^扫描完成：没有发现新的仓库（列表共 (\d+) 个，检查了 (\d+) 个文件夹）。$"),
     r"Scan finished: no new repositories (\1 in the list, \2 folders checked)"),
    (re.compile(r"^正在添加仓库：扫描 (\d+) 个位置（往里找 (\d+) 层）….*$"),
     r"Adding repositories: scanning \1 places (\2 levels deep)…"),
    (re.compile(r"^扫描位置：(.+)$"), r"Scanning: \1"),
    (re.compile(r"^(.+)（点击展开）$"), r"\1 (click to expand)"),
    (re.compile(r"^(.+)（点击收起）$"), r"\1 (click to collapse)"),
    (re.compile(r"^⋯ 从第 (\d+) 行附近开始的一段改动 ⋯$"), r"⋯ around line \1 ⋯"),
    (re.compile(r"^界面语言已切换。$"), r"Interface language changed."),
    (re.compile(r"^已复制路径：(.+)$"), r"Path copied: \1"),
    (re.compile(r"^（刚刚）$"), r" (just now)"),
    (re.compile(r"^（(\d+) 分钟前）$"), r" (\1 min ago)"),
    (re.compile(r"^（(\d+) 小时前）$"), r" (\1 h ago)"),
    (re.compile(r"^（(\d+) 天前）$"), r" (\1 d ago)"),
    (re.compile(r"^（(\d+) 个月前）$"), r" (\1 months ago)"),
    (re.compile(r"^（(\d+) 年前）$"), r" (\1 years ago)"),
    (re.compile(r"^（这条提交没有填写详细说明）$"), r"(no detailed message for this commit)"),
]


def _to_english(text: str) -> str:
    # 「标题（点击展开）」这类拼出来的文字：前缀单独翻，后缀固定译法
    for suffix, suffix_en in (("（点击展开）", " (click to expand)"),
                              ("（点击收起）", " (click to collapse)")):
        if text.endswith(suffix):
            head = text[: -len(suffix)]
            return (_EN.get(head) or _to_english(head)) + suffix_en
    if text in _EN:
        return _EN[text]
    for pattern, repl in _EN_PATTERNS:
        if pattern.match(text):
            return pattern.sub(repl, text)
    return text


def translate(text):
    """把一段界面文字翻译成当前语言；非字符串原样返回。"""
    if not isinstance(text, str) or not text or _lang == "zh_CN":
        return text
    if _looks_like_path(text):
        # 文件路径是"事实"：翻译了就再也对不上真实的文件夹，必须原样保留
        return text
    if _lang == "zh_TW":
        return to_traditional(text)
    return _to_english(text)


_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/)")


def _looks_like_path(text: str) -> bool:
    """像 "D:\\a\\b" 或 "/home/x" 这样的字符串当路径看待，不做翻译。"""
    if "\n" in text or len(text) > 260:
        return False
    return bool(_PATH_RE.match(text))


def html(text: str) -> str:
    """富文本（QTextBrowser 里的大段 HTML）的翻译入口。"""
    if not isinstance(text, str) or not text:
        return text
    if _lang == "zh_TW":
        return to_traditional(text)
    return text


# --------------------------------------------------- 接到 Qt 的「写文字」入口上
#
# 两个必须满足的要求决定了这里的设计：
#
# 1) 切换语言必须可逆。界面是"就地改字"，一旦把「提交历史」改成 History，就再
#    也变不回中文了。所以每次写文字时把**原文**存成控件属性（_SRC），重翻时永远
#    从原文重新翻译，而不是从当前显示的文字翻译。
# 2) 数据不能翻译。仓库名、分支名、提交说明、路径、邮箱这些是"用户的事实"，翻
#    成别的字就和磁盘上的东西对不上了。这类文字用 set_raw() 写，标上 _RAW 后
#    永远原样显示，也不会被重翻。

_SRC = "i18nSrcText"
_SRC_TIP = "i18nSrcTip"
_SRC_PH = "i18nSrcPlaceholder"
_SRC_TITLE = "i18nSrcTitle"
_SRC_TABS = "i18nSrcTabs"
_RAW = "i18nRaw"

_ORIG = {}          # (类, 方法名) -> 原始方法；set_raw / retranslate 用它绕过补丁
_installed = False


def _remember(cls, name, fn):
    _ORIG[(cls, name)] = fn


def _call_orig(widget, name, *args):
    """调用没被补丁的方法；找不到就返回 False。"""
    for (cls, mname), fn in _ORIG.items():
        if mname == name and isinstance(widget, cls):
            fn(widget, *args)
            return True
    return False


def set_raw(widget, text):
    """写"数据"文字：不翻译，切换语言时也不动它。"""
    if widget is None:
        return
    try:
        widget.setProperty(_RAW, True)
    except Exception:
        pass
    if text is None:
        text = ""
    if not _call_orig(widget, "setText", text):
        widget.setText(text)


def is_raw(widget) -> bool:
    try:
        return bool(widget.property(_RAW))
    except Exception:
        return False


def _patch(cls, name, text_index, store_key=_SRC):
    """让某类控件的某个方法：先存原文，再把译文写进去。"""
    orig = getattr(cls, name, None)
    if orig is None:
        return
    _remember(cls, name, orig)

    def wrapper(*args, **kwargs):
        args = list(args)
        if len(args) > text_index and isinstance(args[text_index], str):
            self = args[0]
            try:
                if is_raw(self):
                    self.setProperty(store_key, None)
                else:
                    self.setProperty(store_key, args[text_index])
                    args[text_index] = translate(args[text_index])
            except Exception:
                pass
        return orig(*args, **kwargs)

    wrapper.__name__ = getattr(orig, "__name__", name)
    setattr(cls, name, wrapper)


def _patch_tabs():
    """标签页标题按页存原文，重翻时逐页对照。

    原文按"每页一个字符串属性"存（`_i18nTab0`、`_i18nTab1`…）：Qt 属性只支持
    字符串/数字这类值，往里塞 dict 会存不进去。
    """
    from PySide6.QtWidgets import QTabWidget

    orig_add = QTabWidget.addTab
    _remember(QTabWidget, "addTab", orig_add)

    def add_tab(self, *args):
        # 绑定方法调用：args = (widget, "标题")，标题在 args[1]
        args = list(args)
        if len(args) >= 2 and isinstance(args[1], str):
            self.setProperty(f"i18nTab{self.count()}", args[1])
            args[1] = translate(args[1])
        return orig_add(self, *args)

    add_tab.__name__ = "addTab"
    QTabWidget.addTab = add_tab

    orig_set = QTabWidget.setTabText
    _remember(QTabWidget, "setTabText", orig_set)

    def set_tab_text(self, index, text):
        self.setProperty(f"i18nTab{index}", text)
        return orig_set(self, index, translate(text))

    set_tab_text.__name__ = "setTabText"
    QTabWidget.setTabText = set_tab_text


def _patch_menu_add_action():
    """QMenu.addAction 有两个重载，单独处理。"""
    from PySide6.QtWidgets import QMenu

    orig = QMenu.addAction

    def wrapper(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], str):
            return orig(self, translate(args[0]))
        if len(args) == 2 and isinstance(args[1], str):
            return orig(self, args[0], translate(args[1]))
        return orig(self, *args, **kwargs)

    wrapper.__name__ = "addAction"
    QMenu.addAction = wrapper


def _patch_ctor(cls, positions=(0, 1, 2)):
    """让"构造时就带文字"的控件（QLabel("文字")）也过一遍翻译，并记住原文。

    Shiboken 里 `cls.__init__` 收到的参数有时从 args[0] 开始算文字，有时 args[0]
    是实例本身，所以这里不猜位置：凡是字符串参数都翻（实例永远不是 str，安全）。
    """
    orig = cls.__init__
    if getattr(orig, "_i18n_patched", False):
        return

    def wrapper(self, *args, **kwargs):
        args = list(args)
        source = None
        for i in positions:
            if i < len(args) and isinstance(args[i], str):
                if source is None:
                    source = args[i]
                args[i] = translate(args[i])
        orig(self, *args, **kwargs)
        if source is not None:
            try:
                self.setProperty(_SRC, source)
            except Exception:
                pass

    wrapper.__name__ = getattr(orig, "__name__", "__init__")
    wrapper._i18n_patched = True
    cls.__init__ = wrapper


def install() -> None:
    """在创建 QApplication 之后调用一次，给 Qt 的文字入口打补丁。"""
    global _installed
    if _installed:
        return
    _installed = True

    from PySide6.QtWidgets import (
        QCheckBox,
        QCommandLinkButton,
        QDialogButtonBox,
        QGroupBox,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressDialog,
        QPushButton,
        QRadioButton,
        QStatusBar,
        QTabWidget,
        QTextBrowser,
        QTextEdit,
        QWidget,
        QWizardPage,
    )

    for cls in (QLabel, QPushButton, QCheckBox, QRadioButton, QGroupBox, QWidget):
        _patch(cls, "setWindowTitle", 1, store_key=_SRC_TITLE)
    for cls in (QLabel, QPushButton, QCheckBox, QRadioButton, QCommandLinkButton):
        _patch(cls, "setText", 1)
        _patch(cls, "setToolTip", 1, store_key=_SRC_TIP)
    _patch(QGroupBox, "setTitle", 1, store_key=_SRC_TITLE)
    _patch(QWidget, "setToolTip", 1, store_key=_SRC_TIP)
    _patch(QLineEdit, "setPlaceholderText", 1, store_key=_SRC_PH)
    _patch(QTextEdit, "setPlaceholderText", 1, store_key=_SRC_PH)
    _patch(QStatusBar, "showMessage", 1)
    _patch(QProgressDialog, "setLabelText", 1)
    _patch(QTextBrowser, "setHtml", 1)
    _patch(QTextEdit, "setHtml", 1)
    _patch(QMessageBox, "setText", 1)
    _patch(QMessageBox, "setInformativeText", 1)
    _patch(QDialogButtonBox, "setStandardButtons", 1)
    _patch(QWizardPage, "setTitle", 1, store_key=_SRC_TITLE)
    _patch_tabs()
    _patch_list_items()
    _patch_menu_add_action()
    _patch_dialog_exec()
    _patch_item_widget()

    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QListWidgetItem,
        QMenu,
        QProgressDialog as _PD,
    )
    for cls in (QLabel, QPushButton, QCheckBox, QRadioButton, QGroupBox):
        _patch_ctor(cls, (0, 1))
    for cls in (QAction, QMenu, _PD):
        _patch_ctor(cls, (0, 1, 2))
    # 注意：QListWidgetItem 的原文由 _patch_list_items() 存进 setData，
    # 这里不能再给它套一层构造函数补丁——那会把"已经翻译过的文字"当成原文存下来，
    # 切回中文时还原不回去（设置页左栏语言不跟着变就是这个原因）。
    # 注意：QComboBox 故意不接翻译——里面的内容要么是提交记录（数据），
    # 要么是语言名（各语言用本名显示），都不该被翻译。


def _patch_list_items():
    """列表项（设置页左栏、下拉列表…）也记住原文，切语言时能重翻。

    QListWidgetItem 不是 QWidget，没法用 setProperty 存原文，改用 setData。
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem

    role = int(Qt.UserRole) + 77

    orig_set = QListWidgetItem.setText
    _remember(QListWidgetItem, "setText", orig_set)

    def set_text(self, text):
        try:
            self.setData(role, text)
        except Exception:
            pass
        return orig_set(self, translate(text))

    set_text.__name__ = "setText"
    QListWidgetItem.setText = set_text

    orig_init = QListWidgetItem.__init__
    if not getattr(orig_init, "_i18n_patched", False):

        def wrapper(self, *args, **kwargs):
            args = list(args)
            source = None
            for i in (0, 1):
                if i < len(args) and isinstance(args[i], str):
                    if source is None:
                        source = args[i]
                    args[i] = translate(args[i])
            orig_init(self, *args, **kwargs)
            if source is not None:
                try:
                    self.setData(role, source)
                except Exception:
                    pass

        wrapper.__name__ = "__init__"
        wrapper._i18n_patched = True
        QListWidgetItem.__init__ = wrapper


def _patch_dialog_exec():
    """对话框弹出前把它自己的文字翻一遍（构造函数里写的文字走这条路）。"""
    from PySide6.QtWidgets import QDialog

    orig = QDialog.exec

    def wrapper(self):
        retranslate(self)
        return orig(self)

    wrapper.__name__ = "exec"
    QDialog.exec = wrapper


def _patch_item_widget():
    """列表里塞进去的自定义行（仓库卡片、版本行）建好就翻一遍。"""
    from PySide6.QtWidgets import QListWidget

    orig = QListWidget.setItemWidget

    def wrapper(self, item, widget):
        retranslate(widget)
        return orig(self, item, widget)

    wrapper.__name__ = "setItemWidget"
    QListWidget.setItemWidget = wrapper


def retranslate(root) -> None:
    """按存下的原文，把整棵控件树的文字重新翻成当前语言（可来回切）。"""
    if root is None:
        return

    from PySide6.QtWidgets import (
        QCheckBox,
        QCommandLinkButton,
        QGroupBox,
        QLabel,
        QLineEdit,
        QListWidget,
        QPushButton,
        QRadioButton,
        QTabWidget,
        QWidget,
    )

    text_types = (QLabel, QPushButton, QCheckBox, QRadioButton, QCommandLinkButton)

    def one(w):
        if is_raw(w):
            return
        try:
            if isinstance(w, text_types):
                src = w.property(_SRC)
                if src:
                    _call_orig(w, "setText", translate(src))
            elif isinstance(w, QLineEdit):
                src = w.property(_SRC_PH)
                if src:
                    _call_orig(w, "setPlaceholderText", translate(src))
            elif isinstance(w, QGroupBox):
                src = w.property(_SRC_TITLE)
                if src:
                    _call_orig(w, "setTitle", translate(src))
            elif isinstance(w, QTabWidget):
                for index in range(w.count()):
                    src = w.property(f"i18nTab{index}")
                    if src:
                        _call_orig(w, "setTabText", index, translate(src))
            elif isinstance(w, QListWidget):
                from PySide6.QtCore import Qt as _Qt

                role = int(_Qt.UserRole) + 77
                for index in range(w.count()):
                    item = w.item(index)
                    if item is None or not item.text():
                        continue
                    src = item.data(role)
                    if src:
                        # 必须绕过补丁直接写，否则补丁会把"译文"当成新原文存下来，
                        # 切回中文时就再也翻不回去了（设置页左栏就是这个问题）。
                        if not _call_orig(item, "setText", translate(src)):
                            item.setText(translate(src))
            tip = w.property(_SRC_TIP)
            if tip:
                _call_orig(w, "setToolTip", translate(tip))
            title = w.property(_SRC_TITLE)
            if title and w.windowTitle():
                _call_orig(w, "setWindowTitle", translate(title))
        except RuntimeError:
            return  # 控件已销毁（切语言的瞬间正好关掉了对话框）

    one(root)
    if isinstance(root, QWidget):
        for w in root.findChildren(QWidget):
            one(w)
