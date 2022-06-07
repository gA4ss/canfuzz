# 介绍
对CAN帧保存的封装类。位于*'untils/frag.py'*。

# `FragmentedCAN`类

```python
self.temp_msg[can_msg.frame_id] = collections.OrderedDict()
self.temp_msg[can_msg.frame_id]['idx'] = {}
self.temp_msg[can_msg.frame_id]['length'] = 0
self.temp_msg[can_msg.frame_id]['elements'] = 0
```

* `idx` 一个字典结构，键是can帧索引号，值是can帧数据。
* `length` can帧长度。
* `elements` 当前canid的包计数。

## 主要函数
* `add_can_loop`
* `clean_build_loop`
