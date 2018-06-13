# Embedded file name: client\zigbee_device.pyo
import sys, os, time
import ctypes
import threading
import Queue
import random
import struct
import usbutils
import logging
log = logging.getLogger('device')
from client import devicetypes, device
from client import internationalisation

class ZigbeeDevice(object):
    progress_steps = [50, 50]
    steps = ['Upload firmware', 'Wait for reboot']
    stages = {0: ['Copy data', 30],
     1: ['Upload firmware', 30],
     2: ['Rebooting device', 10],
     3: ['Restoring data', 30]}

    def __init__(self, device, firmware_image, status_message, backup_file):
        self.device = device
        self.device.updating_firmware = True
        self.backup_file = backup_file
        self.firmware_image = open(firmware_image, 'rb').read()
        self.set_message = status_message

    def progress_bar(self, progress, stage, percentage):
        total_steps = sum([ self.stages[x][1] for x in self.stages ])
        done_steps = sum([ self.stages[x][1] for x in self.stages if x < stage ])
        progress((percentage * self.stages[stage][1] + done_steps) / total_steps)

    def status(self, stage, percent):
        self.set_message('%s (stage %d of %d): %d%%' % (self.stages[stage][0],
         stage + 1,
         len(self.stages.keys()),
         int(percent * 100)))

    def get_num_recovery_blocks(self):
        return len(self.firmware_image) / 256 + 1

    def clean_up(self):
        os.unlink(self.backup_file)

    def get_data(self, progress):
        num_blocks = self.get_num_recovery_blocks()
        log.debug('Saving %d blocks from device' % num_blocks)
        self.saved_block_data = ''
        for current_block in range(0, num_blocks):
            self.saved_block_data += self.GetBulkData(2, 0, current_block)
            self.progress_bar(progress, 0, float(current_block) / num_blocks)
            self.status(0, float(current_block) / num_blocks)

        backup_file = open(self.backup_file, 'wb')
        backup_file.write(self.saved_block_data)
        backup_file.flush()
        backup_file.close()
        self.save_block_length = len(self.saved_block_data)

    def write_image(self, progress):

        def WrittenBlock(current_block, total_blocks):
            self.progress_bar(progress, 1, float(current_block) / total_blocks)
            self.status(1, float(current_block) / total_blocks)

        msgs = [self.firmware_image, '\x00' * ((256 - len(self.firmware_image) % 256) % 256)]
        data_to_send = ''.join(msgs)
        data_list = [ ord(x) for x in data_to_send ]
        number_of_blocks = len(data_list) / 256
        self.BulkWriteData(2, 0, 0, number_of_blocks, data_list, WrittenBlock)

    def reset(self):
        response = self.LDMCmd(2, 'E1011(0620000000)')

    def wait_wake_up(self, progress):
        wait_time = 15
        reps = 20
        send_time = 160
        elapsed_time = 0
        detected = False
        while elapsed_time < reps * wait_time:
            sec_count = 0
            while sec_count < wait_time:
                time.sleep(1)
                sec_count += 1
                elapsed_time += 1
                self.progress_bar(progress, 2, float(elapsed_time) / (reps * wait_time))
                self.status(2, float(elapsed_time) / (reps * wait_time))

            if elapsed_time >= send_time:
                log.debug('Sending soft reset')
                self.device.connect(self.device.vendorid, self.device.productid)
                if self.device.soft_reset():
                    log.debug('Device has rebooted')
                    detected = True
                    break
                else:
                    log.debug('Device is asleep')

        if detected:
            try:
                self.device.flush_buffer()
                self.device.message_recv_num(1)
            except Queue.Empty:
                pass
            except:
                pass

            self.device.connect(self.device.vendorid, self.device.productid)
            return True
        else:
            return False

    def restore_data(self, progress):

        def WrittenBlock(current_block, total_blocks):
            self.progress_bar(progress, 3, float(current_block) / total_blocks)
            self.status(3, float(current_block) / total_blocks)

        data_list = [ ord(x) for x in self.saved_block_data ]
        number_of_blocks = self.get_num_recovery_blocks()
        self.BulkWriteData(2, 0, 0, number_of_blocks, data_list, WrittenBlock)
        self.device.updating_firmware = False
        self.set_message('Firmware upgrade complete')

    def restore_data_from_file(self, file_name, progress):
        self.saved_block_data = open(file_name, 'rb').read()
        self.device.updating_firmware = True

        def WrittenBlock(current_block, total_blocks):
            progress(float(current_block) / total_blocks)
            self.set_message('Repairing: %d%%' % (float(current_block) / total_blocks))

        data_list = [ ord(x) for x in self.saved_block_data ]
        number_of_blocks = len(self.saved_block_data) / 256 + (0 if len(self.saved_block_data) % 256 == 0 else 1)
        log.debug('Number of blocks %d.' % number_of_blocks)
        self.BulkWriteData(2, 0, 0, number_of_blocks, data_list, WrittenBlock)
        self.device.updating_firmware = False
        self.set_message(_('Repair complete'))

    def GetBulkData(self, network_id, data_type, block_number):
        trans_id = random.getrandbits(16)
        request = usbutils.pack_request(trans_id, network_id, usbutils.REQUEST_GET_BULK_DATA, data_type, [block_number, 1])
        self.device.message_send(request)
        response = self.device.message_recv()
        r_trans_id, _, got_type, _, params = usbutils.unpack_response(response)
        return params[1]

    def LDMCmd(self, network_id, ldm_str, expect_response = False):
        trans_id = random.getrandbits(16)
        request = usbutils.pack_request(trans_id, network_id, usbutils.REQUEST_LDM_COMMAND, 0, [ldm_str])
        self.device.message_send(request)
        if expect_response:
            response = self.device.message_recv()
            r_trans_id, _, got_type, _, params = usbutils.unpack_response(response)
            return params
        else:
            return

    def set_ldm_reg_value(self, network_id, register, value, expect_response = True):
        ret_val = self.LDMCmd(network_id, 'W%04X(%02X%04X)' % (register, 8, value), expect_response)
        if expect_response:
            ret_val = ret_val.replace('(', '').replace(')', '')
            if ret_val != 'ACK':
                raise DisplayRegisterException('Error reading display register %d (%s)' % (register, ret_val))

    def get_ldm_reg_value(self, network_id, register):
        ret_val = self.LDMCmd(network_id, 'R%04X(%02X)' % (register, 8), True)
        ret_val = ret_val.replace('(', '').replace(')', '')
        if len(set(ret_val.lower()) - set('0123456789abcdef')) != 0:
            raise DisplayRegisterException('Error reading display register %d (%s)' % (register, ret_val))
        return int(ret_val, 16)

    def get_ldm_reg_value(self, network_id, register):
        ret_val = self.LDMCmd(network_id, 'R%04X(%02X)' % (register, 8), True)
        ret_val = ret_val.replace('(', '').replace(')', '')
        if len(set(ret_val.lower()) - set('0123456789abcdef')) != 0:
            raise DisplayRegisterException('Error reading display register %d (%s)' % (register, ret_val))
        return int(ret_val, 16)

    def InitiateBulkWriteData(self, network_id, data_type, first_block_index, number_blocks):
        trans_id = random.getrandbits(16)
        request = usbutils.pack_request(trans_id, network_id, usbutils.REQUEST_WRITE_BULK_DATA, data_type, [first_block_index, number_blocks])
        self.device.message_send(request, 0)
        response = self.device.message_recv_num(1)

    def BuildDataBlock(self, network_id, data_type, current_block_num, data):
        trans_id = random.getrandbits(16)
        header = struct.pack('< HQ H H BB H', 0, 0, trans_id, network_id, usbutils.REQUEST_WRITE_BULK_DATA, data_type, current_block_num)
        bulk_data = struct.pack(('<%dB' % len(data)), *[ c for c in data ])
        buffer = header + bulk_data
        return buffer

    def SendBulkSingleBlock(self, final_block, block_to_send):
        for i in range(0, len(block_to_send), 62):
            final_packet = 1 if final_block and i + 62 >= len(block_to_send) else 0
            self.device.message_send(block_to_send[i:i + 62], final_packet)

    def SendBulkDataBlocks(self, network_id, data_type, first_block_index, number_blocks, data_to_write, observer_func = None):
        for i in range(0, number_blocks):
            current_block_num = i + first_block_index
            data = data_to_write[i * 256:(i + 1) * 256]
            next_block = self.BuildDataBlock(network_id, data_type, current_block_num, data)
            final_block = 1 if (i + 1) * 256 >= len(data_to_write) else 0
            self.SendBulkSingleBlock(final_block, next_block)
            response = self.device.message_recv_num(1)
            if observer_func is not None:
                observer_func(i, number_blocks)

        return

    def BulkWriteData(self, network_id, data_type, first_block_index, number_blocks, data_to_write, observer_func = None):
        self.InitiateBulkWriteData(network_id, data_type, first_block_index, number_blocks)
        self.SendBulkDataBlocks(network_id, data_type, first_block_index, number_blocks, data_to_write, observer_func)