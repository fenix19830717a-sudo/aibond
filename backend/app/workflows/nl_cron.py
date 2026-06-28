"""
Natural Language Cron Expression Parser

Provides parse_nl_cron() that converts Chinese natural language time descriptions
into standard cron expressions. Supports both NL patterns and standard cron passthrough.

Reference: Hermes Agent "/cron add '0 9 * * *' '汇总AI行业新闻'" style.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# 中文数字映射
# ---------------------------------------------------------------------------
_CN_NUM = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
    "二十一": 21, "二十二": 22, "二十三": 23, "二十四": 24,
    "二十五": 25, "二十六": 26, "二十七": 27, "二十八": 28,
    "二十九": 29, "三十": 30, "三十一": 31,
}

# 星期名称映射 (cron: 0=Sun, 1=Mon, ..., 6=Sat)
_WEEKDAY_MAP = {
    "周一": 1, "星期一": 1, "礼拜一": 1,
    "周二": 2, "星期二": 2, "礼拜二": 2,
    "周三": 3, "星期三": 3, "礼拜三": 3,
    "周四": 4, "星期四": 4, "礼拜四": 4,
    "周五": 5, "星期五": 5, "礼拜五": 5,
    "周六": 6, "星期六": 6, "礼拜六": 6,
    "周日": 0, "星期天": 0, "星期日": 0, "礼拜天": 0, "礼拜日": 0,
}

# 时间段映射 (24小时制: base_hour 是偏移基数)
# 下午1点 = 12+1=13, 晚上6点 = 12+6=18, 凌晨1点 = 0+1=1
_TIME_PERIOD_MAP = {
    "凌晨": 0, "早上": 8, "上午": 9, "中午": 12,
    "下午": 12, "傍晚": 12, "晚上": 12, "深夜": 12,
}

# 标准 cron 表达式正则 (5 字段)
_CRON_PATTERN = re.compile(
    r"^("
    r"\*(\/\d+)?|"                   # wildcard, optionally with step: *, */30
    r"\d+(-\d+)?(/\d+)?"             # digit, range, step
    r")(,(\*(\/\d+)?|\d+(-\d+)?(/\d+)?))*"  # comma-separated
    r"$"
)

# ---------------------------------------------------------------------------
# 解析函数
# ---------------------------------------------------------------------------

def _parse_cn_number(text: str) -> Optional[int]:
    """将中文数字字符串转为整数，支持阿拉伯数字和中文数字。"""
    text = text.strip()
    # 尝试阿拉伯数字
    try:
        return int(text)
    except ValueError:
        pass
    # 尝试中文数字
    return _CN_NUM.get(text)


def _parse_time(text: str) -> tuple[Optional[int], Optional[int]]:
    """从时间描述中解析出 (小时, 分钟)。

    支持：
      "9点"    -> (9, 0)
      "9:30"   -> (9, 30)
      "下午3点" -> (15, 0)
      "早上9点" -> (9, 0)
      "晚上8点" -> (20, 0)
      "9点半"  -> (9, 30)
    """
    text = text.strip()

    hour = None
    minute = 0

    # 检查时间段前缀（可能在文本中间，如 "每天下午6点"）
    matched_prefix = None
    matched_base = None
    for prefix, base_hour in _TIME_PERIOD_MAP.items():
        if prefix in text:
            # 找到前缀在文本中的位置
            idx = text.find(prefix)
            if matched_prefix is None or idx < text.find(matched_prefix):
                matched_prefix = prefix
                matched_base = base_hour

    if matched_prefix is not None:
        # 取前缀之后的部分来解析小时
        idx = text.find(matched_prefix)
        rest = text[idx + len(matched_prefix):].strip()
        hour = _parse_hour_from_rest(rest, matched_base)
    else:
        # 没有时间段前缀，直接解析
        hour = _parse_hour_from_rest(text, None)

    # 解析分钟
    match = re.search(r"(\d+)[分:：](\d+)?", text)
    if match:
        minute = int(match.group(1))
        if match.group(2):
            minute = int(match.group(2))
    elif "半" in text:
        minute = 30

    return hour, minute


def _parse_hour_from_rest(rest: str, base_hour: Optional[int]) -> Optional[int]:
    """从去掉前缀后的文本中解析小时。"""
    # 尝试匹配 "9点" 样式
    match = re.search(r"(\d+|[一二三四五六七八九十]+)点", rest)
    if match:
        num = _parse_cn_number(match.group(1))
        if num is not None:
            if base_hour is not None:
                # 下午/晚上: 加上基数偏移
                if base_hour >= 12:
                    if num < 12:
                        return base_hour + num
                    else:
                        return num
                elif base_hour == 0:
                    # 凌晨
                    return num
                else:
                    return num
            return num

    # 尝试 "9:30" 样式
    match = re.search(r"(\d+)[:：]", rest)
    if match:
        hour = int(match.group(1))
        if base_hour is not None and base_hour >= 12:
            if hour < 12:
                return base_hour + hour
            else:
                return hour
        return hour

    # 纯数字
    match = re.search(r"(\d+)", rest)
    if match:
        hour = int(match.group(1))
        if base_hour is not None and base_hour >= 12:
            if hour < 12:
                return base_hour + hour
            else:
                return hour
        return hour

    return base_hour


def _parse_weekday(text: str) -> Optional[int]:
    """解析星期名称，返回 cron 星期值 (0-6)。"""
    for name, value in _WEEKDAY_MAP.items():
        if name in text:
            return value
    return None


def _parse_day_of_month(text: str) -> Optional[int]:
    """解析每月几号，返回日期值 (1-31)。"""
    match = re.search(r"(\d+)号", text)
    if match:
        return int(match.group(1))
    match = re.search(r"每月(\d+)日?", text)
    if match:
        return int(match.group(1))
    return None


def parse_nl_cron(text: str) -> dict:
    """Parse Chinese natural language time description into a cron expression.

    Args:
        text: Natural language time description, e.g. "每天早上9点" or
              a standard cron expression like "0 9 * * *".

    Returns:
        dict with keys:
            - cron: str, the standard 5-field cron expression
            - description: str, human-readable description
            - error: str (only present on failure)
    """
    text = text.strip()

    # -----------------------------------------------------------------------
    # 1. 如果是标准 cron 表达式，直接透传
    # -----------------------------------------------------------------------
    parts = text.split()
    if len(parts) == 5:
        # 验证每个字段是否为有效 cron 字段
        all_valid = True
        for part in parts:
            if not _CRON_PATTERN.match(part):
                all_valid = False
                break
        if all_valid:
            return {"cron": text, "description": _describe_cron(text)}

    # -----------------------------------------------------------------------
    # 2. 自然语言模式匹配
    # -----------------------------------------------------------------------

    # 2a. "每N分钟" 或 "每N分钟一次"
    match = re.match(r"每\s*(\d+)\s*分钟", text)
    if match:
        minutes = int(match.group(1))
        return {
            "cron": f"*/{minutes} * * * *",
            "description": f"每{minutes}分钟",
        }

    # 2b. "每小时" 或 "每小时执行"
    if re.match(r"每小时", text):
        return {"cron": "0 * * * *", "description": "每小时整点"}

    # 2c. "每N小时" 或 "每N小时一次"
    match = re.match(r"每\s*(\d+)\s*小时", text)
    if match:
        hours = int(match.group(1))
        return {
            "cron": f"0 */{hours} * * *",
            "description": f"每{hours}小时",
        }

    # 2d. "工作日每天早上X点" / "工作日上午X点"
    match = re.match(r"工作日(每天)?(早上|上午|下午|晚上|中午)?(\d+|[一二三四五六七八九十]+)点", text)
    if match:
        time_result = _parse_time(text)
        hour = time_result[0]
        if hour is not None:
            return {
                "cron": f"0 {hour} * * 1-5",
                "description": f"工作日每天{_format_hour(hour)}",
            }

    # 2e. "每周X早上Y点" / "每周Y下午Z点"
    match = re.match(r"每周\s*([一二三四五六日天1-6])\s*(早上|上午|下午|晚上|中午)?\s*(\d+|[一二三四五六七八九十]+)点", text)
    if match:
        weekday_name = match.group(1)
        if weekday_name in ("日", "天", "7"):
            weekday = 0
        elif weekday_name in ("六", "6"):
            weekday = 6
        else:
            weekday = _parse_cn_number(weekday_name) or 1

        time_result = _parse_time(text)
        hour = time_result[0]
        if hour is not None:
            return {
                "cron": f"0 {hour} * * {weekday}",
                "description": f"每周{_format_weekday(weekday)}{_format_hour(hour)}",
            }

    # 2f. "周X" 样式 (更灵活)
    match = re.match(r"周([一二三四五六日天1-6])\s*(早上|上午|下午|晚上|中午)?\s*(\d+|[一二三四五六七八九十]+)点", text)
    if match:
        weekday_name = match.group(1)
        if weekday_name in ("日", "天", "7"):
            weekday = 0
        elif weekday_name in ("六", "6"):
            weekday = 6
        else:
            weekday = _parse_cn_number(weekday_name) or 1

        time_result = _parse_time(text)
        hour = time_result[0]
        if hour is not None:
            return {
                "cron": f"0 {hour} * * {weekday}",
                "description": f"每周{_format_weekday(weekday)}{_format_hour(hour)}",
            }

    # 2g. "每月X号早上Y点" / "每月X日下午Z点"
    match = re.match(r"每月\s*(\d+)\s*号?\s*(早上|上午|下午|晚上|中午)?\s*(\d+|[一二三四五六七八九十]+)点", text)
    if match:
        day = int(match.group(1))
        time_result = _parse_time(text)
        hour = time_result[0]
        if hour is not None:
            return {
                "cron": f"0 {hour} {day} * *",
                "description": f"每月{day}号{_format_hour(hour)}",
            }

    # 2h. "每天早上X点" / "每天下午X点" / "每天晚上X点" 等
    match = re.match(r"每天\s*(早上|上午|下午|晚上|中午|凌晨)?\s*(\d+|[一二三四五六七八九十]+)点", text)
    if match:
        time_result = _parse_time(text)
        hour = time_result[0]
        if hour is not None:
            return {
                "cron": f"0 {hour} * * *",
                "description": f"每天{_format_hour(hour)}",
            }

    # 2i. "早X点" / "上午X点" / "下午X点" / "晚上X点" (默认每天)
    match = re.match(r"(早上|上午|下午|晚上|中午|凌晨)\s*(\d+|[一二三四五六七八九十]+)点", text)
    if match:
        time_result = _parse_time(text)
        hour = time_result[0]
        if hour is not None:
            return {
                "cron": f"0 {hour} * * *",
                "description": f"每天{_format_hour(hour)}",
            }

    # 2j. "X点" (默认每天)
    match = re.match(r"(\d+|[一二三四五六七八九十]+)点", text)
    if match:
        time_result = _parse_time(text)
        hour = time_result[0]
        if hour is not None:
            return {
                "cron": f"0 {hour} * * *",
                "description": f"每天{_format_hour(hour)}",
            }

    # 2k. "每周一" / "每周五" (不带具体时间，默认早上9点)
    match = re.match(r"每周\s*([一二三四五六日天1-6])$", text)
    if match:
        weekday_name = match.group(1)
        if weekday_name in ("日", "天", "7"):
            weekday = 0
        elif weekday_name in ("六", "6"):
            weekday = 6
        else:
            weekday = _parse_cn_number(weekday_name) or 1
        return {
            "cron": f"0 9 * * {weekday}",
            "description": f"每周{_format_weekday(weekday)}上午9:00",
        }

    # 2l. "工作日" (默认早上9点)
    if re.match(r"工作日", text):
        return {
            "cron": "0 9 * * 1-5",
            "description": "工作日每天上午9:00",
        }

    # 2m. "每天" (默认早上9点)
    if re.match(r"每天", text):
        return {
            "cron": "0 9 * * *",
            "description": "每天上午9:00",
        }

    # -----------------------------------------------------------------------
    # 3. 无法解析
    # -----------------------------------------------------------------------
    return {
        "error": f"无法解析时间描述: '{text}'。请使用如 '每天早上9点'、'每周五下午6点' 或标准 cron 表达式。",
        "cron": "",
        "description": "",
    }


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _format_hour(hour: int) -> str:
    """将小时格式化为可读中文描述。"""
    if hour == 0:
        return "凌晨0:00"
    elif hour < 6:
        return f"凌晨{hour}:00"
    elif hour < 9:
        return f"早上{hour}:00"
    elif hour < 12:
        return f"上午{hour}:00"
    elif hour == 12:
        return "中午12:00"
    elif hour < 18:
        return f"下午{hour}:00"
    elif hour < 20:
        return f"傍晚{hour}:00"
    elif hour < 23:
        return f"晚上{hour}:00"
    else:
        return f"深夜{hour}:00"


def _format_weekday(weekday: int) -> str:
    """将 cron 星期值格式化为中文。"""
    names = {0: "日", 1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}
    return f"周{names.get(weekday, str(weekday))}"


def _describe_cron(cron: str) -> str:
    """为 cron 表达式生成简要描述。"""
    parts = cron.split()
    if len(parts) != 5:
        return cron

    minute, hour, dom, month, dow = parts

    # 每N分钟
    if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return f"每{minute[2:]}分钟"

    # 每小时整点
    if minute == "0" and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return "每小时整点"

    # 每N小时
    if minute == "0" and hour.startswith("*/") and dom == "*" and month == "*" and dow == "*":
        return f"每{hour[2:]}小时"

    # 工作日
    if dow == "1-5" and dom == "*" and month == "*":
        return f"工作日每天{_format_hour(int(hour) if hour.isdigit() else 9)}"

    # 特定星期
    if dow.isdigit() and dom == "*" and month == "*":
        return f"每周{_format_weekday(int(dow))}{_format_hour(int(hour) if hour.isdigit() else 9)}"

    # 特定日期
    if dom.isdigit() and month == "*" and dow == "*":
        return f"每月{dom}号{_format_hour(int(hour) if hour.isdigit() else 9)}"

    # 每天
    if dom == "*" and month == "*" and dow == "*":
        return f"每天{_format_hour(int(hour) if hour.isdigit() else 9)}"

    return cron


def is_valid_cron(expression: str) -> bool:
    """Check if a string is a valid 5-field cron expression."""
    parts = expression.strip().split()
    if len(parts) != 5:
        return False
    for part in parts:
        if not _CRON_PATTERN.match(part):
            return False
    return True