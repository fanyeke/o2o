"""Decision prompt templates for Agent."""

from typing import Dict, Any
from app.domain.application.decision_case import DecisionCase


def build_decision_prompt(case: DecisionCase, tool_results: Dict[str, Any]) -> str:
    """Build decision prompt for DeepSeek LLM.

    Args:
        case: DecisionCase instance with trigger context
        tool_results: Dictionary of tool execution results

    Returns:
        Formatted prompt string
    """
    # Extract case context
    case_type = case.case_type
    merchant_id = case.merchant_id or "N/A"
    trigger_metrics = case.trigger_metrics_snapshot or {}

    # Format tool results as readable context
    tool_context = _format_tool_results(tool_results)

    prompt = f"""你是优惠券运营决策专家，负责分析商户优惠券活动异常并给出决策建议。

## 案例背景
- **案例类型**: {case_type}
- **商户ID**: {merchant_id}
- **触发规则**: {case.trigger_rule_id}
- **严重级别**: {case.severity_level}

## 触发指标快照
{_format_trigger_metrics(trigger_metrics)}

## 数据查证结果
以下是通过数据工具查询得到的详细指标数据，请基于这些证据进行分析：

{tool_context}

## 决策要求
请基于以上数据和证据，生成决策建议。要求：

1. **证据完整性**: 至少提供3条独立证据来支持你的结论，每条证据包含：
   - 类型（如"指标异常"、"发券规模"、"折扣分析"等）
   - 详细描述（具体数值和变化幅度）
   - 严重级别（高/中/低）

2. **建议动作**: 列出具体的可执行动作，包含：
   - 动作类型（如"暂停活动"、"调整折扣"、"发送优惠券"、"调整人群"等）
   - 执行参数（JSON对象，包含具体执行所需的参数，如merchant_id、coupon_id、duration、new_discount、user_ids等）
   - 优先级（高/中/低）

""" + """
示例：
- 暂停活动: {"merchant_id": "商户ID", "duration": "7天"}
- 调整折扣: {"coupon_id": "优惠券ID", "new_discount": "0.85"}
- 发送优惠券: {"user_ids": ["用户ID列表"], "coupon_id": "优惠券ID"}
- 调整人群: {"target_users": "目标人群描述"}
""" + f"""

3. **风险提示**: 指出可能的风险和后果

4. **置信度评分**: 给出0-1的置信度评分（基于证据充分性）

5. **审批需求**: 高风险动作（如暂停活动、大幅调整折扣）需要人工审批

## 输出格式
请以JSON格式输出，严格按照以下Schema：

""" + """
```json
{
  "summary": "决策摘要（一句话概述核心问题和建议）",
  "evidence_list": [
    {
      "type": "证据类型",
      "description": "证据描述",
      "severity": "严重级别"
    }
  ],
  "suggested_actions": [
    {
      "action_type": "动作类型",
      "params": {"key": "执行参数"},
      "priority": "优先级"
    }
  ],
  "risk_alerts": "风险提示文本",
  "confidence_score": 0.85,
  "requires_approval": true
}
```
""" + f"""

注意：
- evidence_list数组至少包含3个元素
- confidence_score为0-1的浮点数
- requires_approval为布尔值（高风险动作必须为true）
- 所有字符串内容必须使用中文

请开始分析并输出JSON格式的决策建议。
"""

    return prompt


def _format_trigger_metrics(metrics: Dict[str, Any]) -> str:
    """Format trigger metrics snapshot for prompt.

    Args:
        metrics: Trigger metrics dictionary

    Returns:
        Formatted metrics string
    """
    if not metrics:
        return "无触发指标数据"

    lines = []
    for key, value in metrics.items():
        if isinstance(value, float):
            lines.append(f"- {key}: {value:.2%}" if value < 1 else f"- {key}: {value}")
        else:
            lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def _format_tool_results(tool_results: Dict[str, Any]) -> str:
    """Format tool execution results for prompt.

    Args:
        tool_results: Dictionary of tool results

    Returns:
        Formatted tool results string
    """
    sections = []

    if "merchant_metrics" in tool_results:
        merchant_data = tool_results["merchant_metrics"]
        if merchant_data and "metrics" in merchant_data:
            # Extract metrics from nested structure
            metrics = merchant_data["metrics"]
            merchant_id = merchant_data.get("merchant_id", "N/A")
            sections.append(f"""### 商户指标
- 商户ID: {merchant_id}
- 近7日发券量: {metrics.get('total_receipts_7d', 0)}
- 近7日核销数: {metrics.get('redeemed_count_7d', 0)}
- 近7日核销率: {float(metrics.get('redeemed_rate_7d', 0)):.2%}
- 近30日发券量: {metrics.get('total_receipts_30d', 0)}
- 近30日核销数: {metrics.get('redeemed_count_30d', 0)}
- 近30日核销率: {float(metrics.get('redeemed_rate_30d', 0)):.2%}
- 核销率变化幅度: {float(metrics.get('redeemed_rate_change', 0)):.2%}
- 平均折扣深度: {float(metrics.get('avg_discount_depth', 0)):.2%}
- 活动健康分: {float(metrics.get('activity_health_score', 0)):.2f}""")

            # Add evidence if available
            if "evidence" in merchant_data and merchant_data["evidence"]:
                sections.append("\n### 证据列表")
                for i, item in enumerate(merchant_data["evidence"], 1):
                    sections.append(f"{i}. [{item.get('type', '未知')}] {item.get('content', '')}")

    if "coupon_conversion" in tool_results:
        coupon_data = tool_results["coupon_conversion"]
        if coupon_data and "coupons" in coupon_data:
            coupon_details = "\n".join([
                f"  - {c['coupon_id']}: {c.get('conversion_metrics', {}).get('discount_type', '未知')}, "
                f"核销率 {c.get('conversion_metrics', {}).get('redeemed_rate', 0):.2%}, "
                f"平均核销天数 {c.get('conversion_metrics', {}).get('avg_redeem_days', 0):.1f}天"
                for c in coupon_data.get("coupons", [])[:5]  # Limit to top 5
            ])

            sections.append(f"""### 优惠券转化数据
- 商户ID: {coupon_data.get('merchant_id', 'N/A')}
- 总券类型数: {coupon_data.get('total_coupons', 0)}
- 平均核销率: {sum([c.get('conversion_metrics', {}).get('redeemed_rate', 0) for c in coupon_data.get('coupons', [])]) / max(len(coupon_data.get('coupons', [])), 1):.2%}

券详情（前5个）:
{coupon_details}
""")

    if "user_metrics" in tool_results:
        user_data = tool_results["user_metrics"]
        if user_data:
            sections.append("""### 用户指标
- 用户ID: {user_id}
- 近30日领券数: {total_receipts_30d}
- 近30日核销数: {redeemed_count_30d}
- 近30日核销率: {redeemed_rate_30d:.2%}
- 平均距离: {avg_distance:.1f}档位
""".format(**user_data))

    if "recent_receipts" in tool_results:
        receipts = tool_results["recent_receipts"]
        if receipts:
            recent_summary = "\n".join([
                f"  - {r['date_received']}: {r['merchant_id']}/{r['coupon_id']}, "
                f"{'已核销' if r['is_redeemed'] else '未核销'}"
                for r in receipts[:5]  # Limit to top 5
            ])

            sections.append(f"""### 近期领券记录（前5条）
{recent_summary}
""")

    if not sections:
        return "无数据查证结果"

    return "\n\n".join(sections)