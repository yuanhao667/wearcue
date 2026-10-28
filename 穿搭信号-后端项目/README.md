# WearCue 后端项目

当前交付是邮箱账号、邀请码注册、按账号隔离数据的多用户版本，仅保留通勤/约会/出行，提供：

- 当天完整逐小时天气与城市搜索；
- 版本化确定性穿衣规则；
- 官方模板推荐与“换一套”；
- 服装 SVG 素材目录与静态访问；
- 数据库会话、HttpOnly Cookie 接入与接口鉴权；
- 按账号隔离设置、个人穿搭、图片、收藏、推荐池、提醒和反馈；
- SQLite 本地数据持久化；配置 `PERSISTENT_DATA_DIR` 后自动备份、启动恢复，并把图片写入持久化卷；
- 图片上传、EXIF 纠正、三档缩略图、幂等去重；
- 生产视觉 Provider、人工确认、收藏与“我的穿搭”；
- 个人穿搭优先、官方模板兜底；
- Web Push 订阅、VAPID Provider、每日发送幂等；
- 连续跳过和每周冷热反馈；
- 健康检查、运行状态、能力声明和统一错误边界。

## 本地启动

要求 Python 3.11–3.13。请使用对应版本创建虚拟环境。

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

在已安装后端依赖并激活虚拟环境后，从后端项目目录运行完整测试集：

```bash
python -m pip install pytest
PYTHONPATH=backend python -m pytest backend/tests -q
```

`unittest discover` 仅收集类形式的部分规则测试，不能替代包含接口、邮箱认证和用户隔离测试的完整 pytest 验证。此次完整测试共 122 项通过；外部邮件和 AI 服务的真实调用不在离线测试验收范围内。

## 当前产品范围

微信登录和自定义场景已按产品决策移除。首次注册需要邮箱验证码、密码和一个未绑定的邀请码；注册后邀请码绑定账号，以后只用邮箱和密码登录。密码使用 scrypt 加盐摘要存储，邀请码和邮箱验证码也不以明文入库，并提供邮箱验证码重置密码。开发环境可使用 `EMAIL_DELIVERY_MODE=console` 联调；生产环境必须配置 `EMAIL_CODE_SECRET` 以及 `.env.example` 中的 SMTP 参数。视觉模型未配置时，识别接口明确返回不可用；配置后，只有用户主动点击识别时，图片才会发送给第三方视觉 Provider。

### Resend 邮件发送接入

网站与数据库继续部署在火山引擎，Resend 仅负责投递注册及密码重置邮件。用户已同意使用该邮件服务。2026-09-08 已完成账户注册登录并添加 `mail.wearcue.cn`（Tokyo，域名 ID `90c5464d-71d7-4ec8-a391-06ceed6ecc77`）；20:17 左右 Resend 显示 **Verified**。随后已安全配置生产 SMTP 与验证码 HMAC 密钥，并通过 CLI 发布后端稳定版本 23（`fzuv7che`）、前端稳定版本 59（`cbcr9h2y`），两者均为 `release complete`。

火山 TrafficRoute DNS 免费版已由用户本人开通。zone `279723` 已配置三条实际返回记录：`resend._domainkey.mail` TXT（完整公钥从 Resend 页面获取）、`rsend.mail` CNAME → `rsend-apne1.forge.rmta.net`、`send.mail` CNAME → `send.forge.rmta.net`。均已通过 `dig @ns1.volcengine-dns.com` 核验。浏览器输入一度将 rsend 值重复拼接，已修正并复核权威 DNS 正确。不要套用旧版 MX/SPF 示例；未启用收信，未改网站根域名记录。

用户已创建 API key：名称 `wearcue-production-email`、权限 `Sending access`、域名 `mail.wearcue.cn`；由用户本人复制，通过内存传递到后端环境变量，未写入代码或输出密钥。SMTP 465 TLS 实际发送连通性测试邮件成功，Resend 显示 Delivered（邮件 ID `5e7935fa-661a-4439-8463-813e16c606bc`），用户已明确确认在 Gmail 收到。

验收边界：后端 112 项测试、前端 86 项测试与类型检查、生产构建通过。线上健康检查 200，无效密码 401、无效邀请码 403；登录 HTML 含邮箱和验证码字段；过期会话访问设置 307 到登录页。原用户会话仍可访问设置，退出卡片在 1200px 网格中宽 591px、间距 18px，保留 P0 和布局修复。自动提交生产邀请码发送真实注册验证码的测试被安全审批拦截，未执行；不得将连通性邮件误称为完整线上注册验收。剩余本人步骤：用户在注册入口使用原邀请码绑定自己的邮箱、设置密码并输入本人收到的验证码，以验证真实注册、旧资料继承及之后的密码登录；真实密码重置同样尚未由用户验收。不要擅自代用户创建账号或重置密码。

1. 在 Resend 添加发信子域名 `mail.wearcue.cn`，按照其实际返回值在火山 DNS 配置验证记录，等待域名显示 verified。不要自行编造 DKIM/SPF 值。
2. 创建仅有发送权限、限定到该发信域名的 API key，作为后端 `SMTP_PASSWORD` 安全配置，不写入版本库或日志。
3. 后端设置 `APP_ENV=production`、`EMAIL_DELIVERY_MODE=smtp`、随机 `EMAIL_CODE_SECRET`，以及 `.env.example` 中的 Resend SMTP 配置。发送地址为 `WearCue <noreply@mail.wearcue.cn>`。连接使用端口 465 并校验 TLS 证书。
4. 确认生产邀请码和持久化数据目录后发布前后端。使用用户指定的收件邮箱验证注册邮件、一次性验证码、密码登录和密码重置，以及旧邀请码账号数据继承。

免费方案有每日发送上限；出现配额限制时应明确返回发送失败，不能回退为日志模拟发送。正式部署前须核对账户实际额度。官方接入说明：<https://resend.com/docs/send-with-smtp>。

AI 模型按任务分流：视觉识别使用 `VISION_MODEL`；首页实时换一套优先走 TypeSafe JEV（`JEV_API_KEY` 配置后启用，`JEV_MODEL` 默认 `jev-latest`），由 JEV 在天气规则已确定的必备槽位里从正式图标词表中做有限选择，只返回紧凑的图标映射与后续生图输入；JEV 未配置、超时或返回不可用结果时，自动回退到 `AI_FAST_MODEL`（当前默认 `qwen-turbo`，关闭思考模式、`max_tokens=480`），并由 `AI_REALTIME_TIMEOUT_SECONDS`（默认 30 秒，上限 60 秒）限制整条兜底调用，禁止切换到 `AI_QUALITY_MODEL`；AI 命名与详情建议使用 `AI_FAST_MODEL`；系统推荐预生成使用 `AI_QUALITY_MODEL`。JEV 不是对话模型，不能生成自由文本也无法读图，因此它只负责选图标；`label`、`outfit_dna`、`locked_features` 由一次更短的 `outfit_plan_text` 文案补充调用（同样使用 `AI_FAST_MODEL`）基于已定图标写出，该调用失败时降级为稳定词表文案，不影响图标方案。人物图片只在用户进入详情页且无缓存图时生成，不在“换一套”阶段提前生成。当前生产文字与视觉依赖千问 AI 平台（`qwen3.8-flash`、`qwen-turbo`），统一走 OpenAI 兼容接口 `https://dashscope.aliyuncs.com/compatible-mode/v1`，只需在 `VISION_API_KEY` 配置一个 Key，文字服务自动复用。生图单独走 `AI_IMAGE_API_URL`（当前仍为 `https://api.inferera.com/v1`，使用 `AI_IMAGE_API_KEY`），因为千问平台的生图是 DashScope 原生接口，路径与代码使用的 `/images/generations` 不同；待实测通过后再迁移。

业务接口集中在 `/api/v1`：`auth`、`settings`、`outfits`、`inspirations`、`notifications`、`feedback`、`recommendations`、`weather` 和 `garment-assets`。除健康检查与公开 SVG 素材目录外，业务 API 都要求 Bearer 会话；旧的运行状态、能力声明、独立规则评估和单素材详情路由已移除。

## veFaaS 部署准备

项目根目录的 `main.py` 是云端启动入口，自动读取平台的 `PORT`，无需复制后端代码。veFaaS 应识别为 Python HTTP 服务：

```bash
vefaas inspect -o json
vefaas login --check
vefaas gateway list --first -o json
```

首次发布前必须先登录，并确认账号下存在可用的 API Gateway。确认目标后再执行创建应用的部署命令；不要在未确认账号和网关时直接发布。

域名可以绑定到 veFaaS/APIG 的 HTTP 入口，但域名本身不保存数据。生产环境使用 `/tmp` 运行 SQLite，并通过 `PERSISTENT_DATA_DIR=/mnt/tos` 将一致性数据库快照、用户上传图和 AI 生成图保存到 veFaaS 的 TOS 读写挂载目录；实例缩容后可在下次启动时恢复。生产配置通过部署环境和平台健康检查确认，不再对外暴露内部配置状态。

## 参考项目复用

服务分层、`/api/v1` 路由、Open-Meteo Provider、统一错误处理和素材静态服务参考了 Wardrowbe 的工程结构。交付目录不保留未参与运行的参考截图、README、Logo 或 PWA 素材；需要保留的归属与许可信息见 `THIRD_PARTY_NOTICES.md` 和 `third-party-licenses/`。实际服装 SVG 库保存在 `backend/app/static/garments/`。
