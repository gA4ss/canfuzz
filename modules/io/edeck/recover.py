#!/usr/bin/env python3

import sys
import time
import requests
import json
import io

from python import Panda

Panda().reset(enter_bootstub=True)
Panda().reset(enter_bootloader=True)