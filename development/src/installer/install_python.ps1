# Called only by the consenting user's agent. No server-provided commands or arguments.
function Install-ApprovedPython {
    param([string]$Path, [string]$ApprovedHash, [string]$FileName)
    if ($FileName -cnotmatch '^python-(3\.13\.\d+)-amd64\.exe$') { throw 'Unsupported Python installer filename' }
    $version = $Matches[1]
    if ($ApprovedHash -notmatch '^[a-fA-F0-9]{64}$' -or (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $ApprovedHash) { throw 'Installer is not locally approved' }
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { throw 'Windows x64 required' }
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -ne 'Python Software Foundation') { throw 'Python Software Foundation signature required' }
    # Standard per-user destination. Do not accept executable paths or arguments from the API.
    $target = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313'
    $python = Join-Path $target 'python.exe'
    if (Test-Path -LiteralPath $python) {
        $existing = & $python -I --version 2>&1
        if ($LASTEXITCODE -ne 0 -or "$existing" -ne "Python $version") { throw 'Different Python already exists; review locally before installing' }
    } else {
        # Reject an unexpected existing directory, including stale or partial installations.
        if (Test-Path -LiteralPath $target) { throw 'Existing target directory requires local review' }
        $args = @('/quiet','InstallAllUsers=0','Include_launcher=0','Include_test=0','PrependPath=1',"TargetDir=`"$target`"")
        $process = Start-Process -FilePath $Path -ArgumentList $args -WorkingDirectory (Split-Path -Parent $Path) -Wait -PassThru
        if ($process.ExitCode -ne 0) { throw "Installer exit code $($process.ExitCode); review locally" }
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Installed python.exe not found' }
    $actual = & $python -I --version 2>&1
    if ($LASTEXITCODE -ne 0 -or "$actual" -ne "Python $version") { throw 'Installed Python version mismatch' }
    $example = & $python -I -c 'print(1+1)' 2>&1
    if ($LASTEXITCODE -ne 0 -or "$example" -ne '2') { throw 'Python execution verification failed' }
    return "Installed/verified Python $version; example=2"
}
