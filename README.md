# Multi-Agent Rental System 🏠

基于 **LangGraph** 的多智能体租房系统，采用 Supervisor 路由模式，智能协助用户搜索、评估和推荐房源。

## 技术栈

| 层级 | 技术 |
|------|------|
| **编排引擎** | LangGraph (Supervisor 路由) |
| **后端框架** | FastAPI + Uvicorn |
| **LLM** | DeepSeek v4 pro |
| **前端** | Next.js 14 (App Router) + TypeScript + Tailwind CSS |
| **环境管理** | Conda (paper_rag) |

## 项目结构

```
Multi-agentRentalSystem/
├── backend/
│   ├── app/
│   │   ├── agents/          # 智能体（supervisor / profile / search / recommendation）
│   │   ├── graph/           # LangGraph 状态图（RentState + StateGraph）
│   │   ├── models/          # FastAPI 请求/响应 Schema
│   │   ├── tools/           # 自定义工具
│   │   └── api/             # REST 路由
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── app/             # Next.js App Router 页面
│       ├── components/      # React 组件（Chat / PropertyGrid / PropertyCard）
│       └── lib/             # API 客户端
└── README.md
```

## 快速开始

### 1. Backend

```bash
# 激活 conda 环境
conda activate paper_rag

# 安装依赖
cd backend
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 OPENAI_API_KEY

# 启动服务
python -m app.main
# → http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## Supervisor 路由模式

```
用户输入 → Supervisor（决策路由）
              ├── "需求不清晰" → profile_agent（对话澄清）
              ├── "需要搜索"   → search_agent（检索房源）
              ├── "需要评估"   → recommendation_agent（打分排序）
              └── "FINISH"     → 结束本轮
              ↓
         Supervisor 汇总 → 返回用户
```
