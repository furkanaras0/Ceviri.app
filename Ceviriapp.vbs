Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = currentDir
WshShell.Run """" & currentDir & "\.venv\Scripts\pythonw.exe"" """ & currentDir & "\main.py""", 0, False
