# 介绍

此数据包是记录CAN总线数据到文件，并可以将保存的文件恢复到内存中。位于*'utils/replay.py'*。

# 内部变量

|变量名|说明|
|-----|----|
|`_stream`|CAN帧的数据流|
|`_last`|最后一次时间戳|
|`_curr`||
|`_pre_last`||
|`_shift`||
|`_size`||

# 函数接口

|函数原型|说明|
|-------|---|
|`reset(self)`||
|`stream(self)`||
|`passed_time(self)`||
|`restart_time(self, shift=.0)`||
|`append_time(self, times, can_msg)`||
|`append(self, can_msg)`||
|`set_index(self, i=0)`||
|`get_message(self, cnt)`||
|`add_timestamp(self, def_time=None)`||
|`next(self, offset=0, notime=True)`||
|`parse_file(self, name, _bus)`||
|`remove_by_id(self, idf)`||
|`search_messages_by_id(self, idf)`||
|`save_dump(self, fname, offset=0, amount=-1)`||

# 重载运算符

|函数原型|说明|
|-------|---|
|`__iter__(self)`||
|`__add__(self, other)`||
|`__len__(self)`||