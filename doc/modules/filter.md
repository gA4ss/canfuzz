# 介绍
此子模块是起过滤，CANID以及内容的作用，提供了各种黑白名单，在

# 动作参数

|名称|类型|默认值|描述|
|---|----|-----|---|
|"black_list"|整型，列表|无|当前CANID在黑名单中,进行阻断。|
|"white_list"|整型，列表|无|当前CANID不在白名单中，进行阻断。|
|"white_body"|整型，列表|无|对CAN数据进行审核，如果不在白名单中则阻断，其值是一个整数列表。|
|"black_body"|整型，列表|无|对CAN数据进行审核，如果在黑名单中则阻断，其值是一个整数列表。|
|"hex_white_body"|整型，列表|无|对CAN数据进行审核，如果不在白名单中则阻断，描述数据使用16进制字符串。|
|"hex_black_body"|整型，列表|无|对CAN数据进行审核，如果在黑名单中则阻断，描述数据使用16进制字符串。|
|"black_bus"|整型，列表|无|如果bus是在黑名单的，则阻断。|
|"white_bus"|整型，列表|无|如果bus是不在白名单的，则阻断。|

# 工作原理
在`do_effect`中函数中接收管道发来的CAN包随后进行判断。分为三组：**CANID**、**CAN数据**、**总线**。其中数据部分在动作参数中可以使用整型表示也可以使用16进制字符串描述都是一样的判断。依次**CANID**、**CAN数据**、**总线** 进行判断，首先判断白名单随后在判断黑名单，三组都是一样的原则。