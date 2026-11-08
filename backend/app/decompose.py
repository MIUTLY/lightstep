"""Domain classification for preference records only; no task generation."""

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
