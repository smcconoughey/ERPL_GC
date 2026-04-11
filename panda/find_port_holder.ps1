Get-Process python* | Select-Object Id, ProcessName | Format-Table -AutoSize
Get-Process | Where-Object {$_.ProcessName -match 'putty|teraterm|serial|monitor'} | Select-Object Id, ProcessName | Format-Table -AutoSize
