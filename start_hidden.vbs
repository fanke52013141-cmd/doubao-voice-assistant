Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
venvConfig = fso.BuildPath(baseDir, ".venv\pyvenv.cfg")
venvPythonw = fso.BuildPath(baseDir, ".venv\Scripts\pythonw.exe")
runnerPath = fso.BuildPath(baseDir, "hidden_runner.pyw")
launcherPath = fso.BuildPath(baseDir, "launcher.py")
pythonExe = ""

If fso.FileExists(venvConfig) Then
    Set config = fso.OpenTextFile(venvConfig, 1, False)
    Do Until config.AtEndOfStream
        line = config.ReadLine
        If LCase(Trim(Split(line & "=", "=")(0))) = "home" Then
            homeDir = Trim(Mid(line, InStr(line, "=") + 1))
            candidate = fso.BuildPath(homeDir, "pythonw.exe")
            If fso.FileExists(candidate) Then
                pythonExe = candidate
            End If
            Exit Do
        End If
    Loop
    config.Close
End If

If pythonExe = "" Then
    If fso.FileExists(venvPythonw) Then
        pythonExe = venvPythonw
    End If
End If

' venv 不可用时，按版本从新到旧回退到本机常用的 Python 安装位置。
If pythonExe = "" Then
    localAppData = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
    versions = Array("Python313", "Python312", "Python311", "Python310")
    For Each ver In versions
        candidate = fso.BuildPath(localAppData, "Programs\Python\" & ver & "\pythonw.exe")
        If fso.FileExists(candidate) Then
            pythonExe = candidate
            Exit For
        End If
    Next
End If

If pythonExe = "" Then
    pythonExe = "pythonw.exe"
End If

shell.CurrentDirectory = baseDir
If fso.FileExists(runnerPath) Then
    shell.Run """" & pythonExe & """ """ & runnerPath & """ """ & launcherPath & """", 1, False
Else
    shell.Run """" & pythonExe & """ """ & launcherPath & """", 1, False
End If
