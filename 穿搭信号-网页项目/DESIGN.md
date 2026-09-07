# DESIGN.md

> WearCue 灵感库以图片为主、高密度浏览为先，用纸张感线条组织信息，不牺牲移动端双列效率。

## 1. Visual Theme & Atmosphere

**Style**: 编辑感纸张界面 · 高密度穿搭图库
**Keywords**: 克制、清晰、图片主导、细线、荧光标签、紧凑、可扫读
**Tone**: 日常时装编辑感，不做电商瀑布流，也不做大留白作品集。
**Feel**: 像一本可以快速翻阅和收藏的穿搭目录。

**Interaction Tier**: L1 精致静态
**Dependencies**: CSS only，不增加动画依赖。

## 2. Color Palette & Roles

```css
:root {
  --paper: #f8f5ed;
  --surface: #ffffff;
  --surface-alt: #f4f6f3;
  --surface-hover: #f8f9f7;
  --border: #dfe3de;
  --border-strong: #111315;
  --text: #111315;
  --text-secondary: #596067;
  --text-tertiary: #7a817d;
  --accent: #c8ff32;
  --accent-hover: #b8ef25;
  --deep-green: #173b2c;
  --sunshine: #ffda6e;
  --paper-rgb: 248, 245, 237;
  --accent-rgb: 200, 255, 50;
  --glass-rgb: 249, 251, 248;
  --white-rgb: 255, 255, 255;
  --ink-rgb: 17, 19, 21;
  --success: #628f16;
  --error: #b44336;
  --warning: #a36b18;
}
```

新改的灵感卡片只引用以上变量。单张卡只使用黑白灰、深绿和一个荧光强调色。

## 3. Typography Rules

**Font Stack**: 沿用项目本地字体栈，不新增网络字体请求。

```css
font-family: "DM Sans", Inter, ui-sans-serif, system-ui, -apple-system,
  BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
```

| Role | Size | Weight | Line Height | Letter Spacing |
|---|---:|---:|---:|---:|
| Page H1 | 28–32px | 500 | 1.2 | -0.02em |
| Card H2 | 16–20px | 650 | 1.25 | -0.01em |
| Body | 13–14px | 500 | 1.7 | 0.02em |
| Label | 10–12px | 750 | 1.2 | 0.02em |

标题不使用渐变或投影；标签使用纯色胶囊；链接 hover 只做颜色和下划线偏移变化。

## 4. Component Stylings

### Buttons

按钮默认高度 36px、圆角胶囊；hover 只改变边框或背景；active 下压 1px；focus-visible 使用 3px 强调色外框；disabled 降低透明度并移除位移。

### Cards

卡片使用 1px 边框、16px 圆角，整体高度由 2:3 主图决定。来源、标题、二级信息和操作按钮组合成底部毛玻璃浮层，覆盖图片下沿，不再拼接额外白色内容区；浮层使用 76%→94% 的浅色渐变、12px 背景模糊和轻微上投影，并与卡片底部共用圆角裁切，交界处不得露底或出现双边。一级标签叠放在图片右上角；二级信息带同时拥有浅灰顶线和浅灰底线，不能使用黑色重线。hover 仅加深边框和轻微阴影，focus-within 与 hover 一致。

### Navigation

沿用现有顶部导航与 sticky 筛选区。Tab 活跃态保留深绿文字与底部短线。

### Links

整张图片可进入详情，详情按钮为深绿底、黄色文字；hover 背景略亮；focus-visible 清晰可见。

### Tags / Badges

一级标签为场景和主风格，使用图片右上角的荧光绿胶囊，最多两个；二级标签为季节、男装/女装、第二风格和温度，使用双横线之间的紧凑灰色文字。系统/个人来源保留为标题上方的小标识。

## 5. Layout Principles

**Container**: 最大 1200px，桌面左右 24px；平板与手机左右 16px。
**Spacing**: 卡片间距桌面 16px、平板 14px、手机 10px；卡片信息内边距桌面 14px、手机 10px。
**Grid**:

```css
.library-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
@media (max-width: 1100px) {
  .library-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .library-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
```

## 6. Depth & Elevation

| Level | Treatment | Use |
|---|---|---|
| Flat | 无阴影、1px 细线 | 标签信息带、筛选项 |
| Subtle | `0 8px 22px rgb(17 19 21 / 7%)` | 卡片 hover |
| Elevated | `0 14px 34px rgb(20 71 55 / 28%)` | 固定上传按钮 |

## 7. Animation & Interaction

**Motion Philosophy**: 信息先出现，动效只用于状态反馈。
**Tier**: L1。

卡片和按钮使用 160ms 的背景、边框、阴影过渡；hover 不放大图片，避免四列滚动时视觉晃动；active 位移 1px。`prefers-reduced-motion: reduce` 下取消 transition 和 transform。

## 8. Do's and Don'ts

### Do

- 保持电脑 4 列、Pad 3 列、手机 2 列。
- 图片始终是卡片最大视觉区域。
- 文本和操作区以毛玻璃浮层覆盖图片底部，卡片不再额外向下增长。
- 标题单行截断，避免卡片高度失齐。
- 场景和主风格固定放在图片右上角。
- 季节、男装/女装、第二风格和适穿信息固定放在上下双线之间。
- 操作区直接跟随信息带，不再增加上边线。
- 每张卡片都有删除入口；系统预制内容删除时只对当前用户隐藏。
- “喜欢”和“删除”是同尺寸辅助按钮，“查看详情”保持操作区最宽。

### Don't

- ❌ 不恢复桌面双列大卡片。
- ❌ 不在手机端降为单列。
- ❌ 不把一级标签放进双横线信息带。
- ❌ 不隐藏男装/女装二级标签。
- ❌ 不在信息带与按钮之间重复分割线。
- ❌ 不把文本区重新拼接到图片下方。
- ❌ 不让毛玻璃浮层与图片之间出现白缝、双线或圆角穿帮。
- ❌ 不增加轮播、瀑布流或横向滑卡。
- ❌ 不改变现有筛选逻辑和数据结构。
- ❌ 不删除“重新生成”等既有操作。
- ❌ 不增加新的动效依赖。

## 9. Responsive Behavior

| Name | Width | Key Changes |
|---|---:|---|
| Desktop | >1100px | 4 列，16px 间距，完整按钮文案 |
| Tablet | 701–1100px | 3 列，14px 间距 |
| Mobile | ≤700px | 2 列，10px 间距，紧凑标题、标签和按钮 |

触摸按钮最小高度 36px；上传浮钮保持至少 56px。筛选区继续横向滚动或两列折叠，卡片图片和文字不得溢出。
