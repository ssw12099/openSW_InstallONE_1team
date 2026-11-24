# Run as the consenting, ordinary Windows user. Downloads by default; fixed Python installation only with local approval.
param([string]$Server = '', [string]$Name = '', [switch]$AllowPythonInstall)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if (-not $Server) { $Server = Read-Host 'API URL (http://192.168.0.10:8000)' }
if (-not $Name) { $Name = Read-Host 'Registered PC name (pc01)' }
$Server = $Server.TrimEnd('/')
$Name = $Name.ToLowerInvariant()
if ($Name -notmatch '^[a-z0-9][a-z0-9_-]{0,63}$') { throw 'Invalid PC name' }
$secret = Read-Host 'PC-specific token' -AsSecureString
$token = [System.Net.NetworkCredential]::new('', $secret).Password
$headers = @{Authorization = "Bearer $token"}
$approvedHash = ''
if ($AllowPythonInstall) {
    . (Join-Path $PSScriptRoot 'install_python.ps1')
    Write-Host 'Optional per-user Python installation: approve only a trusted official installer SHA-256.'
    $approvedHash = (Read-Host 'Independently verified SHA-256 (64 hex characters)').Trim().ToLowerInvariant()
    if ($approvedHash -notmatch '^[a-f0-9]{64}$') { throw 'Invalid approved SHA-256' }
    if ((Read-Host 'Type INSTALL to approve this exact installer for this session') -cne 'INSTALL') { throw 'Installation not approved' }
    $headers['X-Approved-Python-Sha256'] = $approvedHash
}
$root = Join-Path $env:LOCALAPPDATA 'SoftwareDeploy'
New-Item -ItemType Directory -Path $root -Force | Out-Null
Write-Host "Polling $Server as $Name. Files: $root. Ctrl+C to stop."
$pending = $null
while ($true) {
    try {
        if ($null -eq $pending) {
            $response = Invoke-RestMethod -Uri "$Server/agents/$Name/poll" -Method Post -Headers $headers -TimeoutSec 15
            $task = $response.task
            if ($null -ne $task) {
                $ok = $false; $message = 'Download failed'; $tmp = $null
                $operation = if ($task.operation) { $task.operation } else { 'download' }
                try {
                    if ($task.file_id -notmatch '^[a-f0-9]{32}$' -or $task.filename -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,149}$' -or $task.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Invalid file metadata' }
                    if ($operation -notin @('download','install_python')) { throw 'Unknown operation' }
                    if ($operation -eq 'install_python' -and (-not $AllowPythonInstall -or $task.sha256 -ne $approvedHash -or $task.filename -cnotmatch '^python-3\.13\.\d+-amd64\.exe$')) { throw 'Installation not locally approved' }
                    if (-not $task.url.StartsWith("$Server/download/")) { throw 'Unexpected download server' }
                    $folder = Join-Path $root $task.file_id
                    New-Item -ItemType Directory -Path $folder -Force | Out-Null
                    $dest = Join-Path $folder $task.filename
                    $tmp = "$dest.part"
                    Invoke-WebRequest -UseBasicParsing -Uri $task.url -OutFile $tmp -TimeoutSec 600 -MaximumRedirection 0
                    if ((Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash -ne $task.sha256) { throw 'SHA256 mismatch' }
                    Move-Item -LiteralPath $tmp -Destination $dest -Force
                    Write-Host "Downloaded: $dest"
                    if ($operation -eq 'install_python') {
                        # The server can choose a file but cannot choose executable arguments.
                        $message = Install-ApprovedPython -Path $dest -ApprovedHash $approvedHash -FileName $task.filename
                        Write-Host $message
                    } else { $message = 'SHA256 verified; file saved' }
                    $ok = $true
                } catch {
                    if ($tmp -and (Test-Path -LiteralPath $tmp)) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
                    $message = 'Download/install/verification failed: ' + $_.Exception.Message
                    if ($message.Length -gt 500) { $message = $message.Substring(0,500) }
                    Write-Warning $message
                }
                $pending = @{id=$task.id; claim=$task.claim; success=$ok; log=$message}
            }
        }
        if ($null -ne $pending) {
            $body = @{claim=$pending.claim;success=$pending.success;log=$pending.log} | ConvertTo-Json -Compress
            try {
                Invoke-RestMethod -Uri "$Server/agents/$Name/tasks/$($pending.id)/result" -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 15 | Out-Null
                $pending = $null
            } catch {
                if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 409) { $pending = $null } else { throw }
            }
        }
    } catch { Write-Warning 'API unavailable or authentication failed; retrying.' }
    Start-Sleep -Seconds 5
}
