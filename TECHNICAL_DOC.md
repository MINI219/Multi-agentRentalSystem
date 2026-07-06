# Multi-Agent Rental System — 技术文档

> LangGraph 多智能体租房系统 | DeepSeek + MCP + FastAPI + Next.js

---

## 目录

1. [项目概览](#1-项目概览)
2. [系统架构](#2-系统架构)
3. [技术栈](#3-技术栈)
4. [目录结构](#4-目录结构)
5. [核心模块详解](#5-核心模块详解)
   - [5.1 LangGraph 状态图](#51-langgraph-状态图)
   - [5.2 Supervisor 路由 Agent](#52-supervisor-路由-agent)
   - [5.3 Profile Agent（需求画像）](#53-profile-agent需求画像)
   - [5.4 Search Agent（房源搜索 + MCP）](#54-search-agent房源搜索--mcp)
   - [5.5 Recommendation Agent（评估打分）](#55-recommendation-agent评估打分)
   - [5.6 MCP Server（数据层）](#56-mcp-server数据层)
   - [5.7 FastAPI 会话管理](#57-fastapi-会话管理)
   - [5.8 前端分栏 UI](#58-前端分栏-ui)
6. [数据流全景](#6-数据流全景)

---

## 1. 项目概览

本项目是一个**基于 LangGraph 的多智能体租房推荐系统**。用户通过自然语言对话描述租房需求，系统由 4 个专业化 AI Agent 协同工作，自动完成需求提取、房源检索、评估排序，最终以左右分栏 UI（对话 + 房源卡片）呈现结果。

**核心亮点：**

- **Supervisor 路由模式**：主管 Agent 根据状态动态决策下一步调用哪个 Worker Agent
- **MCP（Model Context Protocol）**：搜索工具封装为独立 MCP Server，通过 stdio 进程间通信
- **多轮会话记忆**：服务端 Session 机制累积对话历史，profile agent 读取完整上下文
- **DeepSeek API 适配**：使用 `function_calling` 模式实现结构化输出（绕过 `response_format` 不支持）

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       Frontend (Next.js)                         │
│  ┌──────────────────────┐    ┌────────────────────────────────┐ │
│  │   ChatInterface.tsx   │    │  PropertyGrid + PropertyCard   │ │
│  │   (左侧 42% 对话)      │    │  (右侧 58% 房源卡片)            │ │
│  └──────────┬───────────┘    └────────────┬───────────────────┘ │
│             │                              │                      │
│             │  POST /api/chat              │                      │
└─────────────┼──────────────────────────────┼──────────────────────┘
              │                              │
┌─────────────▼──────────────────────────────┼──────────────────────┐
│                    Backend (FastAPI)                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  routes.py — Session Store (内存 dict)                      │  │
│  │  每次请求: 恢复历史 → 追加消息 → 重置 profile/search key     │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
│                             │                                     │
│  ┌──────────────────────────▼─────────────────────────────────┐  │
│  │               LangGraph StateGraph                          │  │
│  │                                                              │  │
│  │   START → [supervisor] ←──────────────────────┐             │  │
│  │              │                                 │             │  │
│  │     ┌────────┼────────┬────────┐              │             │  │
│  │     ▼        ▼        ▼        ▼              │             │  │
│  │  [profile] [search] [recommend] END           │             │  │
│  │     │        │        │                        │             │  │
│  │     └────────┴────────┘                        │             │  │
│  │              └─────────────────────────────────┘             │  │
│  │                                                              │  │
│  │  RentState: { messages, user_profile,                        │  │
│  │               candidate_properties,                          │  │
│  │               recommended_properties, next_agent }           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ stdio (subprocess)
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│               MCP Server (RentalTools)                              │
│  FastMCP("RentalTools")                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  search_properties(location, max_budget, pet_friendly)        │  │
│  │  → 过滤 PROPERTIES_DB (properties.csv, 30条真实数据)           │  │
│  │  → 返回 top 5 匹配房源                                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### Agent 协作流程

```
用户输入 "我想在九堡租个房，预算3000，养了只猫"
       │
       ▼
  [supervisor]  分析状态: user_profile 不存在 → 路由到 profile
       │
       ▼
  [profile]     DeepSeek LLM 结构化提取:
                {budget: 3000, location: "九堡", pet_friendly: True}
       │
       ▼
  [supervisor]  profile 完成, search 未执行 → 路由到 search
       │
       ▼
  [search]      启动 MCP subprocess → LLM bind_tools →
                调用 search_properties("九堡", 3000, True) →
                返回 聚英公寓·九堡店 ¥2600
       │
       ▼
  [supervisor]  有 candidates, 无 recommended → 路由到 recommend
       │
       ▼
  [recommend]   按性价比评分排序 → score: 10.0, rank: #1
       │
       ▼
  [supervisor]  全部完成 → FINISH
```

---

## 3. 技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **AI 编排** | LangGraph | ≥0.2.0 | StateGraph 构建多 Agent 流转 |
| **LLM** | DeepSeek (ChatOpenAI 兼容) | deepseek-chat | 需求提取、工具调用 |
| **工具协议** | MCP (Model Context Protocol) | ≥1.9 | stdio 子进程工具封装 |
| **MCP 适配** | langchain-mcp-adapters | ≥0.1 | MCP 工具 → LangChain Tool 转换 |
| **后端框架** | FastAPI + Uvicorn | ≥0.115 | REST API + 热重载 |
| **数据校验** | Pydantic | ≥2.0 | Schema / 结构化输出 |
| **前端框架** | Next.js 14 (App Router) | ^14.2 | React 服务端渲染 |
| **样式** | Tailwind CSS | ^3.4 | 深色科技风 UI |
| **语言** | TypeScript / Python 3.10 | — | 全栈类型安全 |
| **环境管理** | Conda (paper_rag) | — | Python 虚拟环境 |

---

## 4. 目录结构

```
Multi-agentRentalSystem/
│
├── backend/                          # Python 后端
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口 + CORS
│   │   ├── config.py                 # 环境变量 (DeepSeek key/url)
│   │   │
│   │   ├── agents/                   # 4 个 Agent 节点函数
│   │   │   ├── supervisor.py         # 主管路由 (纯规则)
│   │   │   ├── profile_agent.py      # 需求提取 (LLM + 结构化输出)
│   │   │   ├── search_agent.py       # MCP 搜索 (LLM + tool calling)
│   │   │   ├── recommendation_agent.py  # 评估排序 (规则打分)
│   │   │   └── base.py               # get_llm() 工厂函数
│   │   │
│   │   ├── graph/                    # LangGraph 核心
│   │   │   ├── state.py              # RentState TypedDict 定义
│   │   │   └── rental_graph.py       # StateGraph 构建 + 测试入口
│   │   │
│   │   ├── models/
│   │   │   └── schemas.py            # FastAPI 请求/响应 Pydantic
│   │   │
│   │   ├── api/
│   │   │   └── routes.py             # /api/chat 端点 + 会话管理
│   │   │
│   │   └── tools/
│   │       └── search_tools.py       # (预留) 非 MCP 工具
│   │
│   ├── requirements.txt
│   └── .env / .env.example
│
├── mcp_server/                       # 独立 MCP 工具服务
│   ├── server.py                     # FastMCP 服务 + search_properties 工具
│   ├── properties.csv                # 贝壳杭州站 30 条真实房源
│   └── requirements.txt
│
├── frontend/                         # Next.js 前端
│   └── src/
│       ├── app/
│       │   ├── layout.tsx            # 根布局 (Header + 暗色主题)
│       │   ├── page.tsx              # 首页 (左右分栏容器)
│       │   └── globals.css           # Tailwind + 聊天气泡 + 滚动条
│       │
│       ├── components/
│       │   ├── ChatInterface.tsx     # 左侧对话面板
│       │   ├── PropertyGrid.tsx      # 右侧房源网格
│       │   └── PropertyCard.tsx      # 单个房源卡片
│       │
│       └── lib/
│           └── api.ts                # API 客户端 + 类型定义
│
└── RentalScraper/                    # 贝壳爬虫 (数据采集, 独立模块)
    └── properties.csv                # 爬虫输出 → 复制到 mcp_server/
```

---

## 5. 核心模块详解

### 5.1 LangGraph 状态图

**文件：** `backend/app/graph/state.py` + `rental_graph.py`

#### RentState 定义

```python
class RentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]  # 对话历史 (reducer 追加)
    user_profile: dict         # {budget, location, pet_friendly}
    candidate_properties: list[dict]   # 搜索到的原始房源
    recommended_properties: list[dict] # 评分排序后的房源
    next_agent: str            # supervisor 决策: 'profile'|'search'|'recommend'|'FINISH'
```

**关键设计：** `total=False` 允许 key 缺失。Supervisor 用 `"key" in state` 判断某步骤是否已执行，而非检查值是否为空。这区分了"未执行"和"已执行但结果为空"。

#### Graph 拓扑

```
StateGraph(RentState)
  ├── ENTRY → supervisor
  ├── supervisor → conditional_edges → profile | search | recommend | END
  ├── profile    → supervisor (固定回边)
  ├── search     → supervisor (固定回边)
  └── recommend  → supervisor (固定回边)
```

所有 Worker 执行完**必须回到 supervisor** 重新决策。这实现了动态路由：搜索 0 结果时直接 FINISH；用户中途改变需求时重新提取 profile。

---

### 5.2 Supervisor 路由 Agent

**文件：** `backend/app/agents/supervisor.py`

**路由策略（纯规则，无 LLM）：**

| 条件 | 路由目标 | 说明 |
|------|---------|------|
| `"user_profile" not in state` | `profile` | 尚未提取需求 |
| `user_profile` 存在但 budget 缺失 | `FINISH` | 等待用户补充预算 |
| `"candidate_properties" not in state` | `search` | profile 就绪，开始搜索 |
| candidates 为空 | `FINISH` | 搜索无结果，终止 |
| `"recommended_properties" not in state` | `recommend` | 有候选，需评分 |
| 以上全部满足 | `FINISH` | 流程完成 |

**为什么用纯规则而非 LLM 路由？** 路由逻辑是确定性的（有 profile→搜索，有 candidates→打分），LLM 反而引入不确定性。但规则需精细处理边界条件（如"已搜索但 0 结果"不能重复搜索）。

---

### 5.3 Profile Agent（需求画像）

**文件：** `backend/app/agents/profile_agent.py`

#### 核心逻辑

1. 将**完整对话历史**（含多轮累积）发送给 DeepSeek LLM
2. 使用 `with_structured_output(UserProfileExtraction, method="function_calling")` 提取结构化数据
3. DeepSeek 不支持 OpenAI 的 `response_format`（json_schema），因此用 `method="function_calling"` 模式

#### UserProfileExtraction 模型

```python
class UserProfileExtraction(BaseModel):
    needs_clarification: bool   # budget 缺失时 = True
    clarification_message: str  # 追问话术
    budget: int                 # 月预算 (CNY) — 唯一必填字段
    location: str               # 区域 — 可选, "" = 全区域搜索
    pet_friendly: bool          # 是否宠物友好
```

**关键设计决策：**
- **只有 budget 是必填的** — 用户说"所有区域"/"不限"/"看看有哪些"时 location=""，搜索全部
- **每轮都重新提取** — 不缓存 profile。用户说"望京呢"时 LLM 从完整对话中看到 location 应更新为望京
- **system prompt 明确禁止追问 location** — 避免"请问您想租哪个区域？"的死循环追问

---

### 5.4 Search Agent（房源搜索 + MCP）

**文件：** `backend/app/agents/search_agent.py`

#### 核心流程

```
1. 启动 MCP subprocess:  python ../mcp_server/server.py
2. 建立 stdio 双向通信
3. await session.initialize()    → MCP 握手
4. tools = await load_mcp_tools(session)  → 获取 search_properties 工具
5. llm.bind_tools(tools)        → DeepSeek 获取工具定义
6. LLM 根据 user_profile 产生 tool_call
7. tool.ainvoke(tool_args)      → MCP 执行搜索
8. 解析 MCP 返回的 content-block 格式
9. 存入 candidate_properties
```

#### MCP 返回值解析

MCP 工具通过 `langchain_mcp_adapters` 返回的是 **content block 列表**：

```python
# 原始返回格式:
[{"type": "text", "text": '{"id":"...", "title":"...", ...}', "id": "lc_..."}]

# 解析函数 _parse_mcp_result():
# 遍历 block → 取 "text" 字段 → json.loads() → property dict
```

**关键踩坑：** 直接 `print()` 会污染 MCP 的 stdio 通道（JSON-RPC 协议要求 stdout 只输出 JSON）。所有日志必须输出到 `sys.stderr`。

---

### 5.5 Recommendation Agent（评估打分）

**文件：** `backend/app/agents/recommendation_agent.py`

当前阶段使用**规则打分**（非 LLM）：

```python
score = min(10, (5000 / price) * 5 + (area_sqm / 100) * 5)
# 性价比 = 价格因子 + 面积因子，上限 10 分
```

按 score 降序排列，赋予 rank 排名。**后续可升级为 LLM 多维度评估**（交通、装修、周边配套等）。

---

### 5.6 MCP Server（数据层）

**文件：** `mcp_server/server.py`

#### 架构

```
FastMCP("RentalTools")
  │
  ├── 启动时加载 properties.csv → PROPERTIES_DB (30条)
  │
  └── @mcp.tool()
      search_properties(location, max_budget, pet_friendly) → list[dict]
```

#### 数据清洗策略

| 问题 | 处理方式 |
|------|---------|
| price 异常大 (如 `15301560`) | `> 100_000` → 跳过该条 |
| price 无法解析 | try/except → 跳过 |
| pet_friendly 列全为 False | 用关键词 (`宠物友好`,`可养猫`) 从 title/description 二次检测 |
| location 为空 | 不进行位置过滤，返回全部匹配 |

#### 为什么用 MCP 而非直接函数调用？

1. **解耦** — 搜索逻辑独立进程，可替换为远程 HTTP MCP Server
2. **标准化** — MCP 是 Anthropic 提出的工具调用标准协议，LangChain 原生支持
3. **可扩展** — 未来可添加更多 MCP 工具（地图、通勤计算、房价走势等）

---

### 5.7 FastAPI 会话管理

**文件：** `backend/app/api/routes.py`

#### 多轮对话实现

```python
_sessions: dict[str, list] = {}   # session_id → [messages]

@router.post("/chat")
async def chat(request: ChatRequest):
    sid, history = _get_or_create_session(request.session_id)

    # 追加新消息到历史
    history.append(HumanMessage(content=request.message))

    # 构建 state — 注意: 不传 user_profile/candidate/recommended
    # 让 supervisor 通过 key 缺失判断"未执行"
    initial_state: RentState = {
        "messages": list(history),
        "next_agent": "",
    }

    result = await rental_graph.ainvoke(initial_state, {"recursion_limit": 20})

    # 结果存回 session
    _sessions[sid] = list(result["messages"])

    return ChatResponse(session_id=sid, reply=..., properties=...)
```

**设计要点：** 每轮请求都从累积的 messages 重新跑完整 Graph。Graph 运行时会从 messages 重新提取 user_profile 和搜索房源，而非从上一轮的缓存结果继续。这保证了用户改变需求时能正确更新。

---

### 5.8 前端分栏 UI

**文件：** `frontend/src/`

#### 组件树

```
page.tsx (状态管理: properties[])
  ├── ChatInterface.tsx (左侧 42%)
  │   ├── messages[] 状态
  │   ├── sessionIdRef (多轮续传)
  │   └── handleSend → sendMessage() → 更新 properties
  │
  └── PropertyGrid.tsx (右侧 58%)
      └── PropertyCard.tsx × N
          ├── 排名徽章 (TOP / #N)
          ├── 标题 + 位置 + 地图图标
          ├── 价格 (渐变色)
          ├── 户型 / 面积 / 宠物友好标签
          ├── 描述 (line-clamp-2)
          └── 评分条 (渐变色, 按分数分段)
```

#### 前后端通信

```
前端 fetch("/api/chat")
  │
  │  Next.js rewrites 代理
  ▼
后端 http://localhost:8000/api/chat
```

`next.config.mjs`:
```js
async rewrites() {
  return [{ source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }];
}
```

前端只需请求 `/api/chat`，Next.js dev server 自动代理到后端。无需在浏览器中暴露后端端口。

---

## 6. 数据流全景

```
┌────────────┐    POST /api/chat     ┌──────────────┐
│  Browser   │ ──────────────────────>│   FastAPI    │
│  (React)   │ <──────────────────────│  (Uvicorn)   │
│            │   JSON {reply, props}  │              │
└────────────┘                       └──────┬───────┘
                                            │
                              ┌─────────────▼─────────────┐
                              │     LangGraph StateGraph   │
                              │                            │
                              │  [supervisor] → 路由决策    │
                              │       │                    │
                              │  ┌────┼────┬────┐         │
                              │  ▼    ▼    ▼    ▼         │
                              │  P    S    R   END        │
                              │                            │
                              │  RentState 流转            │
                              └────────┬───────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │    DeepSeek API (LLM)    │
                          │  - 结构化输出提取需求     │
                          │  - 工具调用生成搜索参数   │
                          └──────────────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │   MCP Server (stdio)     │
                          │  search_properties()     │
                          │  → properties.csv (30条) │
                          └──────────────────────────┘
```

