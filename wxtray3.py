#!/usr/bin/python

# mytaskbaricon.py

import wx

class MyTaskBarIcon(wx.TaskBarIcon):
    def __init__(self, frame):
        wx.TaskBarIcon.__init__(self)

        self.frame = frame
        self.SetIcon(wx.Icon('icon.png', wx.BITMAP_TYPE_PNG), 'mytaskbaricon.py')

    def CreatePopupMenu(self):
        menu = wx.Menu()
        menu.Append(1, 'Show')
        menu.Append(2, 'Hide')
        menu.Append(3, 'Close')
        return menu

class MyFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, (-1, -1), (290, 280))

        self.tskic = MyTaskBarIcon(self)
        # self.Centre()
        # self.Bind(wx.EVT_CLOSE, self.OnClose)

    # def OnClose(self, event):
    #     self.tskic.Destroy()
    #     self.Destroy()

class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame(None, -1, 'mytaskbaricon.py')
        # frame.Show(True)
        # self.SetTopWindow(frame)
        return True

app = MyApp(0)
app.MainLoop()