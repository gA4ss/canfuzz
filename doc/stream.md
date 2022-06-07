
# *'stream/cmdres.py'*

*CmdResult*类用于子模块执行命令完毕后，将结果反馈给引擎。位于*'steam/cmdres.py'*。此类没有函数仅作为一个数据封装类。

## 结果类型
* `CMDRES_ERROR  = -1`        结果执行错误。
* `CMDRES_NULL   = 0`         结果执行为`None`值。
* `CMDRES_INT    = 1`         结果执行为整型值。
* `CMDRES_STR    = 2`         结果执行为字符串值。
* `CMDRES_TAB    = 3`         结果执行为列表值。
* `CMDRES_OBJ    = 4`         结果执行为对象值。

```python

def __init__(self, cmdline="", result_type=CMDRES_NULL, describe="", result=None, last_error=0, e=None):
  self.last_error = last_error                # 错误代码
  self.e = e                                  # 异常信息
  self.cmdline = cmdline                      # 执行的命令
  self.describe = describe                    # 描述
  self.result = result                        # 结果

  # 结果的类型
  self.result_type = result_type if self.last_error >= 0 else CMDRES_ERROR
```

# *'stream/iostream.py'*

用于项目中保存字节流的类，位于*'stream/iostream.py'*。内部最重要的变量是`output_buffer`是一个字典结构，键是缓冲名
值是一个形如：`{time.time(), 数据}`的字典结构。此类内部是线程安全的，用于多线程存取数据。

`def output(self, source, msg, timeout=3)`是最重要的函数，用于向当前流中输出数据。`source`是当前数据标识，`msg`
是要记录的数据，`timeout`是互斥体超时设定。

```python
def output(self, source, msg, timeout=3):
  self._mutex.wait(timeout)
  self._mutex.clear()

  if source not in self.output_buffer:
    self.output_buffer[source] = []
  outmsg = {time.time(), msg}
  self.output_buffer[source].append(outmsg)

  self._mutex.set()
```

# *'stream/threaderror.py'*
定义了一个线程类继承自`Thread`类。

```python
def __init__(self, funcName, *args):
  Thread.__init__(self)
  self.args = args
  self.funcName = funcName
  self.exitcode = 0
  self.exception = None
  self.exc_traceback = ''
```
初始化时，输入要执行函数以及参数即可。随后运行`run`接口执行即可。

```python
def run(self):
  try:
    self._run()
  except Exception as e:
    # 如果线程异常退出，将该标志位设置为1，正常退出为0
    self.exitcode = 1
    self.exception = e
    # 在改成员变量中记录异常信息
    self.exc_traceback = ''.join(traceback.format_exception(*sys.exc_info()))
    print(self.exception)
    print(self.exc_traceback)
```
可以看到如果执行出错，会将一些出错信息。放置到`exception`与`exc_traceback`变量中，并直接打印。`exitcode`也会设置为1。

# *'stream/processor.py'*

一个迭代器的基类。存在两个类`Processor`与`_Composition`。

## `Processor`类
## `_Composition`类

## 虚函数`def process(self, message) -> Iterable`
此函数用于在各种派生类中实现重写，用于在迭代中进行处理。

## *'stream/integrator.py'*

## *'stream/sampler.py'*

## *'stream/forced_sampler.py'*

## *'stream/normalizer.py'*

## *'stream/selector.py'*

## *'stream/separator.py'*

## *'stream/subnet.py'*
