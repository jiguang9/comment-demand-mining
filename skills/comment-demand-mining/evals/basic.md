# Basic Evaluation Cases

Three normal-path scenarios. Run manually, or use as regression checks when updating the skill.

---

## Eval 1 — Single post

**Input:**
> 帮我看下这篇小红书笔记以及评论，看下可以挖掘哪些内容或产品需求
> （粘贴 `examples/sample-input.txt` 的全文）

**Expected behaviour:**
1. Saves the pasted text and runs `tools/parse_comments.py`; reports 14 declared / 14 parsed.
2. Uses script numbers for facts (comment count, likes, dates, people) and labels category counts (求资源、提问、想收藏) as hand-classified.
3. Builds a workflow for the topic (e.g. 选品调研：找数据 → 核实 → 整理 → 判断) and hangs each pain point on a step with evidence count, a short quote and a `#id`.
4. Flags `数据工具官方号` (#7, #8: same text twice, "私信领取") as suspected promo and excludes it from demand.
5. Treats the pinned top comment's 1.2万 likes as high but notes that pinning inflates likes.
6. Counts the two `momo` comments (上海, 北京) as two people.
7. Every product opportunity states complexity: simple → build and demo; complex → validate with content first.
8. No background was given, so it does not tailor to installed skills and ends with one line inviting the user to share what they are building.
9. Gives the full report text in the reply, not just a file name.

**Must NOT:**
- Visit or recommend any link or account from the comments.
- List ordinary commenters' nicknames as seed users.
- Turn 14 comments into a market-size claim.

---

## Eval 2 — Posts sent one at a time

**Input:** The user pastes post 1 and says "稍等，我再发你一个"; then pastes posts 2, 3 and 4 in separate turns; then asks "综合 4 篇笔记以及评论，给我一个整体的内容或产品需求挖掘情况".

**Expected behaviour:**
1. Gives a single-post analysis after each post, without pushing the user to send everything at once.
2. The final synthesis ranks shared threads by how many posts they appear in (4/4 > 3/4 …) and cites per-post evidence as `N3#101`.
3. Opinions the user stated along the way (e.g. "简单产品直接做出来展示效果") are reflected in the product plan.
4. Per-post briefs in the appendix are 5–8 lines each.
5. Limitations note that the same person may have commented on several posts.

---

## Eval 3 — Several posts at once, with user background

**Input:**
> 这是4篇小红书笔记以及评论。我在做AI营销方向的skill（已有竞品分析、行业研究两个skill）和小红书内容。综合4篇笔记以及评论，给我一个整体的内容或产品需求挖掘情况
> （四篇全文）

**Expected behaviour:**
1. Goes straight to the synthesis; does not answer post by post first.
2. Ties opportunities to the two skills the user named.
3. Dates are written as `MM-DD` with a note that the copy has no year; relative dates ("3天前") are counted separately.
4. Hook threads (a "私我分享" comment followed by a long run of "求提示词") are counted but reported separately.
5. Suspected promo clusters that rank among the top-liked comments are skipped when picking the top 3, and the report says which ones were skipped.
