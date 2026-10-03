import os
import sys
import win32com.client

desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
path = os.path.join(desktop, 'AUREXIS V2.lnk')
target = r'C:\Users\bluzp\AUREXISV2\launch_aurexis.bat'
wDir = r'C:\Users\bluzp\AUREXISV2'

shell = win32com.client.Dispatch("WScript.Shell")
shortcut = shell.CreateShortCut(path)
shortcut.Targetpath = target
shortcut.WorkingDirectory = wDir
shortcut.save()

print(f"Shortcut created at {path}")
