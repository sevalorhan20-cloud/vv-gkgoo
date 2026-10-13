param(
    [Parameter(Mandatory = $true)]
    [string]$Url
)

$ErrorActionPreference = "SilentlyContinue"
$healthUrl = "$($Url.TrimEnd('/'))/api/health"
$deadline = (Get-Date).AddSeconds(120)

while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2 -UseBasicParsing
        if ($health.local_only -eq $true) {
            Start-Process $Url
            exit 0
        }
    }
    catch {
        # Sunucu ilk çalıştırmada bağımlılıkları ve yerel veriyi hazırlıyor olabilir.
    }

    Start-Sleep -Milliseconds 500
}

exit 1
