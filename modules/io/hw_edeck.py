# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import struct
import binascii
import hashlib
import socket
import usb1
import os
import time
import traceback

from frame.message.can import CANMessage, CANSploitMessage
from frame.kernel.module import CANModule, Command
from frame.stream.cmdres import CmdResult, CMDRES_STR

SAFETY_NOOUTPUT = 0
SAFETY_HONDA = 1
SAFETY_TOYOTA = 2
SAFETY_HONDA_BOSCH = 4

SAFETY_TOYOTA_NOLIMITS = 0x1336
SAFETY_ALLOUTPUT = 0x1337
SAFETY_ELM327 = 0xE327

SERIAL_DEBUG = 0
SERIAL_ESP = 1
SERIAL_LIN1 = 2
SERIAL_LIN2 = 3

GMLAN_CAN2 = 1
GMLAN_CAN3 = 2

REQUEST_IN = usb1.ENDPOINT_IN | usb1.TYPE_VENDOR | usb1.RECIPIENT_DEVICE
REQUEST_OUT = usb1.ENDPOINT_OUT | usb1.TYPE_VENDOR | usb1.RECIPIENT_DEVICE


class hw_edeck(CANModule):
    name = "电子甲板"
    version = 1.0
    help = {
        "describe": "这个模块主要用于edeck设备数据读写。",
        "init_parameters": {
            "serial": {
                "describe": "指定设备序列号。",
                "type": "str",
                # "default": None
            },
            "claim": {
                "describe": "释放已捕获的但是未匹配的USB接口资源。",
                "type": "bool",
                "default": "True"
            },
            "wait": {
                "describe": "如果设备此时不存在，则等待设备链接。",
                "type": "bool",
                "default": "False"
            },
            "bus_num": {
                "describe": "设备接口名称。",
                "type": "int",
                "default": 0,
                "range": [0, 1, 2]
            },
            "bus_speed": {
                "describe": "设备波特率。",
                "type": "int",
                "default": 500
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

    def do_init(self, params):
        self.describe = hw_edeck.help.get('describe', hw_edeck.name)
        self._bus = 'edeck'

        self.commands['write'] = Command(
            "直接发送CAN数据帧, 类似如下字符串形式: 304:8:07df300101000000", 1, "<数据帧字符串>", self.dev_write, True)
        self.commands['write2'] = Command(
            "按照给定次数发送CAN数据帧, 类似如下字符串形式: 304:8:07df300101000000,50,0.05", 1, "<数据帧字符串>", self.write_on_count, True)
        self.commands['write3'] = Command(
            "按照给定时间发送CAN数据帧, 类似如下字符串形式: 304:8:07df300101000000,60,0.03", 1, "<数据帧字符串>", self.write_on_time, True)

        self._serial = params.get('serial', None)
        self._claim = params.get('claim', True)
        self._wait = params.get('wait', False)
        self._bus_num = params.get('bus_num', 0)
        self._bus_speed = params.get('bus_speed', 500)
        self._handle = None
        self._run = False

        return 0

    def do_start(self, params):
        if self._handle is None and not self._run:
            self.connect(self._claim, self._wait)
            self.set_can_speed_kbps(self._bus_num, self._bus_speed)
            self.set_safety_mode(SAFETY_ALLOUTPUT)
            self._run = True

    def do_stop(self, params):
        if self._handle and self._run:
            try:
                self.close()
                self._run = False
            except Exception as e:
                self._run = False
                self.error("停止失败: ", e)

    def write_on_count(self, line):
        loop = 10
        delay = 0.05
        canmsg = ""

        params = line.split(',')
        if len(params) == 1:
            canmsg = params[0]
        elif len(params) == 2:
            canmsg = params[0]
            loop = int(params[1], 0)
        else:
            canmsg = params[0]
            loop = int(params[1], 0)
            delay = float(params[2])

        first_time = time.perf_counter()
        last_time = 0.0
        while loop > 0:
            curr_time = int(time.perf_counter())
            if curr_time - last_time >= delay:
                last_time = time.perf_counter()
                ret = self.dev_write(canmsg)
                self.info(ret.result)
                loop -= 1
        total_time = str(last_time - first_time)
        return CmdResult(cmdline='write2 ' + line, describe="发送总时间", result_type=CMDRES_STR, result=total_time)

    def write_on_time(self, line):
        total_sec = 10
        delay = 0.05
        canmsg = ""

        params = line.split(',')
        if len(params) == 1:
            canmsg = params[0]
        elif len(params) == 2:
            canmsg = params[0]
            total_sec = float(params[1])
        else:
            canmsg = params[0]
            total_sec = float(params[1])
            delay = float(params[2])

        begin_time = time.perf_counter()
        end_time = begin_time
        last_time = 0.0
        count = 0
        while end_time - begin_time < total_sec:
            curr_time = time.perf_counter()
            if curr_time - last_time >= delay:
                last_time = time.perf_counter()
                ret = self.dev_write(canmsg)
                self.info(ret.result)
                count += 1
            end_time = time.perf_counter()
        return CmdResult(cmdline='write3 ' + line, describe="发送总计数", result_type=CMDRES_INT, result=count)

    def dev_write(self, line):
        ret = CmdResult()
        if self._run:
            try:
                idf = line.split(":")[0]
                lenf = line.split(":")[1]
                dataf = line.split(":")[2]
                message = CANSploitMessage()
                message.CANData = True
                dataf = bytes.fromhex(dataf)
                can_msg = CANMessage.init_data(
                    int(idf, 0), int(lenf, 0), dataf)
                message.CANFrame = can_msg
                self.do_write(message)
                ret = CmdResult(cmdline='write ' + line, describe="Edeck设备写入数据",
                                result_type=CMDRES_STR, result=can_msg.get_text())
            except Exception as e:  # cmd 0 t 304:8:07d1300101000000
                self.error('写入CAN数据到设备发生异常', e)
                ret = CmdResult(cmdline='write ' + line,
                                describe="写入CAN数据到设备发生异常", last_error=-2, e=e)
        else:
            ret = CmdResult(cmdline='write ' + line,
                            describe="模块未激活", last_error=-2)
        return ret

    def do_write(self, can_msg):
        if can_msg.CANData:
            idf = can_msg.CANFrame.frame_id
            self.info("写入 : CANID : {}".format(idf))
            if can_msg.CANFrame.frame_ext:
                idf |= 0x80000000
            dataf = bytearray(can_msg.CANFrame.frame_data)
            lenf = can_msg.CANFrame.frame_length
            self.set_safety_mode(SAFETY_ALLOUTPUT)
            self.can_send(idf, dataf, self._bus_num)
            self.set_safety_mode(SAFETY_NOOUTPUT)
            self.info("数据 : {}, 长度 : {}".format(self.get_hex(dataf), lenf))
        return can_msg

    def do_read(self, can_msg):
        if self._run and not can_msg.CANData:
            can_recv = self.can_recv()
            for address, _, dat, src in can_recv:
                idf = address
                if idf & 0x80000000:
                    idf &= 0x7FFFFFFF
                can_msg.CANFrame = CANMessage.init_data(idf, len(dat), dat)
                can_msg.CANData = True
                self.info("读取数据 : " + str(self.get_hex(dat)))
        return can_msg

    def do_effect(self, can_msg, args):
        if args.get('action') == 'read':
            can_msg = self.do_read(can_msg)
        elif args.get('action') == 'write':
            self.do_write(can_msg)
        else:
            self.fatal_error('命令 ' + args['action'] + ' 没有实现')
        return can_msg

    # -------------------- edeck --------------------

    def connect(self, claim=True, wait=False):
        if self._handle != None:
            self.close()

        self.info('尝试链接USB设备... ')

        try:
            context = usb1.USBContext()
        except Exception as e:
            self.fatal_error("获取 'USBContext' 失败", e)
            self._handle = None
        this_serial = None

        while True:
            try:
                for device in context.getDeviceList(skip_on_error=True):
                    if device.getVendorID() == 0xbbaa and device.getProductID() in [0xddcc, 0xddee]:
                        try:
                            this_serial = device.getSerialNumber()
                        except Exception:
                            continue

                        if self._serial is None or this_serial == self._serial:
                            self._serial = this_serial
                            self.info('打开设备 {0} , {1}'.format(
                                self._serial, hex(device.getProductID())))
                            time.sleep(1)
                            self.bootstub = device.getProductID() == 0xddee
                            self.legacy = (device.getbcdDevice() != 0x2300)
                            self._handle = device.open()

                            if claim:
                                self._handle.claimInterface(0)
                            #
                            # 一旦找到对应的设备则退出循环
                            #
                            break
            except Exception as e:
                self.fatal_error("打开edeck设备失败", e)
                # traceback.print_exc()
            if wait == False or self._handle != None:
                break
        # 跳出循环后诊断一下
        if self._handle == None:
            self.fatal_error("找不到edeck设备")

    def close(self):
        try:
            self._handle.close()
        except Exception as e:
            self.error("关闭edeck设备失败", e)
        self._handle = None

    def set_safety_mode(self, mode=SAFETY_NOOUTPUT):
        try:
            self._handle.controlWrite(REQUEST_OUT, 0xdc, mode, 0, b'')
        except Exception as e:
            self.error("设置安全模式失败", e)

    def set_can_speed_kbps(self, bus, speed):
        try:
            self._handle.controlWrite(
                REQUEST_OUT, 0xde, bus, int(speed*10), b'')
        except Exception as e:
            self.fatal_error("设置速率失败", e)

    def can_send_many(self, arr):
        snds = []
        transmit = 1
        extended = 4
        for addr, _, dat, bus in arr:
            if addr >= 0x800:
                rir = (addr << 3) | transmit | extended
            else:
                rir = (addr << 21) | transmit
            snd = struct.pack("II", rir, len(dat) | (bus << 4)) + dat
            snd = snd.ljust(0x10, b'\x00')
            snds.append(snd)
        # print("can_send_many[1.1]",snds)
        # while True:  #cmd 0 t 304:8:07d1300101000000
        try:
            self._handle.bulkWrite(3, b''.join(snds))
        except (usb1.USBErrorIO, usb1.USBErrorOverflow):
            self.error("CAN: 发送失败，重新尝试...")

    def can_send(self, addr, dat, bus):
        self.can_send_many([[addr, None, dat, bus]])

    def can_recv(self):
        dat = bytearray()
        while True:
            try:
                dat = self._handle.bulkRead(1, 0x10)
                break
            except (usb1.USBErrorIO, usb1.USBErrorOverflow):
                self.error("CAN: 接收失败，重新尝试...")
        return self.parse_can_buffer(dat)

    def can_clear(self, bus):
        """
        bus : 要清除队列的数量，如果是-1则清除队列内的所有数据。  
        """
        try:
            self._handle.controlWrite(REQUEST_OUT, 0xf1, bus, 0, b'')
        except Exception as e:
            self.error("清除队列失败", e)

    def parse_can_buffer(self, dat):
        """
        从设备读取出来数据后，然后分解成可读的数据结构。
        """
        ret = []
        for j in range(0, len(dat), 0x10):
            ddat = dat[j:j+0x10]
            f1, f2 = struct.unpack("II", ddat[0:8])
            extended = 4
            if f1 & extended:
                address = f1 >> 3
            else:
                address = f1 >> 21
            dddat = ddat[8:8+(f2 & 0xF)]
            #self.dprint(self._DEBUG, "  R %x: %s" % (address, str(dddat).encode("hex")))
            ret.append((address, f2 >> 16, dddat, (f2 >> 4) & 0xFF))
        return ret
