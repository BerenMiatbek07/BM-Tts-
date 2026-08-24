BM Voice Studio v5.6.4 — 3 бөлікке бөлінген ZIP

Windows CMD:
copy /b BM_Voice_Studio_v5.6.4_REMAINING_CLEAR.zip.001 + BM_Voice_Studio_v5.6.4_REMAINING_CLEAR.zip.002 + BM_Voice_Studio_v5.6.4_REMAINING_CLEAR.zip.003 BM_Voice_Studio_v5.6.4_REMAINING_CLEAR.zip

PowerShell:
$parts = 1..3 | ForEach-Object { "BM_Voice_Studio_v5.6.4_REMAINING_CLEAR.zip.{0:D3}" -f $_ }
$out = "BM_Voice_Studio_v5.6.4_REMAINING_CLEAR.zip"
Remove-Item $out -ErrorAction SilentlyContinue
foreach ($p in $parts) { [IO.File]::AppendAllText($out, [Text.Encoding]::Latin1.GetString([IO.File]::ReadAllBytes($p)), [Text.Encoding]::Latin1) }

Ең дұрысы: 7-Zip/WinRAR арқылы .001 файлын ашу немесе CMD copy /b командасын қолдану.
