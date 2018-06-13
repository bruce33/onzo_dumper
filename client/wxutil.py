# Embedded file name: client\wxutil.pyo
import wx
import threading
import os, os.path, logging
log = logging.getLogger(os.path.basename('wxutil'))

def inWxThread(c):

    def a(*args, **kwargs):
        wx.CallAfter(c, *args, **kwargs)

    return a


def inWxThreadSynchronized(c):

    def a(*args, **kwargs):
        cv = threading.Lock()
        cv.acquire(True)
        r = [None]

        def foo():
            try:
                r[0] = c(*args, **kwargs)
            finally:
                cv.release()

        wx.CallAfter(foo)
        cv.acquire()
        return r[0]

    return a


class ViewContainer(wx.PyPanel):

    def __init__(self, parent, *args, **kwargs):
        wx.PyPanel.__init__(self, parent, *args, **kwargs)
        self._subviews = []
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def add_subview(self, on_paint):
        self._subviews.append(on_paint)

    def del_subview(self, on_paint):
        self._subviews.remove(on_paint)

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        for view_paint in self._subviews:
            view_paint(dc)


class View(wx.PySizer):

    def __init__(self, parent, size):
        wx.PySizer.__init__(self)
        self._size = size
        self._parent = parent
        parent.add_subview(self._on_paint)

    def CalcMin(self):
        return wx.Size(self._size[0], self._size[1])

    def ReCalcSizes(self):
        pass

    def _rect(self):
        pos = self.GetPosition()
        size = self._size
        return (pos[0],
         pos[1],
         size[0],
         size[1])

    def _on_paint(self, dc):
        self.on_paint_rect(dc, self._rect())

    def refresh(self):
        self._parent.RefreshRect(self._rect())

    def on_paint_rect(self, dc, rect):
        pass

    def destroy(self):
        self._parent.del_subview(self._on_paint)


class StaticBitmapView(View):
    _bitmap = None
    size = None
    pos = (0, 0)

    def __init__(self, parent, size = None, bitmap = None):
        if not size and bitmap:
            size = bitmap.GetSize()
        View.__init__(self, parent, size)
        self.size = size
        self.SetBitmap(bitmap)

    def SetBitmap(self, bitmap):
        if bitmap:
            size = bitmap.GetSize()
            self.pos = ((self.size[0] - size[0]) / 2, (self.size[1] - size[1]) / 2)
        self._bitmap = bitmap
        self.refresh()

    def on_paint_rect(self, dc, rect):
        if self._bitmap:
            dc.DrawBitmap(self._bitmap, rect[0] + self.pos[0], rect[1] + self.pos[1], True)


def wake_up_window(win):
    if win.IsIconized():
        win.Iconize(False)
    if not win.IsShown():
        win.Show(True)
    win.SetFocus()
    win.Raise()


def MakeIcon(img):
    if 'wxMSW' in wx.PlatformInfo:
        img = img.Scale(16, 16)
    elif 'wxGTK' in wx.PlatformInfo:
        img = img.Scale(22, 22)
    icon = wx.IconFromBitmap(img.ConvertToBitmap())
    return icon


def text_to_bitmap(text, old_bitmap, pos = (0, 0), color = wx.Colour(0, 0, 0)):
    bitmap = wx.EmptyBitmap(old_bitmap.GetWidth(), old_bitmap.GetHeight(), old_bitmap.GetDepth())
    memory = wx.MemoryDC()
    memory.SelectObject(bitmap)
    memory.DrawBitmap(old_bitmap, 0, 0, 1)
    memory.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.NORMAL))
    if color:
        memory.SetBrush(wx.Brush(color))
        memory.SetTextForeground(color)
    try:
        memory.DrawText(text, pos[0], pos[1])
    finally:
        memory.SelectObject(wx.NullBitmap)

    bitmap.SetMask(wx.Mask(bitmap, wx.BLACK))
    return bitmap


def copy_bitmap(bitmap):
    return wx.BitmapFromImage(bitmap.ConvertToImage())