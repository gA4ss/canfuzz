# 介绍

# 主要执行流程

*main.py*中调用`run_canfuzz`，此函数首先生成一个`L6Engine`的类，改类是整个程序框架的引擎类负责调用起来各种模块。
随后将`L6Engine`传输`Cmd`类派生的`CanFuzzCli`类中作为初始化参数。`CanFuzzCli`是一个命令行框架的类，负责按照用户
指定的命令调用`L6Engine`类的功能。在`CanFuzzCli`类中的类似`do_xxx`的函数就是要执行的命令，例如：`do_start`这个就是
start命令，在程序启用后即可使用start来进行调用。也可自行扩展添加任意`do_xxx`的函数来实现定制化的需求。

以下是目前的canfuzz主命令：

* *do_start*          canfuzz开始运行
* *do_stop*           canfuzz停止运行
* *do_cmd*            调用某个子模块的具体命令
* *do_view*           列出canfuzz所加载的子功能模块
* *do_edit*           编译一个策略列表
* *do_help*           帮助
* *do_quit*           完全退出canfuzz

在启动canfuzz后，使用命令start来启动canfuzz引擎。这样会调用[`L6Engine`](./engine.md)的`start_loop`函数。

# 帮助说明

帮助命令`help`，调用了`do_help`函数，如果`help`命令后跟子功能模块的id则列出的就是子功能模块的帮助说明，如果是命令则打印该命令的帮助。子模块的id通过命令`view`进行查看。

# 分模块介绍

canfuzz是一个模块化的结构程序，通过不同模块组合实现不同功能。每个子功能模块的实现都是一个继承自`kernel/module.py`文件下`Command`类的类。通过基类[`Command`](command.md)，L6引擎来通一管理子功能模块的接口。

## IO模块

* [CANSocket](modules/hw_CANSocket.md)
* [hw_edeck](modules/hw_edeck.md)
* [hw_fackIO](modules/hw_fakeIO.md)
* [TCP2CAN](modules/hw_TCP2CAN.md)

## 分析模块

* analyze
* filter
* fuzz
* ping
* pipe_switch
* replay

# 策略文件
参见[策略文件.md](config.md)

# 协议解析

目前本模块支持三种车辆常见的协议：

1. [*CAN协议*](can.md)
2. [*ISOTP协议*](isotp.md)
3. [*UDS协议*](uds.md)

# 数据结构模块

1. [*iostream*](stream.md)
2. [*cmdres*](stream.md)
3. [*forced_sampler*](stream.md)
4. [*integrator*](stream.md)
5. [*normalizer*](stream.md)
6. [*processor*](stream.md)
7. [*sampler*](stream.md)
8. [*selector*](stream.md)
9. [*separator*](stream.md)
10. [*subnet*](stream.md)
11. [*threaderror*](stream.md)

# 辅助模块

1. [*bits*](utils.md)
2. [*correl*](utils.md)
3. [*frag*](frag.md)
4. [*replay*](replay.md)
5. [*stats*](utils.md)