[CmdletBinding()]
param(
    [switch]$Mock,
    [switch]$NoBrowser,
    [switch]$SmokeTest,
    [ValidateRange(1024, 65535)][int]$Port = 8000,
    [string]$Model,
    [string]$DataDir
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$client = $null
$server = $null
$original = @{
    TM_LAW_ADAPTER = $env:TM_LAW_ADAPTER
    TM_LAW_DATA_DIR = $env:TM_LAW_DATA_DIR
    TM_LAW_MODEL = $env:TM_LAW_MODEL
}

function Read-LocalJson([string]$Uri) {
    $response = $client.GetAsync($Uri).GetAwaiter().GetResult()
    try {
        $null = $response.EnsureSuccessStatusCode()
        $result = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        return (ConvertFrom-Json -InputObject $result)
    } finally {
        $response.Dispose()
    }
}

Push-Location $root
try {
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Python virtual environment missing. Run uv sync --locked from this repository first.'
    }
    if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) {
        throw 'Frontend build missing. Run npm.cmd --prefix frontend ci and npm.cmd --prefix frontend run build.'
    }
    if (-not $DataDir) {
        $DataDir = if ($Mock) { '.tm-law/demo' } else { '.tm-law/praca' }
    }
    $env:TM_LAW_DATA_DIR = $DataDir

    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $handler.AllowAutoRedirect = $false
    $client = New-Object System.Net.Http.HttpClient -ArgumentList $handler
    $client.Timeout = [TimeSpan]::FromSeconds(2)

    if ($Mock) {
        $env:TM_LAW_ADAPTER = 'mock'
        foreach ($fixture in @('data/demo-2022.json', 'data/demo-2024.json')) {
            & $python -m scripts.import_legal $fixture --data-dir $DataDir
            if ($LASTEXITCODE -ne 0) { throw 'Mock fixture import failed.' }
        }
    } else {
        $env:TM_LAW_ADAPTER = 'ollama'
        $runtime = $env:TM_LAW_OLLAMA_URL
        if (-not $runtime) { $runtime = 'http://127.0.0.1:11434' }
        if ($runtime -notmatch '^http://(127\.0\.0\.1|localhost|\[::1\])(?::([1-9][0-9]{0,4}))?/?$') {
            throw 'TM_LAW_OLLAMA_URL must be a local HTTP URL without a path.'
        }
        $hostName = if ($Matches[1] -eq '[::1]') { '[::1]' } else { '127.0.0.1' }
        $runtimePort = if ($Matches[2]) { [int]$Matches[2] } else { 11434 }
        if ($runtimePort -gt 65535) { throw 'Invalid local Ollama port.' }
        try {
            $tags = Read-LocalJson ("http://{0}:{1}/api/tags" -f $hostName, $runtimePort)
        } catch {
            throw 'Local Ollama is unavailable. Start ollama serve in another terminal and try again.'
        }
        $localModels = @($tags.models | Where-Object {
            $_.name -and $_.name -notmatch '(:cloud|-cloud)$' -and -not $_.remote_host -and -not $_.remote_model
        } | ForEach-Object { $_.name })
        if (-not $localModels.Count) {
            throw 'No local model installed. Download one explicitly with ollama pull qwen3.5:4b.'
        }
        if (-not $Model) { $Model = $env:TM_LAW_MODEL }
        if (-not $Model) {
            $Model = if ('qwen3.5:4b' -in $localModels) { 'qwen3.5:4b' } else { $localModels[0] }
        }
        if ($Model -cnotin $localModels -and ("${Model}:latest") -cnotin $localModels) {
            throw 'Requested model is missing from the local Ollama model list.'
        }
        $env:TM_LAW_MODEL = $Model
        Write-Host "Local model: $Model"
    }

    $url = "http://127.0.0.1:$Port"
    $server = Start-Process -FilePath $python -WorkingDirectory $root -ArgumentList @(
        '-m', 'uvicorn', 'backend.tm_law.api:app', '--host', '127.0.0.1', '--port', $Port,
        '--no-access-log'
    ) -NoNewWindow -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($server.HasExited) {
            throw "Backend exited with code $($server.ExitCode). Review its output above."
        }
        try {
            $health = Read-LocalJson "$url/api/health"
            $ready = $health.status -eq 'ok' -and $health.simulated -eq [bool]$Mock
        } catch {
            $ready = $false
        }
        if ($ready) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw 'Backend did not become ready at the local address.' }

    $frontend = $client.GetAsync($url).GetAwaiter().GetResult()
    try {
        $null = $frontend.EnsureSuccessStatusCode()
    } finally {
        $frontend.Dispose()
    }
    Write-Host "TM-Law v$($health.version) is ready at $url"
    if (-not $SmokeTest) {
        if (-not $NoBrowser) { Start-Process $url }
        Write-Host 'Press Ctrl+C to stop TM-Law.'
        while (-not $server.WaitForExit(500)) { }
        if ($server.ExitCode -ne 0) { throw "Backend exited with code $($server.ExitCode)." }
    }
} finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -InputObject $server -ErrorAction SilentlyContinue
    }
    if ($client) { $client.Dispose() }
    foreach ($entry in $original.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
    Pop-Location
}
