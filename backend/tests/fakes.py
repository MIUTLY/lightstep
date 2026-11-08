"""Historical deterministic fixtures. Test injection only; not a runtime provider."""
# 情绪关键词（两段式情绪提示的"第一段"：先识别，再决定语气）
EMOTION_KEYWORDS = {
    "焦虑": ["焦虑", "紧张", "慌", "害怕", "担心", "压力", "来不及", "完蛋", "崩溃", "急"],
    "低落": ["低落", "难过", "伤心", "累", "没劲", "不想动", "烦", "丧", "无力", "提不起劲"],
    "亢奋": ["开心", "兴奋", "激动", "冲", "有劲", "状态好", "能量", "嗨"],
}


def detect_emotion(text: str) -> str:
    for emotion, words in EMOTION_KEYWORDS.items():
        for w in words:
            if w in text:
                return emotion
    return "正常"


# 领域识别关键词（用于摩擦地图按领域沉淀"哪里容易卡"）
_DOMAIN_RULES = [
    ("writing", ["写", "作文", "论文", "报告", "总结", "文案", "日记", "文章", "ppt", "PPT", "简历"]),
    ("vocab", ["单词", "背", "词汇", "背诵", "记", "英语", "文言文", "古诗"]),
    ("reading", ["读", "看书", "阅读", "刷题", "题目", "书", "章节", "文献", "论文"]),
    ("coding", ["代码", "编程", "bug", "程序", "调试", "函数", "算法", "项目", "开发", "python", "Python"]),
    ("exercise", ["运动", "跑步", "健身", "锻炼", "瑜伽", "拉伸", "跳"]),
    ("chores", ["收拾", "打扫", "整理", "洗碗", "洗衣", "倒垃圾", "房间", "清洁"]),
]


def domain_of(text: str) -> str:
    """粗判任务属于哪个领域（摩擦地图的分组维度）。"""
    for domain, words in _DOMAIN_RULES:
        for w in words:
            if w in text:
                return domain
    return "generic"


# 领域预设拆解：每个领域给出 细(fine) / 中(normal) / 粗(coarse) 三档
_PRESETS = {
    "writing": {
        "fine": [
            "打开文档，写下标题",
            "写第一句话（不用想好不好）",
            "再写两句话",
            "停一下，回头读一遍",
            "把不顺的地方改一句",
        ],
        "normal": [
            "打开文档，把标题写出来",
            "写三句话，先不管质量",
            "通读一遍，改一处不顺的地方",
        ],
        "coarse": [
            "打开文档，把标题写出来",
            "写三句话，整理成一段",
        ],
    },
    "vocab": {
        "fine": [
            "打开单词本，翻到今天的页",
            "读第一个词，心里默读三遍",
            "遮住中文，回想它什么意思",
            "再过一个词",
            "把卡住的词标一下",
        ],
        "normal": [
            "打开单词本",
            "过 5 个单词，遮住中文回忆",
            "把记不住的标出来",
        ],
        "coarse": [
            "过 10 个单词",
            "标记记不住的那几个",
        ],
    },
    "reading": {
        "fine": [
            "把书打开，翻到该读的位置",
            "读一小段",
            "再读一小段",
            "用一句话记下这段在讲什么",
        ],
        "normal": [
            "翻开书，读 5 页",
            "读完用一句话写下讲了什么",
        ],
        "coarse": [
            "读一个章节",
            "写一句小结",
        ],
    },
    "coding": {
        "fine": [
            "打开编辑器，定位到要改的文件",
            "看清楚这一处现在在做什么",
            "写最小的一处改动",
            "运行一下，看有没有报错",
        ],
        "normal": [
            "定位到要改的地方",
            "写最小可运行的改动",
            "跑一遍，处理第一个报错",
        ],
        "coarse": [
            "实现这一个功能点",
            "跑通并修掉报错",
        ],
    },
    "exercise": {
        "fine": [
            "换上衣服/鞋子",
            "热身 1 分钟",
            "动 5 分钟",
            "再动 5 分钟",
        ],
        "normal": [
            "热身一下",
            "动 10 分钟",
        ],
        "coarse": [
            "动 20 分钟",
        ],
    },
    "chores": {
        "fine": [
            "走到目标区域",
            "收拾一样东西",
            "再收拾一样",
            "把这两样归位",
        ],
        "normal": [
            "收拾一个桌面",
            "把垃圾丢掉",
        ],
        "coarse": [
            "收拾一个房间",
        ],
    },
}


def _generic_preset(title: str) -> dict:
    """无预设领域时的通用拆解。"""
    return {
        "fine": [
            f"先把「{title}」相关的材料打开/摊开",
            "只做第一个最小动作",
            "再做一个最小动作",
            "停下来，确认自己没走神",
        ],
        "normal": [
            f"把「{title}」的第一步做出来",
            "接着做下一步",
            "做一小步，然后停下",
        ],
        "coarse": [
            f"把「{title}」开个头",
            "推进到能看见一点点成果",
        ],
    }


def decompose(title: str) -> dict:
    """把任务拆成 细/中/粗 三档步骤列表，返回 {fine: [...], normal: [...], coarse: [...]}。"""
    domain = domain_of(title)
    preset = _PRESETS.get(domain)
    if preset is None:
        preset = _generic_preset(title)
    return {
        "fine": list(preset["fine"]),
        "normal": list(preset["normal"]),
        "coarse": list(preset["coarse"]),
    }


def derive_levels(normal: int) -> dict:
    """由中档步骤数反推三档步骤数（用于非预设场景）。"""
    return {
        "fine": normal + 1,
        "normal": normal,
        "coarse": max(1, normal - 1),
    }


def decompose_forest(title: str) -> dict:
    """离线时也生成完整父子关系；每次建任务生成一次，切换时不再改写。"""
    import re

    def middle(text, *leaves):
        return {"text": text, "children": [{"text": leaf} for leaf in leaves]}

    def root(*children):
        return {"text": "；然后".join(child["text"] for child in children), "children": list(children)}

    domain = domain_of(title)
    if domain == "writing":
        trees = [root(middle("打开文档，把标题写出来", "打开要写的文档", "在文档中写下标题"),
                      middle("写三句话，先不管质量", "写第一句话，先不管质量", "写第二句话，先不管质量", "写第三句话，先不管质量")),
                 root(middle("通读一遍，改一处不顺的地方", "通读刚写下的三句话", "把其中一处不顺的地方改好"))]
    elif domain == "vocab":
        match = re.search(r"([0-9]+)\s*个?\s*(?:单词|词汇)", title)
        digits = (match.group(1).lstrip("0") or "0") if match else "5"
        count = 100 if len(digits) > 3 else int(digits)
        # 大范围目标的离线启动段明确标注区间，不伪称已覆盖整个长期目标。
        count = max(1, min(count, 100))
        trees = [root(middle("打开单词本", "打开单词本，定位到这次要学的词表"))]
        for first in range(1, count + 1, 10):
            chunks = []
            for begin in range(first, min(first + 10, count + 1), 5):
                end = min(begin + 4, count)
                text = "过 5 个单词，遮住中文回忆" if begin == 1 and end == 5 else f"学习第{begin}到第{end}个单词，遮住中文回忆"
                chunks.append(middle(text, *(f"读第{i}个单词，并遮住中文回忆含义" for i in range(begin, end + 1))))
            trees.append(root(*chunks))
        trees.append(root(middle("把记不住的标出来", "标记这次学习中没能回忆出的词")))
    elif domain == "reading":
        trees = [root(middle("翻开书，读 5 页", "把书翻到这次要读的位置", *(f"读这次的第{i}页" for i in range(1, 6)))),
                 root(middle("读完用一句话写下讲了什么", "回想刚读内容的主题", "用一句话写下这个主题"))]
    elif domain == "coding":
        trees = [root(middle("定位到要改的地方", "打开要修改的文件", "定位并看清当前代码的行为"),
                      middle("写最小可运行的改动", "写下这处改动", "保存修改过的文件")),
                 root(middle("跑一遍，处理第一个报错", "运行修改后的程序", "若有报错，处理第一个报错；无报错则确认结果"))]
    elif domain == "exercise":
        trees = [root(middle("热身一下", "站到适合活动的位置", "缓慢活动肩膀和脚踝")),
                 root(middle("动 10 分钟", "完成这次运动的前5分钟", "完成这次运动的后5分钟"))]
    elif domain == "chores":
        trees = [root(middle("收拾一个桌面", "把桌面物品按用途分开", "把桌面上要保留的物品放回原位")),
                 root(middle("把垃圾丢掉", "收集刚才分出的垃圾", "把收集的垃圾放入垃圾桶"))]
    else:
        display_title = title if len(title) <= 160 else title[:157] + "…"
        trees = [root(middle(f"把「{display_title}」的第一步做出来", f"打开或摊开「{display_title}」需要的材料", "完成眼前第一个可动手的动作")),
                 root(middle("做一小步，然后停下", "检查刚才这一步的结果"))]
    return {"trees": trees}


class MockLLM:
    def detect_emotion(self, text):
        return detect_emotion(text)

    def decompose(self, title):
        return decompose_forest(title)

    def reply(self, situation, text):
        return ""
