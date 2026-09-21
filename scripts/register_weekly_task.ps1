$TaskName   = "PromptForge_Weekly_Tech"
$BatPath    = "E:\SD_OpenVINO\PromptForge\scripts\run_weekly.bat"
$ProjectDir = "E:\SD_OpenVINO\PromptForge"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "09:00"

$Action  = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatPath`"" `
    -WorkingDirectory $ProjectDir

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Description "PromptForge 每周技术文章 + 微信推送" `
    -Force