Option Explicit
Dim shell, fso, folder, python, command, finder, candidate
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
python = shell.ExpandEnvironmentStrings("%LAYA_SNAKE_PYTHON%")
If Not fso.FileExists(python) Then python = folder & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(python) Then
  Set finder = shell.Exec("where.exe pythonw.exe")
  Do While Not finder.StdOut.AtEndOfStream
    candidate = Trim(finder.StdOut.ReadLine)
    If fso.FileExists(candidate) Then
      python = candidate
      Exit Do
    End If
  Loop
End If
If Not fso.FileExists(python) Then
  MsgBox "Python 3.11+ was not found. Install Python with Add to PATH enabled, or run: python app.py --open", 16, "Laya Snake"
  WScript.Quit 1
End If
command = """" & python & """ """ & folder & "\app.py"" --open"
shell.Run command, 0, False
