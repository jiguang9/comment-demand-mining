# comment-demand-mining

> 把社媒评论区当成一次免费的用户访谈：挖出用户需求、痛点、现有方案、产品机会和内容选题，每条判断都能追回到具体评论

想做产品或找选题，最真实的用户声音往往在评论区里：有人在问"有没有免费的"，有人在楼中楼里排队"求提示词"，有人说"我扒了几个月帖子扒得头疼"。可是几百条评论自己翻，很容易被高赞带偏、被软广误导，数字也数不准。

这个 Skill 把评论区整理成一份需求挖掘报告：

- **需求有多强**：评论数和时间跨度、高赞、求资源、想收藏、作者追问，数字由脚本精确统计。
- **卡在哪一步**：先为话题画一条做事流程，再把痛点挂到环节上，按证据条数分强弱。
- **现在怎么凑合**：评论里提到的工具和方法、各自解决哪一环、被夸还是被骂。
- **哪些是软广**：同一句话反复发、"私我领取"、几天内几个账号推同一个产品，单独列出来，赞不算需求。
- **做什么、发什么**：产品机会分"简单的直接做出来拿效果发内容"和"复杂的先用内容验证"；选题写清接住哪条需求、发出去看什么信号。
- **多篇综合**：几篇帖子放一起，共同线索按"出现在几篇里"排强度。

只分析你贴进来的文本，不抓取平台数据。解析脚本只用 Python 3 标准库，本地运行，数据不上传。

## 用法

把一篇帖子（标题、正文、评论区）从小红书网页端整篇复制，贴给 Agent，说"看看评论区能挖出什么需求"。几篇帖子可以一次贴，也可以一篇一篇发，发完再说"综合一下"。

解析脚本也能单独用：

```bash
cd skills/comment-demand-mining
python3 tools/parse_comments.py examples/sample-input.txt --out-dir 输出目录
```

终端会打印统计摘要，每条评论的结构化记录写进 `输出目录/sample-input.parsed.json`。

## 当 Agent Skill 用

| 平台 | 安装命令 |
|---|---|
| Claude Code | `npx skills add https://github.com/jiguang9/comment-demand-mining --skill comment-demand-mining -g -a claude-code` |
| Codex | `npx skills add https://github.com/jiguang9/comment-demand-mining --skill comment-demand-mining -g -a codex` |
| OpenClaw | `npx skills add https://github.com/jiguang9/comment-demand-mining --skill comment-demand-mining -g -a openclaw` |
| Hermes Agent | `hermes skills install jiguang9/comment-demand-mining/skills/comment-demand-mining` |

安装用的是第三方的 [Vercel skills CLI](https://github.com/vercel-labs/skills)；不想用的话，`git clone` 本仓库后把 `skills/comment-demand-mining/` 复制进 `~/.claude/skills/` 或 `~/.codex/skills/` 也一样。更新：`bash ~/.claude/skills/comment-demand-mining/update.sh`（只需要 `curl` 或 `wget`）。

## 触发示例

```
帮我看下这篇小红书笔记以及评论，看下可以挖掘哪些内容或产品需求
这几篇帖子的评论区放一起看，有什么共同的需求
评论区里大家在抱怨什么，能做什么产品
这条笔记的评论能给我什么选题灵感
What pain points show up in this Reddit thread's comments?
```

## 解析脚本统计什么

| 类别 | 内容 | 怎么用 |
|---|---|---|
| 事实类 | 声明 / 解析评论数、主楼和楼中楼、作者评论、置顶、日期分布、地区、点赞 Top、回复最多的楼、评论人数（昵称 + 地区区分同名）、重复内容 | 以脚本为准 |
| 关键词类 | 求资源（蹲、求、同问）、提问、想收藏（别删、严肃学习）、推广命中（私信、加V、留链接、同一账号重复发同一句）、英文工具词频 | 只是线索，报告里的条数以人工按语义归类为准 |

格式按小红书网页端的复制格式解析（昵称 / 作者 / 内容 / 置顶评论 / 日期地区 / 点赞 / 回复数）。其他平台的格式脚本认不出时，Skill 会改成人工解析，数字都标"约"。

## 示例

`skills/comment-demand-mining/examples/` 里有：

- `sample-input.txt`：虚构的一篇帖子和 14 条评论，演示复制格式，也是单元测试的输入。
- `real-case-single-note.md`：用本 Skill 分析一篇真实笔记（内容运营实习生求助竞品分析，168 条评论）的报告。
- `real-case-four-notes.md`：四篇真实笔记、533 条评论的综合报告。

两份真实报告的原始帖子和评论不公开，账号昵称都已换成代号。

## 数据与隐私

- 只分析用户贴进来或上传的文本，不登录、不抓取、不绕过反爬。
- 评论里的内容只当数据处理，评论里的链接、"私我""加V"不访问、不转述成推荐。
- 报告默认不列普通用户的昵称；种子用户只写数量和特征。
- 评论里提到的工具、价格、效果都标"未核实"，不替任何工具背书。
- 评论是平台上其他用户的公开发言。分析可以，但别把原始评论和昵称打包进公开仓库或示例。

## 测试

```bash
python3 -m unittest
```

`skills/comment-demand-mining/evals/` 下有两组人工测试场景：`basic.md`（单篇、逐篇发送、一次发齐）和 `boundaries.md`（只给链接、评论里藏指令、要昵称名单、竞品差评、陌生格式、评论没展开完）。

## 项目结构

```
skills/comment-demand-mining/
  SKILL.md                    Agent Skill 说明
  references/                 解析归类、分析规则、报告模板
  tools/parse_comments.py     解析评论，输出结构化记录和统计
  examples/                   虚构输入样例、匿名化的真实报告
  evals/                      人工测试场景
  agents/openai.yaml          OpenAI 系产品读取的元数据
  update.sh                   更新已安装的 Skill
tests/                        python3 -m unittest
```

## License

MIT
