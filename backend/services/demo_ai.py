"""Explicit local demo implementations.

These are NOT presented as real AI results. They either generate clearly marked
sample structures or apply transparent local heuristics to the user's own text
so the entire product can be explored without API keys.
"""

from __future__ import annotations

import re
from collections import Counter

DEMO_WARNING = "当前为演示模式：未调用外部 AI 模型，结果由本地示例或规则生成，请勿直接作为正式判断依据。"

SUBJECT_KEYWORDS = {
    "数学": ["函数", "方程", "几何", "三角", "概率", "分数", "整数", "不等式", "导数", "向量"],
    "英语": ["english", "grammar", "tense", "sentence", "word", "语法", "时态", "单词", "作文"],
    "语文": ["作文", "古诗", "文言文", "阅读", "修辞", "议论文", "记叙文"],
    "物理": ["力学", "电路", "速度", "加速度", "浮力", "压强", "电功率", "光学"],
    "化学": ["化学式", "方程式", "元素", "溶液", "酸碱", "氧化", "燃烧"],
    "生物": ["细胞", "遗传", "光合作用", "生态", "呼吸作用"],
    "历史": ["朝代", "战争", "历史", "改革", "革命"],
    "地理": ["气候", "地形", "经纬", "洋流", "人口"],
    "政治": ["宪法", "法治", "道德", "经济", "政治"],
}

MISSPELLINGS = {
    "recieve": "receive",
    "becuase": "because",
    "tommorow": "tomorrow",
    "enviroment": "environment",
    "definately": "definitely",
    "seperate": "separate",
    "adress": "address",
    "beleive": "believe",
    "freind": "friend",
    "grammer": "grammar",
}


def _subject_from_text(text: str, subject_hint: str | None = None) -> str:
    if subject_hint and subject_hint.strip():
        return subject_hint.strip()[:30]
    haystack = (text or "").lower()
    best = ("综合", 0)
    for subject, words in SUBJECT_KEYWORDS.items():
        score = sum(1 for word in words if word.lower() in haystack)
        if score > best[1]:
            best = (subject, score)
    return best[0]


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text))


def _apply_replacements(text: str, replacements: list[tuple[str, str]]) -> str:
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def _level(percentage: float) -> str:
    if percentage >= 90:
        return "优秀"
    if percentage >= 75:
        return "良好"
    if percentage >= 60:
        return "及格"
    return "待提升"


def recognize_tasks_demo(payload: dict) -> dict:
    subject = payload.get("subject_hint") or "数学"
    due = payload.get("due_date") or ""
    return {
        "image_summary": "演示模式不会读取或识别图片内容，以下是根据学科提示生成的示例任务结构。",
        "tasks": [
            {
                "title": f"{subject}练习（演示数据，请修改）",
                "subject": subject,
                "description": "这是一条演示任务。请在添加前改为图片中真实的作业内容和要求。",
                "question_count": 10,
                "difficulty": 3,
                "estimated_minutes": 40,
                "difficulty_reason": "演示模板固定使用中等难度；真实模式会依据题目数量、题型和内容判断。",
                "confidence": 0.0,
                "due_date": due or None,
            }
        ],
        "warnings": [
            DEMO_WARNING,
            "如需真实识别图片中的作业，请在 .env 中配置 Qwen 视觉模型 API Key。",
        ],
        "demo": True,
    }


def recognize_note_demo(payload: dict) -> dict:
    title_hint = (payload.get("title_hint") or "").strip()
    title = title_hint or "二次函数基础（演示笔记）"
    markdown = """> ⚠️ **演示模式说明**
>
> 当前没有调用视觉模型，**上传的图片并未被识别**。以下内容是用于体验 Markdown 编辑、KaTeX 公式、笔记纠错与知识图谱功能的示例笔记，请勿当作真实学习材料。

# 二次函数基础（演示）

## 一般式

二次函数的一般式为：

$$y = ax^2 + bx + c \\quad (a \\ne 0)$$

其中 $a$、$b$、$c$ 为常数，且 $a \\ne 0$。

## 顶点与对称轴

顶点横坐标：

$$x = -\\frac{b}{2a}$$

对称轴为直线 $x = -\\frac{b}{2a}$。

- 当 $a > 0$ 时，抛物线开口向上；
- 当 $a < 0$ 时，抛物线开口向下。

## 与坐标轴的交点

令 $x = 0$，得到与 $y$ 轴交点 $(0, c)$。

判别式：

$$\\Delta = b^2 - 4ac$$

当 $\\Delta > 0$ 时，抛物线与 $x$ 轴有两个不同交点。

> 复习提示：待补充配方法推导过程（TODO）。
"""
    return {
        "title": title,
        "subject": "数学",
        "markdown": markdown,
        "confidence": 0.0,
        "warnings": [
            DEMO_WARNING,
            "演示模式未读取图片；保存前请用 OCR 或手动输入替换示例内容。",
        ],
        "demo": True,
    }


def review_essay_demo(payload: dict) -> dict:
    text = (payload.get("text") or "").strip()
    has_image = bool(payload.get("image_url"))
    warnings = [DEMO_WARNING, "当前批改仅覆盖少量常见错误，不是完整的人工或模型批改。"]
    if not text:
        return {
            "recognized_text": "（演示模式没有读取图片文字，请粘贴作文文本或配置视觉模型）",
            "overall": {
                "score": 0,
                "level": "无法评分",
                "summary": "演示模式无法识别作文图片，且没有收到文字内容。请粘贴作文文本，或配置 Qwen 视觉模型后重试。",
            },
            "corrected_text": "",
            "corrections": [],
            "structure": {"strengths": [], "improvements": ["补充作文文字后再进行批改"]},
            "word_usage": {"strengths": [], "improvements": []},
            "next_steps": ["粘贴作文文本，或配置视觉模型 API"],
            "word_count": 0,
            "warnings": warnings,
            "demo": True,
        }

    corrections = []
    corrected = text
    for wrong, right in MISSPELLINGS.items():
        if re.search(rf"\b{re.escape(wrong)}\b", corrected, re.IGNORECASE):
            corrected = re.sub(rf"\b{re.escape(wrong)}\b", right, corrected, flags=re.IGNORECASE)
            corrections.append(
                {
                    "category": "拼写",
                    "original": wrong,
                    "suggestion": right,
                    "explanation": f"“{wrong}”是常见拼写错误，正确拼写为“{right}”。",
                    "certainty": "certain",
                }
            )

    grammar_rules = [
        (r"\bI am agree\b", "I agree", "agree 本身是动词，不需要 be 动词。", "语法"),
        (r"\bmore better\b", "better", "better 已经是比较级，不再加 more。", "语法"),
        (r"\bdidn't went\b", "didn't go", "didn't 后应使用动词原形。", "时态"),
        (r"\bhe go\b", "he goes", "一般现在时第三人称单数需要给动词加 -s。", "语法"),
        (r"\bshe go\b", "she goes", "一般现在时第三人称单数需要给动词加 -s。", "语法"),
        (r"\byesterday I go\b", "yesterday I went", "yesterday 表示过去，动词应使用过去式。", "时态"),
    ]
    for pattern, replacement, explanation, category in grammar_rules:
        match = re.search(pattern, corrected, re.IGNORECASE)
        if match:
            original = match.group(0)
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
            corrections.append(
                {
                    "category": category,
                    "original": original,
                    "suggestion": replacement,
                    "explanation": explanation,
                    "certainty": "certain",
                }
            )

    standalone_i = re.findall(r"(?<![\w'])i(?![\w'])", corrected)
    if standalone_i:
        corrected = re.sub(r"(?<![\w'])i(?![\w'])", "I", corrected)
        corrections.append(
            {
                "category": "拼写",
                "original": "小写 i",
                "suggestion": "I",
                "explanation": "英语中第一人称代词 I 必须大写。",
                "certainty": "certain",
            }
        )

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", corrected) if part.strip()]
    for sentence in sentences:
        if len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence)) > 28:
            corrections.append(
                {
                    "category": "句式",
                    "original": sentence[:90] + ("…" if len(sentence) > 90 else ""),
                    "suggestion": "考虑拆成两个较短的句子，并明确连接关系。",
                    "explanation": "句子超过约 28 个单词，信息密度较高，拆分后更易读。",
                    "certainty": "review",
                }
            )
            break

    if corrected and not corrected[0].isupper():
        corrections.append(
            {
                "category": "拼写",
                "original": corrected[:30],
                "suggestion": corrected[:1].upper() + corrected[1:31],
                "explanation": "句子开头字母应大写。",
                "certainty": "certain",
            }
        )
        corrected = corrected[0].upper() + corrected[1:]

    if corrected and corrected[-1] not in ".!?":
        corrections.append(
            {
                "category": "语法",
                "original": corrected[-30:],
                "suggestion": corrected[-30:] + ".",
                "explanation": "完整句子结尾应有句末标点。",
                "certainty": "certain",
            }
        )
        corrected += "."

    paragraphs = [part for part in re.split(r"\n\s*\n", text) if part.strip()]
    strengths = []
    improvements = []
    if len(paragraphs) >= 2:
        strengths.append("使用了分段结构，层次相对清楚。")
    else:
        improvements.append("尝试按“开头—主体—结尾”分至少两段，每段表达一个中心。")
    if len(sentences) >= 3:
        strengths.append("句子数量适中，具备基本展开。")
    if _word_count(text) < 60:
        improvements.append("篇幅较短，可补充一个具体例子或细节来支撑观点。")

    certain_count = sum(1 for item in corrections if item["certainty"] == "certain")
    review_count = len(corrections) - certain_count
    score = max(55, min(92, 88 - certain_count * 4 - review_count))
    summary = (
        f"本地启发式预检发现 {certain_count} 处较明确的格式/语法问题和 {review_count} 处可进一步优化的建议。"
        "演示模式不进行完整人工批改，请重点参考修改原因并自行判断。"
    )
    return {
        "recognized_text": text,
        "overall": {"score": score, "level": _level(score), "summary": summary},
        "corrected_text": corrected,
        "corrections": corrections,
        "structure": {"strengths": strengths, "improvements": improvements},
        "word_usage": {
            "strengths": [],
            "improvements": ["演示模式不评估词汇丰富度；可尝试用更准确的动词替换重复表达。"],
        },
        "next_steps": [
            "挑出本次修改中的 2 个错误，写进错题/积累本并造句。",
            "朗读修改后的段落，检查句子是否通顺。",
        ],
        "word_count": _word_count(text),
        "warnings": warnings,
        "demo": True,
    }


def polish_demo(payload: dict) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        return {
            "meaning_notes": "",
            "simple": {"text": "", "explanation": "没有收到文本"},
            "natural": {"text": "", "explanation": "没有收到文本"},
            "advanced": {"text": "", "explanation": "没有收到文本"},
            "warnings": [DEMO_WARNING],
            "demo": True,
        }
    simple = text.strip()
    if simple and simple[0].islower():
        simple = simple[0].upper() + simple[1:]
    if simple and simple[-1] not in ".!?":
        simple += "."

    natural_rules = [
        (r"\bvery good\b", "excellent"),
        (r"\ba lot of\b", "many"),
        (r"\bI think\b", "In my opinion"),
        (r"\bget\b", "receive"),
    ]
    advanced_rules = [
        (r"\bvery important\b", "extremely important"),
        (r"\bbig\b", "significant"),
        (r"\bhelp\b", "be helpful"),
        (r"\bIn my opinion\b", "From my perspective"),
    ]
    natural = _apply_replacements(simple, natural_rules)
    advanced = _apply_replacements(natural, advanced_rules)
    return {
        "meaning_notes": (
            "演示模式只做常见短语替换，可能无法准确理解上下文；三个版本均保留了原文的主要意思。"
        ),
        "simple": {
            "text": simple,
            "explanation": "保留原句结构与词汇，只修正开头大写和句末标点。",
        },
        "natural": {
            "text": natural,
            "explanation": "替换少量常见表达，使语气更自然；未改变事实信息。",
        },
        "advanced": {
            "text": advanced,
            "explanation": "对个别词作小幅升级，仍保持中学阶段可理解、可使用的范围。",
        },
        "warnings": [
            DEMO_WARNING,
            "请确认替换词是否贴合上下文；不要为了“高级”而使用不熟悉的词。",
        ],
        "demo": True,
    }


def analyze_sentence_demo(payload: dict) -> dict:
    sentence = (payload.get("sentence") or "").strip()
    if not sentence:
        return {
            "original": "",
            "main_clause": "",
            "clauses": [],
            "components": {
                "subject": "",
                "predicate": "",
                "object": None,
                "attributes": [],
                "adverbials": [],
            },
            "structure_summary": "没有收到句子。",
            "key_points": [],
            "translation": "",
            "caution": DEMO_WARNING,
            "warnings": [DEMO_WARNING],
            "demo": True,
        }

    clause_split = re.split(
        r"(?<=,)\s+|\s+(?=(?:which|that|who|whom|whose|because|although|though|when|while|if|unless|since|after|before|where)\b)",
        sentence,
    )
    clauses = []
    for index, chunk in enumerate([part.strip() for part in clause_split if part.strip()]):
        lower = chunk.lower()
        if index == 0:
            clause_type = "主句"
            function = "句子的核心陈述"
        elif any(lower.startswith(word) for word in ("which", "that", "who", "whom", "whose")):
            clause_type = "定语从句"
            function = "修饰前面的名词，补充信息（启发式判断）"
        elif any(
            lower.startswith(word)
            for word in ("because", "although", "though", "when", "while", "if", "unless", "since", "after", "before", "where")
        ):
            clause_type = "状语从句"
            function = "提供原因、时间、条件或让步等状语信息"
        else:
            clause_type = "并列句或其他分句"
            function = "与主句构成并列或补充关系（需人工确认）"
        clauses.append({"type": clause_type, "text": chunk, "function": function})

    verbs = re.findall(
        r"\b(?:is|are|was|were|am|be|been|have|has|had|do|does|did|can|could|will|would|should|may|might|must|[a-zA-Z]+(?:ed|ing|s))\b",
        sentence,
        re.IGNORECASE,
    )
    predicate = verbs[0] if verbs else ""
    subject = clauses[0]["text"].split(" ")[0] if clauses else ""
    return {
        "original": sentence,
        "main_clause": clauses[0]["text"] if clauses else sentence,
        "clauses": clauses,
        "components": {
            "subject": subject,
            "predicate": predicate,
            "object": None,
            "attributes": [
                "演示模式未进行句法树分析；请结合从句类型人工确认定语和修饰对象。"
            ],
            "adverbials": [],
        },
        "structure_summary": (
            f"本地规则将句子切分为 {len(clauses)} 个部分，首段按主句展示。"
            "这不是完整的句法分析器，主谓宾和从句边界需要结合语境核对。"
        ),
        "key_points": [
            "先找主句的谓语，再判断从句由哪个连接词引导。",
            "注意代词和关系词分别指代什么。",
        ],
        "translation": "",
        "caution": (
            "演示模式的句子切分为启发式结果，可能出现错误；请以课堂语法分析和老师讲解为准。"
        ),
        "warnings": [DEMO_WARNING],
        "demo": True,
    }


def check_grammar_demo(payload: dict) -> dict:
    sentence = (payload.get("sentence") or "").strip()
    issues = []
    corrected = sentence
    if not sentence:
        return {
            "original": "",
            "corrected_text": "",
            "is_correct": False,
            "issues": [],
            "overall": "没有收到句子。",
            "warnings": [DEMO_WARNING],
            "demo": True,
        }

    rules = [
        (r"\bI is\b", "I am", "be 动词与主语 I 搭配时应使用 am。", "语法"),
        (r"\b(he|she|it) go\b", r"\1 goes", "一般现在时第三人称单数需在动词后加 -s。", "语法"),
        (r"\b(he|she|it) have\b", r"\1 has", "第三人称单数主语应使用 has。", "语法"),
        (r"\b(they|we|I) goes\b", r"\1 go", "复数或第一人称主语使用动词原形。", "语法"),
        (r"\bmore better\b", "better", "better 已是比较级，不能再用 more。", "语法"),
        (r"\bdidn't went\b", "didn't go", "助动词 didn't 后应使用动词原形。", "时态"),
        (r"\bI am agree\b", "I agree", "agree 是动词，不需要 be 动词。", "语法"),
        (r"\byesterday I go\b", "yesterday I went", "yesterday 提示过去时间，应使用过去式。", "时态"),
    ]
    for pattern, replacement, explanation, issue_type in rules:
        match = re.search(pattern, corrected, re.IGNORECASE)
        if match:
            original = match.group(0)
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
            issues.append(
                {
                    "type": issue_type,
                    "original": original,
                    "suggestion": re.sub(pattern, replacement, original, flags=re.IGNORECASE),
                    "explanation": explanation,
                    "certainty": "certain",
                }
            )
    for wrong, right in MISSPELLINGS.items():
        if re.search(rf"\b{re.escape(wrong)}\b", corrected, re.IGNORECASE):
            issues.append(
                {
                    "type": "拼写",
                    "original": wrong,
                    "suggestion": right,
                    "explanation": f"常见拼写错误，正确形式是 {right}。",
                    "certainty": "certain",
                }
            )
            corrected = re.sub(rf"\b{re.escape(wrong)}\b", right, corrected, flags=re.IGNORECASE)
    if corrected and corrected[0].islower():
        issues.append(
            {
                "type": "标点/大小写",
                "original": corrected[:20],
                "suggestion": corrected[:1].upper() + corrected[1:21],
                "explanation": "英语句子开头应大写。",
                "certainty": "certain",
            }
        )
        corrected = corrected[0].upper() + corrected[1:]
    if corrected and corrected[-1] not in ".!?":
        issues.append(
            {
                "type": "标点",
                "original": corrected[-20:],
                "suggestion": corrected[-20:] + ".",
                "explanation": "句末需要标点符号。",
                "certainty": "certain",
            }
        )
        corrected += "."

    return {
        "original": sentence,
        "corrected_text": corrected,
        "is_correct": not issues,
        "issues": issues,
        "overall": (
            "本地规则未发现常见错误，但演示模式覆盖范围有限，不能保证句子完全正确。"
            if not issues
            else f"本地规则发现 {len(issues)} 处问题；请核对解释后再修改。"
        ),
        "warnings": [DEMO_WARNING, "未覆盖复杂句法、搭配和语篇层面的问题。"],
        "demo": True,
    }


def generate_questions_demo(payload: dict) -> dict:
    subject = payload.get("subject") or "数学"
    topic = (payload.get("topic") or "未指定知识点").strip()
    difficulty = payload.get("difficulty") or "medium"
    count = max(1, min(int(payload.get("count") or 3), 5))
    templates = [
        {
            "type": "简答题",
            "question": f"请用自己的话解释「{topic}」的核心含义，并写出两条关键特征或规则。",
            "options": [],
            "answer": "答案应包含：该知识点的准确定义；两条来自教材或笔记的关键特征；必要时用一个例子说明。",
            "explanation": "本题用于检验概念复述与结构化表达，具体评分标准需由老师或学生根据教材确定。",
        },
        {
            "type": "应用题",
            "question": f"请设计一个能用到「{topic}」的简单问题情境，写出条件、所求，并说明解决思路。",
            "options": [],
            "answer": "答案应包含：真实或合理的情境；与知识点有关的已知条件；明确的所求；可执行的解题步骤。",
            "explanation": "本题检验知识迁移和问题建模，开放题需人工判断合理性。",
        },
        {
            "type": "辨析题",
            "question": f"写出一个关于「{topic}」的易错点，并说明为什么容易出错、如何避免。",
            "options": [],
            "answer": "答案应指出具体易错点，说明涉及的概念边界，并给出检查或记忆方法。",
            "explanation": "用于错题复盘，答案不唯一。",
        },
    ]
    questions = []
    for index in range(count):
        base = templates[index % len(templates)]
        questions.append(
            {
                "number": index + 1,
                **base,
                "question": f"（演示模板第 {index + 1} 题）" + base["question"],
            }
        )
    return {
        "subject": subject,
        "topic": topic,
        "difficulty": difficulty,
        "questions": questions,
        "warnings": [
            DEMO_WARNING,
            "这是通用的思考题模板，并非针对该知识点的原创题目；请配置文本模型生成可练习的题目。",
        ],
        "demo": True,
    }


def _overlap_ratio(point: str, student: str) -> float:
    english_point = re.findall(r"[A-Za-z]+", point.lower())
    if len(english_point) >= 2:
        student_tokens = set(re.findall(r"[A-Za-z]+", student.lower()))
        if not student_tokens:
            return 0.0
        return sum(1 for token in english_point if token in student_tokens) / len(english_point)
    point_chars = {
        char
        for char in point
        if "\u4e00" <= char <= "\u9fff" and char not in "的了是在和有与或及把被对为"
    }
    if not point_chars:
        return 0.0
    student_chars = set(student)
    return len(point_chars & student_chars) / len(point_chars)


def grade_answer_demo(payload: dict) -> dict:
    reference = (payload.get("reference_answer") or "").strip()
    student = (payload.get("student_answer") or "").strip()
    question = (payload.get("question") or "").strip()
    try:
        max_score = float(payload.get("max_score") or 100)
    except (TypeError, ValueError):
        max_score = 100.0
    points = [part.strip() for part in re.split(r"[。；;\n]+", reference) if len(part.strip()) >= 3]
    matched, missing = [], []
    if student:
        for point in points:
            if _overlap_ratio(point, student) >= 0.35:
                matched.append(point)
            else:
                missing.append(point)
    else:
        missing = points
    ratio = (len(matched) / len(points)) if points else (0.6 if student else 0.0)
    score = round(max_score * ratio, 1)
    percentage = (score / max_score * 100) if max_score else 0
    missing_points = [
        {
            "point": point[:120],
            "suggestion": "对照参考答案，用完整句子补充该得分点，并检查是否说明了理由。",
        }
        for point in missing[:8]
    ]
    matched_points = [
        {
            "point": point[:120],
            "evidence": f"学生答案中检测到与该要点相关的关键词。原文片段：{student[:100]}",
        }
        for point in matched[:8]
    ]
    deductions = [
        {
            "reason": f"可能遗漏：{point[:80]}",
            "points": round(max_score / max(1, len(points)), 1),
        }
        for point in missing[:8]
    ]
    return {
        "score": min(score, max_score),
        "max_score": max_score,
        "level": _level(percentage),
        "matched_points": matched_points,
        "missing_points": missing_points,
        "deductions": deductions,
        "comment": (
            "演示模式使用参考答案与作答的字词重合度做非常粗略的估算，"
            "不能理解语义、同义表达或推理过程，请勿把此分数视为有效评分。"
            + (" 学生作答为空，无法评分。" if not student else "")
        ),
        "improvement": [
            "逐条对照参考答案的得分点，检查是否有“观点+依据”。",
            "把遗漏的得分点写进错题本，并用一句话概括其与题目的关系。",
        ],
        "confidence": "low",
        "warnings": [DEMO_WARNING, "此结果仅用于体验阅卷流程，不可作为正式评分。"],
        "demo": True,
    }


def analyze_grades_demo(payload: dict) -> dict:
    stats = payload.get("analytics") or {}
    records = stats.get("chart_records") or []
    overall = stats.get("overall_series") or []
    comparison = stats.get("subject_comparison") or []
    if not records:
        return {
            "summary": "当前筛选范围内没有成绩记录，无法进行趋势分析。",
            "trend": {
                "direction": "暂时无法判断",
                "explanation": "没有可比较的成绩数据。",
                "limitations": "至少需要 2 次成绩记录才能观察简单趋势。",
            },
            "strengths": [],
            "weaknesses": [],
            "suggestions": [
                {
                    "title": "先建立成绩记录",
                    "detail": "录入最近一次考试的科目、分数和日期，再回来看分析。",
                    "priority": "高",
                }
            ],
            "disclaimer": "本分析仅基于有限成绩记录，仅供参考，不构成预测。",
            "warnings": [DEMO_WARNING],
            "demo": True,
        }
    average = stats.get("kpis", {}).get("average_percentage")
    latest = stats.get("kpis", {}).get("latest_percentage")
    change = stats.get("kpis", {}).get("change_from_previous")
    if len(overall) >= 2 and change is not None:
        if change > 2:
            direction = "上升"
            explanation = f"最近一次合并成绩较前一次提高 {abs(change)} 个百分点。"
        elif change < -2:
            direction = "下降"
            explanation = f"最近一次合并成绩较前一次下降 {abs(change)} 个百分点。"
        else:
            direction = "波动"
            explanation = f"最近两次合并成绩相差 {abs(change)} 个百分点，暂不明显。"
    else:
        direction = "暂时无法判断"
        explanation = "可比较的考试次数不足，不能仅凭一次记录判断趋势。"
    strengths = []
    weaknesses = []
    for item in comparison[:2]:
        if item["average"] >= 80:
            strengths.append(
                {
                    "subject": item["subject"],
                    "evidence": f"范围内平均得分率 {item['average']}%，共 {item['count']} 条记录。",
                    "observation": "当前数据中表现相对稳定。",
                }
            )
    for item in list(reversed(comparison))[:2]:
        if item["average"] < 80:
            weaknesses.append(
                {
                    "subject": item["subject"],
                    "evidence": f"范围内平均得分率 {item['average']}%，共 {item['count']} 条记录。",
                    "observation": "从平均得分率看有提升空间；单次分数不能代表长期水平。",
                }
            )
    suggestions = []
    if weaknesses:
        subject = weaknesses[0]["subject"]
        suggestions.append(
            {
                "title": f"给{subject}安排固定的复盘时段",
                "detail": f"每周 2 次、每次 20 分钟整理{subject}错题，并写下错误原因和改正步骤。",
                "priority": "高",
            }
        )
    if len(records) < 4:
        suggestions.append(
            {
                "title": "补充更多样本",
                "detail": "当前记录较少，趋势推断不稳定。可补充最近几次周测或月考成绩。",
                "priority": "中",
            }
        )
    suggestions.append(
        {
            "title": "保持过程性记录",
            "detail": "除了分数，也记录考试范围、复习时长和主要失分类型，便于找到分数变化的原因。",
            "priority": "中",
        }
    )
    return {
        "summary": (
            f"本地统计（演示）：共分析 {len(records)} 条成绩记录，"
            f"平均得分率 {average if average is not None else '暂无'}%，"
            f"最近一次合并得分率 {latest if latest is not None else '暂无'}%。"
            "这些是已有数据的描述，不是对下次考试的预测。"
        ),
        "trend": {
            "direction": direction,
            "explanation": explanation,
            "limitations": (
                "本地演示只做简单比较，没有考虑试卷难度、科目差异和样本量；"
                "请谨慎解读，并结合老师反馈。"
            ),
        },
        "strengths": strengths[:2],
        "weaknesses": weaknesses[:2],
        "suggestions": suggestions[:3],
        "disclaimer": "本分析仅基于有限成绩记录，仅供参考，不构成分数预测或正式评价。",
        "warnings": [DEMO_WARNING, "成绩受试卷难度、状态等多种因素影响，简单趋势不能说明因果。"],
        "demo": True,
    }


def audit_note_demo(payload: dict) -> dict:
    markdown = (payload.get("markdown") or "").strip()
    corrections = []
    if markdown:
        if markdown.count("$$") % 2 != 0:
            corrections.append(
                {
                    "location": "文中 $$ 公式块",
                    "original": "存在未闭合的 $$ 公式定界符",
                    "suggested": "为独立公式补齐成对的 $$...$$，再检查公式是否完整。",
                    "reason": "Markdown/KaTeX 中独立公式需要成对的 $$ 定界符，否则渲染会异常。",
                    "certainty": "certain",
                    "confidence": 0.98,
                    "category": "公式错误",
                }
            )
        single_dollar_text = markdown.replace("$$", "")
        if single_dollar_text.count("$") % 2 != 0:
            corrections.append(
                {
                    "location": "行内公式",
                    "original": "存在未配对的 $ 定界符",
                    "suggested": "检查行内公式是否都有成对的 $...$。",
                    "reason": "行内公式的 $ 数量不成对，可能导致后续文字被错误渲染为公式。",
                    "certainty": "certain",
                    "confidence": 0.96,
                    "category": "公式错误",
                }
            )
        if re.search(r"(TODO|待补充|待确认|无法辨认)", markdown, re.IGNORECASE):
            corrections.append(
                {
                    "location": "文中标记处",
                    "original": "笔记中留有 TODO/待补充/无法辨认标记",
                    "suggested": "结合教材或老师讲解补全后再复习，避免把占位文字当成知识结论。",
                    "reason": "未完成的内容不是可复习的确定知识；需要人工确认。",
                    "certainty": "review",
                    "confidence": 0.72,
                    "category": "其他",
                }
            )
        if re.search(r"\b(勾股定理|二次函数|牛顿|欧姆|化学式)\b", markdown):
            corrections.append(
                {
                    "location": "学科概念陈述",
                    "original": "笔记包含需要专业核对的概念/公式",
                    "suggested": "暂不自动修改。请对照教材逐条核验公式、条件和适用范围。",
                    "reason": "演示模式只检查格式，不能可靠判断学科知识是否正确。",
                    "certainty": "review",
                    "confidence": 0.4,
                    "category": "其他",
                }
            )
    summary = (
        "演示模式仅进行了公式定界符与占位标记等基础格式检查，未进行学科知识审核。"
        if corrections
        else "演示模式仅进行了基础格式检查，未发现明显格式问题；这不代表笔记没有知识性错误。"
    )
    return {
        "summary": summary,
        "corrections": corrections,
        "coverage_note": (
            "未调用 AI 模型，无法判断概念、公式推导和知识点之间是否存在知识性错误。"
            "所有内容需人工核对；本功能不会自动改动原始笔记。"
        ),
        "warnings": [DEMO_WARNING],
        "demo": True,
    }


def _extract_headings(markdown: str) -> list[str]:
    headings = []
    for match in re.finditer(r"^#{1,4}\s+(.+?)\s*$", markdown, re.MULTILINE):
        text = re.sub(r"[#*_`]", "", match.group(1)).strip()
        if text and text not in headings:
            headings.append(text[:60])
    return headings


def knowledge_graph_demo(payload: dict) -> dict:
    markdown = (payload.get("markdown") or "").strip()
    title = (payload.get("title") or "未命名笔记").strip()
    headings = _extract_headings(markdown)
    candidates: list[str] = []
    for value in [title] + headings:
        cleaned = value.strip("：: ")
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)
    bold_terms = re.findall(r"\*\*([^*\n]{2,30})\*\*", markdown)
    for term in bold_terms:
        if term not in candidates and not term.startswith("演示"):
            candidates.append(term.strip())
    candidates = candidates[:14]
    nodes = []
    for index, label in enumerate(candidates):
        if any(word in label for word in ("公式", "式")):
            node_type = "公式"
        elif any(word in label for word in ("定义", "概念", "基础")):
            node_type = "概念"
        elif any(word in label for word in ("方法", "步骤", "推导")):
            node_type = "方法"
        elif any(word in label for word in ("应用", "例题", "练习")):
            node_type = "应用"
        else:
            node_type = "概念"
        nodes.append(
            {
                "id": f"demo-node-{index + 1}",
                "label": label,
                "type": node_type,
                "description": "演示模式从笔记标题/小标题提取",
            }
        )
    edges = []
    for index in range(1, len(nodes)):
        edges.append(
            {
                "source": nodes[index - 1]["id"],
                "target": nodes[index]["id"],
                "label": "从属关系" if index <= 3 else "相互关联",
            }
        )
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": (
            "演示模式使用笔记标题与小标题构建层级图，不代表真实知识依赖关系。"
            if nodes
            else "笔记内容太少，无法提取知识点。"
        ),
        "warnings": [
            DEMO_WARNING,
            "节点和关系来自标题启发式提取，请人工确认知识关系是否准确。",
        ],
        "demo": True,
    }


def generate_flashcards_demo(payload: dict) -> dict:
    markdown = (payload.get("markdown") or "").strip()
    title = (payload.get("title") or "笔记").strip()
    subject = payload.get("subject") or "综合"
    try:
        count = max(1, min(int(payload.get("count") or 5), 20))
    except (TypeError, ValueError):
        count = 5
    cards = []
    seen = set()
    sections = re.split(r"^##+\s+", markdown, flags=re.MULTILINE)
    first_section = sections[0] if sections else ""
    heading_match = re.search(r"^#\s+(.+)$", first_section, re.MULTILINE)
    page_title = heading_match.group(1).strip() if heading_match else title
    for section in sections[1:]:
        lines = section.strip().splitlines()
        if not lines:
            continue
        heading = lines[0].strip()
        body = " ".join(
            line.strip()
            for line in lines[1:]
            if line.strip() and not line.strip().startswith(">")
        )
        if not body:
            continue
        body = re.sub(r"[*_`$#]", "", body)
        front = f"「{heading}」的核心内容是什么？"
        if front in seen:
            continue
        seen.add(front)
        cards.append(
            {
                "front": front,
                "back": body[:220],
                "knowledge_point": heading,
            }
        )
        if len(cards) >= count:
            break
    for term, definition in re.findall(
        r"\*\*([^*\n]{2,30})\*\*[：:]\s*([^\n]{5,220})", markdown
    ):
        front = f"什么是「{term}」？"
        if front in seen:
            continue
        seen.add(front)
        cards.append(
            {
                "front": front,
                "back": definition.strip(),
                "knowledge_point": term.strip(),
            }
        )
        if len(cards) >= count:
            break
    if not cards and markdown:
        body = re.sub(r"[#>*_`$]", "", markdown).strip()
        cards.append(
            {
                "front": f"「{page_title}」主要讲了什么？",
                "back": body[:220] or "笔记内容为空。",
                "knowledge_point": page_title,
            }
        )
    return {
        "cards": cards[:count],
        "summary": (
            f"演示模式从笔记的小标题/加粗定义提取了 {len(cards[:count])} 张闪卡，"
            "没有进行知识点重构。"
        ),
        "warnings": [DEMO_WARNING, "答案直接截取自笔记，未检查准确性，请在复习前核对。"],
        "demo": True,
    }


def classify_error_demo(payload: dict) -> dict:
    question = (payload.get("question") or "").strip()
    student_answer = (payload.get("student_answer") or "").strip()
    hint = payload.get("subject_hint")
    subject = _subject_from_text(question + " " + student_answer, hint)
    knowledge_candidates = []
    for known_subject, words in SUBJECT_KEYWORDS.items():
        if known_subject != subject and not hint:
            continue
        for word in words:
            if word.lower() in (question + " " + student_answer).lower():
                knowledge_candidates.append(word)
    # Pull common Chinese topic phrases ending in typical knowledge suffixes.
    for match in re.finditer(
        r"[\u4e00-\u9fff]{2,8}(?:定理|公式|定律|概念|性质|用法|时态|从句|方程|函数)",
        question,
    ):
        if match.group(0) not in knowledge_candidates:
            knowledge_candidates.append(match.group(0))
    knowledge_points = knowledge_candidates[:5]
    return {
        "subject": subject,
        "knowledge_points": knowledge_points,
        "analysis": (
            "演示模式仅根据关键词推测知识点，没有分析具体作答过程。"
            + (" 建议对照正确答案，判断是概念理解、审题还是计算/表达导致了失分。" if student_answer else " 未提供学生作答，无法推测错误环节。")
        ),
        "suggested_review": (
            "用教材目录核对上述知识点；重新独立完成本题，并用一句话写出错误原因。"
            if knowledge_points
            else "本地规则未能可靠识别知识点，请手动填写，并请老师或同学帮助归类。"
        ),
        "mastery_hint": "new",
        "confidence": "low",
        "warnings": [DEMO_WARNING],
        "demo": True,
    }
