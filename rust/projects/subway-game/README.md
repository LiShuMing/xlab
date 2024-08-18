# 🚇 地铁小向导 - 儿童地铁线路问答游戏

一个专为6岁儿童设计的地铁线路学习游戏，通过有趣的方式学习各大城市的地铁线路。

## ✨ 功能特点


- 🎮 **简单易用** - 大按钮、清晰界面，适合儿童操作
- 🌍 **多城市支持** - 北京、上海、东京、大阪、首尔等
- 📚 **学习地铁线路** - 了解换乘、站点距离
- 🏆 **闯关模式** - 累计星星，获得成就感
- 🎨 **可爱画风** - 色彩丰富，动画有趣
- 🔒 **完全离线** - 无需网络，随时随地玩

## 🚀 快速开始

### 环境要求


- macOS 10.15+
- Node.js 18+
- Rust 1.70+

### 安装依赖


```bash
npm install
```

### 开发运行


```bash
npm run dev
```

这将在 http://localhost:1420 启动开发服务器。

### 构建发布版


```bash
# 使用构建脚本（推荐）
./build.sh

# 或手动构建
npm run build
cd src-tauri
cargo tauri build
```

## 📁 项目结构


```
subway-game/
├── src/
│   ├── components/          # React 组件
│   │   ├── CitySelector.tsx   # 城市选择页面
│   │   ├── GameScreen.tsx     # 游戏主界面
│   │   ├── QuestionPanel.tsx  # 问题展示
│   │   ├── RouteOptions.tsx   # 路线选择
│   │   ├── FeedbackPanel.tsx  # 答题反馈
│   │   └── SubwayMap.tsx      # 地铁线路图
│   ├── data/                # 数据文件
│   │   ├── cities.json        # 城市元数据
│   │   ├── beijing.json       # 北京地铁数据
│   │   └── ...
│   ├── stores/              # 状态管理
│   │   └── gameStore.ts       # 游戏状态
│   ├── utils/               # 工具函数
│   │   └── routeCalculator.ts # 路线计算
│   └── types/               # TypeScript 类型
│       └── index.ts
├── src-tauri/               # Tauri/Rust 后端
│   ├── src/
│   │   └── main.rs            # 主入口
│   ├── Cargo.toml
│   └── build.rs
├── tauri.conf.json          # Tauri 配置
└── package.json
```

## 🎮 游戏规则


1. 选择一个城市
2. 系统随机出题（起点站 → 终点站）
3. 从3个选项中选择正确的路线
4. 答对获得星星奖励 🎉

## 🏙️ 支持的城市


| 城市 | 国家 | 难度 | 站点数 |
|------|------|------|--------|
| 🏯 北京 | 中国 | ⭐⭐ | 459 |
| 🌃 上海 | 中国 | ⭐⭐ | 459 |
| 🗼 东京 | 日本 | ⭐⭐⭐ | 286 |
| 🍜 大阪 | 日本 | ⭐⭐ | 133 |
| 🏯 首尔 | 韩国 | ⭐⭐ | 600 |

## 🔧 自定义

### 添加新城市


1. 在 `src/data/` 目录下创建城市数据文件（如 `tokyo.json`）
2. 更新 `src/data/cities.json` 添加城市信息
3. 参考现有城市数据结构

### 修改配色


编辑 `tailwind.config.js` 中的颜色配置：

```js
colors: {
  primary: '#FF6B6B',   // 主色调
  secondary: '#4ECDC4', // 辅助色
  success: '#6BCB77',   // 正确反馈
  error: '#FF8B8B',     // 错误反馈
}
```

## 📦 分发


构建完成后，DMG 安装包位于：
```
src-tauri/target/release/bundle/dmg/SubwayGuide_1.0.0_x64.dmg
```

### App Store 提交


1. 注册 Apple Developer Program
2. 配置代码签名
3. 使用 Xcode 提交审核

### 直接分发


- 分享 DMG 文件
- 或上传到网站供用户下载

## 📝 技术栈


- **前端**: React 18 + TypeScript + Vite
- **UI**: Tailwind CSS + Framer Motion
- **状态管理**: Zustand
- **桌面框架**: Tauri 2.0 + Rust
- **构建**: npm + cargo

## 📄 许可证


MIT License

## 👨‍👩‍👧 关于


为6岁宝宝设计的地铁学习游戏，让孩子在游戏中学习城市交通知识，培养方向感和逻辑思维能力。

**Made with ❤️ for kids**
