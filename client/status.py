# Embedded file name: client\status.pyo
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import os
import os.path
import time
import gc
import logging
import threading
import wx
from client import wxutil, upload
from cust_layout import layout
from client import utils, client_version
from client import devicetypes
from time import sleep
from client import internationalisation
log = logging.getLogger(os.path.basename('status'))
WINDOWS = os.name == 'nt'
MAC = sys.platform == 'darwin'
LINUX = sys.platform.startswith('linux')

def get_icon(name):
    return wxutil.MakeIcon(wx.ImageFromStream(utils.resource_stream(__name__, name)))


class StatusController(object):

    def __init__(self, settings, connected_container):
        self._ping_thread = None
        self._settings = settings
        self._dialog = None
        self._connection_status = ''
        self._display_connected = False
        self._display_type = ''
        self._display_fw_version = 0
        self.connected = connected_container
        self.connected_unsubscribe = self.connected.subscribe(self._set_display_status)
        return

    def show_dialog(self, mainwin = None):
        if self._dialog:
            wxutil.wake_up_window(self._dialog)
        else:
            self._dialog = StatusDialog(mainwin, self._settings, on_close=self._on_dialog_close, title=_('About'))
            self._show_connection_status()
            self._dialog.Show(True)
        if self._ping_thread:
            ping_thread = self._ping_thread.isAlive() or PingThread(self._settings)
            ping_thread.on_connection_attempt = lambda : self._set_connection_status(_('Connecting...'))
            ping_thread.on_connection_success = lambda : self._set_connection_status(_('OK'))
            ping_thread.on_connection_failure = lambda error: self._connection_error(error)
            self._ping_thread = ping_thread
            self._ping_thread.start()

    @wxutil.inWxThread
    def _set_connection_status(self, status):
        self._connection_status = status
        self._show_connection_status()

    @wxutil.inWxThread
    def _set_display_status(self, display):
        log.debug('Display state changed: %s' % str(display))
        display_type = display[0]
        display_fw = display[1]
        if len(display_type) == 0:
            self._display_connected = False
            self._display_type = ''
            self._display_fw_version = 0
        else:
            self._display_connected = True
            self._display_type = display_type
            self._display_fw_version = display_fw

    def _connection_error(self, error):
        log.debug('Connection failed with reason: %s' % error)
        self._set_connection_status(_('Failed'))

    def _show_connection_status(self):
        if self._dialog:
            self._dialog.set_connection_status(self._connection_status)
            if self._display_connected:
                fw_version = 'v%d - %d/%d/%d' % (self._display_fw_version,
                 self._display_fw_version & 31,
                 (self._display_fw_version & 480) >> 5,
                 2000 + ((self._display_fw_version & 65024) >> 9))
                display_status = '%s (%s)' % (self._display_type, fw_version)
            else:
                display_status = _('Not connected')
            self._dialog.set_display_status(display_status)

    def destroy_dialog(self):
        if self._dialog:
            self._dialog.Destroy()
        self._dialog = None
        return

    def _on_dialog_close(self):
        self._dialog = None
        return


class StatusDialog(wx.Dialog):

    def __init__(self, parent, settings, on_close = None, **kwargs):
        wx.Dialog.__init__(self, parent=parent, **kwargs)
        self._on_close = on_close
        about = wx.StaticBoxSizer(wx.StaticBox(self, -1, ''), wx.VERTICAL)
        about.Add(wx.StaticText(self, label=settings['device_name'] + ' ' + layout.icon_title + ' v' + client_version.VERSION), flag=wx.ALL, border=7)
        about.Add(wx.StaticText(self, label=_(u'Copyright \xa9 2011 Onzo Ltd. All rights reserved.')), flag=wx.ALL, border=7)
        grid = wx.FlexGridSizer(0, 2, 10, 10)
        grid.AddGrowableCol(1, 1)
        self._connection_field = ConnectionStatus(self)
        self._display_field = ConnectionStatus(self)
        self.SetIcon(get_icon('window_icon.png'))
        fields = [(_('Server connection'), self._connection_field), (_('Display connection'), self._display_field)]
        for name, control in fields:
            grid.Add(wx.StaticText(self, label=name + ':'), flag=wx.ALIGN_LEFT)
            grid.Add(control, flag=wx.GROW | wx.ALIGN_LEFT)

        btn = wx.Button(self, wx.ID_OK)
        btn.Bind(wx.EVT_BUTTON, self._on_ok_button)
        self.Bind(wx.EVT_CLOSE, self._on_close_window)
        btn.SetDefault()
        bsizer = wx.StdDialogButtonSizer()
        bsizer.AddButton(btn)
        bsizer.Realize()
        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(about, flag=wx.GROW | wx.TOP | wx.LEFT | wx.RIGHT, border=10)
        vsizer.Add(grid, flag=wx.GROW | wx.ALL, border=10)
        vsizer.Add(bsizer, flag=wx.GROW | wx.ALL, border=10)
        self.SetSizer(vsizer)
        vsizer.Fit(self)

    def set_connection_status(self, status):
        self._connection_field.SetLabel(status)

    def set_display_status(self, status):
        self._display_field.SetLabel(status)

    def _on_close_window(self, event):
        self._on_ok_button(None)
        wx.CallAfter(gc.collect)
        return

    def _on_ok_button(self, event):
        if self._on_close:
            self._on_close()
        self.Destroy()


class ConnectionStatus(wx.StaticText):

    def __init__(self, parent):
        wx.StaticText.__init__(self, parent, style=wx.ST_NO_AUTORESIZE)
        self.SetMinSize((200, self.GetSizeTuple()[1]))


class PingThread(threading.Thread):

    def __init__(self, settings):
        threading.Thread.__init__(self)
        self._settings = settings
        null_func = lambda *a: False
        self.on_connection_attempt = null_func
        self.on_connection_success = null_func
        self.on_connection_failure = null_func

    def run(self):
        log.debug('PingThread started: %s' % self)
        self._ping_server()
        log.debug('PingThread finished: %s' % self)

    def _ping_server(self):
        self.on_connection_attempt()
        ok, message = upload.test_connection(self._settings)
        if ok:
            self.on_connection_success()
        else:
            self.on_connection_failure(message)


class SafeContainer(object):

    def __init__(self, default = None, observer = None):
        self.c = [default]
        self.observers = []
        if observer:
            self.subscribe(observer)

    def subscribe(self, observer):
        if observer not in self.observers:
            self.observers.append(observer)
        return lambda : self.unsubscribe(observer)

    def unsubscribe(self, observer):
        if observer in self.observers:
            self.observers.remove(observer)

    def get(self):
        return self.c[0]

    def set(self, value):
        return self.put(value)

    def put(self, value):
        different = self.c[0] != value
        self.c[0] = value
        if different:
            for observer in self.observers[:]:
                observer(value)

        return self.c[0]

    def __nonzero__(self):
        if self.c[0]:
            return True
        return False


class ApplicationUpgrade(object):
    UPGRADE_FAILED_DELAY = 86400
    UPGRADE_CHECK_DELAY = 30.0

    def __init__(self, settings):
        self._settings = settings
        self.proxy = None
        self.server_url = None
        self.next_check = None
        self.disable_message_box = False
        return

    def get_version_proxy(self):
        server_url = self._settings['server_url']
        if self.server_url and self.server_url == server_url:
            return self.proxy
        self.proxy = upload.upload_service_proxy(server_url)
        self.server_url = server_url
        return self.proxy

    def _check(self):
        result = upload.check_version(self.get_version_proxy(), self._settings)
        url = result.get('download_url', None)
        if not url:
            return True
        if not result.get('download_md5', None):
            checksum = None
            try:
                filename = upload.download_file(url, checksum, _('Please wait - downloading update'))
            except upload.DownloadException, e:
                log.info('download of %r/%r failed %r' % (url, checksum, e))
                return False

            if self.disable_message_box:
                do_update = True
                self.disable_message_box = False
            else:
                message = result.get('message', None) or _('A new version of %(appname)s is available.\nWould you like to upgrade now?\n\ncurrent version=%(currentversion)s  available version=%(availableversion)s') % {'appname': self._settings['device_name'] + ' ' + layout.icon_title,
                 'currentversion': upload.CLIENT_VERSION,
                 'availableversion': result.get('version', _('unknown'))}
                title_message = result.get('titlemessage', _('update found!'))
                wx.Yield()
                sleep(0.5)
                do_update = utils.onzo_confirmation(message, title=self._settings['device_name'] + ' ' + layout.icon_title + ' ' + title_message, affirmative=_('Download and Install'), negative=_('Remind me later'))
            log.info('do_update %r' % (do_update,))
            if do_update:
                WINDOWS and self.update_windows(filename)
            elif MAC:
                self.update_mac(filename)
            return False
        return False

    def update_windows(self, filename):
        systemroot = os.getenv('SYSTEMROOT', 'c:\\windows')
        utils.run_cmd_and_exit(os.path.join(systemroot, 'system32', 'msiexec.exe'), ' /i "%s"' % (filename,))
        utils.message_box(_('Failed to update the %s.\nWill automatically try again later.') % (self._settings['device_name'] + ' ' + layout.icon_title), _('Update failed!'))

    def update_mac(self, dmg_path):
        import subprocess
        script_path = '/bin/bash "%s"' % os.path.join(os.path.dirname(sys.argv[0]), 'upgrademac.sh')
        app_path = '"%s"' % os.path.abspath(os.path.dirname(sys.argv[0]) + '/../..')
        log.debug('Calling upgrade: %s %s %s' % (script_path, app_path, dmg_path))
        status = subprocess.call(' '.join([script_path, app_path, dmg_path]), shell=True)
        if status:
            utils.message_box(_('Failed to update the %s.\nWill automatically try again later.') % (self._settings['device_name'] + ' ' + layout.icon_title), _('Update failed!'))
        else:
            relaunch_path = '/bin/bash "%s"' % os.path.join(os.path.dirname(sys.argv[0]), 'relaunchmac.sh')
            utils.run_cmd_and_exit(' '.join([relaunch_path, app_path]), '', shell=True)

    def check(self):
        now = time.time()
        if self.next_check > now:
            return
        if self._check() is False:
            self.next_check = now + self.UPGRADE_FAILED_DELAY
        else:
            self.next_check = now + self.UPGRADE_CHECK_DELAY

    def force_download(self):
        self.next_check = None
        self.disable_message_box = True
        return


class NetworkStatusThread(threading.Thread):
    NETWORK_OK_DELAY = 30.0
    NETWORK_FAIL_DELAY = 2.5
    container = None
    _settings = None
    cross = (None, layout.server_cross_text)
    tick = (True, layout.server_tick_text)

    def __init__(self, status_container, settings, application_upgrade):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.container = status_container
        self.container.put(self.cross)
        self._settings = settings
        self._settings.attach(self.check)
        self.application_upgrade = application_upgrade

    def check(self, settings = None):
        ok, message = upload.test_connection(self._settings)
        if ok:
            self.container.put(self.tick)
            log.debug('Server %s is ready.' % self._settings['server_url'])
        else:
            self.container.put(self.cross)
            log.debug('Server %s is not responding.' % self._settings['server_url'])
        return ok

    def run(self):
        log.debug('NetworkStatusThread started: %s' % self)
        while True:
            ok = self.check()
            if ok:
                self.application_upgrade.check()
                time.sleep(self.NETWORK_OK_DELAY)
            else:
                time.sleep(self.NETWORK_FAIL_DELAY)


class DeviceStatusThread(threading.Thread):
    DEVICE_OK_DELAY = 240.0
    DEVICE_FAIL_DELAY = 2.5
    container = None
    _device = None
    cross = (None, layout.device_cross_text)
    bl = (False, layout.device_tick_text)
    ticks = dict()
    tick_mock = (True, 'The display is emulated')

    def __init__(self, status_container, connected_container, device):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.container = status_container
        self.connected = connected_container
        self.container.put(self.cross)
        self._device = device
        for displays in devicetypes.device_types:
            self.ticks[displays] = (True, layout.devices_tick_text[displays])

    def attempt_connect(self):
        for vendor in devicetypes.vendor_ids:
            pairs = []
            for device in devicetypes.device_types:
                pairs.extend([ (x[0], x[1], device) for x in devicetypes.device_types[device] if x[0] == vendor ])

            for pair in pairs:
                try:
                    self._device.connect(pair[0], pair[1])
                except IOError, e:
                    continue
                else:
                    return pair

        return None

    def run(self):
        log.debug('DeviceStatusThread started: %s' % self)
        while True:
            if self._device.bootloadermode or self._device.updating_firmware:
                self.container.put(self.bl)
                time.sleep(self.DEVICE_OK_DELAY)
                self.connected.put(('', 0))
                continue
            detection = self.attempt_connect()
            if detection is None:
                self.container.put(self.cross)
                self.connected.put(('', 0))
                time.sleep(self.DEVICE_FAIL_DELAY)
            else:
                if not self._device.is_real():
                    self.container.put(self.tick_mock)
                else:
                    if self.connected.get() is None or self.connected.get()[0] != detection[2]:
                        fw = self._device.GetRegister(2, 45)
                        self.connected.put((detection[2], fw))
                        log.debug('Found FW version %d' % fw)
                    self.container.put(self.ticks[detection[2]])
                    return False # stop thread because it messes with dumping data
                time.sleep(self.DEVICE_OK_DELAY)

        return