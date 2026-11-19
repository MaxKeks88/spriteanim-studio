' SpriteAnim Studio - stop the server and its helpers (agent, sheet editor).
On Error Resume Next
Set http = CreateObject("MSXML2.XMLHTTP")
http.open "POST", "http://127.0.0.1:8189/api/quit", False
http.send ""
If Err.Number <> 0 Then
  MsgBox "SpriteAnim Studio is not running (port 8189 does not answer).", 64, "SpriteAnim Studio"
End If
