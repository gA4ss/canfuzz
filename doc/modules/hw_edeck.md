# 介绍
本子模块用于使用电子甲板与真实CAN进行链接。

# 初始化参数

|名称|类型|默认值|描述|
|---|----|-----|---|
|"serial"|字符串|无|指定设备序列号。|
|"claim"|布尔值|*"True"*|释放已捕获的但是未匹配的USB接口资源。|
|"wait"|布尔值|*"False"*|如果设备此时不存在，则等待设备链接。|
|"bus_num"|整型|取值从 *[0, 1, 2]*，默认为*0*|总线序号，*edeck*设备有三套总线。|
|"bus_speed"|整型|*"500"*|设备波特率。|

# 动作参数

|名称|类型|默认值|描述|
|---|----|-----|---|
|"action"|字符串|取值从 *["read", "write"]* ，默认为 *"read"*|对数据流进行读写操作。|
||||*"read"*，从*edeck*中读取CAN数据并传输回管道中。|
||||*"write"*，将从管道中读取的CAN数据写入到*edeck*中。|

# 命令

|名称|参数|回调函数|描述|
|---|----|-------|----|
|"write"|<数据帧字符串>|`dev_write`|直接发送CAN数据帧, 类似如下字符串形式: 304:8:07df300101000000。|
|"write2"|<数据帧字符串>|`write_on_count`|按照给定次数发送CAN数据帧, 类似如下字符串形式: 304:8:07df300101000000,50,0.05。|
|"write3"|<数据帧字符串>|`write_on_time`|按照给定时间间隔发送CAN数据帧, 类似如下字符串形式: 304:8:07df300101000000,60,0.03。|

# USB接口相关函数
在模块启用后，会调用`connect`函数来遍历USB设备列表并取出USB设备的'VecdorID'与'ProductID'来确定设备。

```python
if device.getVendorID() == 0xbbaa and device.getProductID() in [0xddcc, 0xddee]:
```

电子甲板的'VecdorID'是`0xbbaa`，'ProductID'可选择两个`[0xddcc, 0xddee]`，任意一个都可以进行链接。

# 数据流

## 接收

1. 调用`usb.bulkRead`接收原始数据。
2. `can_recv`调用`parse_can_buffer`来解析原始数据并还原成数据流。
3. `do_read`接收到原始数据并合成`CANMessage`类的对象存入管道中。

## 发送

1. `do_write`将`CANMessage`类还原成数据流。
2. `can_send`调用`can_send_many`将数据流还原成原始数据流。
3. `can_send_many`调用`usb.bulkWrite`发送到USB设备中。