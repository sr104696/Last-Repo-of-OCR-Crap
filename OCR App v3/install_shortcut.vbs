Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = oWS.SpecialFolders("Desktop") & "\OCR Scanner.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)

' Get directory of this VBS script
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

oLink.TargetPath = currentDir & "\run.bat"
oLink.WorkingDirectory = currentDir
oLink.Description = "Fast Local OCR Scanner"
oLink.Hotkey = "CTRL+ALT+O"
oLink.WindowStyle = 7
oLink.Save

MsgBox "Shortcut created on your Desktop." & vbCrLf & vbCrLf & "You can now press CTRL+ALT+O from anywhere to run OCR!", vbInformation, "OCR App Setup"
