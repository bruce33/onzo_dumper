# Embedded file name: client\defaults.pyo
import sys
import os
import os.path
import UserDict
import logging
import shutil
from wx import StandardPaths
log = logging.getLogger(os.path.basename('defaults'))
from client.onzo_platform import *

class Defaults(UserDict.UserDict):
    must_specify = ['server_url', 'device_name']

    def __init__(self):
        UserDict.UserDict.__init__(self)
        self['server_url'] = 'http://release-be.sse.onzo.co.uk:9000/jsonrpc/'
        self['brand_id'] = 'default'
        self['website_help_url'] = 'http://www.onzo.co.uk/'
        self['device_help_url'] = 'http://www.onzo.co.uk/'
        self['protocol_version'] = '0.04'
        self['device_name'] = 'Onzo'
        if MAC:
            import plistlib
            try:
                config_file = self.get_mac_config_file()
                log.debug('Using config %s file.' % config_file)
                plist = plistlib.readPlist(config_file)
                for key in self.keys():
                    if plist.has_key(key):
                        self[key] = plist[key]
                        log.debug('Config: %s = %s.' % (key, plist[key]))
                    elif key in self.must_specify:
                        log.error('Field %s, must be specified, but not in file %s' % (key, config_file))

            except IOError:
                log.error('Unable to locate the plist file - %s.' % config_file)

        else:
            for key in self.keys():
                log.debug('Config: %s = %s.' % (key, self[key]))

    @classmethod
    def MacWrite(self, key, val):
        if not MAC:
            raise IOError('Writing to plist on non mac (%s)' % sys.platform)
        else:
            import plistlib
            config_file = self.get_mac_config_file()
            log.debug('Using config %s file.' % config_file)
            plist = plistlib.readPlist(config_file)
            plist[key] = val
            plistlib.writePlist(plist, config_file)

    @classmethod
    def get_pref_directory(self):
        dir_pref = StandardPaths.Get().GetUserConfigDir()
        return dir_pref

    @classmethod
    def get_mac_config_file(self):
        if os.environ.has_key('ONZOPLISTFILE'):
            log.info('Using ONZOPLISTFILE config: %s' % config_file)
            config_file = os.environ['ONZOPLISTFILE']
            return config_file
        config_pref_file = os.path.join(self.get_pref_directory(), 'com.onzo.defaults.plist')
        if os.path.isfile(config_pref_file):
            log.info('Using config file: %s' % config_pref_file)
            return config_pref_file
        if os.environ.has_key('_MEIPASS2'):
            config_file_copy = os.path.join(os.environ['_MEIPASS2'], 'defaults.plist')
            shutil.copyfile(config_file_copy, config_pref_file)
            log.info('Copied default config file %s to %s' % (config_file_copy, config_pref_file))
            return config_pref_file
        elif os.path.isfile(os.path.join(os.getcwd(), 'defaults.plist')):
            config_file_copy = os.path.join(os.getcwd(), 'defaults.plist')
            shutil.copyfile(config_file_copy, config_pref_file)
            log.info('Copied default config file %s to %s' % (config_file_copy, config_pref_file))
            return config_pref_file
        else:
            raise IOError('Unable to locate configuration')