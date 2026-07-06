# RentalScraper

基于 Playwright 的租房信息爬虫，用于为 AI 租房系统定期抓取真实的房源数据。

## 项目结构

```
RentalScraper/
├── src/
│   ├── spider.py      # 爬虫核心逻辑
│   └── pipeline.py    # 数据清洗与导出
├── .env               # 环境变量配置
├── requirements.txt   # Python 依赖
├── properties.csv     # 导出结果
└── README.md
```

## 环境要求

- Python 3.9+
- Windows / macOS / Linux

## 安装步骤

### 1. 创建虚拟环境（推荐）

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 安装 Playwright 浏览器

```bash
playwright install chromium
```

> **注意：** 如果 `playwright install` 报错提示缺少系统依赖（常见于 Linux），请运行：
> ```bash
> playwright install-deps chromium
> ```
> 该命令会自动安装 Chromium 所需的系统库（如 libgbm, libnss3 等）。Windows 和 macOS 通常不需要此步骤。

### 4. 配置环境变量

编辑 `.env` 文件，设置目标 URL 和其他参数：

```
TARGET_URL=https://bj.lianjia.com/zufang/wangjing/
HEADLESS=true
TIMEOUT=30000
```

## 使用方法

### 运行完整流程（爬取 + 清洗 + 导出）

```bash
cd src
python pipeline.py
```

`pipeline.py` 会自动调用 `spider.py` 抓取数据，然后清洗并导出为 `properties.csv`。

### 仅运行爬虫

```bash
cd src
python spider.py
```

### 输出格式

导出的 `properties.csv` 包含以下列：

| 字段 | 说明 |
|------|------|
| id | UUID 唯一标识 |
| title | 房源标题 |
| location | 区域/小区名 |
| price | 月租金（纯数字，单位：元） |
| size | 面积（平方米） |
| bedrooms | 几室几厅 |
| pet_friendly | 是否可养宠物（默认 False） |
| description | 标题 + 标签拼接 |

## 自定义目标网站

修改 `.env` 中的 `TARGET_URL`，然后根据目标网站的 HTML 结构调整 `src/spider.py` 中的 CSS 选择器即可。
