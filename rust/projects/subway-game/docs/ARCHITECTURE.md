# 架构设计文档

## 1. 项目概述

**地铁小向导** 是一个专为6岁儿童设计的地铁线路学习游戏，通过有趣的方式帮助孩子学习各大城市的地铁线路知识。

### 1.1 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端框架 | React | 18.x |
| 构建工具 | Vite | 5.x |
| 语言 | TypeScript | 5.x |
| 状态管理 | Zustand | 4.x |
| 动画库 | Framer Motion | 11.x |
| CSS框架 | Tailwind CSS | 3.x |
| 测试框架 | Vitest | 1.x |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    App.tsx                           │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │              GameScreen                      │    │    │
│  │  │  ┌──────────┐  ┌──────────────────────┐    │    │    │
│  │  │  │Question  │  │     SubwayMap        │    │    │    │
│  │  │  │ Panel    │  │      (SVG)           │    │    │    │
│  │  │  └──────────┘  └──────────────────────┘    │    │    │
│  │  │  ┌──────────┐  ┌──────────────────────┐    │    │    │
│  │  │  │ Route    │  │    FeedbackPanel     │    │    │    │
│  │  │  │Options   │  │   (Animation)        │    │    │    │
│  │  │  └──────────┘  └──────────────────────┘    │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   useGameStore                       │    │
│  │  (Zustand + LocalStorage Persistence)                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Data Layer                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  cities.json│  │  beijing.json│  │  other city data    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              routeCalculator.ts                      │    │
│  │  - BFS Shortest Path Algorithm                       │    │
│  │  - Random Station Generator                          │    │
│  │  - Question Option Generator                         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块

### 3.1 游戏状态管理

```typescript
// gameStore.ts
interface GameState {
  // 游戏状态
  gameState: 'selecting' | 'playing' | 'feedback';
  
  // 数据
  cities: City[];
  selectedCity: City | null;
  cityData: CityData | null;
  currentQuestion: Question | null;
  
  // 答题状态
  selectedAnswer: Route | null;
  isCorrect: boolean | null;
  
  // 进度
  score: number;
  totalQuestions: number;
  progress: Record<string, GameProgress>;
}
```

### 3.2 路线计算算法 (BFS)

```typescript
// routeCalculator.ts
function buildGraph(cityData: CityData): Map<string, GraphNode> {
  // 构建地铁网络图
  // 每个站点作为节点，相邻站点用边连接
}

function findShortestRoute(
  startId: string,
  endId: string,
  cityData: CityData
): Route | null {
  // BFS 算法查找最短路线
  // 返回路线、经过的线路、换乘次数
}
```

### 3.3 题目生成流程

```
生成新问题
    │
    ▼
┌────────────────┐
│ 获取当前城市数据 │
└────────────────┘
    │
    ▼
┌────────────────┐
│ 随机选择起点站  │
└────────────────┘
    │
    ▼
┌────────────────┐
│ 随机选择终点站  │
└────────────────┘
    │
    ▼
┌────────────────┐
│ BFS计算最短路线 │
└────────────────┘
    │
    ▼
┌────────────────┐
│ 生成干扰选项    │
└────────────────┘
    │
    ▼
┌────────────────┐
│ 打乱选项顺序    │
└────────────────┘
    │
    ▼
    ✓ 问题生成完成
```

---

## 4. 数据结构

### 4.1 城市数据 (cities.json)

```json
{
  "cities": [
    {
      "id": "beijing",
      "name": "北京",
      "icon": "🏯",
      "color": "#C23A30",
      "difficulty": "medium",
      ...
    }
  ]
}
```

### 4.2 地铁线路数据 (city.json)

```json
{
  "cityId": "beijing",
  "cityName": "北京",
  "lines": [
    {
      "id": "line-1",
      "name": "1号线",
      "color": "#C23A30",
      "stations": [
        {"id": "bj-1-01", "name": "苹果园", "x": 100, "y": 300},
        {"id": "bj-1-02", "name": "古城路", "x": 150, "y": 300}
      ]
    }
  ]
}
```

**坐标系统**:
- x, y 为相对坐标，用于 SVG 地图渲染
- 范围: 0-1300 (x), 0-600 (y)

---

## 5. 组件设计

### 5.1 组件树

```
App
├── CitySelector
│   └── [CityCard × N]
│
└── GameScreen
    ├── Header (返回按钮 + 城市名 + 分数)
    ├── QuestionPanel (起点 → 终点)
    ├── RouteOptions (3个选项按钮)
    ├── FeedbackPanel (答对/答错动画)
    └── SubwayMap (SVG地铁图)
```

### 5.2 组件职责

| 组件 | 职责 |
|------|------|
| `CitySelector` | 展示城市选择卡片网格 |
| `GameScreen` | 游戏主界面容器 |
| `QuestionPanel` | 显示起点和终点站信息 |
| `RouteOptions` | 展示3个路线选项供选择 |
| `FeedbackPanel` | 显示答题结果动画 |
| `SubwayMap` | SVG绘制的交互式地铁图 |

---

## 6. 儿童友好设计

### 6.1 UI 规范

| 设计元素 | 规范 |
|----------|------|
| 按钮尺寸 | 最小 64×64px |
| 圆角 | 16-24px |
| 颜色 | 高饱和度、区分度高 |
| 反馈 | 即时正向反馈 |
| 动画 | 平滑流畅 (Framer Motion) |

### 6.2 交互设计

- 单击选择，无需拖拽
- 大按钮，易点击
- 即时视觉反馈
- 无时间压力

---

## 7. 测试策略

### 7.1 测试类型

| 类型 | 工具 | 覆盖率目标 |
|------|------|-----------|
| 单元测试 | Vitest | ≥ 80% |
| 组件测试 | React Testing Library | ≥ 60% |
| E2E测试 | Playwright | 核心流程 |

### 7.2 测试文件结构

```
src/
├── __tests__/
│   ├── routeCalculator.test.ts    // BFS算法测试
│   ├── types.test.ts              // 类型定义测试
│   └── gameStore.test.ts          // 状态管理测试
```

---

## 8. 性能优化

### 8.1 渲染优化

- React.memo 避免不必要的重渲染
- Framer Motion 使用 transform 而非 layout
- 虚拟列表处理大量站点

### 8.2 加载优化

- 代码分割 (Vite 自动)
- 数据按需加载
- 静态资源压缩

---

## 9. 扩展性

### 9.1 添加新城市

1. 在 `src/data/` 创建城市 JSON 文件
2. 更新 `cities.json` 添加城市信息
3. 遵循相同的数据结构

### 9.2 添加新功能

- 新组件 → `src/components/`
- 新工具 → `src/utils/`
- 新状态 → `src/stores/`

---

## 10. 目录结构

```
subway-game/
├── src/
│   ├── components/       # React 组件
│   │   ├── CitySelector.tsx
│   │   ├── GameScreen.tsx
│   │   ├── QuestionPanel.tsx
│   │   ├── RouteOptions.tsx
│   │   ├── FeedbackPanel.tsx
│   │   └── SubwayMap.tsx
│   ├── data/             # 静态数据
│   │   ├── cities.json
│   │   ├── beijing.json
│   │   ├── shanghai.json
│   │   ├── tokyo.json
│   │   ├── osaka.json
│   │   └── seoul.json
│   ├── stores/           # 状态管理
│   │   └── gameStore.ts
│   ├── utils/            # 工具函数
│   │   └── routeCalculator.ts
│   ├── types/            # 类型定义
│   │   └── index.ts
│   ├── __tests__/        # 单元测试
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── docs/                 # 文档
│   ├── API.md
│   └── ARCHITECTURE.md
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```
