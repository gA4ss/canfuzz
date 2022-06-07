# -*- coding: utf-8 -*-
import struct
import binascii
import bitstring

from frame.kernel.module import CANModule

class CANMessage:

  """
  此类主要用于对CAN消息结构的封装。
  """

  DataFrame = 1
  RemoteFrame = 2
  ErrorFrame = 3
  OverloadFrame = 4

  def __init__(self, fid, length, data, extended, type):
    self.frame_id = min(0x1FFFFFFF, int(fid))           # 消息ID
    self.frame_length = min(8, int(length))             # 数据长度
    self.frame_data = list(data)[0:self.frame_length]   # 数据
    self.frame_ext = bool(extended)                     # 是否使用帧扩展
    self.frame_type = type                              # 数据帧的类型

  def __bytes__(self):
    return self.frame_raw_data

  def __len__(self):
    return self.frame_length

  def __int__(self):
    return self.frame_id

  def __str__(self):
    return hex(self.frame_id)

  def get_bits(self):
    fill = 8 - self.frame_length
    bits_array = '0b'
    bits_array += '0' * fill * 8
    for byte in self.frame_data:
      bits_array += bin(byte)[2:].zfill(8)
    return bitstring.BitArray(bits_array, length=64)

  def get_text(self):
    """
    将当前的CAN数据组成一组形如： '消息ID：数据长度：十六进制数据' 的字符串
    """
    return hex(self.frame_id) + ":" + str(self.frame_length) + ":" + CANModule.get_hex(self.frame_raw_data)

  @property
  def frame_raw_id(self):
    if not self.frame_ext:
      return struct.pack("!H", self.frame_id)
    else:
      return struct.pack("!I", self.frame_id)

  @property
  def frame_raw_length(self):
    return struct.pack("!B", self.frame_length)

  @property
  def frame_raw_data(self):
    return bytes(self.frame_data)

  @frame_raw_data.setter
  def frame_raw_data(self, value):
    self.frame_data = list(value)[0:self.frame_length]  # DATA

  def to_hex(self):
    """CAN frame in HEX format ready to be sent (include ID, length and data)"""
    if not self.frame_ext:
      id = binascii.hexlify(struct.pack('!H', self.frame_id))[1:].zfill(3)
    else:
      id = binascii.hexlify(struct.pack('!I', self.frame_id)).zfill(8)
    length = binascii.hexlify(struct.pack('!B', self.frame_length))[1:].zfill(1)
    data = binascii.hexlify(bytes(self.frame_data)).zfill(self.frame_length * 2)
    return id + length + data

  @staticmethod
  def init_data(fid, length, data):  # Init
    if length > 8:
      length = 8
    if 0 <= fid <= 0x7FF:
      extended = False
    elif 0x7FF < fid <= 0x1FFFFFFF:
      extended = True
    else:
      fid = 0
      extended = False

    return CANMessage(fid, length, data, extended, 1)


class CANSploitMessage:

  """
  负载了CAN消息与其他数据的封装类。
  """

  def __init__(self):
    self.debugText = ""
    self.CANFrame = None
    self.debugData = False
    self.CANData = False
    self.bus = "Default"
