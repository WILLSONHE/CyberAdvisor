# 注册 AI 模拟盘计划任务（需管理员 PowerShell）
# 用法：Set-ExecutionPolicy -Scope Process Bypass; .\scripts\ai_sim_register_tasks.ps1
#
# 时刻说明：
#   09:15        早盘前策略
#   09:30-11:30  盘中每 15 分钟
#   11:45        午休复盘（一次）
#   13:00-15:00  盘中每 15 分钟
#   15:15        收盘复盘

$Root = Split-Path -Parent $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
$Bat = Join-Path $Root "ai_sim_tick.bat"
$Ticks = @(
    "09:15",
    "09:30","09:45","10:00","10:15","10:30","10:45","11:00","11:15","11:30",
    "11:45",
    "13:00","13:15","13:30","13:45","14:00","14:15","14:30","14:45","15:00",
    "15:15"
)

foreach ($t in $Ticks) {
    $name = "CyberAdvisor-AISim-$($t.Replace(':',''))"
    schtasks /Delete /TN $name /F 2>$null | Out-Null
    schtasks /Create /TN $name /TR "`"$Bat`"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST $t /F | Out-Null
    Write-Host "Created: $name @ $t"
}
Write-Host "Done. $($Ticks.Count) tasks (pre-open / intraday / lunch / post-close)."
Write-Host "Ensure .env has CURSOR_API_KEY for Cloud Agent."
