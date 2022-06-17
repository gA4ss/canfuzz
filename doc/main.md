# 介绍

此文件是整个canfuzz的启动文件，负责创建引擎对象以及命令行框架。

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