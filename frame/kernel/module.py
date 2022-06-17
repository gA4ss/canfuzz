# -*- coding: utf-8 -*-
import time
import codecs
import threading
import traceback
import collections

from frame.stream.iostream import IOStream
from frame.stream.cmdres import CmdResult, CMDRES_STR, CMDRES_INT


class Command(object):

    """给模块添加的命令结构。"""

    def __init__(self, description, num_params, desc_params, callback, is_enabled, index=None):
        #: str -- 命令的描述。
        self.description = description
        #: int -- 参数的数量。
        self.num_params = num_params
        #: str -- 参数描述
        self.desc_params = desc_params
        #: function -- 命令的回调函数
        self.callback = callback
        #: bool -- 命令是否开启
        self.is_enabled = is_enabled
        #: int -- 命令的索引
        self.index = index


class CANModule:

    """
    所有模块的的原型类，所有模块的实现必须继承此类，此类中定义了模块的一些要重写的标准接口。继承类需要实现
    此接口
    """

    def __init__(self, params, ios=None):
        """
        构造函数，初始化模拟的动作与命令结构。

        :param dict params: 模块的初始化参数，通过方案文件指定。
        """

        self.name = '子模块基础类'
        self.help = None
        self.version = 0.0

        #
        # 默认的命令
        #
        self.commands = collections.OrderedDict()
        self.commands['status'] = Command(
            '获取当前状态', 0, '', self.get_status, True)
        self.commands['switch'] = Command(
            '停止/激活 当前模块', 0, '', self.do_activate, True)
        self.commands['outscr'] = Command(
            '停止/激活 标准输出', 0, '', self.do_output_screen, True)

        #
        # 输出流
        #
        self._status = 0
        self._ios = ios

        #
        # 模块的默认初始化参数
        #
        self._DEBUG = int(params.get('debug', 0))
        self._output_screen = True if params.get('output_screen', False) in [
            "True", "true", "1"] else False
        self._bus = params.get('bus', self.__class__.__name__)
        self._active = False if params.get('active', False) in [
            "False", "false", "0", "-1"] else True
        self._timeout = int(params.get('timeout', 3))

        #
        # 线程事件
        #
        self._thr_block = threading.Event()

        #
        # 调用自定义的初始化函数
        #
        self.do_init(params)

    @staticmethod
    def get_hex(bytes_in):
        """将`bytes_in`中的数据转换成16进制。"""
        return (codecs.encode(bytes_in, 'hex_codec')).decode("ISO-8859-1")

    def dprint(self, level, msg):
        """打印调试信息。"""
        if level <= self._DEBUG:
            self.output_dbginfo(msg)

    def info(self, msg):
        """打印调试信息。"""
        self.set_error_text(msg, level='info')

    def error(self, msg, e=None):
        """打印错误信息。"""
        self.set_error_text(msg, level='error', e=e)

    def fatal_error(self, msg, e=None):
        """严重错误信息。"""
        self.set_error_text(msg, level='fatal', e=e)

    def output_dbginfo(self, msg):
        """输出到调试缓冲"""
        dbgmsg = '[DEBUG]' + msg
        if self._output_screen is True:
            print(dbgmsg)
        else:
            self._ios.output(self._bus, dbgmsg, self._timeout)

    def output_stdout(self, msg):
        """输出到stdout缓冲"""
        if self._output_screen is True:
            print(msg)
        else:
            self._ios.output(self._bus, msg, self._timeout)

    def output_stderr(self, msg, fatal=False):
        """输出到stderr缓冲"""
        errmsg = '[ERROR]' + msg if fatal is False else '[FATAL]' + msg
        if self._output_screen is True:
            print(errmsg)
        else:
            self._ios.output(self._bus, errmsg, self._timeout)

    def set_error_text(self, text, level='error', e=None):
        """设置错误信息。有三个级别，'info','error','fatal', 默认是'error'。

        :returns: int -- 初始化状态。
        """
        # traceback.print_exc()
        level = level.lower()
        if level == 'fatal':
            msg = text
            self.output_stderr(msg, True)
            self._status = -1
            self._error_text = msg
            if e is None:
                raise RuntimeError(text)
            raise e
        elif level == 'info':
            msg = text
            self.output_stdout(msg)
            self._status = 0
            self._error_text = msg
        else:
            msg = text
            if e is not None:
                msg += ', Exception:' + str(e)
            self.output_stderr(msg)
            self._status = -2
            self._error_text = msg

    def get_status_bar(self):
        """获取模块的状态。

        :returns: dict -- 'bar': 模块的进度条以及状态信息。一个字典用于将进度与状态对应。
        """
        self._thr_block.wait(timeout=self._timeout)
        self._thr_block.clear()
        status = int(self._status)
        error_text = ""
        if self._error_text != "":
            error_text = self._error_text
            self._error_text = ""
        self._thr_block.set()
        return {'bar': status, 'text': error_text}

    def do_output_screen(self, mode=-1):
        """激活当前模块输出

        :param int mode: 模块的激活状态。(默认: `-1`)
          - `0` 反激活
          - `-1` 取当前状态相反的状态 (激活 -> 反激活 / 反激活 -> 激活)
          - `1` 激活

        :returns: str -- 当前模块输出的状态，用字符串描述。
        """
        if mode == -1:
            self._output_screen = not self._output_screen
        elif mode == 0:
            self._output_screen = False
        else:
            self._output_screen = True

        result_str = '激活'
        if not self._output_screen:
            result_str = '未激活'
        return CmdResult(cmdline='outscr ' + str(mode), describe="标准输出激活状态", result_type=CMDRES_STR, result=result_str)

    @property
    def is_active(self):
        """模块是否在激活状态。

        :returns: boolean -- `True` 模块激活，反之关闭
        """
        return self._active

    def get_status(self):
        """获取当前模块状态。

        :returns: str -- 当前状态的描述。
        """
        result_str = '激活'
        if not self._active:
            result_str = '未激活'
        return CmdResult(cmdline='status', describe="当前状态", result_type=CMDRES_STR, result=result_str)

    def do_activate(self, mode=-1):
        """激活当前的模式。

        :param int mode: 模块的激活状态。(默认: `-1`)
          - `0` 反激活
          - `-1` 取当前状态相反的状态 (激活 -> 反激活 / 反激活 -> 激活)
          - `1` 激活

        :returns: str -- 当前模块的状态，用字符串描述。
        """
        if mode == -1:
            self._active = not self._active
        elif mode == 0:
            self._active = False
        else:
            self._active = True

        result_str = '激活'
        if not self._active:
            result_str = '未激活'
        return CmdResult(cmdline='switch ' + str(mode), describe="激活状态", result_type=CMDRES_STR, result=result_str)

    def raw_write(self, string):
        """通过字符串命令来调用模块的命令。

        :param str string: 字符串命令参数。 (例如： 's' 停止模块运行。)

        :returns: CmdResult -- 命令执行结果
        """
        ret = None
        self._thr_block.wait(timeout=self._timeout)  # 3秒超时设定
        self._thr_block.clear()
        full_cmd = string.lstrip()
        if ' ' in full_cmd:  # 是否有其他参数指定
            # 通过空格来区分命令以及参数，如果存在将参数提取到parameters中,
            # 命令字符串提取到in_cmd中
            in_cmd, parameters = full_cmd.split(' ', maxsplit=1)
        else:
            in_cmd = full_cmd
            parameters = None

        # 检查是否是有效的命令
        if in_cmd in self.commands:
            # 取出命令并检测命令是否开启
            cmd = self.commands[in_cmd]
            if cmd.is_enabled:
                try:
                    if cmd.num_params == 0 or (cmd.num_params == 1 and parameters is None):
                        if cmd.index is None:
                            ret = cmd.callback()
                        else:
                            ret = cmd.callback(cmd.index)
                    elif cmd.num_params == 1:
                        if cmd.index is None:
                            ret = cmd.callback(parameters)
                        else:
                            ret = cmd.callback(cmd.index, parameters)
                    else:
                        ret = cmd.callback(cmd.index)
                except Exception as e:
                    self.error("执行指令发生异常", e)
                    ret = CmdResult(
                        cmdline=string, describe="执行指令发生异常", last_error=-2, e=e)
                    # traceback.print_exc()
            else:
                ret = CmdResult(
                    cmdline=string, describe="命令被禁用", last_error=-2)
        self._thr_block.set()
        return ret

    def do_effect(self, can_msg, args):
        """
        [回调函数] 在引擎主循环中运行，负责模块的主要操作。

        :param can.CANSploitMessage can_msg: 在管道变量中的CAN消息结构。
        :param dict args: 在方案文件中的动作参数。

        :returns: str -- 在此函数执行过后的can_msg信息。
        """
        return can_msg

    def do(self, can_msg, args):
        if self._active is True:
            return self.do_effect(can_msg, args)
        return can_msg

    def do_init(self, params):
        """
        [回调函数] 在做所有工作之前进行的初始化工作。在模块的__init__中调用。

        :returns: int -- 初始化状态。
        """
        return 0

    def do_stop(self, params):
        """
        [回调函数] 在停止模块时所需要做的操作。

        :returns: int -- 停止的状态。
        """
        return 0

    def stop(self, params):
        if self._active:
            ret = self.do_stop(params)
            self._thr_block.set()
            return ret
        return 0

    def do_start(self, params):
        """
        [回调函数] 模块被激活时被调用的函数。

        :returns: int -- 开始状态。
        """
        return 0

    def start(self, params):
        if self._active:
            return self.do_start(params)
        return 0

    def do_exit(self, params):
        """
        [回调函数] 当模块退出时被调用的函数。

        :returns: int -- 退出状态。
        """
        return 0

    def exit(self, params):
        if self._active:
            ret = self.do_exit(params)
            return ret
        return 0
