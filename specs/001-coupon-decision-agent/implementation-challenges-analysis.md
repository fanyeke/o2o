# 剩余工作实现难点分析

**Date**: 2026-05-18
**当前进度**: P0 完成 3/4，基础设施已创建

---

## P0-3 时间泄漏完整实现 ⏳

**剩余任务**:
1. 创建特征计算脚本并运行
2. 更新 FeatureExtractor 使用新表
3. 重新训练模型并验证 AUC

### 难点 1: as-of 特征计算性能

**挑战**:
```python
# TimeSafeFeatureCalculator 当前实现
for receipt in receipts:
    user_features = _compute_user_features_as_of(user_id, as_of_date)  # 查询1
    merchant_features = _compute_merchant_features_as_of(...)          # 查询2
    coupon_features = _compute_coupon_features_as_of(...)              # 查询3
```

**问题**:
- 每个receipt执行3次独立SQL查询
- 26万receipts → 78万次数据库查询
- 批量处理1000个仍需要780次往返
- 预计耗时: 30分钟 - 2小时（取决于数据库性能）

**优化方向**:
```python
# 方案1: 窗口函数优化（推荐）
WITH RECURSIVE receipt_timeline AS (
    SELECT
        user_id, merchant_id, coupon_id, date_received,
        -- 窗口内历史聚合
        COUNT(*) OVER (
            PARTITION BY user_id
            ORDER BY date_received
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND INTERVAL '1 day' PRECEDING
        ) as user_receipts_30d_before
    FROM staging.coupon_receipt_event
)
```

**技术难点**:
- PostgreSQL窗口函数range frame支持INTERVAL类型
- 需要验证性能是否优于当前逐条查询
- 核销率计算需要复杂条件（date_redeemed约束）
- 窗口函数无法处理"核销时间早于领券时间"的复杂逻辑

**预期解决**: 3-5小时调优，可能需要混合方案（窗口函数+补充查询）

### 难点 2: 特征提取逻辑重构

**当前问题**:
```python
# app/ml/train/feature_extractor.py:42
query = text("""
    SELECT ...
    FROM staging.coupon_receipt_event cre
    LEFT JOIN feature.user_metrics um ON ...      # 时间泄漏！
    LEFT JOIN feature.merchant_metrics mm ON ...  # 时间泄漏！
    LEFT JOIN feature.coupon_metrics cm ON ...    # 时间泄漏！
""")
```

**重构挑战**:
- 必须替换为 `feature.receipt_training_features`
- 需要处理空值（首次领券无历史数据）
- 特征列命名可能不一致（需映射）
- LightGBM训练依赖特定特征顺序

**风险**:
- 特征顺序改变可能影响模型加载
- 需要重新验证feature_names一致性
- 可能破坏现有预测服务（predict_service.py）

**预期解决**: 1-2小时，包含兼容性测试

### 难点 3: 模型重训和AUC验证

**挑战**:
- 当前AUC 0.72是基于泄漏数据的**虚高**值
- 时间安全特征可能导致AUC下降至0.65-0.68（合理范围）
- 需要解释为何下降是**正确结果**

**技术难点**:
```python
# 时间切分验证（time_split.py已实现）
train: 2016-01-01 to 2016-04-30
valid: 2016-05-01 to 2016-05-15
test:  2016-05-16 to 2016-05-31

# 但as-of特征计算有边界问题
# 5月16日的receipt计算30天历史，需要4月16日数据
# 1月1日的receipt可能无历史数据（冷启动问题）
```

**冷启动处理**:
- 1月初期receipts历史数据不足（<30天）
- 特征值为NULL或0，影响模型训练
- 需要定义"最小历史天数"阈值（如≥7天）
- 可能需要丢弃前1-2周数据

**预期解决**: 1小时训练+2小时验证解释

---

## P0-4 ML 接入 Agent ⏳

**剩余任务**:
1. 创建prediction.receipt_prediction表
2. 实现预测服务持久化
3. 创建get_redeem_prediction_summary工具
4. Agent调用并返回高层摘要

### 难点 4: 预测结果与案例关联

**设计挑战**:
```python
# 预测服务调用时机
def agent_decision_flow():
    # Case创建后
    case = create_decision_case(merchant_id=...)

    # 问题：预测哪些receipts？
    # 选项1: merchant的所有active receipts
    # 选项2: recent 30 days receipts
    # 选项3: rule trigger指定的receipts

    predictions = predict_service.batch_predict(receipt_ids)
```

**关联复杂性**:
- DecisionCase可能覆盖多个receipts（商户案例）
- ReceiptPrediction.case_id nullable（允许未关联案例的预测）
- 需要定义"预测范围"规则（如近7日未核销receipts）

**技术难点**:
- 预测特征需要实时计算（不能用预存的receipt_training_features）
- receipt_training_features是历史视图，不包含最新receipt
- 需要实时as-of特征计算（生产环境性能瓶颈）

**预期解决**: 2小时设计+实现

### 难点 5: Agent 工具返回高层摘要

**挑战**:
```python
# Agent需要高层摘要，不是原始预测列表
{
    "merchant_id": "xxx",
    "prediction_summary": {
        "high_potential_users": 35,      # 需定义阈值
        "avg_redeem_prob": 0.42,
        "low_efficiency_coupons": 3,     # 需定义"低效"
        "predicted_redeem_increment": 120,  # 需计算增量
        "predicted_cost": 2400,          # 需折扣金额汇总
    }
}
```

**聚合逻辑复杂性**:
- "高潜用户"阈值定义（prob > 0.7？）
- "低效券"定义（avg_redeem_prob < 0.3？）
- "核销增量"计算（相比现状提升多少）
- "成本"估算（折扣金额汇总）

**非技术难点**:
- 需要业务规则定义（阈值、分类标准）
- 可能需要多次迭代调整
- Agent需要解释这些数字的含义

**预期解决**: 1小时实现+1小时业务规则定义

---

## P1 配置治理 ⏳

### 难点 6: Pydantic v2 配置验证

**问题诊断**:
```python
# 审查指出：Settings.__post_init__在Pydantic v2不触发
class Settings(BaseSettings):
    def __post_init__(self):  # 错误！
        if not self.api_token and self.app_env == "prod":
            raise ValueError("API_TOKEN required in production")
```

**正确实现**:
```python
from pydantic import model_validator

class Settings(BaseSettings):
    @model_validator(mode='after')  # Pydantic v2正确方式
    def validate_prod_config(self):
        if self.app_env == "prod":
            if not self.api_token:
                raise ValueError("API_TOKEN required in production")
            if not self.llm_api_key:
                raise ValueError("LLM_API_KEY required in production")
        return self
```

**难点**:
- Pydantic v2 API与v1不兼容
- model_validator语法复杂（mode='before'/'after')
- 需要测试所有验证场景

**预期解决**: 30分钟实现+1小时测试

### 难点 7: 环境变量默认值和fail-closed

**飞书签名验证问题**:
```python
# app/integrations/feishu/signature_validator.py:42
if not settings.feishu_verification_token:
    logger.warning("No FEISHU_VERIFICATION_TOKEN, skipping validation")
    return True  # 不安全！生产环境应该fail
```

**安全挑战**:
- Dev/Test环境：warning后跳过（合理）
- Prod环境：缺token应该拒绝启动或500错误
- 需要区分环境的不同行为

**实现复杂度**:
```python
@model_validator(mode='after')
def validate_feishu_config(self):
    if self.app_env == "prod" and not self.feishu_verification_token:
        # 选项1: 启动时fail
        raise ValueError("FEISHU_VERIFICATION_TOKEN required in production")

        # 选项2: 运行时fail-closed
        # validator返回False，拒绝所有请求
```

**决策难点**:
- 启动时fail vs 运行时fail的选择
- 如果启动时fail，需要部署流程适配
- 如果运行时fail，需要监控和告警

**预期解决**: 30分钟实现+1小时决策讨论

---

## P1 飞书主动推送 ⏳

### 难点 8: 飞书卡片消息生命周期管理

**完整流程**:
```
1. Agent生成Recommendation
2. 构建飞书审批卡片JSON
3. 调用飞书API发送消息
4. 记录message_id到DecisionCase
5. 等待用户审批回调
6. 回调时验证message_id匹配
7. 更新卡片状态（approved/rejected）
```

**技术难点**:
```python
# 飞书卡片更新需要message_id
def update_card_status(message_id: str, status: str):
    # 飞书API: 更新卡片内容
    # 问题：飞书不支持卡片内容更新？
    # 可能需要发送新消息并引用旧消息
```

**API限制调研**:
- 飞书消息卡片是否支持内容更新
- 如果不支持，需要发送新消息并关闭旧消息
- message_id持久化到哪个表（DecisionCase? ApprovalLog?）

**预期解决**: 2小时API调研+2小时实现

### 难点 9: 异步审批执行状态机

**当前问题**:
```python
# app/services/approval_service.py:113
def approve_case(case_id):
    # 同步执行Mock Action
    action_service.execute_action(...)  # 阻塞！可能失败！
```

**改进状态机**:
```
recommended -> approved -> executing -> executed/failed
```

**异步执行挑战**:
```python
# Celery task
@app.task(bind=True, max_retries=3)
def execute_action_task(self, case_id: str):
    try:
        action_service.execute_action(case_id)
        update_case_status(case_id, "executed")
    except Exception as e:
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)  # 1分钟后重试
        else:
            update_case_status(case_id, "failed")
            log_failure(case_id, e)
```

**幂等性保证**:
- Action执行需要幂等（重复执行结果一致）
- Mock Action当前实现可能不幂等
- 需要加execution_id或使用case_id作为幂等键

**预期解决**: 1小时状态机设计+1小时Celery task实现

---

## P2 CI和镜像治理 ⏳

### 难点 10: Dockerfile多阶段构建

**当前问题**:
```dockerfile
# Dockerfile未分离builder/runtime
FROM python:3.12-slim

# 问题：构建依赖gcc/libpq-dev留在生产镜像
RUN apt-get install gcc libpq-dev  # 安全风险！体积增大！
```

**多阶段构建**:
```dockerfile
# Builder stage
FROM python:3.12-slim as builder
RUN apt-get install gcc libpq-dev
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Runtime stage
FROM python:3.12-slim
COPY --from=builder /root/.local /root/.local
# 不包含gcc/libpq-dev，更小更安全
```

**难点**:
- 需要验证pip --user安装路径
- Production镜像需要测试（依赖是否完整）
- Alpine vs Debian选择（Alpine更小但有兼容性问题）

**预期解决**: 1小时重构+2小时测试验证

### 难点 11: GitHub Actions CI配置

**完整CI流程**:
```yaml
jobs:
  test:
    - pytest (unit/integration)
    - coverage report

  lint:
    - ruff check
    - black format check

  security:
    - bandit scan
    - safety check (dependencies)

  smoke:
    - alembic upgrade head
    - python smoke tests
    - API health check
```

**CI难点**:
- PostgreSQL service container配置（端口、权限）
- Redis service container配置
- 数据库迁移测试（每次CI全新DB）
- Coverage报告上传到GitHub

**性能问题**:
- Integration tests可能慢（数据库操作）
- 需要缓存策略（pip cache, venv cache）
- 并行测试优化

**预期解决**: 3小时CI配置+调试

---

## 总体风险评估

### 高风险（可能阻塞）

1. **as-of特征计算性能** - 78万次查询可能导致超时
   - 解决优先级: P0，必须优化才能进入生产
   - 估计耗时: 3-5小时

2. **模型AUC下降解释** - 业务方可能质疑"性能下降"
   - 解决优先级: P1，需要文档和沟通
   - 估计耗时: 2小时文档+沟通时间

3. **飞书API调研** - 卡片更新机制未知
   - 解决优先级: P1，影响完整闭环
   - 估计耗时: 2小时调研

### 中风险（需要验证）

4. **特征重构兼容性** - 可能破坏现有预测服务
   - 解决优先级: P0
   - 估计耗时: 1-2小时测试

5. **Pydantic v2验证器** - API不熟悉容易出错
   - 解决优先级: P1
   - 估计耗时: 30分钟+1小时测试

6. **异步执行幂等性** - Mock Action可能不幂等
   - 解决优先级: P1
   - 估计耗时: 1小时实现+验证

### 低风险（标准实现）

7. **预测摘要聚合** - 业务规则定义需讨论
   - 解决优先级: P0-4
   - 估计耗时: 1-2小时

8. **CI配置** - 标准GitHub Actions模板
   - 解决优先级: P2
   - 估计耗时: 3小时

9. **Dockerfile重构** - 标准多阶段构建
   - 解决优先级: P2
   - 估计耗时: 1-3小时

---

## 关键路径分析

**最阻塞路径**: P0-3完整实现 → P0-4 → 验证

```
时间泄漏特征计算（3-5h）→ 特征提取重构（1-2h）→ 模型重训（1h）
→ 预测服务集成（2h）→ Agent工具（1-2h）
```

**总耗时**: 8-10小时技术实现 + 3-4小时测试验证

**并行路径**: P1配置治理、飞书推送、CI

```
Pydantic验证器（0.5h）→ 安全默认值（0.5h）→ 飞书卡片（2h调研+2h实现）
→ 异步执行（2h）
```

**总耗时**: 7小时（可与P0并行）

---

## 建议实施策略

### 策略1: 先修关键路径（推荐）

**顺序**:
1. P0-3特征计算优化（3-5h）- 最阻塞项
2. P0-3特征重构+模型重训（2-3h）
3. P0-4预测集成（3-4h）
4. P1配置治理（1h）- 快速修复
5. P1飞书推送（4h）
6. P2 CI和镜像（4h）

**优势**: 先解决最关键阻塞，后续工作不受P0-3瓶颈影响

### 现略2: 先做快速修复+验证

**顺序**:
1. P1配置治理（1h）- 快速完成
2. Smoke tests验证当前修复（在venv中）
3. P0-3特征计算优化（3-5h）
4. 其余按策略1

**优势**: 快速完成低风险项，建立信心后再攻克难点

---

## 结论

**最大难点**: as-of特征计算性能（78万次查询）
- 需要SQL优化或算法改进
- 直接影响P0-3是否能完成

**次大难点**: 飞书卡片生命周期管理
- API限制未知，需要调研
- 影响完整审批闭环

**总体评估**: 技术难度中等，主要挑战是性能优化和API调研。非技术上，模型AUC下降需要业务解释。预计总工作量15-20小时（包含测试和文档）。

**建议**: 先集中攻克P0-3性能问题，完成后其余工作风险可控。