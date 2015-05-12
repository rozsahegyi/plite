# coding=utf-8

import sys, os, time, itertools
from functools import partial
# sys.path.append(os.path.realpath(os.path.curdir + '\\Lib\\site-packages'))
import wx

class TBI(wx.TaskBarIcon):
	def CreatePopupMenu(self):
		menu = wx.Menu()
		menu.Append(wx.NewId(), 'Item 1')
		menu.Append(wx.NewId(), 'Item 2')
		return menu

class App(wx.App):

	def OnInit(self):
		self.frame = wx.Frame(None, wx.ID_ANY, 'Plite 1.0')#, style=wx.FRAME_NO_TASKBAR)
		self.tb = TBI()
		self.tb.frame = self.frame
		self.tb.SetIcon(wx.Icon('icon.png', wx.BITMAP_TYPE_PNG))

		# self.Bind(wx.EVT_SET_FOCUS, self.FrameFocus)
		# self.frame.Bind(wx.EVT_SET_FOCUS, self.FrameFocus)
		# self.frame.Bind(wx.EVT_CLOSE, self.OnClose)
		# self.tb.Bind(wx.EVT_SET_FOCUS, self.TaskBarFocus)
		# self.tb.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, self.OnClose)
		# self.tb.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.TaskBarMenu)
		# self.tb.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.TaskBarMenu)

		# self.menu = wx.Menu()
		# self.menu.Append(wx.NewId(), 'Item 1')
		# self.menu.Append(wx.NewId(), 'Item 2')
		return True

	def OnClose(self, event):
		print 'program closed', event
		self.tb.RemoveIcon()
		self.tb.Destroy()
		self.frame.Destroy()
		self.Exit()

	def FrameFocus(self, event):
		print 'FrameFocus:', event, event.EventObject, event.Id

	def TaskBarFocus(self, event):
		print 'TaskBarFocus:', event, event.EventObject, event.Id

	def TaskBarMenu(self, event):
		print 'TaskBarMenu:', event, event.EventObject, event.Id
		self.tb.PopupMenu(self.menu)
		# print self.menu.MenuItems[0].Text

	def MenuClick(self, event, *args):
		print 'MenuClick:', event, event.EventObject, event.Id

if __name__ == '__main__':
	app = App(False)
	app.icon_size = 16
	import threading
	t = threading.Thread(target=app.MainLoop)
	t.start()
	print 'in mainloop'
