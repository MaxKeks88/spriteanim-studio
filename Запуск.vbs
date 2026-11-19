' SpriteAnim Studio - start with no console window and no taskbar button.
' Double-click this file. The app opens in the default browser.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
On Error Resume Next
sh.Run "pythonw.exe server.py", 0, False
If Err.Number <> 0 Then
  Err.Clear
  sh.Run "pyw.exe server.py", 0, False
End If
If Err.Number <> 0 Then
  Err.Clear
  sh.Run "run.bat", 0, False
End If
