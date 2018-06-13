# Embedded file name: client\device.pyo
import sys, os, time
reload(sys)
sys.setdefaultencoding('utf-8')
import struct
import ctypes
# import threading
import Queue
import random
import logging
log = logging.getLogger('device')
import wx
from client import devicetypes
from client import usbutils
import usb
# from client import utils
# from client import internationalisation
# RESET_MAYBE = _('If the device has a blank screen, please restart it.\n(Disconnect from USB and remove the batteries. \nThen replace the batteries and reconnect USB)\n')
RESET_MAYBE = 'reset maybe'
WINDOWS = False
MAC = False
LINUX = False
if sys.platform == 'win32':
    WINDOWS = True
elif sys.platform == 'darwin':
    MAC = True
elif sys.platform.startswith('linux'):
    LINUX = True
if WINDOWS:
    onzo_dll = ctypes.windll.LoadLibrary('OnzoDisplayClientLibrary.dll')
elif MAC:
    onzo_dll = ctypes.cdll.LoadLibrary('OnzoPyDisplays.dylib')
#elif LINUX:
#    onzo_dll = {} #ctypes.cdll.LoadLibrary('OnzoPyDisplays.so.1.0.0')
SixtyFourChars = ctypes.c_char * 64
SixtyFourCharsPtr = ctypes.POINTER(SixtyFourChars)
if WINDOWS:
    PROGCALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_int, ctypes.c_float)
    CALLBACK = ctypes.WINFUNCTYPE(None, SixtyFourCharsPtr)
else:
    PROGCALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_float)
    CALLBACK = ctypes.CFUNCTYPE(None, SixtyFourCharsPtr)
if not LINUX:
    onzo_dll.ONZO_DisplayFind.argtypes = []
    onzo_dll.ONZO_DisplayFind.restype = ctypes.c_int
    onzo_dll.ONZO_DisplayWrite.argtypes = [SixtyFourChars]
    onzo_dll.ONZO_DisplayWrite.restype = ctypes.c_int
    onzo_dll.ONZO_DisplayInit2.argtypes = [ctypes.c_int, ctypes.c_int, CALLBACK]
    onzo_dll.ONZO_DisplayInit2.restype = ctypes.c_int
    onzo_dll.ONZO_DisplayUpdateFirmware.argtypes = [ctypes.c_char_p]
    onzo_dll.ONZO_DisplayUpdateFirmware.restype = ctypes.c_int
    onzo_dll.ONZO_DisplayUpdateFirmwareWithProgress.argtypes = [ctypes.c_char_p, PROGCALLBACK]
    onzo_dll.ONZO_DisplayUpdateFirmwareWithProgress.restype = ctypes.c_int
    onzo_dll.ONZO_DisplayReset.argtypes = []
    onzo_dll.ONZO_DisplayReset.restype = ctypes.c_int
if MAC:
    onzo_dll.ONZO_CheckStillConnected.argtypes = []
    onzo_dll.ONZO_CheckStillConnected.restype = ctypes.c_int

class OnzoException(IOError):
    pass


def disconnect_on_error(m):

    def wrapper(self, *args, **kwargs):
        try:
            return m(self, *args, **kwargs)
        except OnzoException, e:
            self.connected = False
            raise

    return wrapper


hexify_string = lambda s: ''.join([ ' %02X' % ord(c) for c in s ])

def message_send(buf, frame_send, final_frame = 1):
    msgs = [struct.pack('<BB', final_frame, len(buf)), buf, chr(255) * (62 - len(buf))]
    msg = ''.join(msgs)
    frame_send(msg)


def message_read(frame_read):
    payloads = []
    while True:
        frame = frame_read()
        frame_fin, frame_size = struct.unpack('<BB', frame[:2])
        payload = frame[2:2 + frame_size]
        payloads.append(payload)
        if frame_fin:
            break

    msg = ''.join(payloads)
    return msg


def message_read_num(frame_read, number_messages = 0):
    payloads = []
    packets_received = 0
    while True:
        frame = frame_read()
        frame_fin, frame_size = struct.unpack('<BB', frame[:2])
        payload = frame[2:2 + frame_size]
        payloads.append(payload)
        packets_received += 1
        if frame_fin or packets_received == number_messages:
            break

    msg = ''.join(payloads)
    return msg


class Device(object):
    COMMAND_DELAY = 0.1
    COMMAND_TIMEOUT = 5.0
    DEVICE_APP_MODE = 63
    DEVICE_BOOT_MODE = 60
    callback_ptr = None
    callback_pointer = None
    queue = None
    bootloadermode = False
    updating_firmware = False
    debug = True
    last_command_time = 0.0
    connected = False

    def __init__(self, firmwareupdate = False, debug = True):
        self.bootloadermode = firmwareupdate
        self.debug = debug
        self.callback_ptr = CALLBACK(self.callback)
        self.queue = Queue.Queue()
        self.vendorid = None
        self.productid = None
        self.dev = None
        return

    def find(self):
        if self.connected:
            return self.productid
        else:
            r = onzo_dll.ONZO_DisplayFind()
            return r or None
        return None

    def connect2(self, vendor_id = devicetypes.vendor_ids[0], product_id = devicetypes.default_product_id):
        if self.bootloadermode:
            return
        if self.connected and MAC:
            connected = onzo_dll.ONZO_CheckStillConnected()
            if connected == 0:
                self.connected = False
        last_call_recent = True
        if (WINDOWS or LINUX) and time.time() - self.last_command_time > self.COMMAND_TIMEOUT + 1.0:
            last_call_recent = False
        if self.connected and last_call_recent:
            if vendor_id == self.vendorid and product_id == self.productid:
                return
            else:
                raise OnzoException(1)
        log.debug('connect - going to connect VID=%d, PID=%d' % (vendor_id, product_id))
        r = onzo_dll.ONZO_DisplayInit2(vendor_id, product_id, self.callback_ptr)
        if r != 0:
            log.debug('Failed to connect to device %d.' % r)
            raise OnzoException(r)
        else:
            log.debug('connected to device VID=%d, PID=%d, return=%d.' % (vendor_id, product_id, r))
        self.vendorid = vendor_id
        self.productid = product_id
        self.last_command_time = time.time()
        self.connected = True

    '''udev rules need to be set in /etc/udev/rules.d'''

    def detach(self, interface=0):
        '''Detach the interface'''
        if self.dev.is_kernel_driver_active(interface):
            print "Detaching kernel driver for interface %d" % (interface)
            self.dev.detach_kernel_driver(interface)

    def attach(self, interface=0):
        if not self.dev.is_kernel_driver_active(interface):
            print "Attaching kernel driver for interface %d" % (interface)
            self.dev.attach_kernel_driver(interface)

    def unclaim(self, interface=0):
        print "Unclaiming interface %d " % (interface)
        usb.util.release_interface(self.dev, interface)

    def claim(self, interface=0):
        '''Claiming interface'''
        usb.util.claim_interface(self.dev, interface)

    def disconnect(self):
#        for interface in range(0,1):
 #           self.detach(interface)
        self.dev.reset()

    def connect(self, vendor_id = devicetypes.vendor_ids[0], product_id = devicetypes.default_product_id):
        self.dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
        if self.dev is None:
            raise ValueError('Device not connected')
        else:
            self.dev.reset()
            for interface in range(0,1):
                self.detach(interface)
                self.unclaim(interface)
        self.dev.set_configuration()
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0,0)]

        self.epWrite = usb.util.find_descriptor(
            intf,
            # match the first OUT endpoint
            custom_match = \
                lambda e: \
                    usb.util.endpoint_direction(e.bEndpointAddress) == \
                    usb.util.ENDPOINT_OUT)

        assert self.epWrite is not None

        self.epRead = usb.util.find_descriptor(
            intf,
            # match the first OUT endpoint
            custom_match = \
                lambda e: \
                    usb.util.endpoint_direction(e.bEndpointAddress) == \
                    usb.util.ENDPOINT_IN)
        assert self.epRead is not None

        self.vendorid = vendor_id
        self.productid = product_id
        self.last_command_time = time.time()
        self.connected = True

    def is_real(self):
        return True

    def callback(self, p):
        buf = ''.join((c for c in p.contents))
        self.queue.put(buf)

    def _frame_write(self, data):
        if len(data) != 64:
            log.warning('bad data length 64!=%r  data=%r' % (len(data), hexify_string(data)))
        i = self.epWrite.write(data)
#        i = onzo_dll.ONZO_DisplayWrite(SixtyFourChars(*[ c for c in data ]))
        if i not in (64,): # 64
            raise OnzoException(i, 'bad return value ONZO_DisplayWrite(%r) = %r' % (hexify_string(data), i))

    def _frame_read(self):
#        try:
            bytes = self.epRead.read(64, timeout = int(self.COMMAND_TIMEOUT*1000))
            return "".join(map(chr,bytes))
#            return self.queue.get(True, self.COMMAND_TIMEOUT)
#        except Queue.Empty:
#            raise OnzoException(-1, 'read timeouted: %.3f seconds' % self.COMMAND_TIMEOUT)

    def flush_buffer(self):
        while not self.queue.empty():
            buf = self.queue.get(block=False)
            log.warning('Flushing buffer: %r' % hexify_string(buf))

    def is_buffer_empty(self):
        return self.queue.empty()

    def soft_reset(self):
        self.write_zero_packet()
        try:
            self.message_recv_num(1)
        except Queue.Empty:
            return False
        except:
            return False
        else:
            return True

    def write_zero_packet(self):
        msg = '\x00' * 64
        self._frame_write(msg)

    @disconnect_on_error
    def message_send(self, msg, final_frame = 1):
        self.last_command_time = time.time()
#        if not self.is_buffer_empty():
#            self.flush_buffer()
#            log.warning('Sending command but buffer is not empty.')

        def fw(buf):
            if self.debug:
                print '\nSENDING FRAME:'
                usbutils.pprint_frame(buf)
            self._frame_write(buf)

        message_send(msg, fw, final_frame)

    message_send_with_no_delay = message_send

    @disconnect_on_error
    def message_recv(self):

        def fr():
            buf = self._frame_read()
            if self.debug:
                print '\nRECEIVED FRAME:'
                usbutils.pprint_frame(buf)
                log.debug('Frame read : %r' % hexify_string(buf))
            return buf

        return message_read(fr)

    @disconnect_on_error
    def message_recv_num(self, number_packets):

        def fr():
            buf = self._frame_read()
            if self.debug:
                print '\nRECEIVED FRAME:'
                usbutils.pprint_frame(buf)
            return buf

        return message_read_num(fr, number_packets)

    @disconnect_on_error
    def message_recv(self):

        def fr():
            buf = self._frame_read()
            if self.debug:
                print '\nRECEIVED FRAME:'
                usbutils.pprint_frame(buf)
            return buf

        return message_read(fr)

    def _update_firmware(self, hex_filename):
        r = onzo_dll.ONZO_DisplayUpdateFirmware(hex_filename)
        if r not in (0,):
            raise OnzoException(r, 'ONZO_DisplayUpdateFirmware(%r)=%r' % (hex_filename, r))

    def progress_upgrade(self, hex_filename, callback_pointer):
        r = onzo_dll.ONZO_DisplayUpdateFirmwareWithProgress(hex_filename, callback_pointer)
        if r not in (0,):
            raise OnzoException(r, 'ONZO_DisplayUpdateFirmwareWithProgress(%r)=%r' % (hex_filename, r))
        return True

    def GetRegister(self, network_id, register):
        try:
            trans_id = random.getrandbits(16)
            request = usbutils.pack_request(trans_id, network_id, usbutils.REQUEST_GET_REGISTER, register, [])
            self.message_send(request)
            response = self.message_recv()
            r_trans_id, _, got_type, _, params = usbutils.unpack_response(response)
            return params[0]
        except:
            return 0

    def update_firmware(self, hex_filename, progress_callback = None):
        log.debug('**** Setting BL to True')
        self.bootloadermode = True
        for attempt in xrange(10):
            pid = self.find()
            if pid == self.DEVICE_BOOT_MODE:
                log.debug('Found device with PID=%s' % str(pid))
                break
            log.debug('Looking for BL SEK (found %s)' % str(pid))
            time.sleep(3)
        else:
            self.bootloadermode = False
            log.error('Device was not in bootloader mode! Last device seen was %r' % pid)
            log.error('Raising error.')
            raise OnzoException(4, 'An error occured - SEK not detected after reset')

        result = False
        try:
            for attempt in xrange(3):
                try:
                    if not result:
                        progress_callback(0, 0)
                        firmware_size = os.stat(hex_filename).st_size
                        callback_pointer = PROGCALLBACK(progress_callback)
                        t0 = time.time()
                        upgraded = self.progress_upgrade(hex_filename, callback_pointer)
                        t1 = time.time()
                        if upgraded:
                            log.info('Firmware installation took %.3f seconds for file of %iKB' % (t1 - t0, firmware_size / 1024))
                            result = True
                except Exception, e:
                    print e.message
                    log.error('Error on firmware update: %r' % (e,))
                    message = _('Error') + '1 \n'
                    title = _('Error!')
                    print e
                    if isinstance(e, OnzoException):
                        if e.args[0] == 20:
                            result = True
                            message = _('Error') + '2 \n'
                            title = _('Warning!')
                            flags = wx.OK | wx.ICON_EXCLAMATION
                            break
                        attempt < 2 and isinstance(e, OnzoException) and time.sleep(0.5)
                        continue
                    flags = wx.OK | wx.ICON_ERROR

        finally:
            result = self.reset()
            self.vendorid = 1240
            self.productid = 63
            self.connected = True
            self.bootloadermode = False
            self.connected = True
            log.debug('Finished upgrade BL=%s' % str(self.bootloadermode))
            return result

    def reset(self):
        result = onzo_dll.ONZO_DisplayReset()
        return result

    def cleanup(self):
        pass