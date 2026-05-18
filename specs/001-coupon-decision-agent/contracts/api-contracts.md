# API Contracts: 优惠券运营决策 Agent 系统

**Feature**: 001-coupon-decision-agent | **Date**: 2026-05-17

## Overview

本文档定义 REST API 端点契约，遵循 OpenAPI 3.0 规范，支持 FastAPI 路由实现和前端集成。

---

## Authentication

### 飞书 OAuth (审批流程)

- **Header**: `Authorization:Bearer <飞书_access_token>`
- **验证**: 飞书签名验证（HMAC-SHA256）
- **适用端点**: POST /api/v1/approvals/callback, GET /api/v1/cases/{id}

### API Token (Dashboard访问)

- **Header**: `X-API-Token: <api_token>`
- **验证**: Token 存储在环境变量或配置文件
- **适用端点**: GET /api/v1/metrics/*, GET /api/v1/cases/*, POST /api/v1/rules/scan

---

## API Endpoints

### 1. Health Check (已实现)

**GET /api/v1/health**

**Description**: 系统健康检查，验证数据库和Redis连接。

**Headers**: 无需认证

**Response 200**:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "healthy",
  "redis": "healthy"
}
```

**Response 503** (降级):
```json
{
  "status": "degraded",
  "version": "0.1.0",
  "database": "unhealthy",
  "redis": "unhealthy"
}
```

---

### 2. 数据导入触发 (已实现)

**POST /api/v1/datasets/import**

**Description**: 触发CSV数据导入到Raw层（异步Celery任务）。

**Headers**: X-API-Token

**Response 202** (Accepted):
```json
{
  "status": "accepted",
  "message": "Import task submitted. Task ID: <celery_task_id>",
  "task_id": "abc123"
}
```

**Errors**:
- 401 Unauthorized: Token无效
- 500 Internal Server Error: Celery连接失败

---

### 3. 商户指标查询

**GET /api/v1/metrics/merchants**

**Description**: 查询商户聚合指标，支持筛选和排序。

**Headers**: X-API-Token

**Query Parameters**:
- `merchant_id` (optional): 指定商户ID
- `min_receipts` (optional): 最小发券量筛选
- `redeemed_rate_range` (optional): 核销率范围（如 "0.5,0.8"）
- `sort_by` (optional): 排序字段（"redeemed_rate_change", "total_receipts_7d"）
- `order` (optional): 排序方向（"asc", "desc"）
- `limit` (optional): 返回数量限制（默认100）
- `offset` (optional): 分页偏移

**Response 200**:
```json
{
  "total": 150,
  "limit": 100,
  "offset": 0,
  "data": [
    {
      "merchant_id": "xxx",
      "total_receipts_7d": 500,
      "redeemed_rate_7d": 0.45,
      "total_receipts_30d": 2000,
      "redeemed_rate_30d": 0.65,
      "redeemed_rate_change": -0.30,
      "avg_discount_depth": 0.25,
      "activity_health_score": 0.72,
      "updated_at": "2026-05-17T00:00:00Z"
    }
  ]
}
```

**Errors**:
- 400 Bad Request: 参数格式错误
- 401 Unauthorized: Token无效

---

### 4. 用户指标查询

**GET /api/v1/metrics/users**

**Description**: 查询用户聚合指标。

**Headers**: X-API-Token

**Query Parameters**:
- `user_id` (optional): 指定用户ID
- `min_receipts` (optional): 最小领券量筛选
- `limit` (optional): 返回数量限制

**Response 200**:
```json
{
  "total": 10000,
  "limit": 100,
  "data": [
    {
      "user_id": "yyy",
      "total_receipts_30d": 15,
      "redeemed_count_30d": 8,
      "redeemed_rate_30d": 0.53,
      "avg_distance": 2.5,
      "last_receipt_date": "2016-06-20",
      "updated_at": "2026-05-17T00:00:00Z"
    }
  ]
}
```

---

### 5. 优惠券指标查询

**GET /api/v1/metrics/coupons**

**Description**: 查询优惠券聚合指标。

**Headers**: X-API-Token

**Query Parameters**:
- `coupon_id` (optional): 指定优惠券ID
- `merchant_id` (optional): 指定商户ID（查询该商户的券）
- `discount_type` (optional): 券类型筛选（"满减", "折扣"）
- `min_redeemed_rate` (optional): 最小核销率筛选

**Response 200**:
```json
{
  "total": 120,
  "data": [
    {
      "coupon_id": "zzz",
      "merchant_id": "xxx",
      "discount_type": "满减",
      "discount_rate": "200:50",
      "discount_value": 0.25,
      "total_receipts": 500,
      "redeemed_count": 250,
      "redeemed_rate": 0.50,
      "avg_redeem_days": 7.5,
      "updated_at": "2026-05-17T00:00:00Z"
    }
  ]
}
```

---

### 6. 决策案例列表查询

**GET /api/v1/cases**

**Description**: 查询决策案例列表，支持筛选和分页。

**Headers**: X-API-Token 或 飞书OAuth

**Query Parameters**:
- `status` (optional): 状态筛选（"pending", "recommended", "approved", "rejected", "executed"）
- `case_type` (optional): 案例类型筛选（"商户异常", "券策略复核", "用户召回"）
- `merchant_id` (optional): 商户ID筛选
- `severity_level` (optional): 严重级别筛选（"高", "中", "低"）
- `created_after` (optional): 创建时间起始（ISO 8601格式）
- `created_before` (optional): 创建时间结束
- `limit` (optional): 返回数量限制
- `offset` (optional): 分页偏移

**Response 200**:
```json
{
  "total": 25,
  "limit": 20,
  "offset": 0,
  "data": [
    {
      "id": 1,
      "case_type": "商户异常",
      "severity_level": "高",
      "merchant_id": "xxx",
      "trigger_rule_id": "merchant_redeemed_rate_drop",
      "status": "recommended",
      "created_at": "2026-05-17T10:00:00Z",
      "updated_at": "2026-05-17T10:30:00Z"
    }
  ]
}
```

---

### 7. 决策案例详情查询

**GET /api/v1/cases/{case_id}**

**Description**: 查询单个案例完整详情（含指标快照、Agent建议、审批记录）。

**Headers**: X-API-Token 或 飞书OAuth

**Path Parameters**:
- `case_id` (required): 案例ID

**Response 200**:
```json
{
  "id": 1,
  "case_type": "商户异常",
  "severity_level": "高",
  "merchant_id": "xxx",
  "trigger_rule_id": "merchant_redeemed_rate_drop",
  "trigger_metrics_snapshot": {
    "redeemed_rate_7d": 0.45,
    "redeemed_rate_30d": 0.65,
    "redeemed_rate_change": -0.30
  },
  "status": "recommended",
  "recommendation": {
    "id": 10,
    "summary": "建议暂停商户xxx活动7天，核销率异常下降",
    "evidence_list": [
      {"type": "指标异常", "content": "..."},
      {"type": "券策略问题", "content": "..."},
      {"type": "历史对比", "content": "..."}
    ],
    "suggested_actions": [
      {"action_type": "暂停活动", "params": {...}, "risk_level": "高"}
    ],
    "risk_alerts": "暂停活动可能导致短期收入下降",
    "confidence_score": 0.85,
    "requires_approval": true,
    "created_at": "2026-05-17T10:30:00Z"
  },
  "approval_logs": [
    {
      "operator_name": "运营人员A",
      "action": "approve",
      "comment": "同意暂停活动",
      "created_at": "2026-05-17T11:00:00Z"
    }
  ],
  "action_executions": [
    {
      "action_type": "暂停活动",
      "execution_status": "success",
      "executed_at": "2026-05-17T11:05:00Z"
    }
  ],
  "created_at": "2026-05-17T10:00:00Z",
  "updated_at": "2026-05-17T11:05:00Z"
}
```

**Errors**:
- 404 Not Found: 案例不存在
- 401 Unauthorized: 认证失败

---

### 8. 飞书审批回调接口

**POST /api/v1/approvals/callback**

**Description**: 接收飞书审批卡片回调，记录审批结果。

**Headers**: 无需Token，验证飞书签名

**Body** (飞书卡片回调格式):
```json
{
  "challenge": "xxx" (optional, 首次验证),
  "type": "card_action",
  "action": {
    "value": {
      "case_id": 1,
      "action_type": "approve" or "reject",
      "operator_id": "飞书用户ID",
      "comment": "审批意见"
    }
  },
  "token": "飞书verification_token",
  "timestamp": 1234567890,
  "sign": "飞书签名"
}
```

**Response 200**:
```json
{
  "status": "success",
  "message": "Approval recorded",
  "case_id": 1,
  "new_status": "approved"
}
```

**Validation**:
- 验证飞书签名（HMAC-SHA256）
- 验证 timestamp（防重放攻击，±5分钟有效）
- 验证 operator_id（飞书用户身份）

**Errors**:
- 400 Bad Request: 签名验证失败
- 404 Not Found: case_id不存在
- 409 Conflict: 案例状态冲突（并发审批）

---

### 9. 规则扫描触发

**POST /api/v1/rules/scan**

**Description**: 手动触发规则扫描，生成DecisionCases。

**Headers**: X-API-Token (管理员权限)

**Body**:
```json
{
  "rule_ids": ["merchant_redeemed_rate_drop", "high_discount_low_conversion"] (optional, 默认扫描所有规则),
  "dry_run": false (optional, 为true时不创建案例仅返回匹配结果)
}
```

**Response 202** (Accepted):
```json
{
  "status": "accepted",
  "message": "Rule scan task submitted. Task ID: <celery_task_id>",
  "task_id": "def456"
}
```

---

### 10. Agent 建议重新生成

**POST /api/v1/cases/{case_id}/regenerate**

**Description**: 审批拒绝后重新触发Agent生成建议。

**Headers**: 飞书OAuth (运营人员权限)

**Path Parameters**:
- `case_id` (required): 案例ID

**Response 202**:
```json
{
  "status": "accepted",
  "message": "Agent regeneration task submitted",
  "task_id": "ghi789"
}
```

**Validation**:
- 案例状态 MUST be "rejected"（只能在驳回后重新生成）

**Errors**:
- 400 Bad Request: 案例状态不允许重新生成
- 401 Unauthorized: 非运营人员权限

---

## Error Responses Format

所有错误响应使用统一格式：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  }
}
```

**Common Error Codes**:
- `AUTHENTICATION_FAILED`: Token无效或签名验证失败
- `NOT_FOUND`: 资源不存在
- `VALIDATION_ERROR`: 参数格式错误
- `STATE_TRANSITION_ERROR`: 状态转换不合法
- `INTERNAL_ERROR`: 内部服务器错误

---

## Rate Limiting

- **默认限制**: 100 requests/minute per API Token
- **飞书回调**: 无限制（飞书平台保证）

---

## Pagination

所有列表查询支持分页：
- `limit`: 单次返回数量（默认20，最大1000）
- `offset`: 偏移量（默认0）
- Response包含 `total` 总数和 `limit`、`offset` 当前值

---

## Sorting

支持 `sort_by` 和 `order` 参数：
- `sort_by`: 排序字段（如 "redeemed_rate_change", "created_at"）
- `order`: "asc" 或 "desc"

---

## Filtering

支持多种筛选参数组合，所有筛选参数为 optional。

---

## Next Steps

- 使用 FastAPI 路由实现各端点
- 编写 Pydantic schemas 定义请求/响应结构
- 实现飞书签名验证中间件
- 实现API Token验证中间件
- 编写集成测试覆盖各端点
