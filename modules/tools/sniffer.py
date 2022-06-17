# -*- coding: utf-8 -*-
import os
import time

from frame.utils.replay import Replay
from frame.kernel.module import CANModule, Command
from frame.stream.cmdres import CmdResult, CMDRES_ERROR, CMDRES_NULL, CMDRES_INT, CMDRES_STR, CMDRES_TAB, CMDRES_OBJ


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

    version = 1.0

    def do_init(self, params):
        self.describe = sniffer.help.get('describe', sniffer.name)

        self._bus = 'sniff'

        self._fname = None
        self._replay = False
        self._sniff = False
        self.CANList = Replay()     # 使用Replay结构用于保存CAN数据包以及调试信息
        self.last = time.clock()
        self._last = 0
        self._full = 1
        self._num1 = 0
        self._num2 = 0

        # 设定保存文件
        if 'save_to' in params:
            self._fname = params['save_to']
        else:
            self._fname = "./dump.can"

        # 加载保存的数据包
        if 'load_from' in params:
            ret = self.cmd_load(params['load_from'])
            if ret.last_error < 0:
                self.error(ret.describe, ret.e)

        self.commands['sniff'] = Command(
            "启用/禁用 嗅探模式", 0, "", self.sniff_mode, True)
        self.commands['print'] = Command(
            "打印已经加载的流量包", 0, "", self.cnt_print, True)
        self.commands['load'] = Command(
            "从文件中加载流量包", 1, "<文件路径>", self.cmd_load, True)
        self.commands['replay'] = Command(
            "从已经加载的流量中回放指定范围的包", 1, "<X>-<Y>", self.replay_mode, True)
        self.commands['save'] = Command(
            "保存指定范围的流量包到文件", 1, "<X>-<Y>", self.save_dump, True)
        self.commands['clean'] = Command(
            "清除已经缓存的包", 0, "", self.clean_table, True)

    def get_status(self):
        status = "当前状态: " + str(self._active) + "\n嗅探模式: " + str(self._sniff) +\
            "\n回放模式: " + str(self._replay) + "\nCAN数据帧数量: " + str(len(self.CANList)) +\
            "\n在队列中的数据帧数量: " + str(self._num2 - self._num1)
        return CmdResult(cmdline='status', describe="当前状态", result_type=CMDRES_STR, result=status)

    def cmd_load(self, name):
        try:
            self.CANList.parse_file(name, self._bus)
            self.info("已经加载 " + str(len(self.CANList)) + " 个数据帧")
        except Exception as e:
            return CmdResult(cmdline='load ' + name, describe="不能打开CAN消息文件", last_error=-2, e=e)
        return CmdResult(cmdline='load ' + name, describe="已加载: " + str(len(self.CANList)), result_type=CMDRES_OBJ, result=self.CANList)

    def clean_table(self):
        self.CANList = Replay()
        self._last = 0
        self._full = 1
        self._num1 = 0
        self._num2 = 0
        return CmdResult(cmdline='clean', describe="清除缓存表")

    def save_dump(self, input_params):
        fname = os.path.abspath(self._fname)
        indexes = input_params.split(',')[0].strip()
        if len(input_params.split(',')) > 1:
            fname = input_params.split(',')[1].strip()

        try:
            _num1 = int(indexes.split("-")[0])
            _num2 = int(indexes.split("-")[1])
        except:
            _num1 = 0
            _num2 = len(self.CANList)
        ret = self.CANList.save_dump(fname, _num1, _num2 - _num1)
        return CmdResult(cmdline='save ' + fname, describe="保存dump文件", result_type=CMDRES_STR, result=ret)

    def sniff_mode(self):
        self._replay = False

        if self._sniff:
            self._sniff = False
            self.commands['replay'].is_enabled = True
            self.commands['save'].is_enabled = True
        else:
            self._sniff = True
            self.commands['replay'].is_enabled = False
            self.commands['save'].is_enabled = False
            self.CANList.restart_time()

        result_str = "嗅探模式开启, 'replay'与'save'命令被禁用"
        if self._sniff is False:
            result_str = "嗅探模式关闭, 'replay'与'save'命令启用"
        return CmdResult(cmdline='sniff', describe="嗅探模式开关", result_type=CMDRES_STR, result=result_str)

    def replay_mode(self, indexes=None):
        self._replay = False
        self._sniff = False
        if not indexes:
            indexes = "0-" + str(len(self.CANList))
        try:
            self._num1 = int(indexes.split("-")[0])
            self._num2 = int(indexes.split("-")[1])
            if self._num2 > self._num1 and self._num1 < len(self.CANList) and self._num2 <= len(
               self.CANList) and self._num1 >= 0 and self._num2 > 0:
                self._replay = True
                self._full = self._num2 - self._num1
                self._last = 0
                self.commands['sniff'].is_enabled = False
                self.CANList.set_index(self._num1)
        except:
            self._replay = False

        return CmdResult(cmdline='replay ' + str(indexes), describe="回放模式改变", result_type=CMDRES_STR, result=str(self._replay))

    def cnt_print(self):
        return CmdResult(cmdline='print', describe="当前缓冲区包总数", result_type=CMDRES_INT, result=len(self.CANList))

    def do_effect(self, can_msg, args):
        #
        # 在嗅探模式下并且当前包是CAN包则缓存CAN包
        #
        if self._sniff and can_msg.CANData:
            self.CANList.append(can_msg)

        #
        # 如果是在回访模式并且非CAN包则回访自身
        #
        elif self._replay and not can_msg.CANData:
            d_time = float(args.get('delay', 0))
            ignore = bool(args.get('ignore_time', False))
            try:
                next_msg = self.CANList.next(d_time, ignore)
                if next_msg and next_msg.CANData:
                    can_msg.CANFrame = next_msg.CANFrame
                    self._num1 += 1
                    can_msg.CANData = True
                    self._last += 1
                can_msg.bus = self._bus
                self._status = self._last / (self._full / 100.0)
            except Exception:
                self._replay = False
                self.commands['sniff'].is_enabled = True
                self.CANList.reset()

            #
            # 当回访范围完成，自动切入嗅探模式。
            #
            if self._num1 == self._num2:
                self._replay = False
                self.commands['sniff'].is_enabled = True
                self.CANList.reset()
        return can_msg
