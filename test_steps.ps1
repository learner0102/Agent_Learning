# test_settings.ps1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$Base = "http://localhost:8000"

$login = Invoke-RestMethod -Uri "$Base/api/auth/login" -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body (@{ username="test"; password="test123" } | ConvertTo-Json)
$h = @{ Authorization = "Bearer $($login.token)" }

Write-Host "=== 1. 统计信息 ===" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$Base/api/settings/info" -Headers $h | ConvertTo-Json

Write-Host "`n=== 2. 长期记忆列表 ===" -ForegroundColor Cyan
$mem = Invoke-RestMethod -Uri "$Base/api/settings/memory" -Headers $h
Write-Host "共 $($mem.Count) 条"
$mem | Select-Object -First 3 | Format-Table idx, memory_type, importance

Write-Host "`n=== 3. 删除索引 0 的记忆（如果存在）===" -ForegroundColor Cyan
if ($mem.Count -gt 0) {
    Invoke-RestMethod -Uri "$Base/api/settings/memory/0" -Method Delete -Headers $h | Out-Null
    Write-Host "已删除"
    $mem2 = Invoke-RestMethod -Uri "$Base/api/settings/memory" -Headers $h
    Write-Host "删除后剩 $($mem2.Count) 条"
} else {
    Write-Host "无记忆可删"
}