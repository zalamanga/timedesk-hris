$ErrorActionPreference = 'Stop'
$AppRoot = Split-Path -Parent $PSScriptRoot
function New-AppSecret {
    $bytes = New-Object byte[] 24
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}
function Invoke-AppDocker {
    param([string[]]$DockerArguments)
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & docker @DockerArguments 2>&1 | ForEach-Object { $_.ToString() }
        $dockerExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($dockerExit -ne 0) { throw "Docker exited with code $dockerExit." }
}
function Invoke-AppCompose {
    param([string[]]$ComposeArguments)
    Invoke-AppDocker -DockerArguments (@('compose', '--project-name', 'timedesk-hris', '--project-directory', $AppRoot, '--file', (Join-Path $AppRoot 'compose.yml'), '--env-file', (Join-Path $AppRoot '.env')) + $ComposeArguments)
}
