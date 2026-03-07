# AGENTS.md - 地铁小向导 (Subway Guide)

本文档为 AI 编程助手提供项目背景、架构和开发指南。项目语言为中文，所有用户界面和文档均使用中文。

---

## 项目概述

**地铁小向导** 是一个专为 6 岁儿童设计的地铁线路学习桌面应用。通过游戏化的问答形式，让孩子在互动中学习各大城市的地铁线路知识，培养方向感和逻辑思维能力。

### 核心功能

- 🎮 **闯关模式** - 系统随机出题（起点站 → 终点站），从 3 个选项中选择正确路线
- 🌍 **多城市支持** - 北京、上海、东京、大阪、首尔等城市的真实地铁数据
- 📚 **教育意义** - 学习换乘、站点距离、路线规划
- 🏆 **星星奖励** - 累计星星，获得成就感
- 🎨 **儿童友好** - 大按钮、清晰界面、丰富动画、可爱配色
- 🔒 **完全离线** - 无需网络，随时随地玩

---

## 技术栈

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.x | UI 框架 |
| TypeScript | 5.x | 类型安全 |
| Vite | 5.x | 构建工具 |
| Tailwind CSS | 3.x | 原子化 CSS |
| Framer Motion | 11.x | 动画效果 |
| Zustand | 4.x | 状态管理 |
| Lucide React | 0.33.x | 图标库 |
| clsx | 2.x | 类名合并 |

### 桌面框架

| 技术 | 版本 | 用途 |
|------|------|------|
| Tauri | 2.x | Rust 桌面应用框架 |
| Rust | 1.70+ | 后端运行时 |

### 测试

| 技术 | 版本 | 用途 |
|------|------|------|
| Vitest | 4.x | 单元测试框架 |
| @testing-library/react | 16.x | React 组件测试 |
| @testing-library/jest-dom | 6.x | DOM 断言 |
| jsdom | 27.x | 浏览器环境模拟 |

---

## 项目结构

```
subway-game/
├── src/                          # 前端源代码
│   ├── components/               # React 组件
│   │   ├── CitySelector.tsx      # 城市选择页面
│   │   ├── GameScreen.tsx        # 游戏主界面容器
│   │   ├── QuestionPanel.tsx     # 问题展示（起点→终点）
│   │   ├── RouteOptions.tsx      # 路线选择选项
│   │   ├── FeedbackPanel.tsx     # 答题反馈（正确/错误动画）
│   │   └── SubwayMap.tsx         # SVG 地铁线路图展示
│   ├── data/                     # 城市地铁数据
│   │   ├── cities.json           # 城市元数据列表
│   │   ├── beijing.json          # 北京地铁数据（27条线路，459站）
│   │   ├── shanghai.json         # 上海地铁数据
│   │   ├── tokyo.json            # 东京地铁数据
│   │   ├── osaka.json            # 大阪地铁数据
│   │   └── seoul.json            # 首尔地铁数据
│   ├── stores/                   # 状态管理
│   │   └── gameStore.ts          # Zustand 游戏状态（含持久化）
│   ├── utils/                    # 工具函数
│   │   └── routeCalculator.ts    # 路线计算（BFS 最短路径算法）
│   ├── types/                    # TypeScript 类型定义
│   │   └── index.ts              # 所有类型接口
│   ├── __tests__/                # 测试文件
│   │   ├── setup.ts              # 测试环境配置（mock localStorage）
│   │   ├── routeCalculator.test.ts  # 路线计算算法测试
│   │   └── types.test.ts         # 类型定义测试
│   ├── main.tsx                  # React 入口
│   ├── App.tsx                   # 根组件（状态切换：selecting/playing/feedback）
│   └── index.css                 # 全局样式（Tailwind + 渐变背景）
├── src-tauri/                    # Rust/Tauri 后端
│   ├── src/
│   │   └── main.rs               # Rust 主入口
│   ├── Cargo.toml                # Rust 依赖配置
│   ├── build.rs                  # Rust 构建脚本
│   └── icons/                    # 应用图标
├── docs/                         # 项目文档
│   ├── ARCHITECTURE.md           # 架构设计文档
│   └── API.md                    # 组件/API 文档
├── tauri.conf.json               # Tauri 配置（窗口、打包、托盘）
├── package.json                  # Node.js 依赖
├── vite.config.ts                # Vite 配置
├── vitest.config.ts              # Vitest 测试配置
├── tsconfig.json                 # TypeScript 配置
├── tailwind.config.js            # Tailwind 配置（自定义颜色主题）
├── build.sh                      # macOS 构建脚本
└── index.html                    # HTML 入口
```

---

## 核心数据类型

```typescript
// 城市元数据
interface City {
  id: string;           // 城市标识，如 "beijing"
  name: string;         // 城市名称，如 "北京"
  nameEn: string;       // 英文名称
  country: string;      // 国家
  flag: string;         // 国旗 emoji
  icon: string;         // 城市图标 emoji
  color: string;        // 主题色
  difficulty: 'easy' | 'medium' | 'hard';
  lineCount: number;    // 线路数量
  stationCount: number; // 站点数量
  description: string;  // 描述
}

// 站点
interface Station {
  id: string;   // 站点唯一标识（格式：{city}-{line}-{number}）
  name: string; // 站点名称
  x: number;    // 地图坐标 X（用于 SVG 渲染，范围约 0-1300）
  y: number;    // 地图坐标 Y（用于 SVG 渲染，范围约 -100 到 700）
}

// 地铁线路
interface Line {
  id: string;       // 线路标识
  name: string;     // 线路名称，如 "1号线"
  color: string;    // 线路颜色（十六进制）
  stations: Station[];
}

// 城市完整数据
interface CityData {
  cityId: string;
  cityName: string;
  lines: Line[];
}

// 路线（计算结果）
interface Route {
  stations: Station[];   // 经过的站点
  lines: string[];       // 经过的线路 ID 列表
  totalStops: number;    // 总站数
  transferCount: number; // 换乘次数
}

// 问题
interface Question {
  cityId: string;
  startStation: Station;
  endStation: Station;
  correctRoute: Route;
  options: Route[];      // 3 个选项（1 正确 + 2 干扰）
}

// 游戏状态
type GameState = 'selecting' | 'playing' | 'feedback';

// 游戏进度（持久化）
interface GameProgress {
  cityId: string;
  correctCount: number;
  totalCount: number;
  lastPlayed: string;
}
```

---

## 可用命令

### 开发命令

```bash
# 启动开发服务器（在 http://localhost:1420）
npm run dev

# 使用 Tauri 启动桌面应用
npm run tauri dev
```

### 构建命令

```bash
# 构建前端（输出到 dist/）
npm run build

# 使用构建脚本（推荐，包含完整流程）
./build.sh
```

### 测试命令

```bash
# 运行所有测试
npx vitest

# 运行测试并监视文件变化
npx vitest --watch

# 运行测试并生成覆盖率报告
npx vitest --coverage
```

### Tauri 命令

```bash
# Tauri 开发模式
npm run tauri dev

# 构建 Tauri 发布版本
npm run tauri build

# 仅构建 Rust 部分
cd src-tauri && cargo build --release
```

---

## 代码风格指南

### TypeScript 规范

1. **严格类型** - 启用 `strict: true`，所有函数参数和返回值必须显式声明类型
2. **接口优先** - 优先使用 `interface` 而非 `type` 定义对象形状
3. **导出规范** - 组件使用命名导出 `export function ComponentName()`
4. **类型文件** - 所有类型定义集中在 `src/types/index.ts`

### React 组件规范

1. **函数组件** - 使用函数组件 + Hooks，不使用类组件
2. **文件命名** - 组件文件名使用 PascalCase，如 `CitySelector.tsx`
3. **组件结构** - 每个组件一个文件，位于 `src/components/`
4. **动画** - 使用 Framer Motion 的 `motion` 组件添加入场/交互动画
5. **样式** - 使用 Tailwind CSS 工具类，复杂样式使用模板字符串

示例：
```tsx
import { motion } from 'framer-motion';

export function ComponentName() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-4 bg-white rounded-lg"
    >
      {/* 内容 */}
    </motion.div>
  );
}
```

### 状态管理规范

1. **使用 Zustand** - 全局状态统一使用 Zustand 管理
2. **持久化** - 使用 `persist` 中间件保存游戏进度到 localStorage
3. **状态分割** - 状态和操作分开定义，便于类型推断

### 样式规范

1. **Tailwind 优先** - 优先使用 Tailwind 工具类
2. **主题色** - 使用 `tailwind.config.js` 中定义的颜色：
   - `primary: '#FF6B6B'` - 主色调（红色）
   - `secondary: '#4ECDC4'` - 辅助色（青色）
   - `accent: '#FFE66D'` - 强调色（黄色）
   - `success: '#6BCB77'` - 成功色（绿色）
   - `error: '#FF8B8B'` - 错误色（粉色）
3. **渐变背景** - 全局背景使用 `bg-gradient-to-br` 渐变

---

## 测试策略

### 测试配置

- **框架**: Vitest
- **环境**: jsdom
- **断言**: Vitest 内置 + @testing-library/jest-dom
- **React 测试**: @testing-library/react

### 测试文件位置

测试文件位于 `src/__tests__/` 目录：
- `src/__tests__/routeCalculator.test.ts` - 测试 BFS 路线计算算法
- `src/__tests__/types.test.ts` - 测试类型定义
- `src/__tests__/setup.ts` - 测试环境配置（已 mock localStorage）

### 测试规范

1. **单元测试** - 重点测试工具函数（如 `routeCalculator.ts`）
2. **Mock 数据** - 使用 mock 数据测试，不依赖真实城市数据
3. **localStorage** - 测试环境中已配置 localStorage mock

### 运行测试

```bash
# 单次运行
npx vitest run

# 开发模式（监视）
npx vitest

# 带覆盖率
npx vitest --coverage
```

---

## 构建与发布

### 开发环境要求

- macOS 10.15+
- Node.js 18+
- Rust 1.70+

### 构建流程

1. **前端构建** - Vite 构建到 `dist/` 目录
2. **Rust 检查** - `cargo check` 检查 Rust 代码
3. **Rust 构建** - `cargo build --release` 构建发布版本
4. **应用打包** - Tauri 打包为 DMG 安装包

### 构建输出

构建完成后，输出文件位于：
```
src-tauri/target/release/bundle/
├── dmg/SubwayGuide_1.0.0_x64.dmg    # DMG 安装包
└── macos/SubwayGuide.app            # 可直接运行的应用
```

### 推荐构建方式

```bash
# 使用构建脚本（自动完成所有步骤）
./build.sh
```

该脚本会：
1. 检查 Node.js 和 Rust 环境
2. 安装 npm 依赖
3. 构建前端
4. 构建 Rust 后端
5. 打包 DMG

---

## 添加新城市

要在游戏中添加新城市，需要：

1. **创建城市数据文件** `src/data/{cityId}.json`：
```json
{
  "cityId": "cityId",
  "cityName": "城市名",
  "lines": [
    {
      "id": "line-1",
      "name": "1号线",
      "color": "#HEX颜色",
      "stations": [
        {"id": "city-1-01", "name": "站点名", "x": 100, "y": 100}
      ]
    }
  ]
}
```

2. **更新城市元数据** `src/data/cities.json`：
```json
{
  "id": "cityId",
  "name": "城市名",
  "nameEn": "CityName",
  "country": "国家",
  "flag": "🇨🇳",
  "icon": "🏯",
  "color": "#主题色",
  "difficulty": "medium",
  "lineCount": 10,
  "stationCount": 200,
  "description": "描述"
}
```

3. **数据要求**：
   - 站点 ID 格式：`{city}-{line}-{number}`（如 `bj-1-01`）
   - 坐标系统：使用相对坐标，范围参考现有数据（约 0-1300）
   - 换乘站：相同 ID 的站点在不同线路中视为换乘站

---

## 路线计算算法

核心算法位于 `src/utils/routeCalculator.ts`：

1. **建图** - 从城市数据构建邻接表图结构
2. **BFS 搜索** - 使用广度优先搜索查找最短路径
3. **换乘计算** - 统计路径中线路切换次数
4. **选项生成** - 生成正确答案 + 2 个干扰选项

---

## 安全注意事项

1. **Tauri 配置** - `tauri.conf.json` 中配置了最小权限：
   - 不使用 `withGlobalTauri`
   - 前端和后端通信仅通过 Tauri 命令
   - 唯一暴露的命令是 `get_app_version`

2. **本地存储** - 游戏进度保存在 localStorage，使用 Zustand 的 `persist` 中间件

3. **离线应用** - 应用完全离线运行，无网络请求

4. **自动启动** - Rust 后端配置了 `tauri-plugin-autostart` 插件

---

## 常见问题

### 开发服务器无法启动

检查端口 1420 是否被占用，或查看 Vite 错误信息。

### Rust 构建失败

确保 Rust 版本 >= 1.70：
```bash
rustc --version
```

### 测试失败

检查是否所有依赖已安装：
```bash
npm install
```

---

## 许可证

MIT License

---

*Made with ❤️ for kids*
