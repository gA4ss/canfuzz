# -*- coding: utf-8 -*-
import os
import sys
import glob
import time
import threading
import collections

from importlib.machinery import SourceFileLoader
from frame.message.can import CANSploitMessage
from frame.stream.iostream import IOStream
from frame.stream.cmdres import CmdResult, CMDRES_ERROR, CMDRES_NULL, CMDRES_INT, CMDRES_STR, CMDRES_TAB, CMDRES_OBJ

class L6Engine:

  """
  CANFUZZ的主要内核模块，负责加载各个模块以及配置文件并进行动态的执行。
  """

  def __init__(self, params={}):

    #
    # 模块相关变量
    #
    self._modules = {}
    self._actions = []

    #
    # 线程相关变量
    #
    self._thread = None
    self._stop = threading.Event()
    self._stop.set()
    self.do_stop_e = threading.Event()
    self.do_stop_e.clear()

    #
    # 输出IO
    #
    self.ios = IOStream()
    self.module_ios = IOStream()

    #
    # 读取参数
    #
    self._timeout = int(params.get('timeout', 3))
    self._DEBUG = int(params.get('debug', 3))
    self._path_modules = str(params.get('path_modules', None))
    self._output_screen = True if params.get('output_screen') in ["True", "true", "1"] else False

    sys.dont_write_bytecode = True

  def dprint(self, level, msg):
    """打印调试信息。"""
    if level <= self._DEBUG:
      self.output_dbginfo(msg)

  def info(self, msg):
    """
    :param str msg: 调试信息.
    """
    self.output_stdout(msg)

  def output_dbginfo(self, msg):
    """输出到调试缓冲"""
    dbgmsg = '[DEBUG]' + msg
    if self._output_screen is True:
      print(dbgmsg)
    else:
      self.ios.output('L6Engine', dbgmsg, self._timeout)

  def output_stdout(self, msg):
    """输出到stdout缓冲"""
    if self._output_screen is True:
      print(msg)
    else:
      self.ios.output('L6Engine', msg, self._timeout)

  def output_stderr(self, msg):
    """输出到stderr缓冲"""
    errmsg = '[ERROR]' + msg
    if self._output_screen is True:
      print(errmsg)
    else:
      self.ios.output('L6Engine', errmsg, self._timeout)

  @property
  def actions(self):
    return self._actions

  @property
  def modules(self):
    return self._modules

  def main_loop(self):
    """
    这里是引擎启动后主要执行模块的主循环。这里负责了加载模块，验证模块是否激活以及执行当前方面中
    指定的动作。
    """
    while not self.do_stop_e.is_set():
      #
      # 保存了当前方案中所需的所有管道变量
      # 这里的 pipes = {} 清空操作很重要，每次循环都要清空，防止走入死循环
      #
      pipes = {}

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

    self.info("主循环停止")
    # 停止所有已经加载的模块
    for name, module, params in self._actions:
      self.info("停止模块: " + name)
      module.stop(params)
    self.do_stop_e.clear()
    self.info("停止完成")

  def call_module(self, index, params):
    """通过模块的index以及指定参数来运行模块。

    :param int index: 模块的索引。
    :param str params: 传递给模块的参数。

    :return: 返回模块的执行结果。
    :rtype: CmdResult
    """
    if index < 0 or index >= len(self._actions):
      return CmdResult(cmdline=str(index), describe='模块 {} 未找到'.format(index), last_error=-2)
    return self._actions[index][1].raw_write(params)

  def engine_exit(self):
    """引擎退出时，退出所有加载的模块。"""
    for name, module, params in self._actions:
      self.info("退出模块: " + name)
      module.exit(params)
    self.ios.clear()
    self.module_ios.clear()

  def start_loop(self):
    """此函数负责引擎加载各个加载的模块并执行模块的'do_start'函数。

    :return: 引擎的状态。
    :rtype: bool
    """
    self.info("准备启动主处理线程")
    if self._stop.is_set() and not self.do_stop_e.is_set():
      self.do_stop_e.set()
      for name, module, params in self._actions:
        self.info("启动模块: " + name)
        module.start(params)
        module._thr_block.set()

      self._thread = threading.Thread(target=self.main_loop)
      self._thread.daemon = True

      self._stop.clear()
      self.do_stop_e.clear()
      self.info("启动主线程")
      self._thread.start()
      self.info("主线程启动完毕")
    return not self._stop.is_set()

  def stop_loop(self):
    """引擎停止函数，负责调用各个模块的'do_stop'函数。

    :return: 引擎的状态。
    :rtype: bool
    """
    self.info("准备停止主处理线程")
    if not self._stop.is_set() and not self.do_stop_e.is_set():
      self.do_stop_e.set()
      while self.do_stop_e.is_set():
        time.sleep(0.01)

    self._stop.set()
    return not self._stop.is_set()

  @property
  def status_loop(self):
    """获取当前的引擎的运行状态。

    :return: 引擎的状态。
    :rtype: bool
    """
    return not self._stop.is_set()

  def find_module(self, module):
    """在动作列表里，以模块名称找寻模块是否存在。

    :param str module: 模块的名称。

    :return: -1:没有找到，其他整数表示加载模块的index。
    :rtype: int
    """
    index = 0
    for name, _, _ in self._actions:
      if name == module:
        return index
      index += 1
    return -1

  def get_module(self, module_name):
    """在动作列表里，以模块名称找寻模块对象。

    :param str module_name: 模块的名称。

    :return: module :模块实例。
    :rtype: object
    """
    module_obj = None
    for name, module_obj, _ in self._actions:
      if module_name == name:
        return module_obj
    return module_obj

  def edit_module(self, index, params):
    """对index指定的模块修改当前的参数。

    :param int index: 模块的索引。
    :param dict params: 模块执行的新的参数。

    :return: 成功返回True，反之False。
    :rtype: int
    """
    if index < 0 or index >= len(self._actions):
      return False
    self._actions[index][2] = self._validate_action_params(params)
    return True

  def _get_load_paths(self):
    """获取当前模块加载的路径。

    :return: 一个列表，保存了所有模块寻找的路径。
    :rtype: list
    """
    strats = []
    # 1. 用户指定的模块路径
    if self._path_modules:
      strats.append(self._path_modules)
    # 2. 从用户工作目录开始
    strats.append(os.path.join(os.path.expanduser('~'), '.canfuzz', 'modules'))
    # 3. 从包目录
    local_modules_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    strats.append(os.path.join(local_modules_dir, 'modules'))
    return strats

  def list_modules(self):
    """列出所有的模块。

    :return: 一个字典结构，保存了所有在搜索目录范围内的所有模块。
    :rtype: collections.OrderedDict
    """
    modules = collections.OrderedDict()
    # 便利所有加载模块的路径
    for search_path in self._get_load_paths()[::-1]:
      search_path = os.path.join(search_path, '**', '*.py')
      for fullpath in glob.iglob(search_path):
        if fullpath.endswith('__init__.py'):
          continue        # 跳过包初始化文件
        path, filename = os.path.split(fullpath)
        subdir = os.path.split(os.path.dirname(fullpath))[1]
        filename = os.path.splitext(filename)[0]
        sys.path.append(path)
        module = __import__(filename)
        if subdir != 'modules':
          new_module = {os.path.join(subdir, filename):(getattr(module, filename), path)}
        else:
          new_module = {filename: (getattr(module, filename).name, path)}
        modules.update(new_module)
    return modules

  def load_config(self, fullpath):
    """加载运行方案。

    :param str fullpath: 方案文件的路径。

    :raises ModuleNotFoundError: 当执行方案没有找到。

    --------------------------------------------------
    例子:

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
    --------------------------------------------------
    """
    path, filename = os.path.split(fullpath)
    if not path:
      path = os.getcwd()
    sys.path.append(path)

    config = __import__(os.path.splitext(filename)[0])

    # 寻找'modules'字段并进行加载
    if hasattr(config, 'modules'):
      modules = config.modules.items()
    else:
      raise AttributeError("丢失 '模块' 检查你的策略文件 '{}'.".format(filename))

    for module, init_params in modules:
      # 在所有搜索路径中找寻当前的模块
      for path in self._get_load_paths():
        if not os.path.exists(path):
          continue
        try:
          self.dprint(1, '搜索模块 {} 从 {}'.format(module, path))
          # 对在方案中的模块进行动态加载并初始化
          self._init_module(path, module, init_params)
          break
        except ImportError:
          self.dprint(1, '模块 {} 未发现在 {}'.format(module, path))
          continue
      else:
        raise ImportError(
            "不能找到模块 '{}'. 检查你的策略文件 '{}' 是否有效.".format(module, filename))

    # 加载方案中的动作
    for action in config.actions:
      # 遍历动作中所有的模块以及参数
      for module, parameters in action.items():
        # 验证参数是否合规，并将其添加到引擎中的动作列表
        validated_parameters = self._validate_action_params(parameters)
        self._actions.append([module, self._modules[module], validated_parameters])

  def load_config_by_json(self, config):
    """加载运行方案。

    :param json config: 配置文件内容。

    :raises ModuleNotFoundError: 当执行方案没有找到。
    """
    # 寻找'modules'字段并进行加载
    name = config.get('name', '')
    modules = config.get('modules', {})
    if not config.get('modules', ''):
      raise AttributeError("丢失模块' 检查你的策略文件 '{}'.".format(name))

    for module, init_params in modules.items():
      # 在所有搜索路径中找寻当前的模块
      for path in self._get_load_paths():
          if not os.path.exists(path):
            continue
          try:
            self.dprint(1, '搜索模块 {} 从 {}'.format(module, path))
            # 对在方案中的模块进行动态加载并初始化
            self._init_module(path, module, init_params)
            break
          except ImportError:
            self.dprint(1, '模块 {} 未发现在 {}'.format(module, path))
            continue
      else:
        raise ImportError(
            "不能找到模块 '{}'. 检查你的策略文件 '{}' 是否有效.".format(module, name))

    # 加载方案中的动作
    actions = config.get('actions', [])
    for action in actions:
      # 遍历动作中所有的模块以及参数
      for module, parameters in action.items():
          # 验证参数是否合规，并将其添加到引擎中的动作列表
        validated_parameters = self._validate_action_params(parameters)
        self._actions.append([module, self._modules[module], validated_parameters])

  def _init_module(self, path, mod, params):
    """动态初始化模块。

    从'modules/'动态查找并加载模块。如果模块没有找到' modules/ '，
    那么它递归地查看'modules/'下的子目录。如果模块名包含子目录在哪里找到它，
    它将搜索特定的指定目录和回退到子目录在该目录。

    .. note::

        模块必须包含与模块本身同名的类。例如，模块'my_Module'
        必须包含一个名为'my_Module'的类。

    :param str path:      要搜索模块的目录路径。
    :param str mod:       模块的名称。
    :param list params:   当初始化模块时提供给模块的参数，是一个列表结构。

    :raises: ImportError 当模块未找到时。

    """
    # 模块名是否包含'/'?然后它可能还指示一个子目录
    subdir = ''
    if os.sep in mod:
      subdir, mod = mod.rsplit(os.sep, 1)
    # 在模块名中发现'/'，则合并路径
    if not subdir and '/' in mod:
      subdir, mod = mod.rsplit('/', 1)
    search_path = os.path.abspath(path)
    search_path = os.path.join(search_path, subdir)
    if not os.path.exists(search_path):
      raise ImportError('不能导入模块. 路径 {} 不存在...'.format(search_path))
    # 相同的模块可以通过'~'进行分割索引,例如：fuzz~0, fuzz~1。通用的模块，加载两边。但是在引擎中是两份对象
    mod_name = mod.split('~')[0]
    # 动态加载模块
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
    #
    # 执行构造函数并保存模块
    # 这里使用了mod作为模块名，也就是说module~1作为模块名，这样就可以区分实例化了
    # 这里传递了module_ios作为所有模块IO的输出
    #
    self._modules[mod] = getattr(loaded_module, mod_name)(params, self.module_ios)

  @staticmethod
  def _validate_action_params(params):
    """验证参数是否合法。如果参数中没有指定的管道变量，则默认创建一个名为'1'的变量。

    :param dict params: 要验证的参数。

    :return: 验证后的参数。
    :rtype: dict
    """
    if 'pipe' not in params:
      params['pipe'] = 1
    return params
