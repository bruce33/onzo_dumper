# Embedded file name: client\utils.pyo
import logging
import os
import os.path
import subprocess
log = logging.getLogger(os.path.basename('utils'))
import wx
from client import wxutil
from client import dialogs
from cust_layout import resources
try:
    from pkg_resources import resource_filename as pkg_resource_filename
    from pkg_resources import resource_stream as pkg_resource_stream
except ImportError:
    pkg_resource_stream = None
    pkg_resource_filename = None

def resource_filename(name, fname):
    if pkg_resource_filename:
        try:
            return pkg_resource_filename(name, fname)
        except NotImplementedError:
            pass

    return fname


def resource_stream(caller_name, fname):
    name, _, ext = fname.rpartition('.')
    if getattr(resources, name, None):
        return getattr(resources, name).getStream()
    raise NotImplementedError('%s' % fname)
    return


@wxutil.inWxThreadSynchronized
def run_cmd_and_exit(exe, args, shell = None):
    from client import ui
    ui.do_exit()
    logging.shutdown()
    if shell:
        subprocess.Popen(exe, shell=True, close_fds=True)
    else:
        subprocess.Popen(' ' + args, executable=exe)


def get_dialog_result(dialog):
    dres = dialog.ShowModal()
    if dres in [wx.ID_OK, wx.ID_YES]:
        ret = True
    else:
        ret = False
    dialog.Destroy()
    return ret


@wxutil.inWxThreadSynchronized
def message_box(message, title, wx_flags = wx.OK | wx.ICON_ERROR):
    wx_flags |= wx.STAY_ON_TOP
    dialog = wx.MessageDialog(None, message, title, wx_flags)
    return get_dialog_result(dialog)


def confirm_box(message, title):
    return message_box(message, title, wx_flags=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)


@wxutil.inWxThreadSynchronized
def onzo_confirmation(message, title, affirmative, negative, icon = None, parent = None):
    if parent is None:
        parent = wx.GetApp().GetTopWindow()
    dlg_position = parent.GetScreenPositionTuple()
    dialog = dialogs.OnzoMessage(parent, message, title, affirmative, negative, icon, dlg_position, style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.WANTS_CHARS)
    return get_dialog_result(dialog)


@wxutil.inWxThreadSynchronized
def onzo_download(download_url, filename, caption, parent = None):
    dialog = dialogs.OnzoDownload(parent, _('Download in progress...'), download_url, filename, caption)
    dres = get_dialog_result(dialog)
    return dres


@wxutil.inWxThreadSynchronized
def onzo_upgrade(device, filename, device_name, parent = None):
    dialog = dialogs.OnzoUpgrade(parent, _('Upgrade in progress...'), device, filename, device_name)
    dialog.Bind(wx.EVT_INIT_DIALOG, dialog.CommenceUpgrade, dialog)
    update = get_dialog_result(dialog)
    if update:
        log.info('Firmware update successful!')
    return update