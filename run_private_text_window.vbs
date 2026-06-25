Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

shell.CurrentDirectory = scriptDir

pythonw = FindOnPath("pythonw.exe")
If pythonw <> "" Then
  command = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & scriptDir & "\private_text_window.py" & Chr(34)
Else
  pyw = FindOnPath("pyw.exe")
  If pyw <> "" Then
    command = Chr(34) & pyw & Chr(34) & " -3 " & Chr(34) & scriptDir & "\private_text_window.py" & Chr(34)
  Else
    command = "python " & Chr(34) & scriptDir & "\private_text_window.py" & Chr(34)
  End If
End If
shell.Run command, 0, False

Function FindOnPath(exeName)
  On Error Resume Next
  Set exec = shell.Exec("%ComSpec% /c where " & exeName)
  output = Trim(exec.StdOut.ReadAll())
  If Err.Number <> 0 Or output = "" Then
    FindOnPath = ""
    Err.Clear
  Else
    FindOnPath = Split(output, vbCrLf)(0)
  End If
  On Error GoTo 0
End Function
