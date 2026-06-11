---
name: "DSA — 股票智能分析系统"
description: "AI 驱动的多市场股票分析工作台，专业、冷静、可信"
colors:
  primary-cyan: "#00bcd4"
  primary-cyan-dark: "#00d4ff"
  accent-purple: "#7c6af7"
  accent-purple-dark: "#978af9"
  neutral-bg: "#f4f6f9"
  neutral-bg-dark: "#0c0e18"
  neutral-fg: "#141929"
  neutral-fg-dark: "#f7f9fb"
  surface-card: "#ffffff"
  surface-card-dark: "#13141f"
  surface-muted: "#edeff2"
  surface-muted-dark: "#1d1e2a"
  border-default: "#cdd3de"
  border-default-dark: "#2a2d3b"
  semantic-success: "#20ac64"
  semantic-warning: "#f59e0b"
  semantic-danger: "#f22d2d"
  semantic-destructive: "#eb3755"
  semantic-destructive-dark: "#ff4269"
typography:
  body:
    fontFamily: "'SF Pro Display', 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "'SF Pro Display', 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.24em"
  data:
    fontFamily: "'SF Pro Display', 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  sm: "0.75rem"
  md: "0.875rem"
  lg: "1rem"
  xl: "0.75rem"
  full: "9999px"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.5rem"
  "2xl": "2rem"
components:
  button-primary:
    backgroundColor: "{colors.primary-cyan}"
    textColor: "#041118"
    rounded: "{rounded.lg}"
    padding: "0.7rem 1.1rem"
  button-primary-hover:
    backgroundColor: "linear-gradient(135deg, #00d4ff, #00a8cc)"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.neutral-fg}"
    rounded: "{rounded.lg}"
    padding: "0.7rem 1.1rem"
  card-terminal:
    backgroundColor: "linear-gradient(180deg, rgba(255,255,255,0.96), rgba(244,246,249,0.96))"
    rounded: "{rounded.lg}"
  chip-accent:
    backgroundColor: "hsla(193,100%,43%,0.1)"
    textColor: "{colors.primary-cyan}"
    rounded: "{rounded.full}"
    padding: "0.25rem 0.75rem"
  input-surface:
    backgroundColor: "{colors.surface-card}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.75rem"
---

# Design System: DSA 股票智能分析系统

## 1. Overview

**Creative North Star: "终端暗室 (Terminal Darkroom)"**

像一个精心控制的暗房：信息是光，在深邃的暗色背景上精准浮现。不是冰冷的机构工具，也不做花哨的装饰。每一次色彩的出现都有目的——cyan 主色标记关键操作和当前选择，purple 标注洞察和二级重点，红绿传达涨跌信号。其余部分保持在克制的中性灰阶中。

这个系统以深色主题为默认（`defaultTheme="dark"`），因为目标用户——从个人投资者到专业交易者——最常在清晨、深夜、或多屏工作环境中查看数据。深色背景降低长时间盯盘的视觉疲劳，也让数据的高亮和警示色更具对比冲击力。浅色主题作为日间/高环境光场景的完整备选。

系统明确拒绝：传统券商的老旧表格堆积感、Robinhood 式的 gamification 娱乐化表达、以及 AI 生成 UI 中泛滥的紫色渐变泛滥 + Inter 垄断 + 毛玻璃过载。渐变边框是品牌签名，但 backdrop-blur 仅保留在关键卡片；Inter 降为 fallback，SF Pro 提升为首选 UI 字体。

**Key Characteristics:**
- 深色优先，浅色完整备选——不是简单反色，而是独立调校
- 数据密度高但可扫读——层次由间距、字重、微妙的边框色调建立，而非大块色彩
- 颜色有语义——cyan 是「系统」、purple 是「洞察」、红绿是「市场信号」——永不纯装饰
- 卡片通过渐变边框（cyan→purple mask）获得识别度，而不是靠 backdrop-blur 堆叠
- 动效克制：150-250ms 状态过渡，不编排入场序列

## 2. Colors

双主题色板：深色为默认，浅色为日间备选。两套主题各自独立调校亮度和饱和度，保证在各自光照环境下的对比度；不是简单色相翻转。

### Primary
- **Cyan (主色)** (`#00bcd4` light / `#00d4ff` dark): 主要操作按钮、当前选中态、导航激活指示器、链接、聚焦环。在深色主题中略微提亮以补偿暗背景。**≤10% 的屏幕面积使用此色**——稀有性是它的力量。

### Secondary
- **Purple (洞察色)** (`#7c6af7` light / `#978af9` dark): Markdown 报告中的二级标题、洞察卡片强调、策略标签、blockquote 左边框。传达「系统分析得出的洞察」，而非「可点击的操作」。不与 cyan 争夺主操作注意力。

### Neutral
- **页面背景** (`#f4f6f9` light / `#0c0e18` dark): 最底层表面，承载所有内容。
- **卡片表面** (`#ffffff` light / `#13141f` dark): 内容容器，通过微妙的渐变边框从背景中抬升。
- **前景/正文** (`#141929` light / `#f7f9fb` dark): 主文本色。浅色主题的前景色特意偏深蓝黑，而非纯黑，保持柔和但不失对比（≥4.5:1 against background）。
- **次级文本** (`hsl(224 18% 28%)` light / `hsl(228 16% 72%)` dark): 辅助信息、标签、描述。
- **静音文本** (`hsl(224 12% 35%)` light / `hsl(228 10% 48%)` dark): placeholder、禁用态、时间戳。
- **边框** (`#cdd3de` light / `#2a2d3b` dark): 分隔线、输入框边框、卡片轮廓。始终可见但始终低调。

### Semantic
- **成功/上涨** (`#20ac64`): 在中国市场语境中，红色上涨、绿色下跌。但该系统选择不绑定单一文化约定——绿色用于正向指标（盈利、得分、成功），具体涨跌颜色在图表中单独处理。
- **警告** (`#f59e0b`): 风险提示、需要注意的信号、评分临界区。
- **危险/下跌** (`#f22d2d`): 强烈负面信号、止损警示、错误状态。
- **破坏性操作** (`#eb3755` light / `#ff4269` dark): 删除、清空、不可逆操作。比 danger 略偏粉，区分「市场下跌」和「用户操作危险」。

### Named Rules
**The One Accent Rule.** Cyan 用于 ≤10% 的任意屏幕面积。主动作、选中态、链接、聚焦环——仅此四类场景。不在装饰元素、背景渐变、或非交互内容中使用 cyan。

**The Signal-Only Semantic Rule.** 红色和绿色不出现在纯装饰场景中。它们只传达市场信号、操作后果、或状态变化。在非金融页面中，优先用 cyan/purple/muted 传达信息。

**The Tinted Neutral Rule.** 所有中性色（背景、卡片、边框）向 cyan 色相微偏 0.005-0.01 chroma，不向暖色偏。这避免了「cream/sand body bg」的 AI 默认暖色调，同时让暗色背景不是纯灰——有微妙的科技冷感。

## 3. Typography

**Body Font:** SF Pro Display, Inter, Segoe UI, system-ui, -apple-system, sans-serif
**Label/Data Font:** 同字体族，通过字重和间距区分

**Character:** SF Pro 提升为首选后，macOS/iOS 用户体验原生 Apple 字体渲染；Inter 作为跨平台 fallback 保证一致性。这是一个专业的工具型产品，不需要 display/body 字体配对。同一字体族通过 weight（400/500/600/700）和 size 建立清晰层次。

### Hierarchy
- **页面标题** (600 weight, 1.25rem, line-height 1.3): 每个页面的主标题。使用 `text-wrap: balance`。
- **区块标题** (600 weight, 1rem, line-height 1.3): 卡片、面板、区块的标题。Purple 色用于报告内标题，foreground 色用于 UI 标题。
- **正文** (400 weight, 0.875rem, line-height 1.6): 报告内容、对话消息、描述文本。最大行长 65-75ch。
- **数据/数字** (500 weight, 0.875rem, line-height 1.4, tabular-nums): 表格数据、价格、百分比。使用 `font-variant-numeric: tabular-nums` 保证数字对齐。
- **标签/微文本** (700 weight, 0.6875rem, line-height 1, letter-spacing 0.24em, uppercase): 分类标签、badge 文字、section kicker。**仅用于 badge 和分类标记，不作为每个 section 的 eyebrow 装饰。**

### Named Rules
**The No-Display Rule.** 产品 UI 不使用 display 字体——没有 hero heading，没有 fluid clamp 标题。所有文字尺寸固定 rem 值（0.6875rem–1.25rem），不随视口缩放。

**The Tabular Data Rule.** 任何可能被用户扫读对齐的数字（价格、百分比、数量、时间）使用 `font-variant-numeric: tabular-nums`。比例数字在 UI 中不可接受。

## 4. Elevation

本系统使用**混合抬升策略**：表面通过渐变边框和极微弱阴影从背景中抬升，而不是通过大量 backdrop-blur 或重度投影。

深色主题中，卡片表面（`#13141f`）比背景（`#0c0e18`）亮约 5%，这个差异在暗环境中足以区分层次而不会刺眼。浅色主题中，卡片（`#ffffff`）在背景（`#f4f6f9`）上是唯一纯白层，自然获得焦点。

### Shadow Vocabulary
- **Soft Card** (`0 12px 24px hsl(220 20% 34% / 0.09), 0 3px 8px hsl(220 16% 28% / 0.05)`): 默认卡片阴影。极轻，仅暗示抬升。
- **Soft Card Strong** (`0 18px 34px hsl(220 20% 32% / 0.12), 0 6px 16px hsl(220 16% 28% / 0.07)`): Hover 态卡片阴影。略加深以响应交互。
- **Glow (Cyan)** (`0 0 20px hsla(193,100%,43%,0.18)`): 恐惧贪婪指数仪表盘等需要强调的圆形元素使用。仅在数据可视化场景中使用。

### Named Rules
**The Flat-By-Default Rule.** 表面在静止时平整。阴影只在 hover/focus 时增强，作为对交互的响应，而非默认装饰。

**The Gradient Border Lift Rule.** 卡片的主要「抬升感」来自 1px 渐变边框（cyan→purple→transparent mask），而非阴影堆叠。阴影是补充，边框是主角。

## 5. Components

### Buttons
- **Shape:** 圆角 0.9rem（`--radius` ≈ 1rem 体系）
- **Primary:** Cyan 渐变背景 (`linear-gradient(135deg, #00d4ff, #00a8cc)`)，深色文字 (`#041118`)，无边框，cyan 辉光阴影。Hover 时上移 1px + 辉光增强。
- **Secondary:** 透明背景，subtle 边框，次级文字色。Hover 时边框转 cyan、文字转主色。
- **Focus:** `0 0 0 3px hsla(var(--primary) / 0.16)` 聚焦环，所有按钮统一。
- **Disabled:** 58% opacity，无阴影，无 hover 位移。

### Cards
- **Terminal Card:** 系统签名卡片。1px 渐变边框（cyan→purple→dim mask），背景从 card 渐变到背景色。默认微阴影。Hover 时边框亮度提升 + 阴影加深 + 上移 1px。
- **Glass Card (克制使用):** 保留在需要强烈视觉区分的 Hero 级区域（报告头图、首页 Hero panel）。`backdrop-filter: blur(18px)` + 72% opacity 背景。**不在常规内容卡片上使用。**
- **Dashboard Card:** 与 Terminal Card 相同的渐变边框 mask 结构，但背景固定为 card 色，不渐变到背景。
- **Home Panel Card:** Terminal Card 的浅色变体，边框和阴影更轻。用于首页子面板。

### Inputs
- **Style:** Card 背景，边框 `hsl(217 28% 84%)` light / `hsl(226 19% 20%)` dark。Placeholder 色需满足 ≥4.5:1 对比度（静音色可能太暗/太亮，需检查）。
- **Focus:** 边框转 cyan + `0 0 0 4px hsla(var(--primary) / 0.15)` 外发光环。
- **Error:** 边框转 destructive 色，无额外辉光。
- **Disabled:** 65% opacity，cursor not-allowed。

### Chips / Badges
- **Cyan Chip:** Cyan 10% 背景，cyan 主色文字，cyan 20% 边框。圆角 full (9999px)。用于 AI 相关标签、策略名称。
- **Purple Badge:** Purple 15% 背景，purple 主色文字，purple 30% 边框。用于报告类别、洞察标签。
- **Success/Danger Badge:** 10% 对应色背景，对应色文字。用于状态指示。
- **History Sentiment Badge:** 带 inset box-shadow 的微光泽感，传达「指标读数」的感觉。

### Navigation
- **Style:** 左侧固定导航栏。Cyan 色作为激活态指示器（左边框 + 背景色微染 + 图标色）。宽度约 16rem。导航项高度 2.75rem，padding-x 1rem。
- **States:** 默认：透明背景 + muted 前景色。Hover：cyan 5% 背景。Active：cyan 9% 背景 + cyan 24% 左边框 + cyan 阴影 + cyan 图标色。
- **Brand:** 侧栏底部品牌区域，cyan 色微辉光阴影。

### Chat Bubbles
- **User Bubble:** Cyan 10% 背景 + cyan 20% 边框。右上角直角（`border-top-right-radius: 0.125rem`）。
- **AI Bubble:** Card 85% 背景 + subtle 边框。左上角直角（`border-top-left-radius: 0.125rem`）。
- **Avatar:** 小型圆形，user 用 cyan 半透明背景 + cyan 边框，AI 用 subtle 背景 + 白/黑边框。

## 6. Do's and Don'ts

### Do:
- **Do** 使用 SF Pro Display 作为首选字体，Inter 作为跨平台 fallback
- **Do** 保持 cyan 在 ≤10% 的屏幕面积内——主操作、选中态、链接、聚焦环
- **Do** 为所有数字数据使用 `font-variant-numeric: tabular-nums`
- **Do** 渐变边框（cyan→purple mask）作为卡片的主要视觉识别——这是品牌签名
- **Do** 在深色主题中保持卡片表面与背景的亮度差 ≤5%，避免刺眼
- **Do** 所有动画提供 `prefers-reduced-motion: reduce` 的 crossfade 回退
- **Do** 使用 OKLCH/HSL 变量体系——全局色板由 `:root` 和 `.dark` 中的 CSS 自定义属性控制

### Don't:
- **Don't** 使用 `background-clip: text` 渐变文字——用纯色，字重和大小传达强调
- **Don't** 使用 `border-left` 或 `border-right` >1px 作为彩色强调——用完整边框、背景色染、或前置图标
- **Don't** 在非关键区域使用 `backdrop-filter: blur`——glassmorphism 仅限 Hero 级报告头图和首页 Hero panel
- **Don't** 在每个 section 上堆叠 tiny uppercase tracked eyebrow（`font-size: 11px, letter-spacing: 0.24em`）——仅在 badge 和分类标签中使用
- **Don't** 使用纯黑（`#000`）或纯白（`#fff`）作为主要表面色——始终有微妙色调
- **Don't** 嵌套卡片——卡片内不应再套卡片。用间距和分区代替
- **Don't** 在非金融/非操作场景中使用红色或绿色——这些颜色是信号，不是装饰
- **Don't** 使用 bounce 或 elastic 缓动曲线——ease-out 指数曲线（quart/quint/expo）是唯一选择
- **Don't** 编排页面入场动画序列——产品加载到任务中，用户不想看加载表演
