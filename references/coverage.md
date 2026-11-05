# 原书覆盖审查

## 审查方法

先从原书产生候选清单，再与已有成果对照。每个阅读单元核对概念、主张、方法步骤、案例、数字、条件、反例与争议；不强制每章都有所有类型。读者需要独立使用的内容可以拆卡；仅重复或支持主张的案例可以合并，但要登记去向。

“逐章有摘要”“已扫过全部页码”“候选要点全有链接”是不同指标。即便它们都是100%，也不能机械证明所有重要知识都已被发现。记录阅读者／审核方式、核对范围、疑点和排除理由；需要更高置信度时做一次独立重读或另一审核者抽查。只有环境与授权允许时才委派代理。

审核状态：

- `not_started`：尚未核对原文。
- `partial`：部分内容核对过，仍有缺口。
- `complete`：该单元已按所列范围逐段核对，疑点另列；不表示绝对无遗漏。

同一页可含多个章节，因此阅读单元的页码可以重叠。纳入和排除范围必须互斥且合起来覆盖整本文件。排除封面、版权页等也需写明理由，不把排除内容算为已提炼。

覆盖表的 `units` 表示连续阅读范围，`start/end` 之间的页均计入范围。跨页段的思想关系另记在关系索引中；不连续片段分为不同阅读单元，不能用首尾页包住中间未读页。

## coverage.json 格式

以下是字段示例；使用真实来源与真实内容替换值。路径相对于覆盖表所在目录，产出去向也应是该目录内的文件。脚本不会创建笔记或填充知识点。

```json
{
  "source": {"path": "source/book.pdf", "sha256": "真实文件的64位SHA-256", "pages": 3},
  "scope": {
    "included": [{"start": 2, "end": 3}],
    "excluded": [{"start": 1, "end": 1, "reason": "封面，不参与知识提炼"}]
  },
  "units": [
    {
      "id": "chapter-01", "title": "原书第一章", "start": 2, "end": 3,
      "review_status": "partial",
      "review_notes": "已核对核心概念，例外条件待复核"
    }
  ],
  "items": [
    {
      "id": "point-001", "unit_id": "chapter-01", "kind": "concept",
      "source_pages": [2], "point": "用自己的话说明原书的一个知识点",
      "attribution": "book", "disposition": "covered",
      "targets": ["notes/chapter-01.md"], "reason": "",
      "review_status": "complete"
    },
    {
      "id": "point-002", "unit_id": "chapter-01", "kind": "boundary",
      "source_pages": [3], "point": "待核对的方法适用条件",
      "attribution": "book", "disposition": "pending",
      "targets": [], "reason": "尚未写入解析",
      "review_status": "not_started"
    }
  ]
}
```

`kind` 可取：`concept`、`claim`、`method`、`case`、`number`、`boundary`、`counterexample`、`question`、`theme`、`other`。

`attribution` 为 `book` 或 `editor`。整理者补充用 `editor`，并记录其与原文的联系；它不能算作原书知识的新增覆盖。

确无可提炼原书候选的单元，可添加 `no_book_candidates_reason`（非空理由），仍须登记审核状态与记录，不虚构要点。已有原书候选时不能使用该例外。输出的 `units_without_book_candidates` 列出所有空单元，`book_candidate_exceptions` 列出理由；未登记例外的空单元阻止完成。若整份清单无原书候选，`recorded_book_candidates_empty=true` 且 `recorded_review_complete=false`，即使全部登记例外也须单独说明。

`disposition`：

- `covered`：已独立写入成果，列出目标文件。
- `merged`：已并入其他条目，列出目标文件，并解释在哪里合并。
- `excluded`：经判断不纳入提炼，说明理由。
- `pending`：尚未处理，保留为缺口。

`targets` 支持 `notes/topic.md` 或 `index.html#section-id`。脚本检查文件存在但不检查锚点；锚点须另做网页校验。按章节或页码检索同一候选清单，避免覆盖表本身只登记已完成项。

## 脚本运行

Python ≥3.11，仅使用标准库。在任意目录执行：

```bash
python3 <skill目录>/scripts/audit_coverage.py <项目目录>/coverage.json
python3 <skill目录>/scripts/test_audit_coverage.py
```

覆盖表内路径相对覆盖表所在目录解析。检查结果输出为 JSON；退出码 `0`＝结构有效，`1`＝校验失败，`2`＝命令参数错误。存在 `pending` 时仍可返回 `0`，完成状态须另读 `recorded_review_complete`，并查看空候选、例外及错误字段。测试命令退出码 `0` 表示用例通过，`1` 表示失败。

## 交付结论的措辞

分别报告：

1. 原书页数与范围登记情况。
2. 纳入范围中有对应阅读单元的页数。
3. 已完成核对的单元数。
4. 已登记原书要点中，已覆盖／合并／排除／待处理的数量。
5. 具体遗漏、来源疑点与下一步。

脚本的 `recorded_review_complete` 只表示清单记录闭合。即使为true，也必须附“基于已登记候选要点”的口径，不宣称机器证明全书无遗漏。
