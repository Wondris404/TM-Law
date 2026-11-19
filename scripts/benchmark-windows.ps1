[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$')][string]$Model,
    [ValidateSet(2048, 4096, 8192)][int[]]$Contexts = @(2048),
    [ValidateSet('auto', 'on', 'off')][string[]]$Reasoning = @('auto'),
    [ValidateRange(1, 5)][int]$Repeats = 2,
    [ValidateRange(64, 4096)][int]$MaxTokens = 768,
    [ValidateRange(0.0, 1.0)][double]$Temperature = 0.15,
    [ValidateSet('auto', 'cpu')][string]$Device = 'cpu',
    [int]$Threads = 0,
    [string]$Cases,
    [string]$DataDir,
    [string]$Output
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $uv = Get-Command uv -CommandType Application -ErrorAction Stop
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        throw 'Prepare the virtual environment first with uv sync --locked.'
    }
    if (-not $Output) {
        $null = New-Item -ItemType Directory -Force -Path '.tm-law/benchmarks'
        $Output = ".tm-law/benchmarks/run-$([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')).json"
    }
    $options = @(
        'run', '--locked', '--offline', '--no-sync', 'python', '-m', 'scripts.benchmark',
        '--model', $Model, '--device', $Device, '--repeats', $Repeats,
        '--max-tokens', $MaxTokens,
        '--temperature', $Temperature.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--measure-memory', '--summary', '--output', $Output
    )
    if ($PSBoundParameters.ContainsKey('Threads')) {
        if ($Threads -lt 1 -or $Threads -gt 256) { throw 'Threads must be an integer from 1 to 256.' }
        $options += @('--num-threads', $Threads)
    }
    foreach ($context in $Contexts) { $options += @('--context-window', $context) }
    foreach ($mode in $Reasoning) { $options += @('--reasoning', $mode) }
    if ($Cases) { $options += @('--cases', $Cases) }
    if ($DataDir) { $options += @('--data-dir', $DataDir) }
    & $uv.Source @options
    $benchmarkExit = $LASTEXITCODE
    if (Test-Path -LiteralPath $Output) { Write-Host "Benchmark report: $Output" }
    if ($benchmarkExit -ne 0) { throw 'Benchmark failed or at least one run did not complete.' }
} finally {
    Pop-Location
}
