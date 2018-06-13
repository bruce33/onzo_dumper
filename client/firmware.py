# Embedded file name: client\firmware.pyo
import random, base64
import datetime
import usbprotocol
from client import blockformats
ENERGY_HIGH_RES = 'E'
ENERGY_LOW_RES = 'e'
POWER_REAL_FINE = 'P'
POWER_REAL_STANDARD = 'p'
POWER_REACTIVE_FINE = 'Q'
POWER_REACTIVE_STANDARD = 'q'
pack_request = usbprotocol.pack_reqest
unpack_response = usbprotocol.unpack_response

def parse_response(resp, resp_type = None, net_id = None):
    try:
        trans_id, got_net_id, got_resp_type, reg_id, params = unpack_response(resp)
    except usbprotocol.UsbException:
        raise

    if net_id is not None and net_id != got_net_id:
        raise usbprotocol.UsbException('Fatal communication error. Invalid net ID %r != %r.' % (got_net_id, net_id))
    if resp_type is not None and resp_type != got_resp_type:
        raise usbprotocol.UsbException('Fatal communication error. Invalid response type %r != %r.' % (got_resp_type, resp_type))
    return params


class Device(object):

    def __init__(self, firmware_version = None):
        pass

    net_id = None

    def get_register(self, reg_id):
        trans_id = random.getrandbits(16)
        req = pack_request(trans_id, self.net_id, usbprotocol.REQUEST_GET_REGISTER, reg_id, [])
        return req

    def set_register(self, reg_id, value):
        trans_id = random.getrandbits(16)
        req = pack_request(trans_id, self.net_id, usbprotocol.REQUEST_SET_REGISTER, reg_id, [value])
        return req

    def reset_device(self):
        trans_id = random.getrandbits(16)
        req = pack_request(trans_id, self.net_id, usbprotocol.REQUEST_CMD_RESET, 0, [])
        return req

    def get_bulk_data_transfer(self, data_type, block_index, max_blocks):
        trans_id = random.getrandbits(16)
        req = pack_request(trans_id, self.net_id, usbprotocol.REQUEST_GET_BULK_DATA, data_type, [block_index, max_blocks])
        return req

    def parse_response(self, resp, resp_type = None):
        try:
            trans_id, net_id, got_resp_type, reg_id, params = unpack_response(resp)
        except usbprotocol.UsbException:
            raise

        if self.net_id != net_id:
            raise usbprotocol.UsbException('Fatal communication error. Invalid net ID %r != %r.' % (net_id, self.net_id))
        if resp_type is not None and resp_type != got_resp_type:
            raise usbprotocol.UsbException('Fatal communication error. Invalid response type %r != %r.' % (got_resp_type, resp_type))
        return params

    def parse_version(self, version):
        year = version >> 9
        month = version >> 5 & 15
        day = version & 31
        if 1 <= month <= 12 and 1 <= day <= 31:
            return datetime.date(2000 + year, month, day)
        return '0x%x' % version


def Sensor(firmware_version = None):
    if firmware_version and firmware_version < 4930:
        return Sensor_pre091002(firmware_version)
    return BaseSensor(firmware_version)


class BaseSensor(Device):
    net_id = 1
    FIRMWARE_VERSION = 1
    SERIAL_NUMBER_LOW = 2
    SERIAL_NUMBER_HIGH = 3
    HIGH_RES_INTERVAL = 6
    TIMESTAMP_LOW = 8
    TIMESTAMP_HIGH = 9
    EAR_LOW = 16
    EAR_HIGH = 17
    registers = {'type': [0],
     'version': [1],
     'serial-hex': [2, 3],
     'serial-low': [2],
     'serial-high': [3],
     'status': [4],
     'power': [5],
     'readinginterval': [6],
     'sendinginterval': [7],
     'timestamp': [8, 9],
     'voltage': [10],
     'calphase0': [11],
     'calgain0': [12],
     'temperature': [13],
     'powervars': [14],
     'RSSI': [15],
     'EAR': [16, 17],
     'batteryvolts': [18],
     'txpower': [19],
     'instwatt': [23],
     'instvar': [24],
     'calgain1': [25],
     'calgain2': [26],
     'txperiodlimits': [27],
     'calgain3': [28],
     'calgain4': [29]}
    register_formats = {'serial-hex': '%08x',
     'serial-low': '%04d'}


class Sensor_pre091002(BaseSensor):
    TIMESTAMP_LOW = 9
    TIMESTAMP_HIGH = 10


class BaseDisplay(Device):
    net_id = 2
    RG_ID_MIN = 1
    RG_ID_HOUR = 2
    RG_ID_DAY = 3
    RG_ID_MON = 4
    RG_ID_YEAR = 5
    FIRMWARE_VERSION = 45
    HARDWARE_VERSION = 46
    SERIAL_NUMBER_LOW = 185
    SERIAL_NUMBER_HIGH = 186
    GEN_COUNTRY_CODE = 187
    CURRENT_TARIFF = 48
    STANDING_CHARGE_LO = 129
    STANDING_CHARGE_HI = 130
    UNIT_COST_LO = 131
    UNIT_COST_HI = 132

    def set_spend_rates(self, standing_charge, rates):
        standing_charge = max(min(int(standing_charge * 10000 + 0.5), 65534), 0)
        rate = max(min(int(rates[0][0] * 10000 + 0.5), 65534), 0)
        return [self.set_register(self.STANDING_CHARGE_LO, standing_charge),
         self.set_register(self.STANDING_CHARGE_HI, 0),
         self.set_register(self.UNIT_COST_LO, rate),
         self.set_register(self.UNIT_COST_HI, 0)]

    ANNUAL_EST_CONSUMPTION_LO = 133
    ANNUAL_EST_CONSUMPTION_HI = 134
    TARGET_LO = ANNUAL_EST_CONSUMPTION_LO
    TARGET_HI = ANNUAL_EST_CONSUMPTION_HI
    CONFIGURED = 83

    def set_target(self, target_value, eac_value):
        eac_value = int(target_value / 0.95 / 3600000)
        eac_hi = eac_value >> 16
        eac_lo = eac_value & 65535
        return [self.set_register(self.TARGET_LO, target_lo), self.set_register(self.TARGET_HI, target_hi), self.set_register(self.CONFIGURED, 1)]

    GRIDWATCH_WEEKDAY_START = 176
    GRIDWATCH_WEEKDAY_STOP = 177
    GRIDWATCH_WEEKEND_START = 178
    GRIDWATCH_WEEKEND_STOP = 179
    stream_order = []
    streams = {}
    registers = {'min': [1],
     'hour': [2],
     'day': [3],
     'month': [4],
     'year': [5],
     'synched': [33],
     'version': [45],
     'hardware': [46],
     'configured': [83],
     'standingcharge': [129, 130],
     'unitcost': [131, 132],
     'EAC': [133, 134],
     'gridweekstart': [176],
     'gridweekstop': [177],
     'gridweekendstart': [178],
     'gridweekendstop': [179],
     'serial-hex': [185, 186],
     'serial-low': [185],
     'serial-high': [186],
     'country': [187],
     'temp-offset': [192],
     'temp-gain': [193],
     'target': [222, 223],
     'cost0': [224],
     'cost1': [225],
     'cost2': [226],
     'cost3': [227],
     'start0': [228],
     'start1': [229],
     'start2': [230],
     'start3': [231]}
    register_formats = {'serial-hex': '%08x',
     'serial-low': '%04d'}


def Display(firmware_version = None):
    if firmware_version and firmware_version < 4978:
        return Display_091002(firmware_version)
    if firmware_version and firmware_version < 5196:
        return Display_091118(firmware_version)
    return Display_100212(firmware_version)


class Display_091002(BaseDisplay):
    stream_order = [ENERGY_LOW_RES,
     ENERGY_HIGH_RES,
     POWER_REAL_STANDARD,
     POWER_REAL_FINE,
     POWER_REACTIVE_STANDARD]
    streams = {ENERGY_LOW_RES: blockformats.Energy_091002(type=1, size=256, CURRENT=88, OFFSET=95, START=102, interval=2048, offset=0, multiplier=4),
     ENERGY_HIGH_RES: blockformats.Energy_091002(type=2, size=256, CURRENT=89, OFFSET=96, START=103, interval=512, offset=256, multiplier=1),
     POWER_REAL_STANDARD: blockformats.RealPower_091002(type=3, size=512, CURRENT=90, OFFSET=97, START=104),
     POWER_REAL_FINE: blockformats.RealPower_091002(type=4, size=512, CURRENT=91, OFFSET=98, START=105),
     POWER_REACTIVE_STANDARD: blockformats.ReactivePower_091002(type=5, size=1024, CURRENT=92, OFFSET=99, START=106)}


class Display_091118(Display_091002):
    TARGET_LO = 222
    TARGET_HI = 223

    def set_target(self, target_value, eac_value):
        eac_value = int(eac_value / 3600000)
        eac_hi = eac_value >> 16
        eac_lo = eac_value & 65535
        target_value = int(target_value / 3600000)
        target_hi = target_value >> 16
        target_lo = target_value & 65535
        return [self.set_register(self.TARGET_LO, target_lo),
         self.set_register(self.TARGET_HI, target_hi),
         self.set_register(self.ANNUAL_EST_CONSUMPTION_LO, eac_lo),
         self.set_register(self.ANNUAL_EST_CONSUMPTION_HI, eac_hi),
         self.set_register(self.CONFIGURED, 1)]


class Display_100212(Display_091118):
    streams = {ENERGY_LOW_RES: blockformats.Energy_091002(type=1, size=256, CURRENT=88, OFFSET=95, START=102, interval=2048, offset=0, multiplier=4),
     ENERGY_HIGH_RES: blockformats.Energy_091002(type=2, size=256, CURRENT=89, OFFSET=96, START=103, interval=512, offset=256, multiplier=1),
     POWER_REAL_STANDARD: blockformats.RealPower_091002(type=3, size=768, CURRENT=90, OFFSET=97, START=104),
     POWER_REAL_FINE: blockformats.RealPower_091002(type=4, size=1536, CURRENT=91, OFFSET=98, START=105),
     POWER_REACTIVE_STANDARD: blockformats.ReactivePower_091002(type=5, size=512, CURRENT=92, OFFSET=99, START=106)}


class Display_pre091002(BaseDisplay):
    stream_order = [ENERGY_HIGH_RES,
     ENERGY_LOW_RES,
     POWER_REAL_STANDARD,
     POWER_REAL_FINE,
     POWER_REACTIVE_STANDARD,
     POWER_REACTIVE_FINE]
    streams = {ENERGY_HIGH_RES: blockformats.Energy_1_069(type=1, size=256, CURRENT=88, OFFSET=95, START=102, interval=512, offset=256),
     ENERGY_LOW_RES: blockformats.Energy_1_069(type=2, size=256, CURRENT=89, OFFSET=96, START=103, interval=2048, offset=2048),
     POWER_REAL_STANDARD: blockformats.RealPower_1_01(type=3, size=512, CURRENT=90, OFFSET=97, START=104),
     POWER_REAL_FINE: blockformats.RealPower_1_01(type=4, size=512, CURRENT=91, OFFSET=98, START=105),
     POWER_REACTIVE_STANDARD: blockformats.ReactivePower_1_01(type=5, size=512, CURRENT=92, OFFSET=99, START=112),
     POWER_REACTIVE_FINE: blockformats.ReactivePower_1_01(type=6, size=512, CURRENT=93, OFFSET=100, START=113)}