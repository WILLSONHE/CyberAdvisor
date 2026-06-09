# 注册 AI 模拟盘 + 休市 daily 计划任务（需管理员 PowerShell）
# 用法：Set-ExecutionPolicy -Scope Process Bypass; .\scripts\ai_sim_register_tasks.ps1
#
# 时刻说明：
#   09:15        早盘前策略
#   09:30-11:15  盘中每 15 分钟（11:30 休市 → daily.bat，不跑 sim tick）
#   11:30        上午收盘 → daily.bat（持仓同步 + 市场日报 + bilibili 等）
#   11:45        午休复盘（ai_sim tick）
#   13:00-14:45  盘中每 15 分钟（15:00 休市 → daily.bat，不跑 sim tick）
#   15:00        全天收盘 → daily.bat
#   15:15        收盘复盘（ai_sim tick）

$Root = Split-Path -Parent $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
$SimBat = Join-Path $Root "ai_sim_tick.bat"
$DailyBat = Join-Path $Root "daily.bat"
$Ticks = @(
    "09:15",
    "09:30","09:45","10:00","10:15","10:30","10:45","11:00","11:15",
    "11:45",
    "13:00","13:15","13:30","13:45","14:00","14:15","14:30","14:45",
    "15:15"
)
$DailyRuns = @("11:30", "15:00")

foreach ($t in $Ticks) {
    $name = "CyberAdvisor-AISim-$($t.Replace(':',''))"
    schtasks /Delete /TN $name /F 2>$null | Out-Null
    schtasks /Create /TN $name /TR "`"$SimBat`"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST $t /F | Out-Null
    Write-Host "Created: $name @ $t (ai_sim_tick)"
}

foreach ($t in $DailyRuns) {
    $name = "CyberAdvisor-Daily-$($t.Replace(':',''))"
    # 休市时刻已无法成交，改跑 daily 流水线（_nopause 供计划任务无交互）
    schtasks /Delete /TN $name /F 2>$null | Out-Null
    schtasks /Delete /TN "CyberAdvisor-AISim-$($t.Replace(':',''))" /F 2>$null | Out-Null
    schtasks /Create /TN $name /TR "`"$DailyBat`" _run _nopause" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST $t /F | Out-Null
    Write-Host "Created: $name @ $t (daily.bat)"
}

Write-Host "Done. $($Ticks.Count) ai_sim + $($DailyRuns.Count) daily tasks."
Write-Host "Ensure .env has CURSOR_API_KEY for Cloud Agent."
