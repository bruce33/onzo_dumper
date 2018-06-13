# Embedded file name: client\usbutils.pyo
import struct
REQUEST_GET_REGISTER = 1
REQUEST_SET_REGISTER = 2
REQUEST_GET_BULK_DATA = 3
REQUEST_GET_NETWORK_LIST = 4
REQUEST_CMD_RESET = 5
REQUEST_WRITE_BULK_DATA = 6
REQUEST_LDM_COMMAND = 160
RESPONSE_GET_REGISTER = 1
RESPONSE_SET_REGISTER = 2
RESPONSE_GET_BULK_DATA = 3
RESPONSE_GET_NETWORK_LIST = 4
RESPONSE_LDM_COMMAND = 160
RESPONSE_ERROR = 240
RESPONSE_END_OF_TRANSFER = 241

class UsbException(Exception):
    pass


pack_request_params = {REQUEST_GET_REGISTER: lambda : '',
 REQUEST_SET_REGISTER: lambda value: struct.pack('< H', value),
 REQUEST_GET_BULK_DATA: lambda block_idx, max_blocks: struct.pack('< H H', block_idx, max_blocks),
 REQUEST_WRITE_BULK_DATA: lambda first_block_index, number_blocks: struct.pack('< H H', first_block_index, number_blocks),
 REQUEST_GET_NETWORK_LIST: lambda : '',
 REQUEST_CMD_RESET: lambda : '',
 REQUEST_LDM_COMMAND: lambda cmd: cmd + '\x00'}

def pack_request(trans_id, net_id, req_type, reg_id, params):
    buf = struct.pack('< HQ H H BB', 0, 0, trans_id, net_id, req_type, reg_id)
    buf += pack_request_params[req_type](*params)
    return buf


unpack_request_params = {REQUEST_GET_REGISTER: lambda payload: None,
 REQUEST_SET_REGISTER: lambda payload: struct.unpack('<H', payload),
 REQUEST_GET_BULK_DATA: lambda payload: struct.unpack('<H H', payload),
 REQUEST_GET_NETWORK_LIST: lambda payload: None,
 REQUEST_LDM_COMMAND: lambda payload: payload.rstrip('\x00')}

def unpack_request(buf):
    header, payload = buf[:16], buf[16:]
    enc_0, enc_1, trans_id, net_id, resp_type, reg_id = struct.unpack('< HQ H H BB', header)
    params = unpack_request_params[resp_type](payload)
    return (trans_id,
     net_id,
     resp_type,
     reg_id,
     params)


pack_reqest = pack_request
unpack_reqest = unpack_request
pack_response_params = {RESPONSE_ERROR: lambda : '',
 RESPONSE_END_OF_TRANSFER: lambda : '',
 RESPONSE_GET_REGISTER: lambda value: struct.pack('< H', value),
 RESPONSE_SET_REGISTER: lambda value: struct.pack('< H', value),
 RESPONSE_GET_BULK_DATA: lambda block_idx, payload: struct.pack('< H', block_idx) + payload,
 RESPONSE_GET_NETWORK_LIST: lambda payload: '\x00\x00' + payload,
 RESPONSE_LDM_COMMAND: lambda payload: payload + '\x00'}

def pack_response(trans_id, net_id, req_type, reg_id, params):
    buf = struct.pack('< HQ H H BB', 0, 0, trans_id, net_id, req_type, reg_id)
    buf += pack_response_params[req_type](*params)
    return buf


unpack_response_payload = {RESPONSE_ERROR: lambda payload: None,
 RESPONSE_END_OF_TRANSFER: lambda payload: None,
 RESPONSE_GET_REGISTER: lambda payload: struct.unpack('<H', payload),
 RESPONSE_SET_REGISTER: lambda payload: struct.unpack('<H', payload),
 RESPONSE_GET_BULK_DATA: lambda payload: (struct.unpack('<H', payload[:2])[0], payload[2:]),
 RESPONSE_GET_NETWORK_LIST: lambda payload: (payload[2:],),
 RESPONSE_LDM_COMMAND: lambda payload: payload.rstrip('\x00')}

def unpack_response(buf):
    header, payload = buf[:16], buf[16:]
    enc_0, enc_1, trans_id, net_id, resp_type, reg_id = struct.unpack('< HQ H H BB', header)
    if resp_type in unpack_response_payload:
        params = unpack_response_payload[resp_type](payload)
        return (trans_id,
         net_id,
         resp_type,
         reg_id,
         params)
    raise UsbException('Fatal usb communication error!' + 'resp_type=0x%x reg_id=0x%x' % (resp_type, reg_id))


hexify_string = lambda s: ''.join([ ' %02X' % ord(c) for c in s ])
response_to_string_dict = {RESPONSE_ERROR: 'error',
 RESPONSE_END_OF_TRANSFER: 'end_of_transfer',
 RESPONSE_GET_REGISTER: 'get_register',
 RESPONSE_SET_REGISTER: 'set_register',
 RESPONSE_GET_BULK_DATA: 'get_bulk_data',
 RESPONSE_GET_NETWORK_LIST: 'get_network_list',
 RESPONSE_LDM_COMMAND: 'ldm_command'}

def response_to_string(resp_id):
    return response_to_string_dict[resp_id]


def pprint_response(msg):
    trans_id, net_id, resp_type, reg_id, params = unpack_response(msg)
    a = ['                  trans_id=0x%04X' % trans_id,
     '                    net_id=0x%04X' % net_id,
     '             req/resp type=%r' % response_to_string(resp_type),
     '     data_type/register_id=0x%02X' % reg_id]
    if params:
        for i, v in enumerate(params):
            if isinstance(v, int) or isinstance(v, long):
                a.append('                    value%1i=0x%04X' % (i, v))
            else:
                a.append('                    value%1i=%r' % (i, v))

    print '\n'.join(a)


def pprint_frame(buf):
    frame_fin, frame_size = struct.unpack('<BB', buf[:2])
    header, payload = buf[2:18], buf[18:]
    enc_0, enc_1, trans_id, net_id, resp_type, reg_id = struct.unpack('< HQ H H BB', header)
    a = ['frame_fin=%02i frame_size=%03i                %r' % (frame_fin, frame_size, hexify_string(buf[:2]))]
    if enc_0 == 0 and enc_1 == 0:
        a += ['    enc_0=0x%04X enc_1=0x%016X  %r' % (enc_0, enc_1, hexify_string(buf[2:12])),
         '    trans_id=0x%04X net_id=0x%04X          %r' % (trans_id, net_id, hexify_string(buf[12:16])),
         '    resp_type=0x%02X reg_id=0x%02X             %r' % (resp_type, reg_id, hexify_string(buf[16:18])),
         '    payload                                %r' % hexify_string(buf[18:frame_size + 2])]
    else:
        a += ['    payload                                %r' % hexify_string(buf[2:frame_size + 2])]
    print '\n'.join(a)


def message_send(buf, frame_send, final_frame = 1):
    msgs = [struct.pack('<BB', final_frame, len(buf)), buf, '\xff' * (62 - len(buf))]
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

    return ''.join(payloads)


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

    return ''.join(payloads)