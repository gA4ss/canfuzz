import time
import copy

from frame.message.can import CANMessage
from frame.kernel.module import CANModule, Command
from frame.stream.cmdres import CmdResult, CMDRES_INT, CMDRES_STR


class hw_fakeIO(CANModule):
  name = "测试设备驱动"
  version = 1.0
  help = {
    "describe": "此模块是一个伪造的IO流模块，用于模拟仿真IO接口。",
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
    self.describe = hw_fakeIO.help.get('describe', hw_fakeIO.name)
    self._bus = 'fakeIO'
    self.commands['write'] = Command("直接发送CAN数据帧, 类似如下字符串形式: 13:8:1122334455667788", 1, " <数据帧字符串> ", self.dev_write, True)
    self.commands['write2'] = Command("按照给定次数发送CAN数据帧, 类似如下字符串形式: 304:8:07df300101000000,50,0.05", 1, "<数据帧字符串>", self.write_on_count, True)
    self.commands['write3'] = Command("按照给定时间发送CAN数据帧, 类似如下字符串形式: 304:8:07df300101000000,60,0.03", 1, "<数据帧字符串>", self.write_on_time, True)
    self.CANList = []
    return 0

  def do_start(self, params):
    if not self._active:
      self.CANList = []

  def do_stop(self, params):
    if self._active:
      self.CANList = []

  def dev_write(self, line):
    fid = line.split(":")[0]
    length = line.split(":")[1]
    data = line.split(":")[2]
    can_msg = CANMessage.init_data(int(fid, 0), int(length, 0), bytes.fromhex(data)[:int(length, 0)])
    self.CANList.append(can_msg)
    return CmdResult(cmdline='write ' + line, describe="CAN列表添加", result_type=CMDRES_STR, result=can_msg.get_text())

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

  def do_effect(self, can_msg, args):
    if args.get('action') == 'read':
      can_msg = self.do_read(can_msg)
    elif args.get('action') == 'write':
      can_msg = self.do_write(can_msg)
    else:
      self.fatal_error('命令 ' + args['action'] + ' 没有实现')
    return can_msg

  def do_write(self, can_msg):
    if len(self.CANList) > 0:
      can_msg.CANData = True
      can_msg.CANFrame = self.CANList.pop(0)
      can_msg.bus = self._bus
    return can_msg

  def do_read(self, can_msg):
    if can_msg.CANData:
      self.CANList.append(copy.deepcopy(can_msg.CANFrame))
    return can_msg
