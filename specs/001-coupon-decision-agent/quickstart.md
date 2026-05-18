# Quickstart: 优惠券运营决策 Agent 系统

**Feature**: 001-coupon-decision-agent | **Date**: 2026-05-17

## Prerequisites

- Docker & Docker Compose (推荐 Docker Desktop or Docker Engine 20.10+)
- Python 3.12 (本地开发需要)
- Git
- DeepSeek API Key (已提供: sk-320b00c6ef524b629909aad6e13156a8)

---

## Quick Setup (Docker方式 - 推荐)

### 1. 克隆仓库

```bash
git clone <repo_url>
cd o2o-coupon-agent
git checkout 001-coupon-decision-agent
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env`:

```bash
cp .env.example .env
```

编辑 `.env` 配置关键变量:

```bash
# DeepSeek API配置
LLM_API_KEY=sk-320b00c6ef524b629909aad6e13156a8
LLM_MODEL=deepseek-v4-flash
LLM_ENDPOINT=https://api.deepseek.com/v1

# 飞书集成（后续配置）
FEISHU_APP_ID=<your_app_id>
FEISHU_APP_SECRET=<your_app_secret>
FEISHU_VERIFICATION_TOKEN=<your_verification_token>

# API Token (Dashboard访问)
API_TOKEN=<generate_random_token>
```

### 3. 启动服务

```bash
# 构建镜像
make build

# 启动所有服务（PostgreSQL, Redis, API, Worker, Beat）
make up

# 查看日志
make logs
```

等待服务启动完成（约30秒），健康检查通过后可继续。

### 4. 数据库迁移

```bash
# 运行Alembic迁移
make migrate

# 验证迁移成功（应看到 raw.offline_train 表）
make psql
# 在psql中执行：
\dt raw.*
\q
```

### 5. 导入数据

```bash
# 导入CSV数据到Raw层
make import-data

# 验证数据导入（应看到约26万条记录）
make psql
# 执行：
SELECT COUNT(*) FROM raw.offline_train;
\q
```

---

## Development Workflow

### 6. 运行测试

```bash
# 在Docker容器内运行pytest
make test

# 或本地运行（需要安装依赖）
pip install -r requirements.txt
pytest tests/ -v
```

### 7. 开发代码

代码挂载到容器（Docker Compose volumes），本地修改立即生效：

- FastAPI 自动重载：修改 `app/` 代码后自动重启
- Celery Worker 需手动重启：`docker compose restart worker`

**推荐IDE**: VS Code + Python扩展、PyCharm

### 8. 查看API文档

访问 FastAPI 自动生成的文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Local Setup (非Docker方式 - 仅用于调试)

### 1. 安装依赖

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. 启动PostgreSQL和Redis

需要本地安装PostgreSQL 17和Redis 7：

```bash
# PostgreSQL (推荐使用Docker)
docker run -d --name postgres \
  -e POSTGRES_DB=coupon_agent \
  -e POSTGRES_USER=coupon_user \
  -e POSTGRES_PASSWORD=coupon_pass \
  -p 5433:5432 \
  postgres:17-alpine

# Redis (推荐使用Docker)
docker run -d --name redis \
  -p 6380:6379 \
  redis:7-alpine
```

### 3. 运行数据库迁移

```bash
alembic upgrade head
```

### 4. 启动API服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 启动Celery Worker

```bash
celery -A app.tasks.celery_app worker -l info --concurrency=2
```

### 6. 启动Celery Beat (定时任务)

```bash
celery -A app.tasks.celery_app beat -l info
```

---

## Database Access

### PostgreSQL

```bash
# Docker方式
make psql

# 本地方式
psql -h localhost -p 5433 -U coupon_user -d coupon_agent
```

常用查询：

```sql
-- 查看所有表
\dt

-- 查看 Raw 层数据
SELECT * FROM raw.offline_train LIMIT 10;

-- 查看 Feature 层指标（迁移后）
SELECT * FROM feature.merchant_metrics LIMIT 10;
```

### Redis

```bash
# Docker方式
docker compose exec redis redis-cli

# 本地方式
redis-cli -p 6380
```

常用命令：

```redis
# 查看Celery任务队列
KEYS celery*

# 查看任务结果
GET celery-task-meta-<task_id>
```

---

## API Endpoints Test

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

### Import Data (需API Token)

```bash
curl -X POST http://localhost:8000/api/v1/datasets/import \
  -H "X-API-Token: your_api_token"
```

### Query Metrics (需API Token)

```bash
curl http://localhost:8000/api/v1/metrics/merchants \
  -H "X-API-Token: your_api_token"
```

---

## Development Tips

### 1. 日志查看

```bash
# API日志
make api-logs

# Celery Worker日志
make worker-logs

# 所有服务日志
make logs
```

日志文件位置：
- `/tmp/app.log` (API日志)
- `/tmp/celery.log` (Celery日志)

### 2. 数据库迁移新表

创建新迁移脚本：

```bash
# 在容器内执行
docker compose exec api alembic revision --autogenerate -m "create_staging_events"
```

手动编辑迁移脚本（alembic/versions/*.py），然后执行：

```bash
alembic upgrade head
```

### 3. Celery任务调试

```python
# 在Python中手动触发任务
from app.tasks.import_dataset import import_dataset_task

# 同步执行（调试）
result = import_dataset_task.apply()
print(result.result)

# 异步执行
task = import_dataset_task.delay()
print(task.id)
```

### 4. Agent Tool调用测试

```python
# 测试DeepSeek API调用
from app.integrations.llm.deepseek_client import DeepSeekClient

client = DeepSeekClient()
response = client.chat_with_tools(
    messages=[{"role": "user", "content": "测试消息"}],
    tools=[get_merchant_metrics_tool]
)
print(response)
```

---

## Troubleshooting

### 问题1: 数据库连接失败

**症状**: API启动报错 "Connection refused"

**解决**:
```bash
# 检查PostgreSQL是否运行
docker compose ps postgres

# 重启PostgreSQL
docker compose restart postgres

# 验证数据库健康
docker compose exec postgres pg_isready -U coupon_user
```

### 问题2: Celery任务不执行

**症状**: 任务提交后无响应

**解决**:
```bash
# 检查Worker是否运行
docker compose ps worker

# 检查Redis连接
docker compose exec redis redis-cli ping

# 重启Worker
docker compose restart worker
```

### 问题3: DeepSeek API调用失败

**症状**: Agent任务报错 "API call failed"

**解决**:
```bash
# 验证API Key配置
cat .env | grep LLM_API_KEY

# 测试API连接
curl -X POST https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer sk-320b00c6ef524b629909aad6e13156a8" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"test"}]}'
```

### 问题4: 飞书回调签名验证失败

**症状**: POST /api/v1/approvals/callback 返回 400

**解决**:
- 检查飞书 Verification Token 配置
- 验证签名算法（HMAC-SHA256）
- 检查 timestamp 是否在有效范围内（±5分钟）

---

## Next Steps

1. **实现Staging层数据清洗** (FR-002)
2. **实现Feature层指标计算** (FR-003)
3. **训练核销预测模型** (FR-004)
4. **实现规则引擎** (FR-005, FR-006)
5. **集成DeepSeek Agent** (FR-007, FR-019-022)
6. **实现飞书审批回调** (FR-009)
7. **实现Mock Action** (FR-010)
8. **完善API端点** (FR-011)
9. **编写测试** (目标: 80%覆盖率)

参考 `/specs/001-coupon-decision-agent/tasks.md` (待生成) 获取详细任务清单。

---

## Useful Commands

```bash
# Docker清理
docker compose down -v  # 删除容器和数据卷
docker compose build --no-cache  # 重新构建镜像

# 数据库清理
make psql
DROP SCHEMA raw CASCADE;
DROP SCHEMA staging CASCADE;
DROP SCHEMA feature CASCADE;
DROP SCHEMA application CASCADE;
\q
alembic upgrade head  # 重新迁移

# Celery任务监控
pip install flower  # Celery监控工具
celery -A app.tasks.celery_app flower  # 启动监控（访问 http://localhost:5555）

# 代码质量检查
pip install flake8 black
flake8 app/  # 语法检查
black app/  # 格式化代码
```

---

## Project Structure Reference

```
.
├── app/               # FastAPI应用
│   ├── api/           # REST API路由
│   ├── core/          # 核心配置
│   ├── domain/        # 领域模型（各数据层）
│   ├── features/      # 特征工程
│   ├── ml/            # ML模型训练和推理
│   ├── agents/        # Agent决策逻辑
│   ├── integrations/  # 外部服务集成（LLM, 飞书）
│   ├── tasks/         # Celery异步任务
│   └── main.py        # 应用入口
├── tests/             # 测试文件
├── alembic/           # 数据库迁移
├── scripts/           # 工具脚本
├── data/              # CSV数据文件
├── docker-compose.yml # Docker编排配置
├── requirements.txt   # Python依赖
└── Makefile           # 常用命令封装
```

---

## Support

遇到问题请：
1. 查看日志 (`make logs`)
2. 查阅 `/specs/001-coupon-decision-agent/` 设计文档
3. 参考 `/doc/实现方案设计.md` 架构设计
4. 联系项目团队

---

**Happy Coding! 🚀**
