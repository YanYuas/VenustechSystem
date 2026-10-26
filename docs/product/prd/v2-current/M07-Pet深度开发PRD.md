# M07 Pet 桌宠深度开发PRD

> 分支：`feature/pet-deep` | 优先级：P1 | 预计工时：4天

## 一、模块定位

桌宠是启明星系统的"情感伴侣"，以二次元形象陪伴用户工作学习。支持桌宠/人形切换，多种互动动作，可主动提醒和对话，是产品的情感化差异化亮点。

**核心目标**：让工具不再冰冷，让陪伴触手可及

## 二、当前实现状态

### 已实现
- 桌宠角色（G01）：基础形象展示
- 桌宠对话气泡（G02）：简单文字气泡
- 桌宠悬浮模式（G03）：可拖动悬浮
- 基础动作：idle状态
- 动作切换UI（但曾出现无响应问题，已修复）

### 未实现/待完善
- 丰富的动作系统（工作/思考/休息/开心等）
- 桌宠与人形炫酷切换
- 互动动作（点击/拖拽/喂食）
- 主动提醒气泡
- 桌宠设置（大小、位置、透明度）
- 多套桌宠形象/皮肤
- 桌宠与第二分身联动
- 桌宠动画效果（呼吸、眨眼）
- 声音反馈
- 桌宠隐藏/显示

## 三、深度开发功能清单

### P0 必须完成

#### F01 动作系统完善
- **需求**：桌宠拥有多种状态动作，根据场景自动切换
- **实现**：
  - 基础动作：idle（待机）、blink（眨眼）、breath（呼吸）
  - 工作动作：working（打字）、thinking（思考）、reading（阅读）
  - 情绪动作：happy（开心）、sad（失落）、excited（兴奋）、sleepy（困倦）
  - 互动动作：wave（挥手）、dance（跳舞）、cheer（加油）
  - 动作切换过渡动画
  - 根据时间/任务状态自动切换动作
- **技术**：CSS动画 + SVG帧动画或Lottie
- **验收**：所有动作可正常切换，过渡流畅

#### F02 桌宠与人形切换
- **需求**：可在Q版桌宠和二次元人形之间炫酷切换
- **实现**：
  - 切换按钮（桌宠上右键或设置中）
  - 切换动画：星光粒子特效 + 渐变过渡
  - 人形模式：更大尺寸，更精细立绘
  - 桌宠模式：小巧Q版，适合角落放置
  - 切换状态记忆
- **验收**：切换动画流畅，两种模式均正常显示

#### F03 互动反馈
- **需求**：用户与桌宠互动时有反馈
- **实现**：
  - 点击桌宠：随机动作 + 对话气泡
  - 拖拽桌宠：移动到新位置，保存位置
  - 双击桌宠：打开第二分身对话
  - 右键菜单：动作选择、切换形态、设置、隐藏
  - 悬停效果：轻微放大 + 眼神跟随
- **验收**：所有互动有明确反馈

#### F04 主动提醒气泡
- **需求**：桌宠可主动弹出气泡提醒用户
- **实现**：
  - 任务到期提醒
  - 复盘时间提醒
  - 休息提醒（工作50分钟后）
  - 鼓励话语（完成任务后）
  - 气泡自动消失（5秒）
  - 点击气泡查看详情
- **依赖**：M09 Infrastructure通知系统
- **验收**：提醒事件触发时桌宠气泡正常弹出

### P1 高质量打磨

#### F05 桌宠设置面板
- **需求**：用户可自定义桌宠行为
- **实现**：
  - 大小调节：小/中/大
  - 透明度调节：50%-100%
  - 位置记忆：记住上次位置
  - 自动隐藏：全屏应用时隐藏
  - 互动开关：关闭点击互动
  - 声音开关
- **数据模型**：`pet_settings`表

#### F06 多套形象/皮肤
- **需求**：支持多种桌宠形象，用户可切换
- **实现**：
  - 内置2-3套基础形象
  - 形象选择器
  - 每套形象有独立动作
  - 自定义形象上传（二期）
- **数据模型**：`pet_skins`表

#### F07 与第二分身联动
- **需求**：桌宠是第二分身的物理化身
- **实现**：
  - 桌宠说话=第二分身说话
  - 第二分身主动建议时桌宠弹气泡
  - 点击桌宠打开对话
  - 人设变化时桌宠形象/动作变化
  - 桌宠动作反映第二分身状态

#### F08 动画效果增强
- **需求**：桌宠动画更生动自然
- **实现**：
  - 呼吸动画：轻微缩放
  - 眨眼动画：定时眨眼
  - 眼神跟随鼠标
  - 移动时的弹跳效果
  - 特殊节日动作（生日/新年）

### P2 二期预研

#### F09 声音反馈
- 桌宠互动时有音效
- 可选语音包
- 音量调节

#### F10 桌宠成长系统
- 桌宠有等级/经验
- 完成任务获得经验
- 升级解锁新动作/皮肤

#### F11 桌宠小游戏
- 简单的互动小游戏
- 休息时可玩

## 四、技术实现要点

### 前端
- `DesktopPet.vue`重构：动作系统 + 互动 + 气泡
- 新增组件：`PetActionController.vue`、`PetBubble.vue`、`PetSettingsPanel.vue`、`PetSkinSelector.vue`、`PetTransformEffect.vue`
- `usePetEvent` composable扩展：动作管理、互动事件、提醒监听
- 动画：CSS Keyframes + SVG动画，避免使用重型动画库
- 桌宠渲染：SVG（可缩放、可换色）或PNG序列帧

### 后端
- 桌宠主要在前端实现，后端提供：
  - `pet_settings`存储
  - 提醒事件推送（通过通知系统）
  - 动作配置（可配置化）
- 新增模型：`PetSetting`、`PetSkin`
- 新增迁移：0016_pet_settings.py

### 性能
- 桌宠使用CSS transform，避免重排
- 动画使用will-change优化
- 闲置时降低动画帧率
- 避免桌宠影响主界面性能

## 五、数据模型扩展

### pet_settings表
```sql
CREATE TABLE pet_settings (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL UNIQUE,
  enabled BOOLEAN DEFAULT 1,
  size TEXT DEFAULT 'medium', -- small/medium/large
  opacity REAL DEFAULT 1.0, -- 0.5-1.0
  position_x INTEGER DEFAULT 100,
  position_y INTEGER DEFAULT 100,
  current_skin TEXT DEFAULT 'default',
  current_form TEXT DEFAULT 'pet', -- pet/human
  auto_hide BOOLEAN DEFAULT 0,
  interaction_enabled BOOLEAN DEFAULT 1,
  sound_enabled BOOLEAN DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### pet_skins表
```sql
CREATE TABLE pet_skins (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  is_builtin BOOLEAN DEFAULT 1,
  config TEXT, -- JSON: 动作配置、颜色、资源路径
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 六、API接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/pet/settings` | 获取桌宠设置 |
| PUT | `/api/v1/pet/settings` | 更新桌宠设置 |
| GET | `/api/v1/pet/skins` | 获取可用皮肤列表 |
| POST | `/api/v1/pet/skins/{id}/activate` | 激活皮肤 |
| POST | `/api/v1/pet/action` | 触发指定动作（调试用） |
| GET | `/api/v1/pet/reminders` | 获取待提醒事件 |

## 七、验收标准

1. 桌宠动作系统完整，所有动作可正常切换
2. 桌宠/人形切换动画流畅
3. 点击/拖拽/双击/右键互动有反馈
4. 任务到期等事件触发桌宠气泡提醒
5. 桌宠设置可保存和恢复
6. 多套皮肤可切换
7. 桌宠与第二分身联动正常
8. 动画流畅，不影响主界面性能
9. 桌宠位置记忆正确
10. 四套主题下桌宠显示协调

## 八、风险与依赖

- **依赖**：M04 Conversation（第二分身联动）、M09 Infrastructure（通知系统）
- **风险**：SVG动画复杂度高，可能需要简化动作
- **性能**：桌宠动画可能影响低端设备性能，需做降级
- **资源**：二次元立绘资源需要设计或生成
- **兼容性**：不同屏幕尺寸下桌宠位置需适配
