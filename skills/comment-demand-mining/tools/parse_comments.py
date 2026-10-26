#!/usr/bin/env python3
"""Parse a pasted social post + comment thread into structured JSON with exact stats.

Understands the Xiaohongshu web copy format (see references/parsing.md):

    昵称 / [作者] / 内容... / [置顶评论] / 日期地区 / 点赞 / 回复数|回复

Keyword flags (ask / promo) are hints for the model, not classifications.

Usage:
    python3 parse_comments.py note1.txt [note2.txt ...] [--out-dir DIR]

Writes <stem>.parsed.json per input and prints a Markdown summary to stdout.
Exit codes: 0 ok, 1 no comments parsed in some input, 2 bad arguments / unreadable input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

DATE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}|\d{2}-\d{2}|\d+\s*(?:天|小时|分钟)前|昨天(?:\s*\d{1,2}:\d{2})?|前天|刚刚)"
    r"(?P<region>[一-鿿]{0,12})$"
)
LIKE_RE = re.compile(r"^(赞|\d+(?:\.\d+)?万?)$")
COUNT_RE = re.compile(r"^\d+$")
TOTAL_RE = re.compile(r"^共\s*(\d+)\s*条评论")
END_RE = re.compile(r"^-\s*THE END\s*-$", re.IGNORECASE)
REPLY_PREFIX_RE = re.compile(r"^回复\s*(?P<to>.+?)\s*[:：]\s*")
AT_ONLY_RE = re.compile(r"^(@\S+\s*)+$")

# "求" inside 需求/要求/请求/追求/诉求/寻求/讲求 is not an ask.
ASK_RE = re.compile(
    r"蹲|(?<![需要请追诉寻讲])求|同问|同想知道|球球|球一|顿顿|顿教程|我也有.{0,6}需求|我也需要|我也想要"
)
# Wanting to keep the post for later: a collect / "save me this" signal, distinct from asking for a resource.
SAVE_RE = re.compile(
    r"收藏(?:了|之|起来|慢慢|学习|一下)|先收藏|我将.{0,4}(?:收藏|学习)|码住|插眼|(?<![A-Za-z])mark(?![A-Za-z])|"
    r"别删|不要删|保留这个|保留帖子|严肃学习|逐帧学习|反复学习|严肃收录|干货",
    re.IGNORECASE,
)
ASK_TOPICS = {
    "教程": r"教程",
    "提示词": r"提示词|prompt|关键词",
    "内测": r"内测",
    "模板": r"模板|框架",
    "链接/网址": r"链接|网址|网站|地址",
    "工具": r"工具|插件|软件|skill",
    "资料/报告": r"资料|报告|文档",
}
# A question or request for help, broader than ASK_RE ("是免费的吗", "怎么做", "跪求指点").
QUESTION_RE = re.compile(r"[?？]|请问|怎么|如何|有没有|能不能|可以.{0,6}吗|是.{0,8}吗|跪求|求指点|求教|请教")
PROMO_RE = re.compile(
    r"私我|私信|主页|加V|加v|vx|VX|微信|找我|欢迎试试|欢迎体验|欢迎提出|我们做了|我们现在|我做了一个|我用ai做了|"
    r"合作|接单|预付|一站式|www\.|https?://|\.com\b|\.ai\b|\.fund\b"
)
ASCII_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9.\-]{2,}")
ASCII_STOP = {"the", "and", "for", "you", "http", "https", "www", "com", "with", "this", "that", "are"}


def parse_likes(s: str) -> int:
    s = s.strip()
    if s == "赞":
        return 0
    if s.endswith("万"):
        return int(float(s[:-1]) * 10000)
    return int(float(s))


def strip_block(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return lines


def parse_post(header: list[str]) -> dict:
    nonempty = [(i, l.strip()) for i, l in enumerate(header) if l.strip()]
    if not nonempty:
        return {"title": "", "date": None, "body": "", "tags": []}
    title_idx, title = nonempty[0]
    date, date_idx = None, len(header)
    for i, s in reversed(nonempty[1:]):
        candidate = s[3:].strip() if s.startswith("编辑于") else s
        if DATE_RE.match(candidate):
            date, date_idx = s, i
            break
    body = "\n".join(l.strip() for l in header[title_idx + 1 : date_idx]).strip()
    tags = re.findall(r"#([^\s#\[]+)", body)
    return {"title": title, "date": date, "body": body, "tags": tags}


def parse_text(text: str) -> dict:
    lines = [l.rstrip() for l in text.splitlines()]
    warnings: list[str] = []

    total_idx = next((i for i, l in enumerate(lines) if TOTAL_RE.match(l.strip())), None)
    if total_idx is None:
        warnings.append("没找到“共 N 条评论”这一行，帖子正文无法和评论区分开，按全文找评论。")
        post = {"title": "", "date": None, "body": "", "tags": []}
        declared = None
        start = 0
    else:
        post = parse_post(lines[:total_idx])
        declared = int(TOTAL_RE.match(lines[total_idx].strip()).group(1))
        start = total_idx + 1
    end = next((i for i in range(start, len(lines)) if END_RE.match(lines[i].strip())), len(lines))
    region = lines[start:end]

    comments: list[dict] = []
    block_start = 0
    i = 0
    while i < len(region):
        s = region[i].strip()
        m = DATE_RE.match(s)
        if m and i + 1 < len(region) and LIKE_RE.match(region[i + 1].strip()):
            likes = parse_likes(region[i + 1].strip())
            term = i + 1
            reply_count = None
            if i + 2 < len(region):
                nxt = region[i + 2].strip()
                if nxt == "回复":
                    term = i + 2
                elif COUNT_RE.match(nxt):
                    term = i + 2
                    reply_count = int(nxt)
            block = strip_block(region[block_start:i])
            if not block:
                warnings.append(f"第 {start + i + 1} 行附近有日期和点赞，但前面没有昵称，已跳过。")
            else:
                name = block[0].strip()
                rest = block[1:]
                is_author = bool(rest) and rest[0].strip() == "作者"
                if is_author:
                    rest = rest[1:]
                pinned = any(l.strip() == "置顶评论" for l in rest)
                rest = [l for l in rest if l.strip() != "置顶评论"]
                content = "\n".join(l.strip() for l in rest).strip()
                comments.append(
                    {
                        "id": len(comments) + 1,
                        "name": name,
                        "is_author": is_author,
                        "pinned": pinned,
                        "content": content,
                        "date": m.group("date"),
                        "region": m.group("region") or None,
                        "likes": likes,
                        "reply_count": reply_count,
                    }
                )
            block_start = term + 1
            i = term + 1
            continue
        i += 1
    leftover = strip_block(region[block_start:])
    if leftover:
        warnings.append(f"评论区末尾有 {len(leftover)} 行无法解析（可能被截断）：{leftover[0][:30]}…")

    # Threading: a comment with a numeric reply count opens a thread of that many replies.
    remaining, parent, shown = 0, None, 0
    for c in comments:
        c["parent_id"] = None
        c["reply_to"] = None
        pm = REPLY_PREFIX_RE.match(c["content"])
        if pm:
            c["reply_to"] = pm.group("to")
        if c["reply_count"]:
            if parent is not None and remaining > 0:
                warnings.append(
                    f"#{parent['id']} 声明 {parent['reply_count']} 条楼中楼，只解析到 {shown} 条（可能没展开完）。"
                )
            c["level"] = "main"
            parent, remaining, shown = c, c["reply_count"], 0
        elif remaining > 0:
            c["level"] = "reply"
            c["parent_id"] = parent["id"]
            remaining -= 1
            shown += 1
        else:
            c["level"] = "reply?" if pm else "main"
    if parent is not None and remaining > 0:
        warnings.append(f"#{parent['id']} 声明 {parent['reply_count']} 条楼中楼，只解析到 {shown} 条（可能没展开完）。")

    for c in comments:
        text_ = c["content"]
        ask_hit = bool(ASK_RE.search(text_)) and not c["is_author"]
        c["flags"] = {
            "ask": ask_hit,
            "ask_topics": [k for k, p in ASK_TOPICS.items() if ask_hit and re.search(p, text_, re.IGNORECASE)],
            "question": bool(QUESTION_RE.search(REPLY_PREFIX_RE.sub("", text_))) and not c["is_author"],
            "save": bool(SAVE_RE.search(text_)) and not c["is_author"],
            "promo_hits": sorted(set(PROMO_RE.findall(text_))),
            "at_only": bool(AT_ONLY_RE.match(text_)),
            "empty": not text_,
        }

    return {"post": post, "declared_total": declared, "comments": comments, "warnings": warnings}


def build_stats(data: dict) -> dict:
    cs = data["comments"]
    month = Counter()
    relative = 0
    abs_dates = []
    for c in cs:
        d = c["date"]
        if re.match(r"^\d{2}-\d{2}$", d):
            month[d[:2]] += 1
            abs_dates.append(d)
        elif re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            month[d[5:7]] += 1
            abs_dates.append(d[5:])
        else:
            relative += 1
    ask = [c for c in cs if c["flags"]["ask"]]
    topic_counts = Counter(t for c in ask for t in c["flags"]["ask_topics"])
    terms = Counter()
    display = {}
    names = {re.sub(r"[^a-z0-9]", "", c["name"].lower()) for c in cs}
    for c in cs:
        body = REPLY_PREFIX_RE.sub("", c["content"])
        letters = sum(ch.isascii() and ch.isalpha() for ch in body)
        if letters >= 20 and letters > 0.5 * len(body.replace(" ", "")):
            continue  # a whole English sentence: its words are prose, not tool names
        seen = set()
        for t in ASCII_TERM_RE.findall(body):
            key = t.lower().rstrip(".-")
            if key in ASCII_STOP or key in seen or re.sub(r"[^a-z0-9]", "", key) in names:
                continue
            seen.add(key)
            terms[key] += 1
            display.setdefault(key, t.rstrip(".-"))
    # Same text posted more than once (copy-paste promos, reposted hooks). Ignore very short texts like "求".
    dup = {}
    for c in cs:
        t = REPLY_PREFIX_RE.sub("", c["content"]).strip()
        if len(t) >= 8:
            dup.setdefault(t, []).append(c["id"])
    duplicates = [{"text": short(t, 40), "ids": ids} for t, ids in dup.items() if len(ids) > 1]
    # The same account posting the same text again is a promo signal even without promo keywords.
    by_id = {c["id"]: c for c in cs}
    for d in duplicates:
        if len({by_id[i]["name"] for i in d["ids"]}) < len(d["ids"]):
            for i in d["ids"]:
                if "重复发同一句" not in by_id[i]["flags"]["promo_hits"]:
                    by_id[i]["flags"]["promo_hits"].append("重复发同一句")
    # Nicknames are not unique (several different "momo"s), so a person is nickname + region.
    people = {(c["name"], c["region"]) for c in cs if not c["is_author"]}
    by_likes = sorted(cs, key=lambda c: -c["likes"])
    by_replies = sorted([c for c in cs if c["reply_count"]], key=lambda c: -c["reply_count"])
    return {
        "parsed_total": len(cs),
        "main": sum(1 for c in cs if c["level"] == "main"),
        "replies": sum(1 for c in cs if c["level"] != "main"),
        "author_comments": sum(1 for c in cs if c["is_author"]),
        "pinned_ids": [c["id"] for c in cs if c["pinned"]],
        "date_min": min(abs_dates) if abs_dates else None,
        "date_max": max(abs_dates) if abs_dates else None,
        "relative_dates": relative,
        "by_month": dict(sorted(month.items())),
        "regions_top": Counter(c["region"] for c in cs if c["region"]).most_common(10),
        "ask_total": len(ask),
        "ask_topics": dict(topic_counts.most_common()),
        "question_total": sum(1 for c in cs if c["flags"]["question"]),
        "save_total": sum(1 for c in cs if c["flags"]["save"]),
        "distinct_people": len(people),
        "duplicates": duplicates,
        "promo_candidate_ids": [c["id"] for c in cs if c["flags"]["promo_hits"]],
        "at_only": sum(1 for c in cs if c["flags"]["at_only"]),
        "empty": sum(1 for c in cs if c["flags"]["empty"]),
        "top_liked": [c["id"] for c in by_likes[:10] if c["likes"] > 0],
        "top_threads": [c["id"] for c in by_replies[:5]],
        "ascii_terms_top": [(display[k], n) for k, n in terms.most_common(25)],
    }


def short(s: str, n: int = 50) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def summary_md(name: str, data: dict) -> str:
    st = data["stats"]
    by_id = {c["id"]: c for c in data["comments"]}
    out = [f"## {data['post']['title'] or name}", ""]
    out.append(f"- 文件：{name}；发布：{data['post']['date'] or '未知'}；话题：{' '.join('#' + t for t in data['post']['tags']) or '无'}")
    out.append(
        f"- 声明评论 {data['declared_total'] if data['declared_total'] is not None else '未知'}，"
        f"解析 {st['parsed_total']}（主楼 {st['main']}，楼中楼 {st['replies']}）；作者评论 {st['author_comments']}；"
        f"置顶 {', '.join('#' + str(i) for i in st['pinned_ids']) or '无'}"
    )
    out.append(
        f"- 日期：{st['date_min'] or '?'} 至 {st['date_max'] or '?'}；相对日期（如“3天前”）{st['relative_dates']} 条；"
        f"按月 {', '.join(f'{k}月:{v}' for k, v in st['by_month'].items())}"
    )
    out.append(f"- 地区 Top：{', '.join(f'{r} {n}' for r, n in st['regions_top']) or '无'}")
    out.append(
        f"- 求资源类关键词命中（不含作者）：{st['ask_total']} 条；"
        f"求的内容：{', '.join(f'{k} {v}' for k, v in st['ask_topics'].items()) or '未细分'}"
    )
    out.append(f"- 提问类（问号、请问、怎么、有没有、是…吗等，不含作者）：{st['question_total']} 条")
    out.append(f"- 想收藏类（收藏、别删、严肃学习等，不含作者）：{st['save_total']} 条")
    out.append(f"- 非作者评论者约 {st['distinct_people']} 人（按昵称 + 地区区分，同名不同地区算不同人）")
    if st["duplicates"]:
        out.append("- 重复内容：" + "；".join(f"{d['text']}（{', '.join('#' + str(i) for i in d['ids'])}）" for d in st["duplicates"]))
    out.append(f"- 推广关键词命中：{len(st['promo_candidate_ids'])} 条（候选，需人工判断）：{', '.join('#' + str(i) for i in st['promo_candidate_ids'])}")
    out.append(f"- 纯 @好友 {st['at_only']} 条；空内容（图片/表情）{st['empty']} 条")
    out.append("")
    out.append("**点赞 Top**")
    for i in st["top_liked"]:
        c = by_id[i]
        tag = "作者" if c["is_author"] else ("楼中楼" if c["level"] != "main" else "主楼")
        out.append(f"- #{i} {c['name']}（{tag}，{c['likes']} 赞，{c['reply_count'] or 0} 回复，{c['date']}）：{short(c['content'])}")
    out.append("")
    out.append("**回复最多的楼**")
    for i in st["top_threads"]:
        c = by_id[i]
        out.append(f"- #{i} {c['name']}（{c['reply_count']} 回复，{c['likes']} 赞）：{short(c['content'])}")
    out.append("")
    out.append("**英文词频（按出现的评论数）**：" + (", ".join(f"{t} {n}" for t, n in st["ascii_terms_top"]) or "无"))
    if data["warnings"]:
        out.append("")
        out.append("**警告**")
        out.extend(f"- {w}" for w in data["warnings"])
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse pasted post + comment threads into JSON with stats.")
    ap.add_argument("inputs", nargs="+", help="text files, one post per file")
    ap.add_argument("--out-dir", default=".", help="where to write <stem>.parsed.json")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    status = 0
    for p in args.inputs:
        path = Path(p)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"无法读取 {p}: {e}", file=sys.stderr)
            return 2
        data = parse_text(text)
        data["source_file"] = path.name
        data["stats"] = build_stats(data)
        (out_dir / f"{path.stem}.parsed.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(summary_md(path.name, data))
        if not data["comments"]:
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
