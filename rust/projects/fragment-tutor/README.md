# FragmentTutor

碎片时间学习助手 - 帮助你在碎片时间高效学习、复习和反思。

## 功能特性

### 📥 采集 (Capture)
- 捕获 URL：粘贴链接，自动提取正文并离线保存
- 手动记录：快速记录想法和笔记
- 离线阅读：所有内容保存在本地

### 🧠 分析 (Analyze)
- AI 驱动的快速摘要 (Quick Digest)
- 提取核心论点、第一性原理、对立观点
- 关键词汇提取
- 行动建议生成

### 🔄 复习 (Review)
- 间隔重复 (Spaced Repetition)
- 词汇卡片生成
- 知识点卡片
- 学习进度追踪

### 🤔 反省 (Reflect)
- 60 秒快速反省卡片
- 每日复盘提醒
- 习惯追踪（深度工作、睡眠、家庭时间）
- 连胜 streak 记录

## 快速开始

### 环境要求
- macOS 11.0+
- Node.js 18+
- Rust 1.70+

### 安装依赖

```bash
# 安装前端依赖
npm install

# 安装 Rust 依赖
cd src-tauri && cargo fetch && cd ..
```

### 配置 Anthropic API Key

1. 打开 [Anthropic Console](https://console.anthropic.com/)
2. 创建 API Key
3. 在应用设置中填入 API Key

### 开发模式

```bash
# 启动前端开发服务器
npm run dev

# 在单独的终端启动 Tauri
npm run tauri dev
```

### 构建发布版

```bash
# 构建前端
npm run build

# 构建 macOS 应用
npm run tauri build
```

## 项目结构

```
fragment-tutor/
├── src/                    # React 前端
│   ├── components/         # UI 组件
│   │   ├── Layout.tsx      # 布局
│   │   ├── Header.tsx      # 顶部导航
│   │   ├── Sidebar.tsx     # 侧边栏
│   │   ├── CaptureModal.tsx # 捕获弹窗
│   │   ├── ReflectionCard.tsx # 反省卡片
│   │   ├── DocumentCard.tsx # 文档卡片
│   │   ├── FlashCard.tsx   # 复习卡片
│   │   └── ReaderView.tsx  # 阅读视图
│   ├── pages/              # 页面
│   │   ├── LibraryPage.tsx # 知识库
│   │   ├── TodayPage.tsx   # 今日任务
│   │   ├── ReviewPage.tsx  # 复习队列
│   │   ├── ReflectionPage.tsx # 反省记录
│   │   └── SettingsPage.tsx # 设置
│   ├── hooks/              # React Hooks
│   │   ├── useDocuments.ts
│   │   ├── useReviews.ts
│   │   ├── useReflection.ts
│   │   └── useShortcuts.ts
│   ├── services/           # API 服务
│   ├── store/              # 状态管理
│   ├── types/              # TypeScript 类型
│   └── utils/              # 工具函数
├── src-tauri/              # Rust 后端
│   ├── src/
│   │   ├── lib.rs          # Tauri 应用入口
│   │   ├── commands/       # Tauri 命令
│   │   │   ├── document.rs # 文档操作
│   │   │   ├── analysis.rs # AI 分析
│   │   │   ├── review.rs   # 复习系统
│   │   │   └── reflection.rs # 反省记录
│   │   └── services/       # Rust 服务
│   │       ├── database.rs # SQLite 操作
│   │       ├── anthropic.rs # Anthropic API
│   │       └── scraper.rs  # 网页抓取
│   └── Cargo.toml
└── package.json
```

## 技术栈

### 前端
- React 18 + TypeScript
- Vite 5
- Tailwind CSS 3
- Zustand (状态管理)
- date-fns (日期处理)

### 后端
- Tauri 2.0
- Rust 1.70
- SQLite + sqlx
- reqwest (HTTP 客户端)

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `⌘⇧N` | 打开捕获窗口 |
| `⌘⇧R` | 打开反省卡片 |
| `⌘1-4` | 切换页面 |
| `Esc` | 关闭弹窗 |

## API 配置

需要配置 Anthropic API Key 来启用 AI 分析功能：

1. 在应用设置中填入 API Key
2. 支持 `claude-sonnet-4-20250514` 模型
3. API 调用在 Rust 后端执行，保护 API Key 安全

## 隐私

- 所有数据存储在本地
- API Key 仅在本地使用，不会上传
- 支持离线使用

## 许可证

MIT License
