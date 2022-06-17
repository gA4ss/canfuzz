# -*- coding: utf-8 -*-
import socket
import struct
import traceback

from frame.message.can import CANMessage, CANSploitMessage
from frame.kernel.module import CANModule, Command
from frame.stream.cmdres import CmdResult, CMDRES_STR


class hw_CANSocket(CANModule):
    name = "CANSocket设备驱动"
    help = {
        "describe": "此模块读写CANSocket设备驱动",
        "init_parameters": {
            "iface": {
                "describe": "设备接口名称。",
                "type": "str",
                "default": "vcan0"
            }
        },
        "action_parameters": {
            "action": {
                "describe": "动作属性，读或者写。",
                "type": "str",
                "default": "read",
                "range": ["read", "write"]
            }
        }
    }

    version = 1.0

    def do_init(self, init_params):
        self.describe = hw_CANSocket.help.get('describe', hw_CANSocket.name)
        self._bus = 'CANSocket'
        self._socket = None
        self._device = init_params.get('iface', None)
        self._bus = init_params.get('bus', 'CANSocket')
        self.commands['write'] = Command(
            "直接发送CAN数据帧, 类似如下字符串形式: 01A#11223344", 1, " <数据帧字符串> ", self.dev_write, True)
        self._active = True
        self._run = False

    def dev_write(self, data):
        ret = CmdResult()
        if self._run:
            try:
                idf, dataf = data.strip().split('#')
                dataf = bytes.fromhex(dataf)
                idf = int(idf, 16)
                lenf = min(8, len(dataf))
                message = CANSploitMessage()
                message.CANData = True
                can_msg = CANMessage.init_data(idf, lenf, dataf[0:lenf])
                message.CANFrame = can_msg
                self.do_write(message)
                ret = CmdResult(cmdline='write ' + data, describe="网络发送数据",
                                result_type=CMDRES_STR, result=can_msg.get_text())
            except Exception as e:
                self.error('写入CAN数据到设备发生异常', e)
                ret = CmdResult(cmdline='write ' + data,
                                describe="写入CAN数据到设备发生异常", last_error=-2, e=e)
        else:
            ret = CmdResult(cmdline='write ' + data,
                            describe="模块没有被激活", last_error=-2)
        return ret

    def do_start(self, params):
        if self._device and not self._run:
            try:
                self._socket = socket.socket(
                    socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
                self._socket.setblocking(0)
                self._socket.bind((self._device,))
                self._run = True
            except Exception as e:
                self._run = False
                self.fatal_error("启动失败", e)

    def do_stop(self, params):
        if self._device and self._run:
            try:
                self._socket.close()
                self._run = False
            except Exception as e:
                self._run = False
                self.fatal_error("停止失败", e)

    def do_effect(self, can_msg, args):
        if args.get('action') == 'read':
            can_msg = self.do_read(can_msg)
        elif args.get('action') == 'write':
            self.do_write(can_msg)
        else:
            self.fatal_error('命令 ' + args['action'] + ' 没有实现')
        return can_msg

    def do_read(self, can_msg):
        if self._run and not can_msg.CANData:
            try:
                can_frame = self._socket.recv(16)
                self.info("读取: " + self.get_hex(can_frame))
                if len(can_frame) == 16:
                    idf = struct.unpack("I", can_frame[0:4])[0]
                    if idf & 0x80000000:
                        idf &= 0x7FFFFFFF
                    can_msg.CANFrame = CANMessage.init_data(
                        idf, can_frame[4], can_frame[8:8 + can_frame[4]])
                    can_msg.bus = self._bus
                    can_msg.CANData = True
            except:
                return can_msg
        return can_msg

    def do_write(self, can_msg):
        if can_msg.CANData:
            idf = can_msg.CANFrame.frame_id
            if can_msg.CANFrame.frame_ext:
                idf |= 0x80000000
            data = struct.pack("I", idf) + struct.pack("B", can_msg.CANFrame.frame_length) + b"\xff\xff\xff" + \
                can_msg.CANFrame.frame_raw_data[0:can_msg.CANFrame.frame_length] + b"0" * (
                    8 - can_msg.CANFrame.frame_length)
            self._socket.send(data)
            self.info("写入: " + self.get_hex(data))
        return can_msg
