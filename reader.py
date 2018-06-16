# Embedded file name: devicetool.pyo
import csv
import datetime
import logging
import optparse
import os
import random
import sys
import time

from client import blockformats
from client import usbutils as usbprotocol
import usb
from client import device

log = logging.getLogger (os.path.basename('devicetool'))




'''udev rules need to be set in /etc/udev/rules.d'''

def detach(dev, interface=0):
    '''Detach the interface'''
    if dev.is_kernel_driver_active(interface):
        print "Detaching kernel driver for interface %d" % (interface)
        dev.detach_kernel_driver(interface)

def attach(dev, interface=0):
    if not dev.is_kernel_driver_active(interface):
        print "Attaching kernel driver for interface %d" % (interface)
        dev.attach_kernel_driver(interface)

def unclaim(dev, interface=0):
    print "Unclaiming interface %d " % (interface)
    usb.util.release_interface(dev, interface)

def claim(dev, interface=0):
    '''Claiming interface'''
    usb.util.claim_interface(dev, interface)


def main(args):
    FORMAT_CONS = '%(asctime)s %(name)-12s %(levelname)8s\t%(message)s'
    logfilename = os.path.normpath(os.path.expanduser('devicetool.log'))
    logging.basicConfig(level=logging.DEBUG, format=FORMAT_CONS, filename=logfilename, filemode='a')
    usage = 'usage: %prog [options] [arguments]'
    desc = 'usblibrary - basic tests for USB Communication Dll'
    parser = optparse.OptionParser(usage, description=desc)
    parser.add_option('--firmware', action='store', dest='firmware', help='upgrade firmware (device must be in bootloader mode)')
    parser.add_option('--test', action='store_true', dest='testsuite', help='run full test suite')
    parser.add_option('--retrieve', action='store_true', dest='testretrieve', help='continously retrieve data')
    parser.add_option('--bug165', action='store_true', dest='bug165', help='test bug165')
    parser.add_option('--bug169', action='store_true', dest='bug169', help='test bug169')
    parser.add_option('--bug168', action='store_true', dest='bug168', help='test bug168')
    parser.add_option('--humanDate', action='store_true', dest='humanDate', help='Print date in human format rather than Unix time')
    parser.add_option('--unitNumber', action='store', dest='unitNumber', help='Specify a unit number (starting at 0)', type='int')
    parser.add_option('--debug', action='store_true', dest='debug', help='Print debug information')
    parser.add_option('--blocktransfer', action='store', dest='blocktransfer', help='Receive all used blocks for specified data_type')
    parser.add_option('-r', '--request', action='store', dest='request', default='0x01', help='register_id (default is %default)')
    parser.add_option('-d', '--data_type', action='store', dest='data_type', default='0x01', help='register_id or data_type (default is %default)')
    parser.add_option('-n', '--network', action='store', dest='network', default='0x02', help='network_id (default is %default)')
    parser.add_option('-t', '--transaction', action='store', dest='transaction', default='0xDEAD', help='network_id (default is %default)')
    options, left_args = parser.parse_args(args=args)
    if options.firmware:
        firmwareupdate(options.firmware)
        sys.exit(0)
    if options.testsuite:
        testsuite()
        sys.exit(0)
    if options.testretrieve:
        get_register, get_block_request = preparedevice(debug=options.debug, unitNumber=options.unitNumber)
        testretrieve(get_register, get_block_request)
        sys.exit(0)
    if options.blocktransfer:
        d, get_register, get_block_request = preparedevice(debug=options.debug, unitNumber=options.unitNumber)
        blocktransfer(int(options.blocktransfer), get_register, get_block_request, humanDate=options.humanDate)
        d.disconnect()
        sys.exit(0)
    for condition, foo in zip((options.bug165, options.bug169, options.bug168), (bug165, bug169, bug168)):
        if condition:
            logging.getLogger('device').setLevel(logging.ERROR)
            get_register, get_block_request = preparedevice(debug=options.debug, unitNumber=options.unitNumber)
            foo(get_register, get_block_request)
            sys.exit(0)

    d = device.Device(debug=options.debug, unitNumber=options.unitNumber)
    d.connect()

    def p(s):
        if s.startswith('0x'):
            return int(s, 16)
        return int(s)

    req = usbprotocol.pack_reqest(p(options.transaction), p(options.network), p(options.request), p(options.data_type), map(p, left_args))
    d.message_send(req)
    while True:
        res = d.message_recv()
        print ('\nRECEIVED MESSAGE: len=%r %r' % (len(res), res))
        usbprotocol.pprint_response(res)


def firmwareupdate(hex_file):
    d = device.Device(firmwareupdate=True)
    log.info(' [*] starting firmware update %r' % (hex_file,))

    def foo(i):
        log.info('progress... %.3f' % (i,))

    d.update_firmware(hex_file, progress_callback=foo)
    log.info(' [*] finished firmware update')


def testretrieve(get_register, get_block_request):
    l = open('log.txt', 'a')
    log.info(' [*] retrieving data')
    try:
        while True:
            ts = datetime.datetime.now().isoformat()
            time.sleep(1)
            cur_block = get_register(2, 88)
            time.sleep(1)
            cur_offset = get_register(2, 95)
            time.sleep(1)
            start_block = get_register(2, 102)
            time.sleep(1)
            blocks = []
            if cur_block < 20:
                for i in range(cur_block + 1):
                    blocks.append(get_block_request(2, 1, i))

            time.sleep(1)
            time.sleep(1)
            ear_low = get_register(1, 16)
            time.sleep(5)
            ear_high = get_register(1, 17)
            ear = ear_high * 65536 + ear_low
            s = 'ear=%r start_block=%r cur_block=%r cur_offset=%r block=%r' % (ear,
             start_block,
             cur_block,
             cur_offset,
             blocks)
            l.write(ts + ':  ' + s + '\n')
            l.flush()
            log.info(s)
            time.sleep(25)

    except KeyboardInterrupt:
        pass

    l.close()
    log.info(' [*] retrieving data finished')


def blocktransfer(data_type, get_register, get_block_request, humanDate=False):
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
    print ('# Firmware: display=%i (0x%x) clamp=%i (0x%x)' % (display_firmware,
     display_firmware,
     clamp_firmware,
     clamp_firmware))
    print ('# Timestamp: display=%i (0x%x) clamp=%i (0x%x)' % (display_timestamp,
     display_timestamp,
     clamp_timestamp,
     clamp_timestamp))
    print ('# Clamp ear: %i (0x%x)' % (clamp_ear, clamp_ear))
    epoch = int(time.time() - clamp_timestamp) #fixup for the retarded timestamp on the clamp
    print ('calculated epoch=%i' % epoch)
    curr_time = int(time.time())
    print ('current time=%i' % curr_time)
    cur_block = get_register(2, 87 + data_type)
    cur_offset = get_register(2, 94 + data_type)
    start_block = get_register(2, 101+ data_type)
    print ('cur_block=%i # get_register(%i)' % (cur_block, 87 + data_type))
    print ('cur_offset=%i # get_register(%i)' % (cur_offset, 94 + data_type))
    print ('start_block=%i # get_register(%i)' % (start_block, 101 + data_type))
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
        if start_block != 0:
            for index in range(start_block,buffsize):
                i, block = get_block_request(2, data_type, index)
                decoded = powerdata.decode(block)
                decoded_length = len(decoded)
                for x in range(decoded_length):
                    sample = list(decoded[x])
                    if humanDate:
                        sample[0] = datetime.datetime.fromtimestamp(float(sample[0]+epoch)) # use this for human readable timestamp
                    else:
                        sample[0] = sample[0]+epoch # use this for unix timestamp
                    file_writer.writerow(sample)
        for index in range(cur_block):
            i, block = get_block_request(2, data_type, index)
            decoded = powerdata.decode(block)
            decoded_length = len(decoded)
            for x in range(decoded_length):
                sample = list(decoded[x])
                if humanDate:
                    sample[0] = datetime.datetime.fromtimestamp(float(sample[0]+epoch)) # use this for human readable timestamp
                else:
                    sample[0] = sample[0]+epoch # use this for unix timestamp
                file_writer.writerow(sample)


    log.info(' [*] retrieving data finished')


def bug165(get_register, get_block_request):
    log.info(' [*] #165 retrieving data')
    while True:
        for data_type in [1, 3]:
            cur_block = get_register(2, 87 + data_type)
            cur_offset = get_register(2, 94 + data_type)
            if cur_block == 65535 or cur_offset == 65535:
                log.error('register %i=0x%x   register %i=0x%x' % (87 + data_type,
                 cur_block,
                 94 + data_type,
                 cur_offset))

    log.info(' [*] retrieving data finished')


display = 2
clamp = 1
DISPLAY_FIRMWARE_VERSION = 45
DISPLAY_SERIAL_NUMBER_LOW = 185
DISPLAY_SERIAL_NUMBER_HIGH = 186
DISPLAY_CUR_BLOCK_LOW_ENERGY = 88
DISPLAY_CUR_OFFSET_LOW_ENERGY = 95
DISPLAY_START_BLOCK_LOW_ENERGY = 102
CLAMP_FIRMWARE_VERSION = 1
CLAMP_SERIAL_NUMBER_LOW = 2
CLAMP_SERIAL_NUMBER_HIGH = 3
CLAMP_TIMESTAMP_LOW = 8
CLAMP_TIMESTAMP_HIGH = 9
CLAMP_READING_INTERVAL = 6
CLAMP_EAR_LOW = 16
CLAMP_EAR_HIGH = 17
DISPLAY_CUR_BLOCK_REAL = 90
DISPLAY_CUR_OFFSET_REAL = 97
DISPLAY_START_BLOCK_REAL = 104
commands_a = [(display, DISPLAY_FIRMWARE_VERSION),
 (display, DISPLAY_SERIAL_NUMBER_LOW),
 (display, DISPLAY_SERIAL_NUMBER_HIGH),
 (display, DISPLAY_CUR_BLOCK_LOW_ENERGY),
 (display, DISPLAY_CUR_OFFSET_LOW_ENERGY),
 (display, DISPLAY_START_BLOCK_LOW_ENERGY),
 (clamp, CLAMP_FIRMWARE_VERSION),
 (clamp, CLAMP_SERIAL_NUMBER_LOW),
 (clamp, CLAMP_SERIAL_NUMBER_HIGH),
 (clamp, CLAMP_TIMESTAMP_LOW),
 (clamp, CLAMP_TIMESTAMP_HIGH),
 (clamp, CLAMP_READING_INTERVAL),
 (clamp, CLAMP_EAR_LOW),
 (clamp, CLAMP_EAR_HIGH)]
commands_b = [(display, DISPLAY_CUR_BLOCK_REAL),
 (display, DISPLAY_CUR_OFFSET_REAL),
 (display, DISPLAY_START_BLOCK_REAL),
 (clamp, CLAMP_TIMESTAMP_LOW),
 (clamp, CLAMP_TIMESTAMP_HIGH)]

def bug169(get_register, get_block_request):
    log.info(' [*] #169 retrieving data')
    while True:
        for x, data_type in [(commands_a, 1), (commands_b, 3)]:
            cur_block = get_register(2, 87 + data_type)
            start_block = get_register(2, 101 + data_type)
            for n, r in x:
                _ = get_register(n, r)

            s = 'data_type=%i' % (data_type,)
            s += '  cur_block=%i # get_register(%i)' % (cur_block, 87 + data_type)
            s += '  start_block=%i # get_register(%i)' % (start_block, 101 + data_type)
            log.info(s)
            if cur_block < 250:
                for index in range(cur_block + 1):
                    i, block = get_block_request(2, data_type, index)
                    if len(block) != 256:
                        log.critical('data_type:%i block_number=%i block_length=%i' % (data_type, index, len(block)))

            else:
                log.error('data_type:%r cur_block: %r' % (data_type, cur_block))

    log.info(' [*] retrieving data finished')


import array

def tohex(data):
    return ''.join(map(lambda b: '%02x' % b, array.array('B', data)))


def bug168(get_register, get_block_request):
    log.info(' [*] #168 retrieving data')
    data_type = 1
    cur_block = get_register(2, 87 + data_type)
    cur_offset = get_register(2, 94 + data_type)
    s = 'data_type=%i' % (data_type,)
    s += '  cur_block=%i # get_register(%i)' % (cur_block, 88)
    s += '  cur_offset=%i # get_register(%i)' % (cur_offset, 95)
    log.info(s)
    if cur_block < 250:
        for index in range(cur_block + 1):
            i, block = get_block_request(2, data_type, index)
            if index == cur_block:
                block = block[:cur_offset]
            x = tohex(block)
            if 'ffff' in x[24:]:
                log.info('error in packet %i' % (index,))
                log.info('_%s_%s' % (x[:24], x[24:32]))
                for i in range(32, 512, 32):
                    log.info('  %s' % x[i:i + 32].replace('ffff', '*ffff*'))

    else:
        log.error('data_type:%r cur_block: %r' % (data_type, cur_block))
    log.info(' [*] retrieving data finished')


def preparedevice(debug=False, unitNumber=0):
    d = device.Device(debug = debug, unitNumber = unitNumber)
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

    return (d, get_register, get_block_request)


def testsuite():
    d = device.Device(debug=False)
    d.connect()
    pr = usbprotocol.pack_reqest
    trans_id = random.getrandbits(16)
    tests = [('get register from display', pr(trans_id, 2, usbprotocol.REQUEST_GET_REGISTER, 1, []), [usbprotocol.RESPONSE_GET_REGISTER]),
     ('get register from bad device=0xFF', pr(trans_id, 255, usbprotocol.REQUEST_GET_REGISTER, 1, []), [usbprotocol.RESPONSE_ERROR]),
     ('get register from bad device=0x00', pr(trans_id, 255, usbprotocol.REQUEST_GET_REGISTER, 1, []), [usbprotocol.RESPONSE_ERROR]),
     ('get invalid register=0xFF from display', pr(trans_id, 2, usbprotocol.REQUEST_GET_REGISTER, 255, []), [usbprotocol.RESPONSE_ERROR]),
     ('get invalid register from display', pr(trans_id, 2, usbprotocol.REQUEST_GET_REGISTER, 255, []), [usbprotocol.RESPONSE_ERROR]),
     ('get bulk data, device=0x02, type=0x01', pr(trans_id, 2, usbprotocol.REQUEST_GET_BULK_DATA, 1, [0, 1]), [usbprotocol.RESPONSE_GET_BULK_DATA]),
     ('get bulk data, device=0x02, type=0x02', pr(trans_id, 2, usbprotocol.REQUEST_GET_BULK_DATA, 2, [0, 1]), [usbprotocol.RESPONSE_GET_BULK_DATA]),
     ('get bulk data, device=0x02, type=0x03', pr(trans_id, 2, usbprotocol.REQUEST_GET_BULK_DATA, 3, [0, 1]), [usbprotocol.RESPONSE_GET_BULK_DATA]),
     ('get bulk data, device=0x02, type=0x04', pr(trans_id, 2, usbprotocol.REQUEST_GET_BULK_DATA, 4, [0, 1]), [usbprotocol.RESPONSE_GET_BULK_DATA]),
     ('get bulk data, device=0x02, type=0x05', pr(trans_id, 2, usbprotocol.REQUEST_GET_BULK_DATA, 5, [0, 1]), [usbprotocol.RESPONSE_GET_BULK_DATA])]
#     ('get network list, device=0x00', pr(trans_id, 0, usbprotocol.REQUEST_GET_NETWORK_LIST, 0, []), [usbprotocol.RESPONSE_GET_NETWORK_LIST]),
#     ('get network list, device=0x02', pr(trans_id, 2, usbprotocol.REQUEST_GET_NETWORK_LIST, 0, []), [usbprotocol.RESPONSE_ERROR])]
# Thes two commented out as the device appears to send the response in the wrong order
    for msg, request, response_types in tests:
        d.message_send(request)
        print ('%-40s' % (msg,),)
        for response_type in response_types:
            try:
                response = d.message_recv()
                _, _, got_type, _, params = usbprotocol.unpack_response(response)
            except device.OnzoException:
                got_type = device.OnzoException
                params = None

            if got_type == response_type:
                print (' **OK**        ',)
            else:
                print (' **FAILED!**  (%r is not %r) ' % (got_type, response_type),)
            if params:
                for param in params:
                    if isinstance(param, str):
                        print ('%.10r' % usbprotocol.hexify_string(param),)
                    else:
                        print ('0x%04X' % param,)

            print
            sys.stderr.flush()
            sys.stdout.flush()

    return


if __name__ == '__main__':
    main(sys.argv[1:])