# 介绍
此子模块用于接收can包，以及加载保存can包的文件。

# 初始化参数

|名称|类型|默认值|描述|
|---|----|-----|---|
|"load_from"|字符串|无|文件路径，用于从文件中加载流量数据。|
|"save_to"|字符串|*"~/.canfuzz/dump.can"*|用于保存当前缓存的流量数据到文件。|

# 动作参数

|名称|类型|默认值|描述|
|---|----|-----|---|
|"delay"|整型|*0*|用于回放流量包时的时间间隔。|
|"ignore_time"|布尔值|*false*|是否忽略延迟时间。|

# 命令

|名称|参数|回调函数|描述|
|---|----|-------|----|
|"sniff"|无|`sniff_mode`|启用/禁用 嗅探模式。在开启嗅探模式下，"replay"与"save"命令将被禁用。|
|"print"|无|`cnt_print`|打印已经加载的流量包的数量。|
|"load"|*<文件路径>*|`cmd_load`|从文件中加载流量包。|
|"replay"|*<X>-<Y>*|`replay_mode`|从已经加载的流量中回放指定范围的包。|
|"save"|*<X>-<Y>*|`save_dump`|保存指定范围的流量包到文件。|
|"clean"|无|`clean_table`|清除已经缓存的包。|

# 工作原理

此模块分为两个模式，回访模式与嗅探模式，在嗅探模式下，保存引擎发过来的包并保存到变量`CANList`变量。在此模式下回访模式与保存模式将被禁用，因为此模式就是为了保存现有的数据包。回访模式是将`CANList`变量保存的包在回访到数据流中供引擎其他的模块读取，当回访完毕将自动转入嗅探模式。