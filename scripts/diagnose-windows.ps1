[CmdletBinding()]
param(
    [string]$Output,
    [ValidateRange(1, 65535)][int]$OllamaPort = 11434
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $Output) {
    $Output = Join-Path $root ".tm-law/hardware/windows-$([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')).json"
}
$reportPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)

function Read-ToolVersion([string]$Name) {
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $command) { return $null }
    $info = & $command.Source --version 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($info -join ' ').Trim()
}

function Read-OllamaStatus {
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $handler.AllowAutoRedirect = $false
    $client = New-Object System.Net.Http.HttpClient -ArgumentList $handler
    $client.Timeout = [TimeSpan]::FromSeconds(2)
    $baseUri = "http://127.0.0.1:$OllamaPort"
    $values = [ordered]@{
        endpoint = $baseUri
        version = $null
        installed_models = $null
        loaded_models = $null
        caller_no_cloud_environment = $env:OLLAMA_NO_CLOUD
        errors = [ordered]@{}
    }
    $fields = [ordered]@{ version = 'version'; tags = 'installed_models'; ps = 'loaded_models' }
    try {
        foreach ($operation in $fields.Keys) {
            try {
                $body = $client.GetStringAsync("$baseUri/api/$operation").GetAwaiter().GetResult()
                $payload = ConvertFrom-Json -InputObject $body
                if ($operation -eq 'version') {
                    if (-not $payload.version) { throw 'Missing version in the local response.' }
                    $values.version = $payload.version
                } else {
                    $models = @($payload.models | Where-Object {
                        $_.name -and $_.name -notmatch '(:cloud|-cloud)$' -and -not $_.remote_host -and -not $_.remote_model
                    })
                    $values[$fields[$operation]] = @($models | ForEach-Object {
                        [ordered]@{
                            tag = $_.name
                            digest = $_.digest
                            parameter_size = $_.details.parameter_size
                            quantization = $_.details.quantization_level
                            reported_size_bytes = $_.size
                            reported_vram_bytes = $_.size_vram
                        }
                    })
                }
            } catch {
                $values.errors[$operation] = $_.Exception.GetBaseException().Message
                if ($operation -eq 'version') { break }
            }
        }
    } finally {
        $client.Dispose()
    }
    return $values
}

$system = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$drive = (Get-Item -LiteralPath $root).PSDrive
Add-Type -AssemblyName System.Net.Http

$report = [ordered]@{
    schema = 1
    captured_utc = [DateTime]::UtcNow.ToString('o')
    os = [ordered]@{ name = $os.Caption; version = $os.Version; build = $os.BuildNumber; architecture = $os.OSArchitecture }
    computer_model = $system.Model
    cpu = @(Get-CimInstance Win32_Processor | ForEach-Object {
        [ordered]@{ name = $_.Name.Trim(); physical_cores = $_.NumberOfCores; logical_processors = $_.NumberOfLogicalProcessors }
    })
    gpu = @(Get-CimInstance Win32_VideoController | ForEach-Object {
        [ordered]@{ name = $_.Name; driver_version = $_.DriverVersion }
    })
    memory = [ordered]@{
        physical_bytes = [long]$system.TotalPhysicalMemory
        os_visible_bytes = [long]$os.TotalVisibleMemorySize * 1024
        os_free_bytes = [long]$os.FreePhysicalMemory * 1024
        os_used_bytes = ([long]$os.TotalVisibleMemorySize - [long]$os.FreePhysicalMemory) * 1024
    }
    repository_drive = [ordered]@{ used_bytes = $drive.Used; free_bytes = $drive.Free }
    tools = [ordered]@{
        powershell = $PSVersionTable.PSVersion.ToString()
        python = (Read-ToolVersion 'python.exe')
        uv = (Read-ToolVersion 'uv.exe')
        node = (Read-ToolVersion 'node.exe')
        npm = (Read-ToolVersion 'npm.cmd')
        git = (Read-ToolVersion 'git.exe')
        ollama = (Read-ToolVersion 'ollama.exe')
    }
    vulkan = [ordered]@{
        system_loader_present = (Test-Path -LiteralPath (Join-Path $env:SystemRoot 'System32/vulkan-1.dll'))
        diagnostic_tool_present = [bool](Get-Command vulkaninfo.exe -CommandType Application -ErrorAction SilentlyContinue)
    }
    ollama = (Read-OllamaStatus)
}

$null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportPath)
$stream = [System.IO.File]::Open($reportPath, [System.IO.FileMode]::CreateNew)
try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($report | ConvertTo-Json -Depth 8) + [Environment]::NewLine)
    $stream.Write($bytes, 0, $bytes.Length)
} finally {
    $stream.Dispose()
}
Write-Host "Local diagnostics: $reportPath"
