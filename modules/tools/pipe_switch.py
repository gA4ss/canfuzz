# -*- coding: utf-8 -*-
import copy

from frame.kernel.module import CANModule


class pipe_switch(CANModule):
    name = "总线交换"
    version = 1.0
    help = {
        "describe": "此模块用于读/写/保存CAN数据，负责CAN包的消息中转。",
        "action_parameters": {
            "action": {
                "describe": "读取保存CAN包到缓存，或者将缓存数据写入管道中。",
                "type": "str",
                "default": "read",
                "range": ["read", "write"]
            }
        }
    }

    def do_init(self, params):
        self.describe = pipe_switch.help.get('describe', pipe_switch.name)
        self._bus = 'pipe_switch'
        self._can_buffer = None

    def do_start(self, params):
        self._can_buffer = None

    def do_effect(self, can_msg, args):
        if args.get('action') == 'read' and can_msg.CANData:
            self._can_buffer = copy.deepcopy(can_msg)
        elif args.get('action') == 'write' and self._can_buffer:
            can_msg = copy.deepcopy(self._can_buffer)
            self._can_buffer = None
        else:
            self.error('命令 ' + args['action'] + ' 未实现')
        return can_msg
