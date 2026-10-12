# 05 · HTTP API、训练状态与本地数据

**当前 API 只控制模拟器。** 不存在真实 BLE 订阅、ERG 指令、COROS 云端写入或 FIT 导出。请勿把模拟功率、心率看作实测值。

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

前端目前每秒轮询一次 /api/status，不是 WebSocket 实时推送；页面只缓存本次打开输入的 token，不提供持久登录。

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

当前没有正式数据库迁移系统、同步队列、来源标签持久化和 FIT 文件生成能力。使用自定义 CYCLING_DB 时请放在不受 Git 跟踪的位置。改变 schema 必须同时更新测试、这里的字段表与备份/迁移说明，旧数据库升级前做备份。

## 5. 数据归档原则

实际训练数据未来以本地原始采样和事件为权威来源，再计算摘要、导出 FIT、尝试经正式验证的 COROS 同步。同步必须可重试且避免重复上传；当前以上仅为发展原则，非已交付能力。安全运维见 [06](06-security-and-operations.md)。
