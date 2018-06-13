# Embedded file name: client\blockformats.pyo
import struct
import logging
log = logging.getLogger(__name__)

def unpack_from(format, data, offset):
    s = struct.calcsize(format)
    return struct.unpack(format, data[offset:offset + s])


class DataFormat(object):

    def __init__(self, type, size, CURRENT, OFFSET, START, **kwargs):
        self.type = type
        self.size = size
        self.CURRENT = CURRENT
        self.OFFSET = OFFSET
        self.START = START
        for kw, value in kwargs.iteritems():
            setattr(self, kw, value)

        self.ffff_values = 0

    def decode(self, raw_data, block_index = None, **kw):
        count = (len(raw_data) - self.header_size) / self.sample_size
        loSamples = [ unpack_from(self.sample_format, raw_data, self.header_size + self.sample_size * i) for i in xrange(count) ]
        if len(raw_data) >= self.header_size:
            header_values = unpack_from(self.header_format, raw_data, 0)
        else:
            log.debug('Block %i has no data!' % (block_index,))
            return []
        headers = dict(zip(self.header_fields, header_values))
        self.ffff_values = 0
        samples = self._decode(headers, loSamples, block_index=block_index, **kw)
        if self.ffff_values:
            log.debug('0xFFFF data spotted in %i samples' % self.ffff_values)
        return samples

    def _decode(self, headers, loSamples, **kw):
        raise NotImplemented

    def fix_cur_registers(self, start_block, cur_block, cur_offset):
        if start_block > self.size:
            log.error('stream#%s: start_block fixed %i -> 0x0' % (self.type, start_block))
            start_block = 0
        if cur_offset > 256:
            log.error('stream#%s: cur_offset fixed %i -> 0x0' % (self.type, cur_offset))
            cur_offset = 256
        if cur_block >= self.size:
            log.error('stream#%s: cur_block fixed %i -> 0x0' % (self.type, cur_block))
            cur_block = 0
        return (start_block, cur_block, cur_offset)


class RealPower_091002(DataFormat):
    header_size = 8
    sample_size = 4
    sample_format = '<HH'
    header_format = '<II'
    header_fields = ['timestamp', 'ear']
    flip_threshold = 30000

    def _decode(self, headers, loSamples, block_index = None, last_timestamp = None, last_value = None):
        timestamp = headers['timestamp']
        if timestamp == 4294967295:
            if last_timestamp is None:
                log.error('Bug #???: Block %i has no valid headers. Ignoring.' % (block_index,))
                return []
            log.error('Bug #167: Block %i has broken headers' % (block_index,))
            timestamp = last_timestamp
        hiTime = timestamp >> 16
        prev_loTime = timestamp & 65535
        prev_timestamp = timestamp
        samples = []
        for index, (curr_loTime, curr_value) in enumerate(loSamples):
            if curr_loTime == 65535 and curr_value in (-1, 65535):
                self.ffff_values += 1
                continue
            elif abs(curr_value) > 28672:
                log.debug('Sample %r[%r]: bad data (%i,%i)' % (block_index,
                 index,
                 curr_loTime,
                 curr_value))
                continue
            if curr_loTime < prev_loTime:
                hiTime += 1
            curr_timestamp = (hiTime << 16) + curr_loTime
            if prev_timestamp and abs(curr_timestamp - prev_timestamp) > self.flip_threshold:
                log.debug('Sample %r[%r]: too long interval %i -> %i,%i' % (block_index,
                 index,
                 prev_timestamp,
                 curr_timestamp,
                 curr_value))
            samples.append((curr_timestamp, curr_value))
            prev_timestamp = curr_timestamp
            prev_loTime = curr_loTime

        return samples


class ReactivePower_091002(RealPower_091002):
    sample_format = '<Hh'


class Energy_091002(DataFormat):
    header_size = 8
    sample_size = 2
    sample_format = '<H'
    header_format = '<II'
    header_fields = ['timestamp', 'ear']

    def _decode(self, headers, loSamples, block_index = None, last_timestamp = None, last_value = None):
        shift = 16
        i = self.multiplier
        while i > 1:
            shift += 1
            i /= 2

        timestamp = headers['timestamp']
        if timestamp == 4294967295:
            if last_timestamp is None:
                log.error('Bug #???: Block %r has no valid headers. Ignoring.' % block_index)
                return []
            log.debug('Bug #167: Block %r has broken timestamp' % block_index)
            timestamp = last_timestamp + self.interval
        if (timestamp - self.offset) % self.interval != 0:
            timestamp = (timestamp - self.offset + self.interval / 2) // self.interval * self.interval + self.offset
        hiValue = headers['ear'] >> shift
        prev_loValue = 0
        if hiValue == 65535:
            if last_timestamp is None:
                log.error('Bug #???: Block %r has no valid headers. Ignoring.' % block_index)
                return []
            log.debug('Bug #167: Block %r has broken EAR' % block_index)
            hiValue = last_value >> shift
            prev_loValue = last_value & 65535
        samples = []
        prev_value = None
        for index, (curr_loValue,) in enumerate(loSamples):
            if curr_loValue == 65535:
                self.ffff_values += 1
                curr_value = prev_value
            else:
                if curr_loValue < prev_loValue:
                    hiValue += 1
                curr_value = (hiValue << shift) + curr_loValue * self.multiplier
                prev_value = curr_value
                prev_loValue = curr_loValue
            if curr_value is not None:
                samples.append((timestamp, curr_value))
            timestamp += self.interval

        return samples


class RealPower_1_01(DataFormat):
    _version_number = 1.01
    _version_name = 'Real power data format as for 2009-02-13'
    header_size = 8
    sample_size = 4
    sample_format = '>HH'
    header_format = '<HHBBH'
    header_fields = ['hiStart',
     'hiEnd',
     'status',
     'entries',
     'reserved']
    flip_threshold = 30000

    def fix_cur_registers(self, start_block, cur_block, cur_offset):
        start_block, cur_block, cur_offset = DataFormat.fix_cur_registers(self, start_block, cur_block, cur_offset)
        if start_block == 65535 or start_block % self.size != 0:
            log.error('stream#%s: start_block fixed %i -> 0x0' % (self.type, start_block))
            start_block = 0
        return (start_block, cur_block, cur_offset)

    def _decode(self, headers, loSamples, block_index = None, last_timestamp = None, last_value = None):
        hiTime = headers['hiStart']
        if hiTime == 65535:
            if not last_timestamp:
                hiTime = 0 >> 16
            samples = []
            prev_loTime = 0
            prev_timestamp = None
            for index, (curr_loTime, curr_value) in enumerate(loSamples):
                if curr_loTime == 65535 or curr_value in (-1, 65535):
                    self.ffff_values += 1
                    continue
                elif abs(curr_value) > 28672:
                    log.debug('Sample %r[%r]: bad data (%i,%i)' % (block_index,
                     index,
                     curr_loTime,
                     curr_value))
                    continue
                if curr_loTime < prev_loTime:
                    hiTime += 1
                curr_timestamp = (hiTime << 16) + curr_loTime
                prev_loTime = curr_loTime
                if prev_timestamp and abs(curr_timestamp - prev_timestamp) > self.flip_threshold:
                    log.debug('Sample %r[%r]: too long interval %i -> %i,%i' % (block_index,
                     index,
                     prev_timestamp,
                     curr_timestamp,
                     curr_value))
                samples.append((curr_timestamp, curr_value))
                prev_timestamp = curr_timestamp

            headers['hiEnd'] not in [None, 65535, hiTime] and log.debug('Block %r hiEnd missed. should be 0x%04x, is 0x%04x' % (block_index, headers['hiEnd'], hiTime))
        return samples


class ReactivePower_1_01(RealPower_1_01):
    _version_number = 1.01
    _version_name = 'Reactive power data format as for 2009-02-13'
    sample_format = '>Hh'


class Energy_1(DataFormat):
    _version_number = 1.069
    _version_name = 'Totally broken format from current hardware 2009-02-13'
    header_size = 12
    sample_size = 2
    sample_format = '<H'
    header_format = '<IHHBBH'
    header_fields = ['timestamp',
     'hiStart',
     'hiEnd',
     'status',
     'entries',
     'interval']

    def fix_cur_registers(self, start_block, cur_block, cur_offset):
        start_block, cur_block, cur_offset = DataFormat.fix_cur_registers(self, start_block, cur_block, cur_offset)
        if start_block == 65535 or start_block % self.size != 0:
            log.error('stream#%s: start_block fixed %i -> 0x0' % (self.type, start_block))
            start_block = 0
        return (start_block, cur_block, cur_offset)

    def _decode(self, headers, loSamples, block_index = None, last_timestamp = None, last_value = None):
        timestamp = block_index * (256 - self.header_size) / self.sample_size * self.interval + self.offset
        prev_value = None
        prev_loValue = 0
        hiValue = headers['hiStart']
        if hiValue == 65535:
            log.debug('Bug #167: Block %r has broken EAR' % block_index)
            if last_value is not None:
                prev_value = last_value
                hiValue = last_value >> 16
                prev_loValue = last_value & 65535
            elif block_index == 0:
                log.debug('Bug #167: Broken headers in first block')
                hiValue = 0
            else:
                self.ffff_values = len(loSamples)
                return []
        samples = []
        for index, (curr_loValue,) in enumerate(loSamples):
            if curr_loValue == 65535:
                self.ffff_values += 1
                curr_value = prev_value
            elif index == len(loSamples) - 1 and curr_loValue & 255 == 0:
                log.debug('Sample %r: bad data (%i)' % (index, curr_loValue))
            else:
                if curr_loValue < prev_loValue:
                    hiValue += 1
                curr_value = (hiValue << 16) + curr_loValue
                prev_value = curr_value
                prev_loValue = curr_loValue
            if curr_value is not None:
                samples.append((timestamp, curr_value))
            timestamp += self.interval

        if headers['hiEnd'] not in [None, 65535, hiValue]:
            log.debug('hiEnd missed. should be 0x%04x, is 0x%04x' % (headers['hiEnd'], hiValue))
        return samples


class Energy_1_069(Energy_1):
    _version_number = 1.069
    _version_name = 'Totally broken format from current hardware 2009-02-13'
    sample_format = '>H'