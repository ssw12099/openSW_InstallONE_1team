# InstallONE: 좌석 PC(테스트 VM)에서 원격 설치(WinRM)를 허용하는 설정
# VM 안에서 "관리자 권한 PowerShell"로 실행하세요. 테스트용 VM에서만 쓰세요.
# 참고: Ansible 문서 "Windows Remote Management" > WinRM Setup

# 1) WinRM 서비스와 HTTP(5985) 리스너 켜기 (VM 네트워크가 '공용'으로 잡혀 있어도 진행)
Enable-PSRemoting -Force -SkipNetworkProfileCheck

# 2) 방화벽에서 5985 포트 열기 (모든 네트워크 프로필)
if (-not (Get-NetFirewallRule -Name "InstallONE-WinRM-HTTP" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name "InstallONE-WinRM-HTTP" -DisplayName "Windows Remote Management (HTTP-In) - InstallONE" `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5985 -Profile Any | Out-Null
}

# 3) 로컬 관리자 계정이 원격에서도 관리자 권한을 쓰도록 허용
New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" `
    -Name LocalAccountTokenFilterPolicy -Value 1 -PropertyType DWORD -Force | Out-Null

# 확인: 리스너 목록과 이 VM의 IP 주소 (seats.yml의 host에 적을 값)
winrm enumerate winrm/config/Listener
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
    Select-Object InterfaceAlias, IPAddress
