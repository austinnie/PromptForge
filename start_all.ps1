# start_all.ps1
Write-Host "🚀 启动 PromptForge..." -ForegroundColor Cyan

# 1. 检查环境
if (-not (Test-Path ".env")) {
    Write-Host "⚠️ 未找到 .env 文件，请先配置 API Key！" -ForegroundColor Red
}
if (-not (Test-Path "cloudflared.exe")) {
    Write-Host "⚠️ 未找到 cloudflared.exe，公网访问将不可用。" -ForegroundColor Yellow
}

# 2. 启动后端
Write-Host "📡 正在启动 API 服务端 (后台)..." -ForegroundColor Green
$apiProcess = Start-Process -FilePath "python" -ArgumentList "api_server.py" -NoNewWindow -PassThru
Start-Sleep -Seconds 3

# 3. 启动 cloudflared
if (Test-Path "cloudflared.exe") {
    Write-Host "🌍 正在启动 Cloudflare 隧道..." -ForegroundColor Green
    Write-Host "   (请复制下方输出的 trycloudflare.com 网址，并在末尾加上 /?token=你的密码)" -ForegroundColor Yellow
    Start-Process -FilePath ".\cloudflared.exe" -ArgumentList "tunnel --url http://localhost:8000 --edge-ip-version 4"
}

Write-Host "`n✅ 启动完成！按任意键退出此脚本 (服务将继续在后台运行)。" -ForegroundColor Cyan
Pause