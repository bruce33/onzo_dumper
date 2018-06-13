# Embedded file name: client\ui.pyo
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import os
import time
import datetime
import traceback
import gc
import interlocks
import webbrowser
import logging
log = logging.getLogger(os.path.basename('ui'))
import wx
from client import wxutil
from client import utils
from client import upload
from client import status
from cust_layout import layout
from client.utils import resource_stream
from client.settings import Settings, SettingsDialog
from client.dialogs import BalloonTaskBarIcon
from client import internationalisation
from client.client_version import DEBUG, VERSION
WINDOWS = False
MAC = False
LINUX = False
if os.name == 'nt':
    WINDOWS = True
if sys.platform == 'darwin':
    MAC = True
if sys.platform.startswith('linux'):
    LINUX = True

def get_bitmap(name):
    return wx.BitmapFromImage(wx.ImageFromStream(utils.resource_stream(__name__, name)))


def get_icon(name):
    return wxutil.MakeIcon(wx.ImageFromStream(utils.resource_stream(__name__, name)))


class SharedState(object):

    def __init__(self, settings):
        self.settings = settings
        self.disable_cancel = status.SafeContainer()
        self.disable_close = status.SafeContainer()
        self.ui_flavour = status.SafeContainer('welcome')
        self.upload_progress = status.SafeContainer(0.0)
        self.upload_started = status.SafeContainer(False)
        self.upload_status = status.SafeContainer('')


class OnzoTaskBarIcon(BalloonTaskBarIcon):
    TBMENU_SETTINGS = wx.NewId()
    TBMENU_CLOSE = wx.ID_EXIT
    TBMENU_SHOW = wx.NewId()
    TBMENU_STATUS = wx.NewId()
    TBMENU_REPAIR = wx.NewId()

    def __init__(self, create_device, show_main = False):
        from client.defaults import Defaults
        BalloonTaskBarIcon.__init__(self)
        self.mainwin = None
        self.settingswin = None
        self.device = create_device(debug=False)
        self.display_type = ''
        defaults = Defaults()
        self.settings = Settings('Onzo', [('server_url', 'Server root URL (empty for disconnected operation)', defaults['server_url']),
         ('last_dump_time', 'Last upload time', ''),
         ('instance_id', 'Instance identifier', ''),
         ('brand_id', 'Brand identifier', defaults['brand_id']),
         ('website_help_url', 'Website problem help page', defaults['website_help_url']),
         ('device_help_url', 'Device problem help page', defaults['device_help_url']),
         ('protocol_version', "Version of the protocol we're using", defaults['protocol_version']),
         ('device_name', 'Device name', defaults['device_name'])])
        self.device_connected = status.SafeContainer(None, self.DeviceConnected)
        self.status = status.StatusController(self.settings, self.device_connected)
#        upload.update_protocol_version(self.settings.get('protocol_version'))
        self.state = SharedState(self.settings)
        self._animateTimer = wx.PyTimer(self.SetNextIcon)
        self._images = [ get_icon(name) for name in ('onzo_icon.png', 'onzo_icon_active.png') ]
        self.SetIconImage(0)
        self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, self.OnTaskBarActivate)
        self.Bind(wx.EVT_MENU, self.OnTaskBarClose, id=self.TBMENU_CLOSE)
        self.Bind(wx.EVT_MENU, self.OnTaskBarShow, id=self.TBMENU_SHOW)
        self.Bind(wx.EVT_MENU, self.OnTaskBarSettings, id=self.TBMENU_SETTINGS)
        self.Bind(wx.EVT_MENU, self.OnTaskBarStatus, id=self.TBMENU_STATUS)
        self.devicestatus = status.SafeContainer(None, self.DeviceStatusChanged)
        status.DeviceStatusThread(self.devicestatus, self.device_connected, self.device).start()
        self.networkstatus = status.SafeContainer(True)
 #       self.application_upgrade = status.ApplicationUpgrade(self.settings)
 #       status.NetworkStatusThread(self.networkstatus, self.settings, self.application_upgrade).start()
        self.DoUploadThread()
        if show_main or MAC:
            self.OnTaskBarShow()
        return

    def CreatePopupMenu(self):
        menu = wx.Menu()
        menu.Append(self.TBMENU_SHOW, _('Show'))
        menu.AppendSeparator()
        if DEBUG:
            menu.Append(self.TBMENU_SETTINGS, _('Settings...'))
        menu.Append(self.TBMENU_STATUS, _('About...'))
        if not MAC:
            menu.AppendSeparator()
            menu.Append(self.TBMENU_CLOSE, _('Exit'))
            menu.Enable(self.TBMENU_CLOSE, not self.state.disable_close)
        return menu

    def SetIconImage(self, index):
        self.SetIcon(self._images[index], layout.icon_title)
        self._imageIndex = index

    def SetNextIcon(self):
        self.SetIconImage((self._imageIndex + 1) % len(self._images))

    def OnTaskBarActivate(self, event):
        self.OnTaskBarShow()

    def OnTaskBarClose(self, event = None):
        if self.state.disable_close:
            return
        if self.mainwin:
            wx.CallAfter(self.mainwin.Destroy)
        if self.settingswin:
            wx.CallAfter(self.settingswin.Destroy)
        self.upload_thread.cleanup()
        wx.CallAfter(self.status.destroy_dialog)
        wx.CallAfter(self.device.cleanup)
        self.device = None
        wx.CallAfter(self.Destroy)
        log.info('Application exit')
        wx.CallAfter(sys.exit, 0)
        return

    def OnTaskBarShow(self, event = None):
        if self.mainwin:
            wxutil.wake_up_window(self.mainwin)
            return
        size = layout.window_size
        wnd_styles = wx.DEFAULT_FRAME_STYLE
        if WINDOWS:
            wnd_styles |= wx.STAY_ON_TOP
        self.mainwin = MainWindow(None, -1, title=self.settings['device_name'] + layout.window_title, size=size, style=wnd_styles & ~(wx.RESIZE_BORDER | wx.RESIZE_BOX | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX))
        self.mainwin.on_upload_start = self.UploadStart
        self.mainwin.on_upload_stop = self.UploadStop
        self.mainwin.on_upload_error = self.UploadError
        self.mainwin.on_close = self.OnMainWinClose
        self.settings.attach(self.mainwin.update_settings, True)
        self.mainwin.subscribe_to_state(self.state)
        self.DeviceStatusChanged(self.devicestatus.get())
        self.NetworkStatusChanged((True,'Network not needed'))
        self.mainwin.Show(True)
        return

    def OnMainWinClose(self):
        self.mainwin = None
        self.OnTaskBarClose()
        return

    def OnTaskBarStatus(self, event):
        wx.CallAfter(self.status.show_dialog)


    def OnTaskBarSettings(self, event):
        wx.CallAfter(self.DoSettingsDialog)

    def DoSettingsDialog(self):
        if self.settingswin:
            wxutil.wake_up_window(self.settingswin)
            return
        self.settingswin = SettingsDialog(None, self.settings, on_close=self.OnSettingsClose, title=_('Settings'))
        self.settingswin.Show(True)
        return

    def OnSettingsClose(self):
        self.settingswin = None
        return

    def DoUploadThread(self):
        self.upload_thread = upload.UploadThread(self.device, self.settings)
        self.upload_thread.on_upload_start = self.UploadStart
        self.upload_thread.on_upload_stop = self.UploadStop
        self.upload_thread.on_upload_error = self.UploadError
 #       self.upload_thread.application_upgrade = self.application_upgrade
        self.upload_thread.start()

    @wxutil.inWxThread
    def SetLogo(self, flavour):
        self.state.ui_flavour.set(flavour)

    @wxutil.inWxThread
    def UploadStart(self, flavour = 'uploading'):
        if not self.state.upload_started:
            self.state.upload_started.set(True)
            self.state.upload_progress.set(0.001)
            self.state.upload_status.set('')
            client = upload.ClientRPC(self.device, self.settings, self.state, self)
            client.display = self.display_type
            self.upload_thread.UploadStart(client)
            self.Animate(True)
            self.state.ui_flavour.set(flavour)

    @wxutil.inWxThread
    def UploadStop(self, flavour = 'uploaded'):
        if self.state.upload_started:
            self.state.upload_started.set(False)
            self.upload_thread.UploadStop()
            self.state.ui_flavour.set(flavour)
            self.state.upload_status.set('')
            self.Animate(False)

    @wxutil.inWxThread
    def UploadError(self, *args, **kwargs):
        log.error('UploadError: %r %r' % (args, kwargs))
        self.UploadStop(flavour='error')

    @wxutil.inWxThread
    def ErrorMessage(self, when, excinfo):
        tb = traceback.format_exception(*excinfo)
        log.error(when, exc_info=excinfo)
        dlg = wx.MessageDialog(None, 'An error has occured, please try operation again.', 'Error ' + when, wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()
        wx.CallAfter(self.UploadError)
        return

    def Animate(self, animate):
        timer = self._animateTimer
        if animate:
            if not timer.IsRunning():
                timer.Start(1000)
        else:
            timer.Stop()
            self.SetIconImage(0)

    @wxutil.inWxThread
    def DeviceStatusChanged(self, tick_text):
        if self.mainwin:
            self.mainwin.display_bar.set_message(*tick_text)
            self.mainwin.refresh_button_state()
        if tick_text[0] == True:
            if not self.mainwin:
                self.OnTaskBarShow()
            else:
                wxutil.wake_up_window(self.mainwin)

    @wxutil.inWxThread
    def DeviceConnected(self, device_tup):
        log.debug('Device %s connected' % device_tup[0])
        self.display_type = device_tup[0]

    @wxutil.inWxThread
    def get_display_type(self):
        return self.display_type

    @wxutil.inWxThread
    def NetworkStatusChanged(self, tick_text):
        if self.mainwin:
            self.mainwin.network_bar.set_message(*tick_text)
            self.mainwin.refresh_button_state()


class BackgroundPanel(wxutil.ViewContainer):
    image_map = None

    def __init__(self, parent, *args, **kwargs):
        wxutil.ViewContainer.__init__(self, parent, *args, **kwargs)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnGradientEraseBackground)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.image_map = {}
        self.Bind(wx.EVT_MOTION, self.evt_motion)
        self.Bind(wx.EVT_LEFT_UP, self.evt_left_down)

    def OnGradientEraseBackground(self, event):
        dc = event.GetDC()
        if not dc:
            dc = wx.ClientDC(self)
            rect = self.GetUpdateRegion().GetBox()
            dc.SetClippingRect(rect)
        top = layout.background_top
        bottom = layout.background_bottom
        dc.GradientFillLinear(self.GetRect(), top, bottom, wx.SOUTH)

    def evt_motion(self, event):
        is_hovered = False
        for k, (hover, hover_callback, action_callback) in self.image_map.items():
            x, y, p, r = k
            if x < event.X < p and y < event.Y < r:
                if not hover:
                    self.image_map[k] = [True, hover_callback, action_callback]
                    self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                    hover_callback(event, True)
                is_hovered = True
            elif hover:
                self.image_map[k] = [False, hover_callback, action_callback]
                hover_callback(event, False)

        if not is_hovered:
            self.SetCursor(wx.StockCursor(wx.CURSOR_ARROW))

    def evt_left_down(self, event):
        for (x, y, p, r), (_, _, action_callback) in self.image_map.items():
            if x < event.X < p and y < event.Y < r:
                action_callback()

    def register_active_field(self, (x, y, p, r), hover_callback, click_callback):
        self.image_map[x, y, p, r] = [False, hover_callback, click_callback]

    def unregister_active_field(self, (x, y, p, r)):
        del self.image_map[x, y, p, r]


class ProgressBar(wx.Panel):
    _progress = 0

    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        col = layout.progressbar_background
        self.SetBackgroundColour(col)
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def _set_progress(self, progress):
        if progress is None or progress < 0:
            progress = 0
        if progress != self._progress:
            self._progress = progress
            self.Refresh()
            self.Update()
        return

    progress = property(lambda self: self._progress, _set_progress)

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        col = layout.progressbar_foreground
        dc.SetBrush(wx.Brush(col))
        dc.SetPen(wx.TRANSPARENT_PEN)
        sz = self.GetSize()
        dc.DrawRectangle(0, 0, sz.width * self._progress, sz.height)


class LoadedBitmap(wxutil.StaticBitmapView):
    _messages = None

    def __init__(self, parent, size):
        wxutil.StaticBitmapView.__init__(self, parent, size)
        self.set_message('error')

    @classmethod
    def _get_message(cls, message):
        if not cls._messages:
            cls._messages = dict(((msg, get_bitmap('status_%s.png' % msg)) for msg in ('cancelled', 'error', 'uploaded', 'uploading', 'welcome', 'days', 'hours', 'downloading', 'updating', 'updatecomplete')))
            cls._messages.update(dict(((msg, get_bitmap('%s.png' % msg)) for msg in ('i0', 'i1', 'i2', 'i3', 'i4', 'i5', 'i6', 'i7', 'i8', 'i9'))))
        return cls._messages[message]

    def set_message(self, message):
        bitmap = self._get_message(message)
        self.SetBitmap(bitmap)


class StatusMessage(wx.BoxSizer):
    items = None
    size = None
    panel = None

    def __init__(self, panel, size):
        wx.BoxSizer.__init__(self, wx.HORIZONTAL)
        self.items = []
        self.size = size
        self.panel = panel
        self.set_message('days')

    def set_message(self, message, value = None):
        while self.items:
            item = self.items.pop()
            item.destroy()
            self.Detach(item)

        if message == 'days':
            if value is not None:
                for v in '%i' % value:
                    sn = LoadedBitmap(self.panel, size=(13, 50))
                    sn.set_message('i%s' % v)
                    self.Add(sn, 0, wx.ALIGN_CENTRE)
                    self.items.append(sn)

            sb = LoadedBitmap(self.panel, size=(220, 50))
            sb.set_message(message)
            self.Add(sb, 0, wx.ALIGN_CENTRE)
            self.items.append(sb)
        else:
            sb = LoadedBitmap(self.panel, size=self.size)
            sb.set_message(message)
            self.Add(sb, 0, wx.ALIGN_CENTRE)
            self.items.append(sb)
        self.Layout()
        return


def paint_background_gradient(widget, dc):
    _, yy = widget.GetPositionTuple()
    _, hh = widget.GetClientSizeTuple()
    _, HH = widget.GetParent().GetClientSizeTuple()
    topcol = layout.background_top
    botcol = layout.background_bottom

    def safe_interpolate(col1, col2, fraction, total):
        factor = float(fraction) / total
        if factor > 1.0:
            factor = 1
        if factor < 0.0:
            factor = 0
        return wx.Colour(int(col1.Red() - (col1.Red() - col2.Red()) * factor), int(col1.Green() - (col1.Green() - col2.Green()) * factor), int(col1.Blue() - (col1.Blue() - col2.Blue()) * factor))

    col1 = safe_interpolate(topcol, botcol, yy, HH)
    col2 = safe_interpolate(topcol, botcol, yy + hh, HH)
    sz = widget.GetSize()
    rect = wx.Rect(0, 0, sz.width, sz.height)
    dc.GradientFillLinear(rect, col1, col2, wx.SOUTH)


class ProgressStatus(wx.Panel):

    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self._parent = parent
        self._message = ''
        self.font = wx.Font(10, wx.SWISS, wx.NORMAL, wx.NORMAL)
        self.hover = False
        self.url = None
        self.Bind(wx.EVT_LEFT_UP, self.on_action)
        self.Bind(wx.EVT_ENTER_WINDOW, self.on_hover)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_hover)
        self.rectangle = None
        return

    def on_hover(self, event):
        if not self.rectangle:
            x, y = (0, 0)
            w, h = self.GetSize()
            b = 1
            self.rectangle = (x + b,
             y + b,
             x + w - b,
             y + h - b)
        x1, y1, x2, y2 = self.rectangle
        if x1 <= event.X < x2:
            h = y1 <= event.Y <= y2
            if h != self.hover:
                self.hover = h
                if self.url:
                    h and self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                else:
                    self.SetCursor(wx.StockCursor(wx.CURSOR_ARROW))
                self.Refresh()
                self.Update()

    def on_action(self, event):
        if self.url:
            webbrowser.open_new(self.url)
            self.hover = False
            self.SetCursor(wx.StockCursor(wx.CURSOR_ARROW))
            self.Refresh()
            self.Update()

    def set_message(self, message, url = None):
        if isinstance(message, (list, tuple)):
            message, url = message
        self.url = url
        if message != self._message:
            log.info('set_message(%r, %r)' % (message, url))
            self._message = message
            self.Refresh()
            self.Update()

    def _on_paint(self, event = None):
        dc = wx.PaintDC(self)
        sz = self.GetSize()
        rect = wx.Rect(0, 0, sz.width, sz.height)
        paint_background_gradient(self, dc)
        self.font.SetUnderlined(self.hover)
        dc.SetFont(self.font)
        col = layout.status_normal
        if self.hover:
            col = layout.status_hover
        dc.SetTextForeground(col)
        sz = self.GetSize()
        rect = wx.Rect(0, 0, sz.width, sz.height)
        dc.DrawLabel(self._message, rect, wx.ALIGN_CENTRE | wx.ALIGN_TOP)


class TickBar(wxutil.StaticBitmapView):
    _messages = None
    ticked = object()
    text = None
    hover = False
    rectangle = None
    url = None

    def __init__(self, parent, size, url):
        wxutil.StaticBitmapView.__init__(self, parent, size)
        self.set_message(True, '...')
        self._parent = parent
        self.url = url
        self.font = wx.Font(10, wx.SWISS, wx.NORMAL, wx.NORMAL)

    @classmethod
    def _get_message(cls, message):
        if not cls._messages:
            cls._messages = dict(((msg, get_bitmap('bar_%s.png' % msg)) for msg in ('tick', 'update', 'cross', 'cross_hover')))
            cls._questionmark = get_bitmap('questionmark.png')
        return cls._messages[message]

    def set_message(self, ticked, text):
        if self.ticked is not None and ticked is None:
            s = self.GetSize()
            x, y = self.GetPosition()
            b = 5
            self.rectangle = (x + b,
             y + b,
             s[0] + x - b,
             s[1] + y - b)

            def hover(h, e):
                self.hover = h
                self.repaint_message()

            def action():
                webbrowser.open_new(self.url)

            self._parent.register_active_field(self.rectangle, hover, action)
        if self.ticked is None and ticked is not None:
            self._parent.unregister_active_field(self.rectangle)
        self.text = text
        self.ticked = ticked
        self.repaint_message()
        return

    def repaint_message(self):
        if self.ticked:
            message = 'tick'
        elif self.ticked is False:
            message = 'update'
        elif not self.hover:
            message = 'cross'
        else:
            message = 'cross_hover'
        bitmap = self._get_message(message)
        bitmap = wxutil.text_to_bitmap(self.text, bitmap, layout.tickbar_text_pos, layout.tickbar_foreground)
        self.SetBitmap(bitmap)

    def on_paint_rect(self, dc, rect):
        if self.ticked:
            message = 'tick'
        elif not self.hover:
            message = 'cross'
        else:
            message = 'cross_hover'
        x = rect[0] + self.pos[0]
        y = rect[1] + self.pos[1]
        bitmap = self._get_message(message)
        dc.DrawBitmap(bitmap, x, y, 1)
        dc.SetFont(self.font)
        dc.SetBrush(wx.Brush(layout.tickbar_foreground))
        dc.SetTextForeground(layout.tickbar_foreground)
        pos = layout.tickbar_text_pos
        dc.DrawText(self.text, x + pos[0], y + pos[1])


if MAC:
    from wx.lib import platebtn
    BTNClass = platebtn.PlateButton
else:
    from wx.lib import platebtn
    BTNClass = wx.BitmapButton

class UploadButton(BTNClass):
    _variants = None
    _bitmap_setters = dict(normal='SetBitmapLabel', hover='SetBitmapHover', disabled='SetBitmapDisabled')

    @classmethod
    def _get_variant(cls, variant):
        if not cls._variants:
            cls._variants = dict([ (v, [ (state, get_bitmap('button_%s_%s.png' % (v, state))) for state in ('normal', 'hover', 'disabled') ]) for v in ('cancel', 'retry', 'upload', 'finish') ])
        return cls._variants[variant]

    def __init__(self, parent, **kwargs):
        kwargs.setdefault('style', wx.NO_BORDER)
        BTNClass.__init__(self, parent, **kwargs)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self._copy_gradient)
        self.set_variant('upload')

    def _copy_gradient(self, event):
        paint_background_gradient(self, event.GetDC())

    def _set_bitmaps(self, variant):
        variant = self._get_variant(variant)
        for state, bitmap in variant:
            getattr(self, self._bitmap_setters[state])(bitmap)

    def set_variant(self, variant):
        self._set_bitmaps(variant)
        self._variant = variant

    def get_variant(self):
        return self._variant

    def HasTransparentBackground(self):
        return True


class UsageTipMessage(wx.Dialog):

    def __init__(self, parent, message, caption = wx.MessageBoxCaptionStr, style = None, pos = wx.DefaultPosition):
        if style is None:
            style = wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, parent, wx.ID_ANY, caption, pos, wx.DefaultSize, style)
        topsizer = wx.BoxSizer(wx.VERTICAL)
        icon_text = wx.BoxSizer(wx.HORIZONTAL)
        icon = wx.ArtProvider.GetIcon(wx.ART_INFORMATION, wx.ART_MESSAGE_BOX)
        bitmap = wx.BitmapFromIcon(icon)
        icon = wx.StaticBitmap(self, wx.ID_ANY, bitmap)
        icon_text.Add(icon, 0, wx.CENTER)
        text = self.CreateTextSizer(message)
        icon_text.Add(text, 0, wx.ALIGN_CENTER | wx.LEFT, 10)
        self.checkbox = wx.CheckBox(self, label=_('Show this message again?'))
        self.checkbox.SetValue(True)
        text.Add(self.checkbox, 0, wx.LEFT | wx.ALL, 10)
        topsizer.Add(icon_text, 1, wx.CENTER | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        center_flag = wx.EXPAND | wx.CENTRE
        sizerBtn = self.CreateSeparatedButtonSizer(wx.OK)
        topsizer.Add(sizerBtn, 0, center_flag | wx.ALL, 10)
        self.SetAutoLayout(True)
        self.SetSizer(topsizer)
        topsizer.SetSizeHints(self)
        topsizer.Fit(self)
        size = self.GetSize()
        if size.x < size.y * 3 / 2:
            size.x = size.y * 3.2
            self.SetSize(size)
        self.Centre(wx.BOTH | wx.CENTER_FRAME)
        return


class MainWindow(wx.Frame):

    def __init__(self, parent, *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)
        self.on_upload_start = None
        self.on_upload_stop = None
        self.on_upload_error = None
        self.on_close = None
        self.settings = None
        self.flavour = None
        self.bflavour = 'upload'
        if MAC:
            self.CreateMenu()
        self.panel = panel = BackgroundPanel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(10)
        self.status_message = StatusMessage(panel, size=(330, 50))
        self.progress_bar = ProgressBar(panel, size=(240, 6))
        self.progress_status = ProgressStatus(panel, size=(240, 16))
        self.upload_button = UploadButton(panel)
        self.upload_button.Bind(wx.EVT_BUTTON, self.OnUploadButton)
        self.display_bar = TickBar(panel, layout.tickbar_size, 'http://www.onzo.co.uk/')
        self.network_bar = TickBar(panel, layout.tickbar_size, 'http://www.onzo.co.uk/')
        logo = wxutil.StaticBitmapView(panel, bitmap=get_bitmap('onzo_logo.png'))
        sizer.Add(self.status_message, 0, wx.ALIGN_CENTRE)
        sizer.AddSpacer(5)
        sizer.Add(self.progress_bar, 0, wx.ALIGN_CENTRE)
        sizer.AddSpacer(5)
        sizer.Add(self.progress_status, 0, wx.ALIGN_CENTRE)
        sizer.Add((5, 5), 6)
        sizer.Add(self.upload_button, 0, wx.ALIGN_CENTRE)
        sizer.Add((5, 5), 10)
        sizer.Add(self.display_bar, 0, wx.ALIGN_CENTRE)
        sizer.AddSpacer(10)
        sizer.Add(self.network_bar, 0, wx.ALIGN_CENTRE)
        sizer.AddSpacer(10)
        sizer.Add(logo, 0, wx.ALIGN_CENTRE)
        sizer.AddSpacer(10)
        panel.SetSizer(sizer)

        def show_progress_bar(show):
            sizer.Layout()
            panel.Refresh()

        self.show_progress_bar = show_progress_bar
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.SetIcon(get_icon('window_icon.png'))
        return

    def CreateMenu(self):
        menubar = wx.MenuBar()
        menu = wx.Menu()
        if DEBUG:
            item = menu.Append(wx.ID_PREFERENCES, _('Settings...'))
            self.Bind(wx.EVT_MENU, self.OnMenuSettings, item)
        item = menu.Append(wx.ID_ABOUT, _('About...'))
        self.Bind(wx.EVT_MENU, self.OnMenuStatus, item)
        item = menu.Append(wx.ID_CLOSE, text=_('Close\tCTRL-W'))
        self.Bind(wx.EVT_MENU, self.OnCloseWindow, item)
        item = menu.Append(wx.ID_EXIT, text=_('&Quit'))
        self.Bind(wx.EVT_MENU, self.OnMenuQuit, item)
        menubar.Append(menu, _('&File'))
        menubar.SetAutoWindowMenu(False)
        self.SetMenuBar(menubar)

    def OnMenuSettings(self, event):
        global taskbar
        return taskbar.OnTaskBarSettings(event)

    def OnMenuStatus(self, event):
        return taskbar.OnTaskBarStatus(event)

    def OnMenuQuit(self, event):
        return taskbar.OnTaskBarClose(event)

    def update_settings(self, settings):
        self.settings = settings
        self.display_bar.url = settings.get('device_help_url')
        self.network_bar.url = settings.get('website_help_url')
 #       upload.update_protocol_version(settings.get('protocol_version'))

    def subscribe_to_state(self, state):
        self.state = state
        self.unsubscribe_handlers = [state.disable_cancel.subscribe(self.OnDisableCancel),
         state.upload_progress.subscribe(self.UploadProgress),
         state.ui_flavour.subscribe(self.OnUiFlavourChange),
         state.upload_status.subscribe(self.UploadStatus)]
        self.OnDisableCancel(state.disable_cancel.get())
        self.UploadProgress(state.upload_progress.get())
        self.UploadStatus(state.upload_status.get())
        self._update_ui(state.ui_flavour.get())

    def unsubscribe(self):
        if self.settings:
            self.settings.detach(self.update_settings)
        for unsubscriber in self.unsubscribe_handlers:
            unsubscriber()

        del self.unsubscribe_handlers

    @wxutil.inWxThread
    def OnDisableCancel(self, disable_cancel):
        self.refresh_button_state(unsure_state=disable_cancel)

    @wxutil.inWxThread
    def OnUiFlavourChange(self, flavour):
        self._update_ui(flavour)

    def refresh_button_state(self, unsure_state = False):
        if (not self.display_bar.ticked or not self.network_bar.ticked) and self.flavour != 'uploaded':
            unsure_state = True
        if unsure_state:
            self.upload_button.Disable()
        else:
            self.upload_button.Enable()

    def _update_ui(self, flavour, unsure_state = False):
        value = None
        if self.state.upload_started:
            self.upload_button.set_variant('cancel')
            self.status_message.set_message(flavour)
            self.show_progress_bar(True)
        else:
            self.bflavour = 'upload'
            self.flavour = flavour
            hide_progress = True
            if flavour == 'uploaded':
                self.bflavour = 'finish'
            elif flavour == 'error':
                self.bflavour = 'retry'
                hide_progress = False
            elif flavour == 'cancelled':
                hide_progress = False
            elif flavour == 'welcome':
                try:
                    last_dump_time = datetime.datetime.fromtimestamp(float(self.settings['last_dump_time']))
                except ValueError:
                    last_dump_time = None

                if last_dump_time:
                    td = datetime.datetime.now() - last_dump_time
                    days = td.days + td.seconds / 60.0 / 60.0 / 24.0
                    value = int(days * 1.0)
                    if value < 1.0:
                        self.flavour = flavour = 'hours'
                    else:
                        self.flavour = flavour = 'days'
            self.upload_button.set_variant(self.bflavour)
            self.status_message.set_message(self.flavour, value=value)
            if hide_progress:
                self.show_progress_bar(False)
        self.refresh_button_state(unsure_state)
        return

    def OnUploadButton(self, event):
        if self.bflavour == 'finish':
            self.OnMenuQuit(event)    # change to self.OnCloseWindow(event) if you want it in the taskbar
            return
        if not self.state.upload_started:
            self.on_upload_start()
        else:
            self.on_upload_stop('cancelled')
        self._update_ui(self.state.ui_flavour.get(), unsure_state=True)

    @wxutil.inWxThread
    def UploadProgress(self, progress):
        if progress == 0.0:
            self.progress_bar.progress = progress
        else:
            self.progress_bar.progress = progress * 0.97 + 0.03

    @wxutil.inWxThread
    def UploadStatus(self, status):
        self.progress_status.set_message(status)
        self.panel.Refresh()

    def OnCloseWindow(self, event):
        if hasattr(self, 'closing'):
            return
        if not self.settings.get('hide_close_warning') and not MAC:
            wind = UsageTipMessage(self, _("%s will continue running in the \nsystem tray. To exit completely, select 'Exit' \nfrom the system tray icon menu.") % (self.settings['device_name'] + layout.window_title), _('Minimizing ') + self.settings['device_name'] + ' ' + layout.window_title)
            wind.ShowModal()
            if not wind.checkbox.IsChecked():
                self.settings['hide_close_warning'] = 'yes'
                self.settings.save()
        self.closing = True
        self.unsubscribe()
        if self.on_close:
            self.on_close()
        self.Destroy()
        if not self.state.upload_started:
            self.state.ui_flavour.set('welcome')
        wx.CallAfter(gc.collect)


do_exit = lambda : os.abort()
taskbar = None

class OnzoApp(wx.PySimpleApp):

    def MacReopenApp(self):
        self.taskbar.OnTaskBarShow()

    def IsDisplayAvailable(self):
        return True


def main():
    global do_exit
    global taskbar
    from client import device
    DeviceClass = device.Device
    FORMAT_FILE = '%(asctime)s %(name)s[%(process)d] %(levelname)10s %(message)s'
    FORMAT_CONS = '%(name)-12s %(levelname)8s\t%(message)s'
    if not MAC:
        FORMAT_CONS = '%(asctime)s ' + FORMAT_CONS
    verbose = logging.INFO
    if '--debug' in sys.argv or '-debug' in sys.argv or '-d' in sys.argv:
        verbose = logging.DEBUG
    if '--log' in sys.argv or '-log' in sys.argv or '-l' in sys.argv or WINDOWS:
        console = False
    else:
        console = True
    showMainWin = False
    if '--show' in sys.argv or '-show' in sys.argv:
        showMainWin = True
    if console:
        logging.basicConfig(level=verbose, format=FORMAT_CONS)
    else:
        logfilename = os.environ.get('LOCALAPPDATA', '')
        logfilename = logfilename and os.path.join(logfilename, 'Onzo', 'Onzo Uploader')
        logfilename = os.path.normpath(os.path.join(logfilename, 'dumper.log'))
        logfilename = 'dumper.log'
        logging.basicConfig(level=verbose, format=FORMAT_FILE, filename=logfilename, filemode='w')
    import platform
    log.info('Application %s start (%s %s %s)' % (VERSION,
     platform.system(),
     platform.release(),
     platform.version()))
    log.debug('Running with verbose %i (>=%s)' % (verbose, logging.getLevelName(verbose)))
    log.debug('Main dir is %r' % os.getcwd())
    log.debug('Argv: %r' % (sys.argv,))
    l = interlocks.InterProcessLock('Uploader Client Application')
    try:
        l.lock()
    except interlocks.SingleInstanceError:
        log.error('One instance is already running!')
        log.error('exiting')
        sys.exit(1)

    app = OnzoApp()
    taskbar = OnzoTaskBarIcon(DeviceClass, showMainWin)
    app.taskbar = taskbar
    do_exit = taskbar.OnTaskBarClose

    def _exceptionhook(type, value, traceback):
        taskbar.ErrorMessage(_('Fatal error in main loop:'), (type, value, traceback))

    sys.excepthook = _exceptionhook
    app.MainLoop()
    return 0


if __name__ == '__main__':
    main()