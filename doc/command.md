# Command类简介

任何canfuzz的子模块都继承自此类，此类相当于canfuzz的插件系统。任何子模块按照此模块来编写即可。

# 帮助系统与参数

每个子模块都有一套固定帮助形式，在继承类的初始定义时，如下所示：

```python
class sniffer(CANModule):
  name = "嗅探器"
  help = {
    "describe": "此模块用于捕获并保存数据包流量。",
    "init_parameters": {
      "load_from": {
        "describe": "文件路径，用于从文件中加载流量数据。",
        "type": "str"
      },
      "save_to": {
        "describe": "用于保存当前缓存的流量数据到文件。",
        "type": "str",
        "default": "~/.canfuzz/dump.can"
      }
    },
    "action_parameters": {
      "delay": {
        "describe": "用于回放流量包时的时间间隔。",
        "type": "int",
        "default": 0
      },
      "ignore_time": {
        "describe": "是否忽略延迟时间。",
        "type": "bool",
        "default": "false"
      }
    }
  }
```

* `name`是一个字符串，表明当前子模块的名称。
* `help`主要显示在帮助文档时。
* `init_parameters`是用于初始化时的一些参数。
* `action_parameters`是用于`do_effect`时关于数据交换时的一些参数定义。

在具体描述参数时，直接使用`参数名:{}`的形式定义，例如：`ignore_time`就是一个参数的名称随后是参数的描述。`describe`用来字符串描述参数，`type`是参数的值类型，`default`是参数的默认值。
定义以上变量后在打印子模块帮助时既会按照定义显示。

## 与策略文件的对应
这里的`init_parameters`与`action_parameters`分别对应了在[策略文件](./config.md)的`modules`与`actions`中指定的参数。

# 重载函数说明

|重载函数名|说明|
|--------|----|
|`do_start`|调用子模块'start'命令时要实现的功能。|
|`do_stop`|调用子模块'stop'命令时要实现的功能。|
|`do_exit`|子模块退出时要实现的功能。|
|`do_init`|子模块初始化时要实现的功能。|
|`do_effect`|子模块的函数'do'要实现的功能。*主要数据流交换的函数* |

# 重要执行流
在`L6Engine`中的`main_loop`中，依次遍历动作列表。并执行子模块的数据流函数`do`。

```python
# 运行当前动作中指定的模块以及相关的动作，并将结果保存在指定的管道变量中
pipes[pipe_name] = module.do(pipes[pipe_name], params)
```

`do`函数会调用`do_effect`实现动作列表。所以这个函数根据具体的`params`来执行对应的动作。一个摘自'hw_fakeIO'子模块的例子如下：

```python
def do_effect(self, can_msg, args):
  if args.get('action') == 'read':
    can_msg = self.do_read(can_msg)
  elif args.get('action') == 'write':
    can_msg = self.do_write(can_msg)
  else:
    self.fatal_error('命令 ' + args['action'] + ' 没有实现')
  return can_msg
```

# 子模块内部命令调用

`raw_write`函数主要用来，外部调用内部所定义的命令。