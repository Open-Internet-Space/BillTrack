param([string]$Root=(Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference='Stop'
$name='BillTrack-MailReminders'
$rootPath=[IO.Path]::GetFullPath($Root)
if(-not (Test-Path -LiteralPath (Join-Path $rootPath 'manage.py'))){throw 'BillTrack installation root is missing manage.py'}
$existing=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if($existing){throw 'Reminder task already exists; review it before changing its schedule.'}
$production=Get-ScheduledTask -TaskName BillTrack-Production
if($production.Actions.WorkingDirectory -ne $rootPath){throw 'Production task points to another installation.'}
$python=Join-Path $rootPath 'venv\Scripts\python.exe'
if(Test-Path -LiteralPath (Join-Path $rootPath '.venv\Scripts\python.exe')){$python=Join-Path $rootPath '.venv\Scripts\python.exe'}
$action=New-ScheduledTaskAction -Execute $python -Argument ('"'+(Join-Path $rootPath 'manage.py')+'" send_bill_reminders --automatic') -WorkingDirectory $rootPath
$principal=New-ScheduledTaskPrincipal -UserId $production.Principal.UserId -LogonType S4U -RunLevel Limited
$trigger=New-ScheduledTaskTrigger -Daily -At '09:30'
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Trigger $trigger -Settings $settings | Out-Null
Write-Output 'Installed daily 09:30 LOCAL TIME reminder task. Confirm Windows timezone is India Standard Time. Automatic sending remains controlled by the disabled-by-default administrator switch.'
