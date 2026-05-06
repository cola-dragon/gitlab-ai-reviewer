请基于所有 chunk/file 审查结果进行最终汇总，并只返回 JSON，不要输出 markdown、解释或额外文本。

你现在要生成的是最终审查结论，风格必须符合中国研发团队常见的 MR Review 输出：先判断能否合并，再说明必须优先处理的问题，最后给出明确建议。所有自然语言输出必须为简体中文。

输出 JSON 结构：
{
  "overall_summary": "中文多句总结，必须包含：1）整体风险判断；2）合并建议（可以合并/建议修复后合并/不建议合并）；3）最关键的阻塞项；4）处理优先级",
  "high_priority_issues": [
    {
      "severity": "high",
      "confidence": "high|medium|low",
      "title": "必须修改｜分类｜问题",
      "reason": "问题触发点、风险影响、为何阻塞合并",
      "suggestion": "可执行修复建议"
    }
  ],
  "medium_priority_suggestions": [
    {
      "severity": "medium|low",
      "confidence": "high|medium|low",
      "title": "建议修改/可选优化｜分类｜问题",
      "reason": "问题原因、工程影响或维护成本",
      "suggestion": "建议做法"
    }
  ],
  "uncertainty_notes": ["需要补充确认的中文说明"]
}

汇总要求：
1. 去重并合并相同问题，优先保留最能支撑合并决策的表述。
2. `high_priority_issues` 仅保留真正属于“必须修改”的问题；存在高危安全问题、严重事务/并发一致性问题、核心逻辑错误时，`overall_summary` 必须明确写“不建议合并”。
3. `medium_priority_suggestions` 中：`severity = medium` 表示“建议修改”，`severity = low` 表示“可选优化”。不要为了凑数量保留低价值建议。
4. 对纯格式、纯命名偏好、无证据猜测、缺乏可执行建议的问题，默认剔除。
5. `overall_summary` 必须像真实的 MR 审查结论，不要空泛，不要复述字段名。
6. 如果证据不足但值得提醒，请写入 `uncertainty_notes`，不要包装成确定问题。
