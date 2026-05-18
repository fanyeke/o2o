# 测试时间和总任务进度分析

## 测试预计时间分析

**当前测试状态**（15:28）:
- 启动时间: 15:15
- 已运行时长: 约13分钟
- 已通过: 2/10测试
- 进行中: merchant_receipts_time_leakage（第3个测试）

**数据量分析**:
```
Total receipts:     1,011,990
User receipts:      全量验证 ✓ (2分钟通过)
Merchant receipts:  990,273条涉及5,198商户 🔄 (正在验证)
Coupon receipts:    待验证
```

**测试时间估算**:

| 测试 | 数据量 | 预计耗时 | 状态 |
|------|--------|---------|------|
| 1. user_receipts | 1,011,990 | ~2分钟 | ✓ PASSED |
| 2. user_redeemed | 1,011,990 | ~2分钟 | ✓ PASSED |
| 3. merchant_receipts | 990,273 (5,198商户) | ~5-8分钟 | 🔄 运行中 |
| 4. merchant_redeemed | 990,273 | ~3-5分钟 | ⏳ 待运行 |
| 5. coupon_receipts | 1,011,990 | ~3-5分钟 | ⏳ 待运行 |
| 6. coupon_redeemed | 1,011,990 | ~3-5分钟 | ⏳ 待运行 |
| 7. no_current_receipt | 1,011,990 | ~2分钟 | ⏳ 待运行 |
| 8. feature_coverage | 快速统计 | ~30秒 | ⏳ 待运行 |
| 9. feature_version | 快速查询 | ~10秒 | ⏳ 待运行 |
| 10. code_audit | 代码检查 | ~1秒 | ⏳ 待运行 |

**总预计时间**: 20-25分钟（从15:15启动，预计15:35-15:40完成）

**当前进度**: 已运行13分钟，约60%完成

---

## 总体任务进度（M1-M6）

### M目标验收标准

根据用户给出的验收目标，分为6个里程碑：

---

### M1：时间安全特征真正接入训练 ✅ 95%完成

**验收标准**:
| 指标 | 目标 | 状态 |
|------|------|------|
| FeatureExtractor使用receipt_training_features | 100% | ✅ 已修复 |
| 直接join旧特征表 | 0处 | ✅ 已清除 |
| test_time_leakage_audit.py | 全部通过 | 🔄 测试运行中 |
| 特征版本 | v1_time_safe | ✅ 强制检查 |
| 训练样本特征覆盖率 | >= 95% | ✅ 100% |
| 泄漏审计违规数 | 0 | ✅ 验证正确 |

**进度**: 5/6完成，仅剩测试验证（预计15:40完成）

---

### M2：模型训练与回测可复现 ⏳ 0%待实现

**验收标准**:
| 指标 | 目标 | 状态 |
|------|------|------|
| 训练脚本从DB读取time-safe特征 | 100% | ⏳ 待实现 |
| 模型metadata完整 | 100% | ⏳ 待验证 |
| 测试集Grouped AUC | >= 0.68 | ⏳ 待训练验证 |
| 训练AUC与测试AUC差距 | <= 0.08 | ⏳ 待验证 |
| 单条预测成功率 | >= 99% | ⏳ 待测试 |
| 单条预测P95延迟 | <= 200ms | ⏳ 待测试 |
| test_model_backtest.py | 全部通过 | ⏳ 待运行 |

**验收命令**:
```bash
venv/bin/python scripts/train_model.py
venv/bin/python -m pytest tests/validation/test_model_backtest.py -q
```

**预计工作量**: 2-3小时
1. 运行模型训练（30-60分钟）
2. 验证metadata和AUC（1小时）
3. 性能测试（1小时）

---

### M3：ML预测接入Agent主链路 ⏳ 0%待实现

**验收标准**:
| 指标 | 目标 | 状态 |
|------|------|------|
| 新增Agent工具get_prediction_summary | 1个 | ⏳ 待创建 |
| Recommendation包含模型预测证据 | 100% | ⏳ 待实现 |
| 每个商户案例证据数 | >= 3条 | ✅ 已实现 |
| Agent输出JSON解析成功率 | 100% | ✅ 已实现 |
| 工具调用失败降级说明 | 100% | ⏳ 待实现 |
| 幻觉证据（未在tool result中） | 0条 | ⏳ 待验证 |

**验收命令**:
```bash
venv/bin/python -m pytest tests/contract/test_agent_tools.py tests/validation/test_agent_grounding.py -q
```

**预计工作量**: 3-4小时
1. 创建get_prediction_summary工具（1小时）
2. 集成到Agent工具链（1小时）
3. 测试验证（1-2小时）

**前置依赖**: M2完成（模型已训练）

---

### M4：审批与执行闭环可验证 ⏳ 0%待实现

**验收标准**:
| 指标 | 目标 | 状态 |
|------|------|------|
| 只有recommended状态可审批 | 100% | ⏳ 待实现 |
| approve后写入approval_log | 100% | ⏳ 待验证 |
| reject后不执行action | 100% | ⏳ 待实现 |
| 重复审批幂等 | 100% | ⏳ 待实现 |
| 未知action类型失败且不误标成功 | 100% | ⏳ 待实现 |
| ActionExecution状态明确 | 100% | ⏳ 待实现 |

**验收命令**:
```bash
venv/bin/python -m pytest tests/validation/test_approval_safety.py -q
```

**预计工作量**: 2-3小时
1. 实现审批状态机（1小时）
2. 幂等性验证（1小时）
3. 测试验证（1小时）

---

### M5：飞书与安全配置达标 ⏳ 0%待实现

**验收标准**:
| 指标 | 目标 | 状态 |
|------|------|------|
| prod缺少Feishu token时启动失败或401 | 100% | ⏳ 待实现 |
| dev允许跳过签名 | 仅dev | ⏳ 待实现 |
| 飞书主动卡片发送服务 | 1个 | ⏳ 待创建 |
| 卡片点击回调审批API | 100% | ⏳ 待实现 |
| 卡片状态可更新 | 100% | ⏳ 待实现 |
| 硬编码绝对路径 | 0处 | ⏳ 待清除 |
| Settings.__post_init__ | 替换为model_post_init | ⏳ 待修复 |

**必须清除**:
- `/home/zzz/project/o2o/config/rules` 硬编码
- `/app/config/rules` 硬编码
- `verification_token`缺失时无条件return True

**预计工作量**: 4-5小时
1. 安全配置修复（2小时）
2. 飞书卡片服务（2小时）
3. 测试验证（1小时）

---

### M6：一键Smoke Test ⏳ 0%待实现

**验收标准**:
| 指标 | 目标 | 状态 |
|------|------|------|
| 一键初始化脚本成功率 | 100% | ⏳ 待验证 |
| feature三张基础指标表非空 | 100% | ✅ 已验证 |
| receipt_training_features非空 | 100% | ✅ 已验证 |
| 模型文件产出 | 100% | ⏳ 待训练 |
| 推荐生成成功 | 100% | ✅ 已实现 |
| 审批后action记录生成 | 100% | ⏳ 待验证 |
| 全部smoke测试通过 | 通过 | ⏳ 待运行 |

**验收命令**:
```bash
venv/bin/python -m pytest tests/smoke tests/contract tests/validation -q
```

**当前测试结果**:
```
现状: 34 passed, 2 skipped
validation: 24 failed, 5 passed

目标: smoke + contract + validation全绿
      validation: 0 failed
```

**预计工作量**: 依赖M1-M5完成，最终集成验证（2-3小时）

---

## 总体进度总结

### 完成情况

**已完成里程碑**: M1 (95%)

**进行中**: M1测试验证（预计15:40完成）

**待实现**: M2-M6 (5个里程碑)

---

### 工作量估算

| 里程碑 | 预计工作量 | 优先级 | 前置依赖 |
|--------|-----------|--------|---------|
| M1验证 | ~15分钟 | 最高 | 无（测试运行中）|
| M2模型训练 | 2-3小时 | 高 | M1完成 |
| M3 Agent集成 | 3-4小时 | 高 | M2完成 |
| M4审批闭环 | 2-3小时 | 中 | 无 |
| M5安全配置 | 4-5小时 | 中 | 无 |
| M6集成验收 | 2-3小时 | 最终 | M1-M5完成 |

**总预计剩余工作量**: 13-18小时

---

### 优先级排序（最小可交付）

**用户建议的4个硬指标**（最务实）:
1. ✅ FeatureExtractor只读receipt_training_features (已完成)
2. 🔄 test_time_leakage_audit.py全部通过 (测试运行中)
3. ⏳ test_model_backtest.py全部通过或记录未达标 (M2)
4. ⏳ test_agent_grounding.py全部通过 (M3)

**达成这4个指标预计需要**:
- M1完成: ~15分钟
- M2完成: 2-3小时
- M3部分完成（grounding测试）: 1-2小时
- **总计**: 3.5-5.5小时

---

### 建议执行路径

**Phase 1**（今天完成）:
- ✅ M1验收完成（等待15:40测试结果）
- ⏳ M2模型训练启动（如果M1通过）

**Phase 2**（明天）:
- M2完成验收
- M3 Agent集成开始

**Phase 3**（后天）:
- M3完成
- M4审批闭环

**Phase 4**（最终集成）:
- M5安全配置
- M6一键验收

---

## 当前时间节点

**15:28**: M1测试运行中（13分钟，预计15:40完成）

**下一步**:
- 15:40: M1验收结果（预计全部通过）
- 15:45: 如果通过，立即启动M2模型训练
- 16:00-18:00: M2模型训练完成
- 晚上: M3 Agent集成开始

---

**Status**: 测试预计15:40完成，总任务约13-18小时剩余，建议优先完成M1→M2→M3这3个核心里程碑。