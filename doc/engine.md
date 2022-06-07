# L6Engine结构说明

本类是主引擎类，负责加载功能子模块以及读取策略文件，并按照策略文件中的内容执行子模块的内容。

## 初始参数

`L6Engine`初始化时可以通过构造参数以关键字形式进行构造。

* `timeout`         超时设定,默认是3秒。
* `debug`           调试级别，默认是3。
* `path_modules`    模块加载路径。
* `output_screen`   是否输出到屏幕。

初始化代码如下：
```python
self._timeout = int(params.get('timeout', 3))
self._DEBUG = int(params.get('debug', 3))
self._path_modules = str(params.get('path_modules', '~/.canfuzz/modules/'))
self._output_screen = True if params.get('output_screen') in ["True", "true", "1"] else False
```

## 属性

可通过`actions`属性来获取当前引擎加载的策略文件，也可通过`modules`属性来获取当前功能子模块。

# 配置说明

函数以及`load_config_by_json`两个函数来加载配置文件。

# 策略机制
L6Engine的最重要的一个能力是采用了策略文件，策略文件也是一个python脚本，这个脚本中规定了一些特殊的变量名称，
用户按照规则填写并进行组合，既可以让多个子功能模块协同到一起完成一个大的功能。具体请参照[策略文件说明](策略文件.md)。
这里通过`load_config`函数进行加载。此函数用于加载_python_文件的策略文件格式。

## 对动作参数的验证

可以看出`load_config`函数会遍历当前策略的动作，并且从动作中获取动作所依赖的模块以及要执行的参数。这里调用
`_validate_action_params`来验证动作参数是否合理。此函数只是检验动作参数列表中是否有`pipe`参数，如果没有
则自动添加一个1号管道。

```python
# 加载方案中的动作
for action in config.actions:
  # 遍历动作中所有的模块以及参数
  for module, parameters in action.items():
    # 验证参数是否合规，并将其添加到引擎中的动作列表
    validated_parameters = self._validate_action_params(parameters)
    self._actions.append([module, self._modules[module], validated_parameters])
```

`load_config_by_json`是策略文件的json版本。

# 引擎启动与停止
函数`start_loop`负责启动引擎，引擎启动后第一件重要的事情是从`actions`策略列表里获取策略信息。
随后会遍历策略文件。如下代码所示：

```python
for name, module, params in self._actions:
  self.info("启动模块: " + name)
  module.start(params)
  module._thr_block.set()
self._thread = threading.Thread(target=self.main_loop)
self._thread.daemon = True
```

从代码可以看出，启动后会遍历当前策略文件的动作列表，并且调用模块的`start`函数。随后遍历完毕后会调用线程类`Thread`来负责启动`main_loop`函数。

在函数`stop_loop`中会设置`main_loop`线程的终止标志。还可以通过`status_loop`函数来获取当前引擎开关的状态。

# 主循环流程介绍

主要工作模块在`main_loop`函数中实现，在此函数启动后检测是否退出引擎，如果没有退出标记设置，则轮询的执行在当前策略文件中
定义的动作列表。以下是主要代码。

```python
# 以下的循环遍历当前方案所有要执行的动作，并依次执行
for name, module, params in self._actions:
  if not module.is_active:
    continue  # 如果当前模块没有被激活，则执行跳过此模块
  module._thr_block.wait(3)
  module._thr_block.clear()

  pipe_name = params['pipe']
  # 如果发现管道变量是新创建的，则初始一个空的CAN消息结构，并保存在pipes字典中
  if pipe_name not in pipes:
    pipes[pipe_name] = CANSploitMessage()

  # self.dprint(1, "执行 " + name)

  # 运行当前动作中指定的模块以及相关的动作，并将结果保存在指定的管道变量中
  pipes[pipe_name] = module.do(pipes[pipe_name], params)
  module._thr_block.set()
```
从上述代码可以看出，从当前策略中读取'pipe'的参数并存放到`pipe_name`变量中，如果当前管道不存在则创建一个空的CAN消息类。
随后`当前管道 = module.do(当前管道，模块执行参数)`，也就是说当前模块执行的命令，从'当前管道'里读取数据，执行完毕后将结果在写回到'当前管道'中，而`pipes`是一个总变量，这样通过在策略文件中指定不同管道名称，即可实现每个子模块的输入输出的关联。

另外这是一个`for`循环，每次循环后便设置模块的同步事件，策略文件时依次执行动作。`CANSploitMessage`是CAN消息类，这里可以参加[_message/can.py_](CAN%E5%8D%8F%E8%AE%AE.md)中的定义。

# 对外输出函数

这里如果初始化参数`output_screen`的值为`False`，则将信息输出到类变量`ios`(`IOStream类型`)的缓冲中。

* `dprint`            按照`debug`调试级别来打印输出。
* `info`              输出一般信息。
* `output_dbginfo`    输出调试信息。
* `output_stderr`     输出错误信息。

# 对子模块的相关操作函数

* `find_module`     查找模块是否存在
* `get_module`      获取模块对象
* `edit_module`     实时编辑模块当前运行参数
* `list_modules`    列出当前所有模块

`list_modules`也用于当子模块代码发生变化或新的模块存入加载目录时，引擎动态加载模块。这里的加载目录有三个路径如下：

1. 用户指定的模块路径
2. 从用户工作目录开始"_~/.canfuzz/modules_"
3. 当前引擎包的目录的"_canfuzz/modules_"

加载模块时会从以上三个目录递归寻找子模块。这里可参加函数`_init_module`。当找不到子模块时，会在搜索它的子目录，只进行**_第一层子目录_**进行搜索。

```python
try:
  loaded_module = SourceFileLoader(mod_name, os.path.join(search_path, mod_name + '.py')).load_module()
  self.dprint(1, '加载 {} 从目录 {}'.format(mod_name, search_path))
except FileNotFoundError:  # 模块在指定目录没有找到，则搜索它的子目录，只进行第一层子目录的搜索
  for subdir in os.listdir(search_path):
    if os.path.isdir(os.path.join(os.path.abspath(search_path), subdir)):
      new_search_path = os.path.join(search_path, subdir)
      try:
        loaded_module = SourceFileLoader(mod_name, os.path.join(new_search_path, mod_name + '.py')).load_module()
        self.dprint(1, '加载 {} 从子目录 {}'.format(mod_name, new_search_path))
        break  # 模块没有找到在子目录
      except FileNotFoundError:
        continue
  else:  # 没有找到抛出异常
    raise ImportError('不能找到 {}, 在子目录中也找不到...'.format(mod_name))
```
