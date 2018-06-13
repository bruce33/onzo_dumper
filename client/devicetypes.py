# Embedded file name: client\devicetypes.pyo
OLD_VENDOR_ID = 1240
NEW_VENDOR_ID = 9290
vendor_ids = [OLD_VENDOR_ID, NEW_VENDOR_ID]
default_product_id = 63

class displays(object):
    SEK = 'SEK'
    ZIGBEE = 'ZIGBEE'


device_types = {displays.SEK: [(OLD_VENDOR_ID, 63), (NEW_VENDOR_ID, 1)],
 displays.ZIGBEE: [(NEW_VENDOR_ID, 2)]}