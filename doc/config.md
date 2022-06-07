# 策略文件说明

策略文件主要用于将不同的子模块联合起来共同实现一个组合性功能，也是调用单一子模块的启动方式。

# 例子说明

以下例子是调用edeck接口来实现分析。

```python
# -*- coding: utf-8 -*-
version = 1.0
name = 'edeck缓存测试'
describe = '当前策略用于edeck测试'

modules = {
  'io/hw_edeck': {'bus_num': 0, 'bus_speed': 500},
  'basic/analyze': {}
}

actions = [
  {'hw_edeck': {'action': 'read', 'pipe': 1}},
  {'analyze': {'action': 'read', 'pipe' : 1}},
  {'analyze': {'action': 'write', 'pipe' : 2}},
  {'hw_edeck': {'action': 'write', 'pipe': 2}}
]

```

## 关键元素

* `version`         策略文件版本
* `name`            策略名称
* `describe`        策略描述
* `modules`         当前策略使用的模块
* `actions`         策略执行流程

## 基本信息

基本信息是`version`,`name`,`describe`是描述这个策略文件的基本信息，三个简单的变量。

## `modules`

模块是一个字典机构，每项的建名是一个字符串用来表示模块名称，这里可以是以相对目录结构。例如下面的 *'io/hw_edeck'*
在启动模块时，会在引擎的加载模块目录的 *'io'* 目录下查找 *'hw_edeck.py'* 模块。值字段也是一个字典结构用于存放
模块初始化参数。

```python
modules = {
  'io/hw_edeck': {'bus_num': 0, 'bus_speed': 500},
  'canfuzz/analyze': {}
}
```

在*kernel/engine.py*的`load_config`函数可以看出。调用`self._init_module(path, module, init_params)`函数对
子模块进行初始化。

## `actions`

```python
actions = [
  {'hw_edeck': {'action': 'read', 'pipe': 1}},
  {'analyze': {'action': 'read', 'pipe' : 1}},
  {'analyze': {'action': 'write', 'pipe' : 2}},
  {'hw_edeck': {'action': 'write', 'pipe': 2}}
]
```
动作是一组字典，按照顺序进行执行。**'action'表示是'read'还是'write'。这里的'read'与'write'并没有严格的执行顺序，其读写都是相对模块来解释的。例如：第一个'hw_edeck'就是读取真实CAN数据并写入到管道1中，而第二个'analyze'的'read'指的是读取管道1中的数据。'write'也一样，`{'analyze': {'action': 'write', 'pipe' : 2}}`表示，写入数据到管道2中。而最后一条的'write'表示读取管道2中的数据并写入到真实设备上。'read','write'参数是由具体模块来指定，并没有固定的顺序。这里是特比需要注意的地方，所以在编写策略文件时需要仔细观看子模块提供的说明。**

## 创建多个对象
相同的模块可以通过'~'进行分割索引,例如：`fuzz~0, fuzz~1`。通用的模块，加载两边。但是在引擎中是两份对象。