# WearCue 后端项目

当前交付是邀请码登录、按账号隔离数据的多用户版本，仅保留通勤/约会/出行，提供：

- 当天完整逐小时天气与城市搜索；
- 版本化确定性穿衣规则；
- 官方模板推荐与“换一套”；
- 服装 SVG 素材目录与静态访问；
- 数据库会话、HttpOnly Cookie 接入与接口鉴权；
- 按账号隔离设置、个人穿搭、图片、收藏、推荐池、提醒和反馈；
- SQLite 本地数据持久化，并自动把升级前数据归入首个登录账号；
- 图片上传、EXIF 纠正、三档缩略图、幂等去重；
- 生产视觉 Provider、人工确认、收藏与“我的穿搭”；
- 个人穿搭优先、官方模板兜底；
- Web Push 订阅、VAPID Provider、每日发送幂等；
- 连续跳过和每周冷热反馈；
- 健康检查、运行状态、能力声明和统一错误边界。

## 本地启动

要求 Python 3.11+。当前电脑的系统 Python 是 3.9，需先安装 Python 3.11。

```bash
cp .env.example .env
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn --env-file .env app.main:app --app-dir backend --reload --port 8000
```

打开：

- 后端根地址：<http://localhost:8000/>（自动跳转前端，避免未携带会话访问个人接口）
- 最终素材验收页：<http://localhost:8000/assets-review>
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/v1/health>
- 素材目录：<http://localhost:8000/api/v1/garment-assets>

也可以在已安装 Docker 的环境中运行：

```bash
cp .env.example .env
docker compose up --build
```

## 测试

纯规则测试不依赖第三方包，可直接运行：

```bash
cd backend
PYTHONPATH=. python -m unittest discover -s tests -v
```

本次交付已完成 14 项自动化测试和核心 API 冒烟，并真实调用 Open-Meteo 验证北京城市搜索及 2026-08-27 的 24 个小时数据点。生产运行要求 Python 3.11–3.13。

## 当前产品范围

微信登录和自定义场景已按产品决策移除。每个邀请码对应一个独立账号，同一邀请码可以在其他设备登录同一账号；邀请码只以摘要形式存储。视觉模型未配置时，识别接口明确返回不可用；配置后，只有用户主动点击识别时，图片才会发送给第三方视觉 Provider。

AI 模型按任务分流：视觉识别使用 `VISION_MODEL`；首页换一套、AI 命名与详情建议使用 `AI_FAST_MODEL`，系统推荐预生成使用 `AI_QUALITY_MODEL`。当前生产只依赖 qwen3.8-flash 与 qwen-turbo：视觉识别不配置其他备用模型，实时文本任务失败时可在两者之间切换一次。所有结构化调用均关闭思考模式。AIHubMix 主域名在本地网络不可达时，使用其官方同能力备用接口 `https://api.inferera.com/v1`。

业务接口集中在 `/api/v1`：`auth`、`settings`、`outfits`、`inspirations`、`notifications`、`feedback`、`recommendations`、`weather` 和 `garment-assets`。除健康检查与公开 SVG 素材目录外，业务 API 都要求 Bearer 会话；旧的运行状态、能力声明、独立规则评估和单素材详情路由已移除。

## veFaaS 部署准备

项目根目录的 `main.py` 是云端启动入口，自动读取平台的 `PORT`，无需复制后端代码。veFaaS 应识别为 Python HTTP 服务：

```bash
vefaas inspect -o json
vefaas login --check
vefaas gateway list --first -o json
```

首次发布前必须先登录，并确认账号下存在可用的 API Gateway。确认目标后再执行创建应用的部署命令；不要在未确认账号和网关时直接发布。

域名可以绑定到 veFaaS/APIG 的 HTTP 入口，但域名本身不保存数据。当前 SQLite 与本地图片卷用于本地完整验收；正式云端上线前还要提供云数据库和对象存储，由部署环境注入连接信息。生产配置通过部署环境和平台健康检查确认，不再对外暴露内部配置状态。

## 参考项目复用

服务分层、`/api/v1` 路由、Open-Meteo Provider、统一错误处理和素材静态服务参考了 Wardrowbe 的工程结构。交付目录不保留未参与运行的参考截图、README、Logo 或 PWA 素材；需要保留的归属与许可信息见 `THIRD_PARTY_NOTICES.md` 和 `third-party-licenses/`。实际服装 SVG 库保存在 `backend/app/static/garments/`。
