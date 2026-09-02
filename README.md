<div align="center">

# WearCue

**每天少想一件事：穿什么。**

把实时天气、出行场景和个人穿搭灵感，变成今天可以直接照着穿的一套建议。

[![线上状态：可访问](https://img.shields.io/badge/%E7%BA%BF%E7%8A%B6%E6%80%81-%E5%8F%AF%E8%AE%BF%E9%97%AE-22C55E?style=flat-square&labelColor=111827)](https://ss2fri90im8h5gjbjf5c8.apigateway-cn-beijing.volceapi.com/)
![Web: Next.js 16](https://img.shields.io/badge/Web-Next.js_16-22C55E?style=flat-square&labelColor=111827&logo=nextdotjs&logoColor=white)
![API: FastAPI](https://img.shields.io/badge/API-FastAPI-14B8A6?style=flat-square&labelColor=111827&logo=fastapi&logoColor=white)
![Runtime: Python 3.11+](https://img.shields.io/badge/Runtime-Python_3.11+-4F8FF7?style=flat-square&labelColor=111827&logo=python&logoColor=white)

<br>

[![在线体验](https://img.shields.io/badge/%E5%9C%A8%E7%BA%BF%E4%BD%93%E9%AA%8C-%E6%89%93%E5%BC%80_WearCue-A3E635?style=for-the-badge&labelColor=111827)](https://ss2fri90im8h5gjbjf5c8.apigateway-cn-beijing.volceapi.com/)

<br>

[在线体验](#online) · [产品简介](#intro) · [核心功能](#features) · [本地开发](#run) · [项目结构](#structure) · [技术说明](#stack)

</div>

<a id="online"></a>
## 在线体验

访问 **[WearCue 线上版](https://ss2fri90im8h5gjbjf5c8.apigateway-cn-beijing.volceapi.com/)**。首次进入会跳转到登录页，填写昵称、性别和邀请码后即可使用；允许位置访问后，WearCue 会按当前位置获取天气。

<a id="intro"></a>
## 产品简介

WearCue 是一款面向日常出行的天气穿搭助手。它根据所在城市的逐小时天气和通勤、约会、出行三种场景，生成可直接执行的穿搭组合；你也可以上传自己的穿搭照片，让 AI 识别单品并沉淀为个人灵感。

项目由 Next.js Web 前端与 FastAPI 后端组成，包含邀请码登录、账号数据隔离、SQLite 持久化、天气查询、穿搭推荐、图片识别和 Web Push 提醒等完整链路。

<a id="features"></a>
## 核心功能

| 能力 | 说明 |
|---|---|
| 天气 × 场景推荐 | 结合逐小时天气与通勤、约会、出行场景给出今日穿搭 |
| 个人穿搭灵感 | 上传穿搭照片，识别服装款式、颜色、薄厚与适用温度 |
| AI 穿搭建议 | 生成穿搭名称、搭配分析、复刻步骤、替代建议与效果图 |
| 穿搭库管理 | 收藏、删除并设置个人首页推荐，系统方案作为兜底 |
| 多设备同步 | 通过邀请码登录，同一账号可在不同设备访问个人数据 |
| 晨间提醒 | 设置提醒时间，通过浏览器通知查看当天穿搭 |

<a id="run"></a>
## 本地开发

### 环境要求

- Node.js 与 pnpm 11
- Python 3.11–3.13
- 可选：Docker

### 1. 启动后端

```bash
cd 穿搭信号-后端项目
cp .env.example .env
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn --env-file .env app.main:app --app-dir backend --reload --port 8000
```

也可以使用 Docker：

```bash
cd 穿搭信号-后端项目
cp .env.example .env
docker compose up --build
```

后端启动后可访问：

- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/v1/health`

### 2. 启动前端

另开一个终端窗口：

```bash
cd 穿搭信号-网页项目
cp .env.example .env.local
pnpm install
pnpm dev
```

浏览器打开 `http://localhost:3456`。开发环境可使用 `.env` 中配置的邀请码登录；天气查询默认使用 Open-Meteo。

### 3. 启用 AI 与提醒

基础天气和规则推荐可以独立运行。图片识别、AI 命名、穿搭建议、效果图和 Web Push 需要在后端 `.env` 中补充相应 Provider 与 VAPID 配置；字段说明见 [`穿搭信号-后端项目/.env.example`](穿搭信号-后端项目/.env.example)。请勿提交真实密钥。

<a id="structure"></a>
## 项目结构

```text
wearcue/
├── 穿搭信号-网页项目/        # Next.js 前端、页面组件与浏览器能力
├── 穿搭信号-后端项目/        # FastAPI API、推荐服务与持久化
└── 穿搭信号 MVP 产品需求文档/ # 品牌与产品资料
```

更详细的运行与配置说明：

- [网页项目说明](穿搭信号-网页项目/项目说明.md)
- [后端项目说明](穿搭信号-后端项目/README.md)
- [第三方软件声明](穿搭信号-后端项目/THIRD_PARTY_NOTICES.md)

<a id="stack"></a>
## 技术说明

- **Web：** Next.js 16、React 19、TypeScript、Tailwind CSS 4
- **API：** FastAPI、Pydantic、Uvicorn
- **数据：** SQLite，本地持久化并支持外部持久化目录
- **天气：** Open-Meteo 城市搜索与逐小时天气
- **AI：** OpenAI Schema 兼容 Provider，视觉、文本和图片任务可分别配置模型
- **通知：** Service Worker、Web Push、VAPID

---

<div align="center">

**Built with ❤️ by [@yuanhao667](https://github.com/yuanhao667)**

[在线体验](https://ss2fri90im8h5gjbjf5c8.apigateway-cn-beijing.volceapi.com/) · [本地开发](#run) · [反馈问题](https://github.com/yuanhao667/wearcue/issues)

</div>
