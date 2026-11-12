# Windows SDK / Build Tools read-only diagnostics for PEGINELAB.
# Windows PowerShell 5.1+ or PowerShell 7. No installs, writes, or PATH changes.
$ErrorActionPreference = 'Continue'
Write-Host '=== PEGINELAB Windows SDK Doctor ===' -ForegroundColor Cyan
Write-Host ('Windows: ' + [Environment]::OSVersion.VersionString)
Write-Host ('PowerShell: ' + $PSVersionTable.PSVersion)
Write-Host ('Architecture: ' + [Environment]::Is64BitOperatingSystem)

function Show-Command($label, $name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { Write-Host ('[OK] ' + $label + ': ' + $cmd.Source) -ForegroundColor Green }
    else { Write-Host ('[INFO] ' + $label + ' not in PATH') -ForegroundColor Yellow }
}
function Show-Files($label, [string[]]$paths) {
    $found = @($paths | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique)
    if ($found.Count) {
        Write-Host ('[OK] ' + $label + ':') -ForegroundColor Green
        $found | ForEach-Object { Write-Host ('    ' + $_) }
    } else { Write-Host ('[INFO] ' + $label + ' not found') -ForegroundColor Yellow }
}
$kitRoots = @()
foreach ($reg in @('HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows Kits\Installed Roots')) {
    if (Test-Path $reg) {
        $root = Get-ItemProperty -Path $reg -ErrorAction SilentlyContinue
        foreach ($name in @('KitsRoot10','KitsRoot81')) {
            if ($root -and $root.$name) { $kitRoots += $root.$name }
        }
    }
}
$kitRoots += @('C:\Program Files (x86)\Windows Kits\10\','F:\WindowsKits\10\','T:\WindowsKits\10\')
$kitRoots = @($kitRoots | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique)
Write-Host ''
Show-Files 'Windows Kits installation roots' $kitRoots
foreach ($root in $kitRoots) {
    Write-Host ('--- ' + $root)
    $inc = Join-Path $root 'Include'
    if (Test-Path $inc) {
        $versions = @(Get-ChildItem $inc -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending)
        foreach ($v in $versions) {
            $windowsH = Join-Path $v.FullName 'um\Windows.h'
            $lib64 = Join-Path (Join-Path $root 'Lib') ($v.Name + '\um\x64\kernel32.lib')
            Write-Host ('  SDK ' + $v.Name + ': Windows.h=' + (Test-Path $windowsH) + '; x64 kernel32.lib=' + (Test-Path $lib64))
        }
    }
    foreach ($tool in @('signtool.exe','wpr.exe','wpa.exe','windbg.exe')) {
        $hits = @(Get-ChildItem -Path $root -Filter $tool -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 3 -ExpandProperty FullName)
        if ($hits.Count) { Show-Files $tool $hits }
        else { Write-Host ('  [INFO] ' + $tool + ' not found under this Kit') }
    }
}
Write-Host ''
foreach ($tool in @('python','py','git','cl','link','signtool','wpr','wpa','windbg')) { Show-Command $tool $tool }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (Test-Path $vswhere) {
    Show-Files 'Visual Studio discovery tool' @($vswhere)
    & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
} else { Write-Host '[INFO] vswhere not found (Build Tools can still be installed)' }
Write-Host ''
Write-Host 'If cl.exe is not in PATH, open "x64 Native Tools Command Prompt for VS" and run: cl /Bv' -ForegroundColor Cyan
Write-Host 'Do not delete installed SDK folders based only on this report.' -ForegroundColor Cyan
