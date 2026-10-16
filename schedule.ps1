param([string]$Time = "18:30")
# Rejestruje codzienne zadanie "GPW Tracker - pobieranie" dla bieżącego użytkownika.
# StartWhenAvailable: jeśli komputer był wyłączony o tej godzinie, zadanie uruchomi się po włączeniu.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$action = New-ScheduledTaskAction -Execute "$dir\run_daily.bat" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
            -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName "GPW Tracker - pobieranie" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Codzienne pobieranie notowan, komunikatow ESPI i akcjonariatu spolek GPW" -Force | Out-Null
Write-Host "Zadanie zarejestrowane: codziennie o $Time (Harmonogram zadan -> 'GPW Tracker - pobieranie')."
