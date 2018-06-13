# Embedded file name: client\settings.pyo
import logging
import os
import os.path
import sys
import UserDict
import uuid
from client.defaults import Defaults
log = logging.getLogger(os.path.basename('settings'))
import wx
from client.onzo_platform import *

class Settings(UserDict.DictMixin):

    def __init__(self, appname, settings):
        self.config = wx.Config(appname)
        self.keyList = [ key for key, label, default in settings ]
        self.defaults = dict([ (key, default) for key, label, default in settings ])
        self.labels = dict([ (key, label) for key, label, default in settings ])
        self.observers = []

    def get(self, key):
        if MAC:
            return self.defaults.get(key, '')
        else:
            return self.config.Read(key, self.defaults.get(key, ''))

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, val):
        if not MAC:
            self.config.Write(key, val)
        else:
            Defaults.MacWrite(key, val)

    def keys(self):
        return self.keyList

    def attach(self, observer, call_immediate = False):
        if observer not in self.observers:
            self.observers.append(observer)
        if call_immediate:
            observer(self)
        return lambda : self.detach(observer)

    def detach(self, observer):
        if observer in self.observers:
            self.observers.remove(observer)

    def save(self):
        self.config.Flush()
        for observer in self.observers[:]:
            observer(self)

    def complete(self):
        for v in self.itervalues():
            if not bool(v):
                return False

        return True

    def get_instance_id(self):
        instance_hex = self.get('instance_id')
        if instance_hex:
            try:
                uuid.UUID(instance_hex)
            except ValueError:
                instance_hex = None

        if not instance_hex:
            instance_hex = uuid.uuid4().hex
            self['instance_id'] = instance_hex
            self.save()
        return instance_hex


class SettingsDialog(wx.Dialog):

    def __init__(self, parent, settings, on_close = None, **kwargs):
        wx.Dialog.__init__(self, parent=parent, **kwargs)
        self.settings = settings
        self.fields = {}
        self.on_close = lambda : None
        self.on_close = on_close or self.on_close
        grid = wx.FlexGridSizer(0, 2, 10, 10)
        grid.AddGrowableCol(1, 1)
        for key in self.settings:
            grid.Add(wx.StaticText(self, label=settings.labels[key] + ':'), flag=wx.ALIGN_LEFT)
            f = wx.TextCtrl(self, value=settings[key])
            w, h = f.GetBestSizeTuple()
            f.SetMinSize(wx.Size(w * 3, h))
            self.fields[key] = f
            grid.Add(f, flag=wx.GROW | wx.ALIGN_LEFT)

        bsizer = wx.StdDialogButtonSizer()
        btn = wx.Button(self, wx.ID_OK)
        btn.Bind(wx.EVT_BUTTON, self.OnOkButton)
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        btn.SetDefault()
        bsizer.AddButton(btn)
        btn = wx.Button(self, wx.ID_CANCEL)
        bsizer.AddButton(btn)
        bsizer.Realize()
        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(grid, flag=wx.GROW | wx.ALIGN_CENTER | wx.ALL, border=10)
        vsizer.Add(bsizer, flag=wx.GROW | wx.ALIGN_CENTER | wx.ALL, border=10)
        self.SetSizer(vsizer)
        vsizer.Fit(self)

    def OnCloseWindow(self, event):
        self.on_close()
        self.Destroy()

    def OnOkButton(self, event):
        for k, f in self.fields.iteritems():
            self.settings[k] = f.GetValue()

        self.OnCloseWindow(None)
        self.settings.save()
        event.Skip()
        return