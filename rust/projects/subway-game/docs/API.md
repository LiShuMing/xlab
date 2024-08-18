# API 文档

## 组件 API

### CitySelector


城市选择组件，显示所有可用的城市卡片。

```tsx
import { CitySelector } from './components/CitySelector';

function App() {
  return <CitySelector />;
}
```

**Props**: 无

**使用示例**:
```tsx
<CitySelector />
```

---

### GameScreen


游戏主界面，包含问题展示、路线选择和地图显示。

```tsx
import { GameScreen } from './components/GameScreen';
```

**Props**: 无 (从 Zustand store 获取状态)

**内部组件**:
- `QuestionPanel` - 显示起点和终点
- `RouteOptions` - 显示3个路线选项
- `FeedbackPanel` - 显示答题结果反馈
- `SubwayMap` - 显示地铁线路图

---

### Question
Panel


```tsx
interface QuestionPanelProps {
  startStation: Station;
  endStation: Station;
}

<QuestionPanel 
  startStation={{ id: 's1', name: '天安门', x: 100, y: 200 }}
  endStation={{ id: 's2', name: '西单', x: 200, y: 200 }}
/>
```

---

### Route
Options


```tsx
interface RouteOptionsProps {
  options: Route[];
  onSelect: (route: Route) => void;
  disabled: boolean;
}

<RouteOptions 
  options={[route1, route2, route3]}
  onSelect={(route) => handleSelect(route)}
  disabled={false}
/>
```

---

### SubwayMap


```tsx
interface SubwayMapProps {
  cityData: CityData;
  startStation: Station;
  endStation: Station;
  highlightRoute: Route | null;
}

<SubwayMap 
  cityData={cityData}
  startStation={start}
  endStation={end}
  highlightRoute={route}
/>
```

---

## Store API

### useGameStore


```tsx
import { useGameStore } from './stores/gameStore';

const { 
  gameState,      // 'selecting' | 'playing' | 'feedback'
  cities,         // City[]
  selectedCity,   // City | null
  currentQuestion,// Question | null
  score,          // number
  selectCity,     // (cityId: string) => Promise<void>
  generateQuestion,// () => void
  selectAnswer,   // (route: Route) => void
  nextQuestion,   // () => void
  goHome,         // () => void
} = useGameStore();
```

### Actions


| Action | Description | Parameters |
|--------|-------------|------------|
| `selectCity(cityId)` | 选择城市并加载地铁数据 | `cityId: string` |
| `generateQuestion()` | 生成新的问题 | - |
| `selectAnswer(route)` | 选择答案并判断对错 | `route: Route` |
| `nextQuestion()` | 进入下一题 | - |
| `goHome()` | 返回城市选择页面 | - |

---

## 工具函数 API

### routeCalculator.ts


```tsx
import { 
  findShortestRoute, 
  generateRandomStations,
  generateQuestionOptions 
} from './utils/routeCalculator';

// 查找最短路线
findShortestRoute(startId, endId, cityData): Route | null

// 生成随机起终点
generateRandomStations(cityData): { start: Station; end: Station }

// 生成题目选项
generateQuestionOptions(correctRoute, allStations, cityData): Route[]
```

---

## 数据类型

### City


```ts
interface City {
  id: string;           // 城市ID，如 'beijing'
  name: string;         // 中文名称，如 '北京'
  nameEn: string;       // 英文名称，如 'Beijing'
  country: string;      // 国家，如 '中国'
  flag: string;         // 国旗emoji，如 '🇨🇳'
  icon: string;         // 城市图标emoji，如 '🏯'
  color: string;        // 主题色，如 '#C23A30'
  difficulty: 'easy' | 'medium' | 'hard';
  lineCount: number;    // 线路数量
  stationCount: number;// 站点数量
  description: string;  // 城市描述
}
```

### Station


```ts
interface Station {
  id: string;      // 站点ID
  name: string;    // 站点名称
  x: number;       // X坐标（用于地图显示）
  y: number;       // Y坐标（用于地图显示）
}
```

### Line


```ts
interface Line {
  id: string;        // 线路ID
  name: string;      // 线路名称，如 '1号线'
  color: string;     // 线路颜色
  stations: Station[];// 站点列表
}
```

### Route

```ts
interface Route {
  stations: Station[];    // 路线经过的站点
  lines: string[];        // 经过的线路ID列表
  totalStops: number;     // 总站数
  transferCount: number;  // 换乘次数
}
```

### Question

```ts
interface Question {
  cityId: string;           // 城市ID
  startStation: Station;    // 起点站
  endStation: Station;      // 终点站
  correctRoute: Route;      // 正确答案
  options: Route[];         // 选项列表（3个）
}
```
