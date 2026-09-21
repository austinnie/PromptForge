# scripts/register_daily_task.ps1
$TaskName   = "PromptForge_Daily"
$BatPath    = "E:\SD_OpenVINO\PromptForge\scripts\run_daily.bat"
$ProjectDir = "E:\SD_OpenVINO\PromptForge"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Trigger = New-ScheduledTaskTrigger -Daily -At "08:00"

$Action  = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatPath`"" `
    -WorkingDirectory $ProjectDir

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Description "PromptForge 每日生图 + 鉴赏 + 排版 + 推公众号" `
    -Force

Write-Host "✅ 已注册：$TaskName"