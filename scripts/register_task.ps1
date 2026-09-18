<#
.SYNOPSIS
    注册 Windows 计划任务：每天固定时间执行 run_daily.bat

.DESCRIPTION
    需要管理员权限。项目路径默认从脚本位置自动推导（脚本位于 <项目根>\scripts\ 下）。

.PARAMETER ProjectDir
    项目根目录。默认取当前脚本的上两级的父目录。

.PARAMETER TaskTime
    每日执行时间，默认 08:00。

.PARAMETER TaskName
    计划任务名称，默认 PromptForge_Daily。

.EXAMPLE
    # 用默认项目路径和时间注册
    .\register_task.ps1

.EXAMPLE
    # 自定义项目路径和时间
    .\register_task.ps1 -ProjectDir "D:\Work\PromptForge" -TaskTime "07:30"
#>
[CmdletBinding()]
param(
    # [改] 项目路径默认从脚本位置推导，不再硬编码
    [string]$ProjectDir = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$TaskTime   = "08:00",
    [string]$TaskName   = "PromptForge_Daily"
)

$ErrorActionPreference = "Stop"

# [改] 自检：需要管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "请以管理员身份运行此脚本（右键 → 以管理员身份运行）"
    exit 1
}

# 校验项目目录 & bat 是否存在
if (-not (Test-Path $ProjectDir)) {
    Write-Error "项目目录不存在：$ProjectDir"
    exit 1
}

$BatPath = Join-Path $ProjectDir "scripts\run_daily.bat"
if (-not (Test-Path $BatPath)) {
    Write-Error "找不到 $BatPath，请确认项目路径或用 -ProjectDir 指定"
    exit 1
}

Write-Host "📁 项目目录：$ProjectDir" -ForegroundColor Cyan
Write-Host "🎯 任务名称：$TaskName"   -ForegroundColor Cyan
Write-Host "⏰ 执行时间：每天 $TaskTime" -ForegroundColor Cyan
Write-Host "🚀 执行脚本：$BatPath"   -ForegroundColor Cyan
Write-Host ""

# 删除旧任务（如果存在）
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# 触发器：每天固定时间
$Trigger = New-ScheduledTaskTrigger -Daily -At $TaskTime

# 动作：运行 bat
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatPath`"" `
    -WorkingDirectory $ProjectDir

# [改] 设置：唤醒、失败重试、电源策略、超时
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# 注册（当前用户）
Register-ScheduledTask `
    -TaskName    $TaskName `
    -Trigger     $Trigger `
    -Action      $Action `
    -Settings    $Settings `
    -Description "PromptForge 每日生图 + 鉴赏 + 排版" `
    -Force | Out-Null

# [改] 注册后立即校验并打印下次运行时间
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $TaskName

Write-Host "✅ 计划任务已注册" -ForegroundColor Green
Write-Host "   名称     : $($task.TaskName)"
Write-Host "   状态     : $($task.State)"
Write-Host "   下次运行 : $($info.NextRunTime)"
Write-Host ""
Write-Host "常用命令：" -ForegroundColor Yellow
Write-Host "   立即测试 : Start-ScheduledTask -TaskName $TaskName"
Write-Host "   查看状态 : Get-ScheduledTask -TaskName $TaskName | Format-List"
Write-Host "   删除任务 : Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"