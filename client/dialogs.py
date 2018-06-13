# Embedded file name: client\dialogs.pyo
import time
import urllib
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import logging
import os
import wx
import struct
log = logging.getLogger(os.path.basename('dialogs'))
MAC = False
if sys.platform == 'darwin':
    MAC = True
try:
    import win32gui, win32con
    WIN32 = True
except:
    WIN32 = False

import wx
import wx.lib.agw.genericmessagedialog as gmd
from client import internationalisation
from cust_layout import layout
from client import wxutil

class OnzoMessage(gmd.GenericMessageDialog):

    def __init__(self, parent, message, caption, affirmative = 'OK', negative = 'Cancel', pos = wx.DefaultPosition, size = layout.dialog_size, style = wx.DEFAULT_DIALOG_STYLE | wx.WANTS_CHARS):
        self._parent = parent
        self._message = message
        self._caption = caption
        self._affirmative = affirmative
        self._negative = negative
        self._pos = pos
        self._size = size
        self._style = style
        wx.Dialog.__init__(self, parent, wx.ID_ANY, caption, pos, size, style)
        topsizer = self._topsizer = wx.BoxSizer(wx.VERTICAL)
        content_sizer = self.MakeContentSizer()
        button_sizer = self.MakeButtonSizer()
        topsizer.Add(content_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        topsizer.Add(button_sizer, 0, wx.CENTRE | wx.ALL, 10)
        self.SetAutoLayout(True)
        self.SetSizer(topsizer)
        topsizer.SetSizeHints(self)
        topsizer.Fit(self)
        size = self.GetSize()
        if size.x < size.y * 3 / 2:
            size.x = size.y * 3 / 2
            self.SetSize(size)
        self.Layout()
        self.Centre(wx.BOTH | wx.CENTER_FRAME)
        from ui import get_icon
        self.SetIcon(get_icon('window_icon.png'))
        self.Bind(wx.EVT_BUTTON, self.OnYes, id=wx.ID_YES)
        self.Bind(wx.EVT_BUTTON, self.OnOk, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnNo, id=wx.ID_NO)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_NAVIGATION_KEY, self.OnNavigation)
        self.SwitchFocus()

    def OnCancel(self, event):
        self.EndModal(wx.ID_NO)

    def MakeContentSizer(self):
        from ui import get_bitmap
        contents = wx.BoxSizer(wx.HORIZONTAL)
        icon = get_bitmap('onzo_logo.png')
        static = wx.StaticBitmap(self, wx.ID_ANY, icon)
        contents.Add(static, 0, wx.ALIGN_CENTER_HORIZONTAL)
        contents.Add(self.CreateTextSizer(self._message), 1, wx.ALIGN_CENTER | wx.LEFT, 10)
        return contents

    def MakeButtonSizer(self):
        bs = gmd.StdDialogButtonSizer()
        yes_button = wx.Button(self, wx.ID_YES, self._affirmative)
        no_button = wx.Button(self, wx.ID_NO, self._negative)
        bs.SetAffirmativeButton(yes_button)
        bs.SetNegativeButton(no_button)
        yes_button.SetDefault()
        yes_button.SetFocus()
        self.SetAffirmativeId(wx.ID_YES)
        bs.Realize()
        return bs


class OnzoProgressDialog(wx.Dialog):

    def __init__(self, parent, title):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title, size=layout.dialog_size, style=wx.STAY_ON_TOP | wx.DEFAULT_DIALOG_STYLE)
        self.topsizer = topsizer = wx.BoxSizer(wx.VERTICAL)
        from ui import get_bitmap
        icon = get_bitmap('onzo_logo.png')
        static_icon = wx.StaticBitmap(self, wx.ID_ANY, icon)
        topsizer.InsertSpacer(0, 20)
        topsizer.Add(static_icon, 0, wx.ALIGN_CENTER_HORIZONTAL)
        self.gauge = wx.Gauge(self, -1, 100, size=(250, 5))
        topsizer.Add(wx.StaticText(self, wx.ID_ANY, self.static_title, style=wx.ALIGN_CENTRE), 2, wx.ALIGN_CENTRE)
        topsizer.Add(self.gauge, 1, wx.ALIGN_CENTRE)
        self.CreateUIElements()
        for text in self.status_texts:
            topsizer.Add(text, 2, wx.ALIGN_CENTRE)

        self.buttonsizer = self.MakeButtons()
        topsizer.Add(self.buttonsizer, 2, wx.ALIGN_CENTRE)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_BUTTON, self.OnOk, id=wx.ID_OK)
        from ui import get_icon
        self.SetIcon(get_icon('window_icon.png'))
        self.SetAutoLayout(True)
        self.SetSizer(self.topsizer)
        self.Layout()

    def ReLayout(self):
        self.topsizer.Layout()

    def CreateUIElements(self):
        raise NotImplementedError()

    def MakeButtons(self):
        raise NotImplementedError()

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnOk(self, event):
        self.EndModal(wx.ID_OK)


class OnzoDownload(OnzoProgressDialog):

    def __init__(self, parent, title, download_url, filename, caption, autostart = True):
        self._download_url = download_url
        self._filename = filename
        self._autostart = autostart
        self.static_title = caption
        OnzoProgressDialog.__init__(self, parent, title)
        from ui import get_icon
        self.SetIcon(get_icon('window_icon.png'))

    def CreateUIElements(self):
        self.estimated = wx.StaticText(self, wx.ID_ANY, '', style=wx.ALIGN_CENTRE)
        if len(self._filename) > 20:
            fname = '...' + self._filename[:20]
        else:
            fname = self._filename
        self.target = wx.StaticText(self, wx.ID_ANY, 'Download to %s' % fname, style=wx.ALIGN_CENTRE)
        self.transfer = wx.StaticText(self, wx.ID_ANY, '', style=wx.ALIGN_CENTRE)
        self.status_texts = [self.estimated, self.target, self.transfer]

    def MakeButtons(self):
        bs = wx.BoxSizer(wx.HORIZONTAL)
        self.upgrade = upgrade = wx.Button(self, wx.ID_OK, _('Upgrade'))
        self.cancel = cancel = wx.Button(self, wx.ID_CANCEL, _('Cancel'))
        upgrade.Disable()
        bs.Add(upgrade, 1)
        bs.Add(cancel, 1)
        return bs

    def ShowModal(self):
        if self._autostart:
            self.CommenceDownloading()
        return wx.Dialog.ShowModal(self)

    def CommenceDownloading(self):
        url_retrieve(self._download_url, self._filename, self.OnDownloadReport, self.OnDownloadComplete)

    def OnDownloadReport(self, progress, remaining, transfer):
        self.gauge.SetValue(progress * 100)
        self.estimated.SetLabel(remaining)
        self.transfer.SetLabel(_('Transfer rate: %d kb / sec') % transfer)
        return True

    def OnDownloadComplete(self):
        self.upgrade.Enable()
        self.gauge.SetValue(100)
        self.estimated.SetLabel(_('Download Complete'))
        self.transfer.SetLabel('')
        wx.PostEvent(self.upgrade, wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.upgrade.GetId()))


class OnzoUpgrade(OnzoProgressDialog):
    stages = {'-1': _('Preparing your %(device_name)s'),
     0: _('Your %(device_name)s firmware is being updated'),
     1: _('Your %(device_name)s firmware is being verified'),
     2: _('Thank you. \nYour %(device_name)s firmware has been \nupdated to %(fw_version)s'),
     3: _('Upgrade failed')}

    def __init__(self, parent, title, device, filename, device_name):
        self.device_name = device_name
        self._device = device
        self._filename = filename
        self._upgrading = False
        self.static_title = _('Upgrading your %s') % device_name
        OnzoProgressDialog.__init__(self, parent, title)
        from ui import get_icon
        self.SetIcon(get_icon('window_icon.png'))
        self.Layout()

    def CreateUIElements(self):
        self.stage = wx.StaticText(self, wx.ID_ANY, self.stages['-1'] % {'device_name': self.device_name}, style=wx.ALIGN_CENTRE)
        self.status_texts = [self.stage]

    def MakeButtons(self):
        bs = wx.BoxSizer(wx.HORIZONTAL)
        self.done = wx.Button(self, wx.ID_OK, _('Done'))
        self.done.Disable()
        bs.Add(self.done, 1)
        return bs

    @wxutil.inWxThread
    def CommenceUpgrade(self, event):
        self.stage.SetLabel(self.stages['-1'] % {'device_name': self.device_name})

        def upgrade_callback(x, y):
            self.OnUpgradeReport(x, y)

        self._upgrading = True
        try:
            self._device.update_firmware(self._filename, upgrade_callback)
            self.gauge.SetValue(100)
            self.done.Enable()
            time.sleep(4)
            fw_value = self._device.GetRegister(2, 45)
            log.debug('After upgrade fw=%d' % fw_value)
            if fw_value > 0:
                fw_version_str = 'v%d - %d/%d/%d' % (fw_value,
                 fw_value & 31,
                 (fw_value & 480) >> 5,
                 2000 + ((fw_value & 65024) >> 9))
            else:
                fw_version_str = 'the latest version'
            self.stage.SetLabel(self.stages[2] % {'device_name': self.device_name,
             'fw_version': fw_version_str})
            self._upgrading = False
        except:
            log.error('An error occured during the upgrade: %s' % sys.exc_info()[0])
            self.stage.SetLabel(self.stages[3])
            self.gauge.SetValue(100)
            self.done.Enable()
            wx.Yield()

    def OnUpgradeReport(self, stage, progress):
        self.ChangeLabel(int(stage))
        self.gauge.SetValue(progress * 100)
        wx.Yield()

    def ChangeLabel(self, stage_num):
        params = {'device_name': self.device_name}
        label = self.stages[int(stage_num)] % params
        if self.stage.GetLabel() != label:
            self.stage.SetLabel(label)
            self.Refresh()
            self.Update()
            self.ReLayout()
            wx.Yield()

    def OnCancel(self, event):
        if self._upgrading:
            return False
        OnzoProgressDialog.OnCancel(self, event)

    def OnOk(self, event):
        OnzoProgressDialog.OnOk(self, event)


class BalloonTaskBarIcon(wx.TaskBarIcon):

    def __init__(self):
        wx.TaskBarIcon.__init__(self)
        self.icon = None
        self.tooltip = ''
        return

    @wxutil.inWxThread
    def ShowBalloon(self, title, text, msec = 0, flags = 0):
        if WIN32 and self.IsIconInstalled():
            try:
                self.display_balloon(title, text, msec)
            except Exception, e:
                print e

    def display_balloon(self, title, text, ms_timeout):

        class PyNOTIFYICONDATA:
            _struct_format = 'IIIIII128sII256sI64sI'
            _struct = struct.Struct(_struct_format)
            hWnd = 0
            uID = 0
            uFlags = 0
            uCallbackMessage = 0
            hIcon = 0
            szTip = ''
            dwState = 0
            dwStateMask = 0
            szInfo = ''
            uTimeoutOrVersion = 0
            szInfoTitle = ''
            dwInfoFlags = 0

            def pack(self):
                return self._struct.pack(self._struct.size, self.hWnd, self.uID, self.uFlags, self.uCallbackMessage, self.hIcon, self.szTip, self.dwState, self.dwStateMask, self.szInfo, self.uTimeoutOrVersion, self.szInfoTitle, self.dwInfoFlags)

            def __setattr__(self, name, value):
                if not hasattr(self, name):
                    raise NameError, name
                self.__dict__[name] = value

        nid = PyNOTIFYICONDATA()
        nid.hWnd = self.__GetIconHandle()
        nid.uFlags = win32gui.NIF_MESSAGE | win32gui.NIF_INFO | win32gui.NIF_ICON
        nid.dwInfoFlags = win32gui.NIIF_INFO
        nid.szInfo = text
        nid.szInfoTitle = title
        nid.uTimeoutOrVersion = ms_timeout
        nid.hIcon = self.icon.GetHandle()
        from ctypes import windll
        Shell_NotifyIcon = windll.shell32.Shell_NotifyIconA
        ret_val = Shell_NotifyIcon(win32gui.NIM_MODIFY, nid.pack())
        wx.Yield()
        print '********** called %s' % str(ret_val)

    def _get_lpdata(self, hicon, title, msg, msec, flags):
        infoFlags = 0
        if flags & wx.ICON_INFORMATION:
            infoFlags |= win32gui.NIIF_INFO
        elif flags & wx.ICON_WARNING:
            infoFlags |= win32gui.NIIF_WARNING
        elif flags & wx.ICON_ERROR:
            infoFlags |= win32gui.NIIF_ERROR
        lpdata = (self.__GetIconHandle(),
         99,
         win32gui.NIF_MESSAGE | win32gui.NIF_INFO | win32gui.NIF_ICON,
         0,
         hicon,
         '',
         msg,
         msec,
         title,
         infoFlags)
        return lpdata

    def __SetBalloonTip(self, hicon, title, msg, msec, flags):
        lpdata = self._get_lpdata(hicon, title, msg, msec, flags)
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, lpdata)
        self.SetIcon(self.icon, self.tooltip)

    def __GetIconHandle(self):
        if not hasattr(self, '_chwnd'):
            try:
                for handle in wx.GetTopLevelWindows():
                    if handle.GetWindowStyle():
                        continue
                    handle = handle.GetHandle()
                    if len(win32gui.GetWindowText(handle)) == 0 and win32gui.GetWindowRect(handle) == (0, 0, 400, 250):
                        self._chwnd = handle
                        break

                if not hasattr(self, '_chwnd'):
                    raise Exception
            except:
                raise Exception, 'Icon window not found'

        return self._chwnd

    def SetIcon(self, icon, tooltip = ''):
        self.icon = icon
        self.tooltip = tooltip
        wx.TaskBarIcon.SetIcon(self, icon, tooltip)

    def RemoveIcon(self):
        self.icon = None
        self.tooltip = ''
        wx.TaskBarIcon.RemoveIcon(self)
        return


def url_retrieve(url, dst, reporting, completed):
    download_start = time.time()
    progress = [0.0]

    def reporthook(numblocks, blocksize, filesize):
        if filesize is None or filesize < 1:
            filesize = 10485760
        progress[0] = max(progress[0], min(numblocks * blocksize * 0.99 / filesize, 1.0))
        filekb = int(filesize / 1024)
        time_taken = time.time() - download_start
        retrieved = int((filesize - numblocks * blocksize) / 1024)
        if time_taken:
            rate = int(retrieved / time_taken)
        else:
            rate = 0
        remaining = filekb - retrieved
        est_tmpl = _('Time left (%(retrieved)d kb of %(filekb)d kb)')
        remaining = est_tmpl % locals()
        reporting(progress=progress[0], remaining=remaining, transfer=rate)
        return

    if reporting:
        urllib.urlretrieve(url, dst, reporthook)
    else:
        urllib.urlretrieve(url, dst)
    completed()