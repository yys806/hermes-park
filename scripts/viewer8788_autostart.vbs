' 开机自启：园区驾驶舱后端（127.0.0.1:8788）
' 已有实例在跑就跳过，不会重复起；日志写 cache/viewer8788.log
Option Explicit
Dim sh, fso, port, cmd, logDir
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' 端口已经有人监听就直接退出
port = sh.Exec("cmd /c netstat -ano -p tcp | findstr LISTENING | findstr :8788").StdOut.ReadAll
If InStr(port, ":8788") > 0 Then
  WScript.Quit
End If

If Not fso.FolderExists("D:\hermes\home\cache") Then fso.CreateFolder("D:\hermes\home\cache")
logDir = "D:\hermes\home\cache\viewer8788.log"

sh.CurrentDirectory = "D:\hermes\home"
cmd = "cmd /c """"D:\nodejs\node.exe"" server\server.js > """ & logDir & """ 2>&1"""
sh.Run cmd, 0, False
