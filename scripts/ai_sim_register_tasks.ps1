# 注册 AI 模拟盘 15 分钟计划任务（需管理员 PowerShell）
# 用法：右键「使用 PowerShell 运行」或在管理员终端：
#   Set-ExecutionPolicy -Scope Process Bypass; .\scripts\ai_sim_register_tasks.ps1

$Root = Split-Path -Parent $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
$Bat = Join-Path $Root "ai_sim_tick.bat"
$Ticks = @(
    "09:30","09:45","10:00","10:15","10:30","10:45","11:00","11:15","11:30",
    "13:00","13:15","13:30","13:45","14:00","14:15","14:30","14:45","15:00"
)

foreach ($t in $Ticks) {
    $name = "CyberAdvisor-AISim-$($t.Replace(':',''))"
    schtasks /Delete /TN $name /F 2>$null | Out-Null
    schtasks /Create /TN $name /TR "`"$Bat`"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST $t /F | Out-Null
    Write-Host "Created: $name @ $t"
}
Write-Host "Done. Tasks run ai_sim_tick.bat at each session tick (Mon-Fri)."
