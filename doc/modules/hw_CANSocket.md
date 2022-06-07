# 介绍
建立与*cansock*的通讯。通过*cansock*可以与其他软件进行交互CAN数据。

# 初始化参数

|名称|类型|默认值|描述|
|---|----|-----|---|
|"iface"|字符串|*"vcan0"*|设备接口名称。|

# 动作参数

|名称|类型|默认值|描述|
|---|----|-----|---|
|"action"|字符串|取值从 *["read", "write"]* ，默认为 *"read"*|对数据流进行读写操作。|
||||*"read"*，从*cansock*中读取CAN数据并传输回管道中。|
||||*"write"*，将从管道中读取的CAN数据写入到*cansock*中。|


# 命令

|名称|参数|回调函数|描述|
|---|----|-------|----|
|"write"|<数据帧字符串>|`dev_write`|直接发送CAN数据帧, 类似如下字符串形式: 304:8:07df300101000000。|

# 工作原理
此模块在`do_start`时会`self._socket = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)`建立一个`cansock`的链接。随后将管道流模式与*cansock*做了对接。


