# Embedded file name: cust_layout\layout.pyo
import wx
from client import layout_strings as lys
window_size = (345, 305)
dialog_size = (310, 230)
background_top = wx.Colour(127, 197, 57)
background_bottom = wx.Colour(127, 197, 57)
progressbar_background = wx.Colour(255, 255, 255)
progressbar_foreground = wx.Colour(0, 110, 145)
status_normal = wx.Colour(255, 255, 255)
status_hover = wx.Colour(255, 255, 255)
tickbar_size = (310, 40)
tickbar_foreground = wx.Colour(15, 49, 127)
tickbar_text_pos = (43, 12)
icon_title = lys.icon_title
window_title = lys.window_title
server_cross_text = lys.server_cross_text
server_tick_text = lys.server_tick_text
device_cross_text = lys.device_cross_text
device_tick_text = lys.device_tick_text
devices_tick_text = {'SEK': lys.devices_tick_text_sek,
 'ZIGBEE': lys.devices_tick_text_zbd,
 'ZBD': lys.devices_tick_text_zbd}