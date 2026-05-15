Set ws  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
pasta = fso.GetParentFolderName(WScript.ScriptFullName)

' Mata processos anteriores silenciosamente
ws.Run "cmd /c taskkill /IM python.exe /F", 0, True
ws.Run "cmd /c taskkill /IM node.exe   /F", 0, True
WScript.Sleep 800

' Sobe o manager Node.js em background sem janela preta
ws.Run "cmd /c cd /d """ & pasta & """ && node manager.js", 0, False

' Aguarda o Python subir (mais lento que o Node)
WScript.Sleep 3000

' Abre o painel de controle no navegador
ws.Run "http://localhost:3006"
