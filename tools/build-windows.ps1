[CmdletBinding()]
param(
    [ValidateSet('all', 'cpp', 'cclab', 'kv-store', 'query-engine', 'thread-pool', 'rlab', 'rdb', 'toydb')]
    [string]$Project = 'cpp',
    [ValidateSet('Debug', 'Release', 'RelWithDebInfo')]
    [string]$Configuration = 'Debug',
    [string]$BuildRoot = (Join-Path $env:LOCALAPPDATA 'xlab-build'),
    [string]$Generator,
    [ValidateRange(1, 64)]
    [int]$Jobs = 4,
    [switch]$Benchmarks,
    [switch]$NoFetch,
    [switch]$Clean,
    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
# Avoid the literal dollar sign in Ninja rules generated for the WSL share.
if ($repoRoot.StartsWith('\\wsl$\', [StringComparison]::OrdinalIgnoreCase)) {
    $repoRoot = '\\wsl.localhost\' + $repoRoot.Substring(7)
}
$BuildRoot = [System.IO.Path]::GetFullPath($BuildRoot)

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    Write-Host ('> {0} {1}' -f $Executable, ($Arguments -join ' '))
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE"
    }
}

function Find-VisualStudio {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    if (Test-Path -LiteralPath $vswhere) {
        $instances = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json
        if ($LASTEXITCODE -eq 0) {
            return ($instances | ConvertFrom-Json | Select-Object -First 1)
        }
    }
    return $null
}

function Build-Cpp {
    param([string]$Name)
    $vs = Find-VisualStudio
    $cmakeCommand = Get-Command cmake -ErrorAction SilentlyContinue
    if ($cmakeCommand) {
        $cmake = $cmakeCommand.Source
    } elseif ($vs) {
        $cmake = Join-Path $vs.installationPath 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
    } else {
        throw 'Install Visual Studio with Desktop development with C++, or add CMake and your compiler to PATH.'
    }
    if (-not (Test-Path -LiteralPath $cmake)) {
        throw 'CMake was not found. Add the C++ CMake tools component in Visual Studio Installer.'
    }
    $ctest = Join-Path (Split-Path $cmake -Parent) 'ctest.exe'
    $selectedGenerator = $Generator
    if (-not $selectedGenerator) {
        if (-not $vs) { throw 'Pass -Generator for a non-Visual-Studio compiler.' }
        $selectedGenerator = 'Ninja'
    }
    $originalEnvironment = @{}
    $originalEnvironment['VSLANG'] = [Environment]::GetEnvironmentVariable('VSLANG', 'Process')
    try {
        $env:VSLANG = '1033'
        if ($selectedGenerator -like 'Ninja*' -and $vs) {
            $devCmd = Join-Path $vs.installationPath 'Common7/Tools/VsDevCmd.bat'
            $commandLine = 'call "{0}" -no_logo -arch=x64 -host_arch=x64 >nul && set' -f $devCmd
            Push-Location $env:TEMP
            try { $environmentLines = & $env:ComSpec /d /c $commandLine }
            finally { Pop-Location }
            if ($LASTEXITCODE -ne 0) { throw 'Failed to initialize the MSVC environment.' }
            foreach ($line in $environmentLines) {
                $separator = $line.IndexOf('=')
                if ($separator -gt 0) {
                    $key = $line.Substring(0, $separator)
                    if (-not $originalEnvironment.ContainsKey($key)) {
                        $originalEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
                    }
                    [Environment]::SetEnvironmentVariable($key, $line.Substring($separator + 1), 'Process')
                }
            }
        }
        $env:VSLANG = '1033'
        $source = $repoRoot
        if ($Name -eq 'cclab') { $source = Join-Path $repoRoot 'cc/cclab' }
        elseif ($Name -ne 'cpp') { $source = Join-Path $repoRoot "cc/projects/$Name" }
        $generatorName = $selectedGenerator -replace '[^A-Za-z0-9]+', '-'
        $build = Join-Path $BuildRoot "cpp/$Name-$generatorName-native"
        $configure = @('-S', $source, '-B', $build, '-G', $selectedGenerator,
            "-DCMAKE_BUILD_TYPE=$Configuration", "-DXLAB_FETCH_DEPENDENCIES=$(-not $NoFetch)",
            "-DXLAB_BUILD_BENCHMARKS=$([bool]$Benchmarks)", "-DBUILD_TESTING=$(-not $SkipTests)")
        if ($selectedGenerator -like 'Visual Studio*') { $configure += @('-A', 'x64') }
        if ($selectedGenerator -like 'Ninja*' -and $vs) {
            $ninja = Join-Path $vs.installationPath 'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe'
            if (Test-Path -LiteralPath $ninja) { $configure += "-DCMAKE_MAKE_PROGRAM=$ninja" }
            $compilerDirectory = Split-Path (Get-Command cl -ErrorAction Stop).Source -Parent
            if ((Test-Path (Join-Path $compilerDirectory '2052')) -and
                -not (Test-Path (Join-Path $compilerDirectory '1033'))) {
                # CMake may misdecode /showIncludes when only Chinese compiler resources exist.
                $prefix = -join ([char[]](0x6CE8, 0x610F, 0x003A, 0x0020, 0x5305,
                    0x542B, 0x6587, 0x4EF6, 0x003A, 0x0020))
                $configure += "-DXLAB_MSVC_SHOWINCLUDES_PREFIX=$prefix"
            }
        }
        if ($Name -eq 'cclab') { $configure += '-DCCLAB_PORTABLE_ONLY=ON' }
        Invoke-Checked $cmake $configure
        $buildArguments = @('--build', $build, '--config', $Configuration, '--parallel', "$Jobs")
        if ($Clean) { $buildArguments += '--clean-first' }
        Invoke-Checked $cmake $buildArguments
        if (-not $SkipTests) {
            Invoke-Checked $ctest @('--test-dir', $build, '-C', $Configuration,
                '--output-on-failure', '--no-tests=error', '--timeout', '60')
        }
        Write-Host "C++ outputs: $build"
    } finally {
        foreach ($key in $originalEnvironment.Keys) {
            [Environment]::SetEnvironmentVariable($key, $originalEnvironment[$key], 'Process')
        }
    }
}

function Build-Rust {
    param([string]$Name)
    $cargo = (Get-Command cargo -ErrorAction Stop).Source
    $manifest = Join-Path $repoRoot "rust/$Name/Cargo.toml"
    $arguments = @('--manifest-path', $manifest, '--target-dir', (Join-Path $BuildRoot "rust/$Name"))
    if ($Name -eq 'rlab') { $arguments += '--workspace' }
    if ($Configuration -eq 'Release') { $arguments += '--release' }
    Invoke-Checked $cargo (@('build') + $arguments)
    if (-not $SkipTests) { Invoke-Checked $cargo (@('test') + $arguments) }
}

function Build-ToyDb {
    $python = (Get-Command python -ErrorAction Stop).Source
    $environment = Join-Path $BuildRoot 'python/toydb-venv'
    $venvPython = Join-Path $environment 'Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Invoke-Checked $python @('-m', 'venv', $environment)
    }
    $source = Join-Path $repoRoot 'python/projects/py-toydb'
    Invoke-Checked $venvPython @('-m', 'pip', 'install', '-e', $source, 'pytest')
    if (-not $SkipTests) {
        Invoke-Checked $venvPython @('-m', 'pytest', (Join-Path $source 'tests'), '-q')
    }
}

$projects = @($Project)
if ($Project -eq 'all') { $projects = @('cpp', 'rlab', 'rdb', 'toydb') }
$failures = @()
foreach ($name in $projects) {
    try {
        switch ($name) {
            'rlab' { Build-Rust $name }
            'rdb' { Build-Rust $name }
            'toydb' { Build-ToyDb }
            default { Build-Cpp $name }
        }
    } catch {
        $failures += $name
        Write-Warning "${name}: $($_.Exception.Message)"
    }
}
if ($failures.Count -gt 0) { throw "Failed projects: $($failures -join ', ')" }
Write-Host "Completed: $($projects -join ', ')"
