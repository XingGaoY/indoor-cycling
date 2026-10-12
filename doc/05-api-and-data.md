# 05 · HTTP API、训练状态与本地数据

**当前 API 只控制模拟器。** 支持可选真实 BLE 心率订阅；不存在 ERG 指令、COROS 云端写入或 FIT 导出。请勿把模拟功率、心率看作实测值。

## 1. 服务与认证

~~~bash
export CYCLING_TOKEN="你自己的随机强令牌"
indoor-cycling serve   # 默认 127.0.0.1:8765
~~~

所有 /api/ 路径均要求请求头 X-Cycling-Token。缺少或错误返回 HTTP 401。服务从进程环境读取 token；修改后需要重启。没有细化用户权限、速率限制或生产级会话体系，不能把简单令牌当成适合公网的认证机制。

## 2. API 列表

| 路径 | 方法 | 请求体 | 行为 |
| --- | --- | --- | --- |
| /api/status | GET | 无 | 返回当前模拟训练状态 |
| /api/start | POST | 空 JSON 可选 | 新建模拟会话或恢复暂停 |
| /api/pause | POST | 空 JSON 可选 | 暂停运行中的会话 |
| /api/stop | POST | 空 JSON 可选 | 结束当前会话 |
| /api/power | POST | {"watts": 100} | 设置模拟目标功率（整数，40–150 W） |
| / | GET | 无 | 响应式网页 |
| /manifest.webmanifest | GET | 无 | 基础 manifest；完整可安装 PWA 未完成 |
| /sw.js | GET | 无 | 最小 Service Worker；当前不缓存业务数据 |

调用例子（示例需要在已有 CYCLING_TOKEN 的 shell 中执行）：

~~~bash
curl -H "X-Cycling-Token: $CYCLING_TOKEN" http://127.0.0.1:8765/api/status
curl -X POST -H "X-Cycling-Token: $CYCLING_TOKEN" -H 'Content-Type: application/json' -d '{"watts":100}' http://127.0.0.1:8765/api/power
curl -X POST -H "X-Cycling-Token: $CYCLING_TOKEN" http://127.0.0.1:8765/api/start
curl -X POST -H "X-Cycling-Token: $CYCLING_TOKEN" http://127.0.0.1:8765/api/pause
curl -X POST -H "X-Cycling-Token: $CYCLING_TOKEN" http://127.0.0.1:8765/api/stop
~~~

/api/status 示例响应：

~~~json
{
  "mode": "SIMULATOR",
  "state": "running",
  "target_power_w": 100,
  "actual_power_w": 100,
  "heart_rate_bpm": 125,
  "cadence_rpm": 82,
  "elapsed_s": 64.3,
  "session_id": "20261012T070000000000Z"
}
~~~

这里的数值和 session_id 仅说明字段含义，不代表真实设备数据。空闲/暂停/结束状态下，actual_power_w 为零、心率为 null、踏频为零。

## 3. 状态和计时

当前 state 值：idle、running、paused、ended。start 在 idle/ended 时创建会话，在 paused 时继续既有会话；pause 仅在 running 有效；stop 将 running/paused 会话写为 ended。重复 start（已 running）不会新建会话。

时间累积基于进程中的 monotonic 时钟，运行期间记录器约每秒写一条样本；计时器不是持久状态机。**重启服务后无法自动恢复正在训练的会话**，数据库中可能保留未标记结束的 session。未来引入真实硬件控制之前需要明确 crash recovery 和安全行为。

前端目前每秒轮询一次 /api/status，不是 WebSocket 实时推送；页面使用当前标签页 sessionStorage 保存 token，不提供长期持久登录。

## 4. SQLite schema（当前）

默认数据库：~/.local/share/indoor-cycling/sessions.sqlite3；可在服务启动前用 CYCLING_DB 指定绝对路径。

**sessions**
| 字段 | 含义 |
| --- | --- |
| id TEXT PRIMARY KEY | 当前模拟会话唯一标识 |
| started_at TEXT NOT NULL | UTC ISO 8601 |
| ended_at TEXT | 结束时间，可能为空 |
| duration_s REAL | 累计运行秒数 |
| final_state TEXT | 目前正常结束写入 ended |

**samples**
| 字段 | 含义 |
| --- | --- |
| session_id TEXT | 关联会话标识（当前未设置外键约束） |
| timestamp TEXT | UTC ISO 8601 |
| elapsed_s REAL | 累计运动秒数 |
| target_power_w INTEGER | 模拟目标功率 |
| actual_power_w INTEGER | 模拟实际功率 |
| heart_rate_bpm INTEGER | 模拟心率 |
| cadence_rpm INTEGER | 模拟踏频 |

当前只有 heart_rate_source 的增量迁移和来源标记，没有通用迁移系统、同步队列或 FIT 文件生成能力。使用自定义 CYCLING_DB 时请放在不受 Git 跟踪的位置。改变 schema 必须同时更新测试、这里的字段表与备份/迁移说明，旧数据库升级前做备份。

## 5. 数据归档原则

实际训练数据未来以本地原始采样和事件为权威来源，再计算摘要、导出 FIT、尝试经正式验证的 COROS 同步。同步必须可重试且避免重复上传；当前以上仅为发展原则，非已交付能力。安全运维见 [06](06-security-and-operations.md)。

## BLE 心率与设备管理更新

新增认证接口 GET /api/devices，POST /api/devices/scan、/save（identifier,name）、/connect（identifier）、/disconnect、/forget（identifier）。设备表 devices(identifier TEXT PRIMARY KEY,name TEXT NOT NULL)。samples 自动追加 heart_rate_source TEXT NOT NULL DEFAULT SIMULATOR，旧数据保持 SIMULATOR；迁移前请备份数据库。状态新增 heart_rate_source 和 heart_rate_device（state,identifier,heart_rate_bpm,age_s,stale,error）。选择真实设备后断连/超过 5 秒无数据为 null，来源仍 BLE；主动断开回到模拟器。模拟训练中记录的 BLE 心率不会使功率/踏频变为实测，混合会话不能视为真实训练记录。

## 手机多页面布局

底部导航提供训练（/）、设备（/devices）和记录（/history）三页，共享标签页访问凭证。触控控件至少 48px，兼容手机安全区。记录通过认证 GET /api/history 读取最近 50 条本机会话，并标注模拟训练和 BLE 心率来源。切换页面不停止后台训练或设备连接。当前服务仍监听本机；手机实机访问需要后续可信 HTTPS 与访问方案，当前未完成离线 PWA 安装能力。

## 6. 课程计划库 API（本次新增）

课程规划 API 仍使用相同的 `X-Cycling-Token`，所有课程均保存在 Mac mini 本地 SQLite。该接口只读写计划，**不会开始训练或发送 ERG 指令**。

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| GET | /api/plans | 列表（名称、时长、展开执行段数、更新时间） |
| GET | /api/plans/selected | 获取选中的计划或 null |
| POST | /api/plans/select | 传入 {"id": "..."} 选择课程；id=null 清除选择 |
| POST | /api/plans | 创建课程，JSON body |
| GET | /api/plans/{id} | 课程详情 |
| PUT | /api/plans/{id} | 更新已有课程，JSON body |
| POST | /api/plans/{id}/duplicate | 复制课程 |
| DELETE | /api/plans/{id} | 删除课程，同时清除对应选择 |

`POST /api/plans` 请求示例（单位：秒和 W）：

~~~json
{
  "name": "43 分钟模拟课程",
  "note": "只是课程规划，不会自动执行",
  "stages": [
    {"kind": "ramp", "name": "热身", "purpose": "warmup", "duration_s": 480, "start_watts": 50, "end_watts": 110},
    {"kind": "constant", "name": "稳定骑行", "purpose": "main", "duration_s": 600, "watts": 110},
    {"kind": "repeat", "name": "间歇", "repeat_count": 5, "steps": [
      {"kind": "constant", "name": "训练", "purpose": "main", "duration_s": 120, "watts": 140},
      {"kind": "constant", "name": "恢复", "purpose": "recovery", "duration_s": 120, "watts": 70}
    ]},
    {"kind": "ramp", "name": "冷身", "purpose": "cooldown", "duration_s": 300, "start_watts": 110, "end_watts": 50}
  ]
}
~~~

合法用途：`warmup/main/recovery/cooldown/custom`。每个叶子阶段必须有名称、用途、10–7200 秒整数时长；`constant` 使用 `watts`，`ramp` 使用 `start_watts/end_watts`。计划值允许 40–500 W（**不是**实机支持范围）。`repeat` 只允许一层，必须有 2–10 个叶子步骤，重复 1–30 次。课程包含 1–30 个顶层阶段，总时长不得超过 6 小时。不满足校验返回 HTTP 422；找不到 ID 返回 404。

持久化结构：

- `workout_plans(id TEXT PRIMARY KEY, content TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)`，content 为已校验、规范化的 JSON；数据保留原创建时间，修改更新更新时间。
- `workout_settings(key TEXT PRIMARY KEY, value TEXT)`，目前存储 `selected_plan` ID。

每次请求进行幂等建表，因此升级后旧 SQLite 不会丢弃原会话及 samples。备份依然遵循 [06](06-security-and-operations.md)，未来正式 schema 迁移需独立设计。删除课程不会移除旧会话（现有会话仍不包含计划快照）。

## 7. 可视化编辑器区间数据与预设

详见 [10](10-visual-workout-editor-design.md)。阶段可选 `power_zones: {"from":2,"to":2}` 与 `hr_zones: {"from":2,"to":3}`，数值均为 1–6；恒定功率目标只能是一个区间。存在 power_zones 时不要求任何绝对瓦数；旧 `watts/start_watts/end_watts` 仍兼容。hr_zones 下限不可超过上限。

新增认证 API：GET `/api/plans/presets`，POST `/api/plans/presets/{slug}/copy`，GET/PUT `/api/plans/zones`（保存 `ftp_w` 和 `hr_max_bpm`，允许 null）。模板只读，每次主动复制生成独立用户课程；个人参考值保存在 SQLite 的 workout_settings 中，默认 null。不存在自动校准、训练执行或实际 ERG 控制。
