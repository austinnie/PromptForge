# scripts/register_github_daily_task.ps1
# 以管理员身份运行一次，注册"每天 09:00"的 GitHub 日报任务

$TaskName   = "PromptForge_GitHubDaily"
$BatPath    = "E:\SD_OpenVINO\PromptForge\scripts\run_github_daily.bat"
$ProjectDir = "E:\SD_OpenVINO\PromptForge"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# 每日 09:00 触发（比每日生图晚 1 小时，避免抢 Ollama）
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00"

$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatPath`"" `
    -WorkingDirectory $ProjectDir

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Description "PromptForge GitHub 每日仓库推荐 + 配图 + 排版 + 推公众号" `
    -Force

Write-Host "✅ 已注册：$TaskName"
Write-Host "   触发时间：每天 09:00"
Write-Host "   执行脚本：$BatPath"
Write-Host ""
Write-Host "常用操作："
Write-Host "   立即测试：Start-ScheduledTask -TaskName $TaskName"
Write-Host "   查看状态：Get-ScheduledTask -TaskName $TaskName | Format-List"
Write-Host "   取消注册：Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"