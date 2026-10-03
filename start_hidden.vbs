' start_hidden.vbs
' AUREXIS Silent Launcher
' Executes the PowerShell watchdog invisibly to prevent accidental closure by RDP users.

Set objFSO = CreateObject("Scripting.FileSystemObject")
strScriptFolder = objFSO.GetParentFolderName(WScript.ScriptFullName)

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = strScriptFolder

' Run PowerShell hidden (0 = vbHide)
strCommand = "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File run_aurexis_watchdog.ps1"
WshShell.Run strCommand, 0, False
