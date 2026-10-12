# 04 · T300 / COROS 蓝牙诊断流程

## 前置条件

- 在支持 BLE 的 macOS 主机执行；给 Terminal（或运行 Python 的宿主程序）开启系统蓝牙权限。
- T300 通电、没有其他应用正在独占控制；COROS 手表开启心率广播。
- 只做**发现、连接、服务枚举和允许的读取**；不要用这份诊断工具对设备发送 FTMS 控制指令。
- macOS CoreBluetooth 通常给出系统设备 UUID，并非传统 MAC 地址；同一设备的标识可能随机器/系统发生变化，不适合作为跨主机恒定配置。

## 步骤一：扫描

~~~bash
source .venv/bin/activate
indoor-cycling scan --seconds 10
~~~

每一行 JSON 可能包括 identifier、name、service_uuids、rssi。未发现设备时检查距离、电源、蓝牙权限、设备是否处于可广播状态，以及是否已被其他 App 连接。广播中没有标准服务 UUID **不能据此认定不支持**：需要进一步连接检查。

## 步骤二：逐台检查 GATT

~~~bash
indoor-cycling inspect '<T300-scan-identifier>'
indoor-cycling inspect '<COROS-scan-identifier>'
~~~

inspect 枚举服务/特征/descriptor，并对带 read 属性的特征执行读取。带 notify/indicate 的特征**并没有订阅**，因此不会持续显示实时心率、功率与踏频。

重点记录标准服务与特征（服务必须实机确认）：

| 意义 | 标准 UUID |
| --- | --- |
| Fitness Machine Service | 0x1826 |
| Fitness Machine Feature | 0x2ACC |
| Indoor Bike Data | 0x2AD2 |
| Supported Power Range | 0x2AD8 |
| Fitness Machine Control Point | 0x2AD9 |
| Fitness Machine Status | 0x2ADA |
| Heart Rate Service | 0x180D |
| Heart Rate Measurement | 0x2A37 |

即使看到控制点 0x2AD9，也不代表已证明 ERG 写入、控制权管理、应答格式或断连保护符合预期。后续硬件写入必须单独实现、测试和审查。

## 步骤三：采集设备兼容性信息

只记录：macOS 版本、Python/Bleak 版本、固件版本（如可读）、标准服务列表、特征属性、是否能读取相关能力位、异常类型。为避免暴露隐私，在公开 issue 中遮蔽设备 UUID、MAC/序列号以及个人心率记录。

## 常见故障

- 扫描为空：检查 macOS 系统设置 → 隐私与安全性 → 蓝牙、设备电源及广播状态。
- 能扫描但不能连接：关掉可能占用设备的训练 App；不要强行重复连接。
- 能连接但读失败：该特征可能没有 read 权限；notify/indicate 特征需要未来的实时订阅实现。
- 心率广播缺失：确认当前 COROS 型号确实开启 BLE 心率广播，并排除其他客户端连接。
- 读取成功但没有实时数据：这是当前版本的预期行为；实时订阅还没开发。

## 硬件安全边界

实验阶段不要执行高功率试错，也不要凭猜测构造私有控制包。真实写入实现后，应先校验控制权、参数范围、回执以及人体能主动停止踩踏的退出路径，再进行有监督的低功率实机验证。

参考 [07 - 状态与验收](07-status-and-acceptance.md)。

## BLE 心率与设备管理更新

CLI inspect 仍不订阅。Web /devices 新增标准 0x2A37 通知订阅，扫描、保存、连接、断开和移除均可操作；仅列表中的设备允许连接。扫描筛选标准心率广播或 COROS 名称，连接时再次验证标准服务和 notify 属性。
