# Embedded file name: client\upload.pyo
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import os
import os.path
import time
import logging
import wx
import threading
from client import device
from client import devicetypes
from client import internationalisation
from client import utils
from client import zigbee_device
log = logging.getLogger(os.path.basename('upload'))
from client.onzo_platform import *

import random
import optparse
import datetime
from client import usbutils as usbprotocol
import device
import csv
from client import blockformats

def preparedevice():
    d = device.Device(debug=False)
    d.connect()
    pr = usbprotocol.pack_reqest

    def get_register(network_id, register_id):
        log.info('get_register(%r, %r)' % (network_id, register_id))
        trans_id = random.getrandbits(16)
        request = pr(trans_id, network_id, usbprotocol.REQUEST_GET_REGISTER, register_id, [])
        d.message_send(request)
        response = d.message_recv()
        r_trans_id, _, got_type, _, params = usbprotocol.unpack_response(response)
        if r_trans_id != trans_id:
            log.error('transactions id differ %r %r' % (r_trans_id, trans_id))
        if params is not None:
            return params[0]
        log.error('get_register error %r' % (got_type,))
        return 'ERROR %r' % (got_type,)

    def get_block_request(network_id, data_type, block_number):
        log.info('get_block_request(%r, %r, %r)' % (network_id, data_type, block_number))
        trans_id = random.getrandbits(16)
        request = pr(trans_id, network_id, usbprotocol.REQUEST_GET_BULK_DATA, data_type, [block_number, 1])
        d.message_send(request)
        response = d.message_recv()
        r_trans_id, _, got_type, _, params = usbprotocol.unpack_response(response)
        if r_trans_id != trans_id:
            log.error('transactions id differ %r %r' % (r_trans_id, trans_id))
        return (params[0], params[1])

    return (get_register, get_block_request)

def blocktransfer(data_type, get_register, get_block_request):
    log.info(' [*] retrieving data')
    display_firmware = get_register(2, 45)
    clamp_firmware = get_register(1, 1)
    display_timestamp = 0
    clamp_timestamp_low = get_register(1, 8)
    clamp_timestamp_high = get_register(1, 9)
    clamp_timestamp = clamp_timestamp_high * 65536 + clamp_timestamp_low
    clamp_ear_low = get_register(1, 16)
    clamp_ear_high = get_register(1, 17)
    clamp_ear = clamp_ear_high * 65536 + clamp_ear_low
    print '# Firmware: display=%i (0x%x) clamp=%i (0x%x)' % (display_firmware,
     display_firmware,
     clamp_firmware,
     clamp_firmware)
    print '# Timestamp: display=%i (0x%x) clamp=%i (0x%x)' % (display_timestamp,
     display_timestamp,
     clamp_timestamp,
     clamp_timestamp)
    print '# Clamp ear: %i (0x%x)' % (clamp_ear, clamp_ear)
    epoch = int(time.time() - clamp_timestamp) #fixup for the retarded timestamp on the clamp
    print 'calculated epoch=%i' % epoch
    curr_time = int(time.time())
    print 'current time=%i' % curr_time
    cur_block = get_register(2, 87 + data_type)
    cur_offset = get_register(2, 94 + data_type)
    start_block = get_register(2, 101+ data_type)
    print 'cur_block=%i # get_register(%i)' % (cur_block, 87 + data_type)
    print 'cur_offset=%i # get_register(%i)' % (cur_offset, 94 + data_type)
    print 'start_block=%i # get_register(%i)' % (start_block, 101 + data_type)
    if cur_block == 65535:
        log.info('capped the block number to 5')
        cur_block = 5
    if cur_block < 1537:
        if data_type == 1:
            savefile = "1-ENERGY_LOW_RES.csv"
            buffsize = 256
            kwargs = {"interval": 2048, "offset":0, "multiplier":4}
            powerdata = blockformats.Energy_091002(data_type, buffsize, cur_block, cur_offset, start_block, **kwargs)
        if data_type == 2:
            savefile = "2-ENERGY_HIGH_RES.csv"
            buffsize = 256
            kwargs = {"interval": 512, "offset":256, "multiplier":1}
            powerdata = blockformats.Energy_091002(data_type, buffsize, cur_block, cur_offset, start_block, **kwargs)
        if data_type == 3:
            savefile = "3-POWER_REAL_STANDARD.csv"
            buffsize = 768
            powerdata = blockformats.RealPower_091002(data_type, buffsize, cur_block, cur_offset, start_block)
        if data_type == 4:
            savefile = "4-POWER_REAL_FINE.csv"
            buffsize = 1536
            powerdata = blockformats.RealPower_091002(data_type, buffsize, cur_block, cur_offset, start_block)
        if data_type == 5:
            savefile = "5-POWER_REACTIVE_STANDARD.csv"
            buffsize = 512
            powerdata = blockformats.ReactivePower_091002(data_type, buffsize, cur_block, cur_offset, start_block)
        save_file = open(savefile, 'wb')
        file_writer = csv.writer(save_file,lineterminator='\n')
        header = ('Unix time','Date YYYY-MM-DD HH:MM:SS','Sample value')
        file_writer.writerow(header)
        if start_block != 0:
            for index in range(start_block,buffsize):
                i, block = get_block_request(2, data_type, index)
                decoded = powerdata.decode(block)
                decoded_length = len(decoded)
                for x in range(decoded_length):
                    sample = list(decoded[x])
                    unixtime = sample[0]+epoch # use this for unix timestamp
                    sample[0] = datetime.datetime.fromtimestamp(float(sample[0]+epoch)) # use this for human readable timestamp
                    sample.insert(0,unixtime)
                    file_writer.writerow(sample)
        for index in range(cur_block):
            i, block = get_block_request(2, data_type, index)
            decoded = powerdata.decode(block)
            decoded_length = len(decoded)
            for x in range(decoded_length):
                sample = list(decoded[x])
                unixtime = sample[0]+epoch # use this for unix timestamp
                sample[0] = datetime.datetime.fromtimestamp(float(sample[0]+epoch)) # use this for human readable timestamp
                sample.insert(0,unixtime)
                file_writer.writerow(sample)

		
    log.info(' [*] retrieving data finished')



class UploadException(Exception):

    def __init__(self, message):
        Exception.__init__(self, message)


def progress_step_decorator(foo):

    def wrapper(self, *args, **kwargs):
        if 'progress_step' in kwargs:
            self.progress_step(kwargs['progress_step'])
            del kwargs['progress_step']
        if 'status' in kwargs:
            self.progress_status(kwargs['status'])
            del kwargs['status']
        return foo(self, *args, **kwargs)

    return wrapper


class UploadFailedError(Exception):
    pass

class ClientRPC(object):
    progress = 0.0

    def __init__(self, device, settings, state, taskbar = None):
        self.device = device
        self.state = state
        self.settings = settings
        self.taskbar = taskbar
        self.display = ''
 #       self.on_popup_url = webbrowser.open_new
        self._ignore_fail = False

    def set_logo(self, name):
        self.state.ui_flavour.set(name)

    def noop(self, *args, **kwargs):
        pass

    def sleep(self, timeout):
        time.sleep(timeout)

    def log(self, *args, **kwargs):
        log.info(*args, **kwargs)

    def message_box(self, message, title = _('Error!')):
        return utils.message_box(message, title)

    def confirm_box(self, message, title = 'Error!'):
        return map_confirm(message, title, self.taskbar)

    def onzo_confirm_box(self, message, title, affirmative, negative):
        log.debug('onzo_confirm_box()')
        return utils.onzo_confirmation(message, title, affirmative, negative)

    def fail(self, message = None):
        if self._ignore_fail:
            log.debug('Ignoring Fail')
            self._ignore_fail = False
            return True
        log.info('Upload fail: %s' % message)
        raise UploadFailedError(message)

    def popup_url(self, url):
        log.debug('Opening url: %s' % url)
        self.on_popup_url(url)

    def upload_finished(self):
        log.info('Upload finished')
        self.settings['last_dump_time'] = str(time.time())
        self.settings.save()

    def update_settings(self, param, value):
        self.settings[str(param)] = value
        self.settings.save()

    def upload_prepare_to_repeat(self):
        self.progress_bar(0.01)
        self.state.ui_flavour.set('uploading')

    def progress_bar(self, progress):
        self.progress = progress
        self.state.upload_progress.set(self.progress)
        return self.progress

    def progress_step(self, step):
        self.progress += step
        self.state.upload_progress.set(self.progress)
        return self.progress

    def progress_status(self, message, url = None):
        if url:
            self.state.upload_status.set((message, url))
        else:
            self.state.upload_status.set(message)

    @progress_step_decorator
    def msg_single_no_errors(self, msg):
        if not self.device.connected:
            self.device.connect()
        msg = base64.b64decode(msg)
        try:
            self.device.message_send(msg)
            res = self.device.message_recv()
            return base64.b64encode(res)
        except Exception:
            return None

        return None

    @progress_step_decorator
    def msg_single(self, msg):
        if not self.device.connected:
            self.device.connect()
        msg = base64.b64decode(msg)
        for i in xrange(3):
            try:
                self.device.message_send(msg)
                res = self.device.message_recv()
                break
            except Exception:
                if i == 2:
                    log.critical('Repeating query failed!')
                    raise
                log.critical(str(traceback.format_exc()).strip())
                time.sleep(1)
                self.device.connect()

        return base64.b64encode(res)

    def msg_multi(self, msg, message_number, progress_step = None):
        if not self.device.connected:
            self.device.connect()
        progress_done = 0.0
        msg = base64.b64decode(msg)
        self.device.message_send(msg)
        responses = []
        for x in range(message_number):
            try:
                res = self.device.message_recv()
            except Exception:
                log.critical(str(traceback.format_exc()).strip())
                raise

            responses.append(base64.b64encode(res))
            if not res or len(res) < 256:
                break
            if progress_step is not None:
                x = progress_step / float(message_number)
                progress_done += x
                self.progress_step(x)

        if progress_step is not None:
            self.progress_step(progress_done - progress_step)
        return responses

    def echo(self, data):
        return data

    def disable_cancel_button(self, disable_cancel):
        self.state.disable_close.set(disable_cancel)
        self.state.disable_cancel.set(disable_cancel)

    def get_instance_id(self):
        if float(PROTOCOL_VERSION) < 1.0:
            return (self.state.settings.get_instance_id(), self.state.settings['brand_id'])
        else:
            return self.state.settings.get_instance_id()

    def get_brand_id(self):
        return self.state.settings['brand_id']

    def get_display_type(self):
        return self.display


class UploadThread(threading.Thread):

    def __init__(self, device, settings):
        threading.Thread.__init__(self)
        self.device = device
        self.settings = settings
        self.settings.attach(self.update_settings)
        self.on_upload_start = lambda : None
        self.on_upload_stop = lambda : None
        self.on_upload_error = lambda : eNone
        self._start_event = threading.Event()
        self._stop_event = threading.Event()
        self._exiting = False
        self.response = []
        return


    def run(self):
        log.debug('UploadThread started: %s' % self)
        while not self._exiting:
            self._start_event.clear()
            self._start_event.wait()
            if self._exiting:
                return
            if self.device and self.settings:
                self._stop_event.clear()

                try:
                    while self.loop_once(self._stop_event.isSet):
                        if self._stop_event.isSet():
                            break

                    log.info('Upload stop')
                    self.on_upload_stop()
                except UploadFailedError:
                    self.on_upload_error()
                except device.OnzoException:
                    log.critical('Device error', exc_info=True)
                    utils.message_box(_('Problem communicating with the display.\nPlease check your display and USB cable.\n'), _('Error uploading data'))
                    self.on_upload_error()
                except IOError:
                    log.critical('Network error', exc_info=True)
                    utils.message_box(_('Network problems occurred.\nPlease check your internet connection and try again.\n'), _('Error uploading data'))
                    self.on_upload_error()

                except:
                    log.critical('Unknown error', exc_info=True)
                    utils.message_box(_('Error occurred. Please retry later.\n'), _('Error uploading data'))
                    self.on_upload_error()



    def loop_once(self, stop_condition):
        get_register, get_block_request = preparedevice()
        self.client.progress_status('Dump: ENERGY_LOW_RES','http://en.wikipedia.org/wiki/Kilowatt_hour')
        blocktransfer(int(1), get_register, get_block_request)
        self.client.progress_step(0.2)
        if stop_condition():
            log.info('Upload cancelled')
            return False
        self.client.progress_status('Dump: ENERGY_HIGH_RES','http://theoatmeal.com/comics/tesla')
        blocktransfer(int(2), get_register, get_block_request)
        self.client.progress_step(0.2)
        if stop_condition():
            log.info('Upload cancelled')
            return False
        self.client.progress_status('Dump: POWER_REAL_STANDARD','http://en.wikipedia.org/wiki/AC_power')
        blocktransfer(int(3), get_register, get_block_request)
        self.client.progress_step(0.2)
        if stop_condition():
            log.info('Upload cancelled')
            return False
        self.client.progress_status('Dump: POWER_REAL_FINE','http://xkcd.com/643/')
        blocktransfer(int(4), get_register, get_block_request)
        self.client.progress_step(0.2)
        if stop_condition():
            log.info('Upload cancelled')
            return False
        self.client.progress_status('Dump POWER_REACTIVE_STANDARD','http://en.wikipedia.org/wiki/Power_factor')
        blocktransfer(int(5), get_register, get_block_request)
        self.client.progress_step(0.2)
        if stop_condition():
            log.info('Upload cancelled')
            return False
        self.client.progress_status('All Done')
        self.client.upload_finished()
        return False

    def update_settings(self, settings = None):
        pass

    def UploadStart(self, client):
        self.client = client
        self._start_event.set()

    def UploadStop(self):
        self._stop_event.set()

    def cleanup(self):
        self.settings.detach(self.update_settings)
        self._exiting = True
        self._stop_event.set()
        self._start_event.set()


class DownloadException(Exception):
    pass


class UpgradeCancelledException(Exception):
    pass

