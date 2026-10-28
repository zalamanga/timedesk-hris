. (Join-Path $PSScriptRoot 'Common.ps1')
Invoke-AppCompose -ComposeArguments @('stop')
Write-Output 'Layanan dihentikan; volume database tetap tersimpan.'
