请对整个 Merge Request 进行一次性审查，不要分片处理。

输入数据中：
- `meta`：MR 总文件数、总提交数
- `files`：每个变更文件的最终 diff 与该文件在 MR 内的提交历史摘要（已压缩，不包含原始历史 diff 文本）

审查要求：
1. 审查所有 changed files，包括新增、修改、删除、重命名文件。
2. 如果某个文件在 MR 内经历了“创建 -> 修改 -> 删除”或多次变更，要结合 `commit_history.touch_count`、`change_type_path`、`first_commit`、`last_commit`、`recent_commits` 判断风险，不要只看最终 diff 文本表面。
3. 输出要能支撑 GitLab 行级评论，所以问题项应尽量包含：
   - `file_path`
   - `line_start`
   - `line_end`
   - `line_side` (`new` 或 `old`)
4. 如果问题能准确定位到最终 diff 的某一行，必须给出定位信息。
5. 如果问题明确存在但无法稳定定位到最终 diff 行，请将定位字段设为 null。
6. 忽略纯格式和纯命名建议，优先输出真正影响合并决策的问题。
7. 除了已确认缺陷，也要尽量覆盖高风险疑点，尤其关注：参数校验缺失、空指针/空集合风险、边界条件遗漏、状态流转不闭合、权限绕过、SQL/命令注入、事务一致性、幂等性、兼容性回归、枚举/字段迁移不完整、删除/重命名导致的调用链断裂。
8. 如果问题是“高风险疑点”而不是完全坐实的缺陷，`reason` 必须写清触发依据，`suggestion` 必须给出具体验证或修复方向，`confidence` 不要滥用 `high`。
9. `overall_summary` 先概括本次 MR 的主要改动，再总结整体风险和合并建议。

输出必须符合系统提供的 JSON Schema。
