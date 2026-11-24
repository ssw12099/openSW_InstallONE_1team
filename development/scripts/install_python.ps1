# SSH 대상 Windows VM에서만 실행. AI/요청 문자열은 입력받지 않는다.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$version = '3.14.7'
$target = Join-Path $env:LOCALAPPDATA 'InstallONE\Python314'
$python = Join-Path $target 'python.exe'
$stage = 'install_failed'
$reused = $false
$installer = $null
try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'x64 Windows required' }
    if (Test-Path -LiteralPath $python) {
        $reused = $true
    } else {
        if (Test-Path -LiteralPath $target) { throw 'Existing incomplete installation; inspect manually' }
        $installer = Join-Path $env:TEMP ('installone-' + [guid]::NewGuid().ToString() + '.exe')
        Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe' -OutFile $installer
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Python Software Foundation(?:,|$)') {
            throw 'Installer signature invalid'
        }
        $arguments = '/quiet InstallAllUsers=0 Include_launcher=0 Include_test=0 PrependPath=0 AssociateFiles=0 Shortcuts=0 Include_pip=1 TargetDir="' + $target + '"'
        $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
        if ($process.ExitCode -notin @(0, 3010)) { throw 'Installer failed' }
    }
    $stage = 'verification_failed'
    # 전용 경로의 기존 설치도 동일하게 검증. 다른 버전이면 덮어쓰지 않는다.
    $actualVersion = & $python -I -c 'import platform; print(platform.python_version())'
    if ($LASTEXITCODE -ne 0 -or $actualVersion -ne $version) { throw 'Version mismatch' }
    $example = & $python -I -c 'print(sum([20,22]))'
    if ($LASTEXITCODE -ne 0 -or $example -ne '42') { throw 'Example failed' }
    & $python -I -m pip --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'pip unavailable' }
    @{status='verified'; version=$actualVersion; example=$example; reused=$reused} | ConvertTo-Json -Compress
    exit 0
} catch {
    @{status=$stage; version=''; example=''; reused=$reused} | ConvertTo-Json -Compress
    exit 1
} finally {
    # 이 실행이 생성한 단일 임시 설치 파일만 정리한다.
    if ($installer -and (Test-Path -LiteralPath $installer)) { Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue }
}
