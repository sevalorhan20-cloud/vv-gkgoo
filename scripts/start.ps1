$ErrorActionPreference = "Stop"

try {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = $utf8
    $OutputEncoding = $utf8
}
catch {
    # Eski konsollarda kodlama ayarı başarısız olsa da başlatmaya devam edilir.
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDirectory = Split-Path -Parent $scriptDirectory
$environmentFile = Join-Path $rootDirectory ".env"
$environmentExample = Join-Path $rootDirectory ".env.example"
$frontendDirectory = Join-Path $rootDirectory "frontend"
$frontendOutput = Join-Path $frontendDirectory "dist\index.html"
$modelsDirectory = Join-Path $rootDirectory "models"
$dataDirectory = Join-Path $rootDirectory "data\projects"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Notice {
    param([string]$Message)
    Write-Host $Message -ForegroundColor DarkGray
}

function Stop-WithError {
    param([string]$Message)
    throw $Message
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError $FailureMessage
    }
}

function Update-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (($machinePath, $userPath) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ";"
}

function Install-WithWinget {
    param(
        [Parameter(Mandatory = $true)][string]$DisplayName,
        [Parameter(Mandatory = $true)][string]$PackageId
    )

    $wingetCommand = Get-Command "winget.exe" -ErrorAction SilentlyContinue
    if ($null -eq $wingetCommand) {
        Stop-WithError "$DisplayName bulunamadı ve Windows Paket Yöneticisi (winget) kurulu değil. $DisplayName bileşenini kurup bu dosyayı yeniden çalıştırın."
    }

    Write-Host "`n$DisplayName bulunamadı." -ForegroundColor Yellow
    $installReply = Read-Host "winget ile şimdi otomatik kurulsun mu? [E/h]"
    if (-not [string]::IsNullOrWhiteSpace($installReply) -and $installReply -notmatch "^(e|evet|y|yes)$") {
        Stop-WithError "$DisplayName olmadan KlipForge başlatılamaz. Kurduktan sonra bu dosyayı yeniden çalıştırın."
    }

    Write-Step "$DisplayName kuruluyor"
    Invoke-Checked -FilePath $wingetCommand.Source -Arguments @(
        "install", "--id", $PackageId, "-e",
        "--accept-package-agreements", "--accept-source-agreements"
    ) -FailureMessage "$DisplayName winget ile kurulamadı. Windows Paket Yöneticisi çıktısını kontrol edin."
    Update-ProcessPath
}

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    $existingVariables = [Environment]::GetEnvironmentVariables("Process")
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed.Split(@("="), 2, [System.StringSplitOptions]::None)
        if ($parts.Count -ne 2) {
            continue
        }

        $name = $parts[0].Trim()
        if ($name -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
            continue
        }

        if ($existingVariables.Contains($name)) {
            continue
        }

        $value = $parts[1].Trim()
        if ($value.Length -ge 2) {
            $firstCharacter = $value.Substring(0, 1)
            $lastCharacter = $value.Substring($value.Length - 1, 1)
            if (($firstCharacter -eq '"' -and $lastCharacter -eq '"') -or
                ($firstCharacter -eq "'" -and $lastCharacter -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Get-PythonLauncher {
    $pyCommand = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($null -ne $pyCommand) {
        & $pyCommand.Source -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return [PSCustomObject]@{
                FilePath = $pyCommand.Source
                Prefix = @("-3")
            }
        }
    }

    $pythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand) {
        & $pythonCommand.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return [PSCustomObject]@{
                FilePath = $pythonCommand.Source
                Prefix = @()
            }
        }
    }

    return $null
}

function Test-PythonImports {
    param(
        [string]$PythonPath,
        [string]$ImportCode
    )

    & $PythonPath -c $ImportCode *> $null
    return ($LASTEXITCODE -eq 0)
}

function Test-KlipForgeHealth {
    param([string]$HealthUrl)

    try {
        $health = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2 -UseBasicParsing
        return ($health.local_only -eq $true)
    }
    catch {
        return $false
    }
}

try {
    Set-Location -LiteralPath $rootDirectory

    Write-Host "KlipForge Local - Windows başlatıcı" -ForegroundColor Green
    Write-Notice "Bu pencere açık kaldığı sürece uygulama çalışır."

    if (-not (Test-Path -LiteralPath $environmentFile -PathType Leaf)) {
        if (-not (Test-Path -LiteralPath $environmentExample -PathType Leaf)) {
            Stop-WithError ".env.example dosyası bulunamadı. ZIP'i eksiksiz çıkardığınızdan emin olun."
        }
        Copy-Item -LiteralPath $environmentExample -Destination $environmentFile
        Write-Notice ".env yapılandırma dosyası oluşturuldu."
    }

    Import-DotEnv -Path $environmentFile

    $venvSetting = [Environment]::GetEnvironmentVariable("KLIPFORGE_VENV_DIR", "Process")
    if ([string]::IsNullOrWhiteSpace($venvSetting)) {
        $venvDirectory = Join-Path $rootDirectory ".venv"
    }
    elseif ([System.IO.Path]::IsPathRooted($venvSetting)) {
        $venvDirectory = [System.IO.Path]::GetFullPath($venvSetting)
    }
    else {
        $venvDirectory = [System.IO.Path]::GetFullPath((Join-Path $rootDirectory $venvSetting))
    }
    $venvPython = Join-Path $venvDirectory "Scripts\python.exe"

    $ffmpegCommand = Get-Command "ffmpeg.exe" -ErrorAction SilentlyContinue
    $ffprobeCommand = Get-Command "ffprobe.exe" -ErrorAction SilentlyContinue
    if ($null -eq $ffmpegCommand -or $null -eq $ffprobeCommand) {
        Install-WithWinget -DisplayName "FFmpeg" -PackageId "Gyan.FFmpeg"
        $ffmpegCommand = Get-Command "ffmpeg.exe" -ErrorAction SilentlyContinue
        $ffprobeCommand = Get-Command "ffprobe.exe" -ErrorAction SilentlyContinue
        if ($null -eq $ffmpegCommand -or $null -eq $ffprobeCommand) {
            Stop-WithError "FFmpeg kuruldu ancak bu terminalin PATH listesine henüz eklenmedi. Pencereyi kapatıp BASLAT-WINDOWS.bat dosyasına yeniden çift tıklayın."
        }
    }

    $didCreateEnvironment = $false
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        Write-Step "İlk kurulum: Python sanal ortamı hazırlanıyor"
        $pythonLauncher = Get-PythonLauncher
        if ($null -eq $pythonLauncher) {
            Install-WithWinget -DisplayName "Python 3.12" -PackageId "Python.Python.3.12"
            $pythonLauncher = Get-PythonLauncher
        }
        if ($null -eq $pythonLauncher) {
            Stop-WithError "Python kuruldu ancak bu terminal tarafından henüz görülemiyor. Pencereyi kapatıp BASLAT-WINDOWS.bat dosyasına yeniden çift tıklayın."
        }
        $venvArguments = @($pythonLauncher.Prefix) + @("-m", "venv", $venvDirectory)
        Invoke-Checked -FilePath $pythonLauncher.FilePath -Arguments $venvArguments -FailureMessage "Python sanal ortamı oluşturulamadı. Python kurulumunda venv bileşeninin bulunduğunu doğrulayın."
        $didCreateEnvironment = $true
    }

    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        Stop-WithError "Sanal ortam Python dosyası bulunamadı: $venvPython"
    }

    & $venvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Mevcut .venv Python 3.11 veya üstünü kullanmıyor. .venv klasörünü silip başlatıcıyı yeniden çalıştırın."
    }

    $runtimeReady = Test-PythonImports -PythonPath $venvPython -ImportCode "import fastapi, uvicorn, multipart, numpy"
    if (-not $runtimeReady) {
        Write-Step "İlk kurulum: yerel çalışma bileşenleri kuruluyor"
        Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip") -FailureMessage "pip güncellenemedi. İnternet bağlantınızı kontrol edin."

        try {
            Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", (Join-Path $rootDirectory "requirements-ai.txt")) -FailureMessage "AI bağımlılıkları kurulamadı."
        }
        catch {
            Write-Host "Uyarı: AI bileşenleri kurulamadı; temel sürüm kurulacak." -ForegroundColor Yellow
            Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", (Join-Path $rootDirectory "requirements.txt")) -FailureMessage "Python bağımlılıkları kurulamadı. İnternet bağlantınızı ve antivirüs ayarlarınızı kontrol edin."
        }
    }

    if (-not (Test-PythonImports -PythonPath $venvPython -ImportCode "import fastapi, uvicorn, multipart, numpy")) {
        Stop-WithError "Gerekli Python bileşenleri doğrulanamadı. .venv klasörünü silip yeniden deneyin."
    }

    if (-not (Test-Path -LiteralPath $frontendOutput -PathType Leaf)) {
        Write-Step "Arayüz hazırlanıyor"
        $nodeCommand = Get-Command "node.exe" -ErrorAction SilentlyContinue
        $npmCommand = Get-Command "npm" -ErrorAction SilentlyContinue
        if ($null -eq $nodeCommand -or $null -eq $npmCommand) {
            Stop-WithError "Arayüz çıktısı bulunamadı ve Node.js kurulu değil. https://nodejs.org/ adresinden LTS sürümünü kurup yeniden deneyin."
        }

        & $nodeCommand.Source -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit((a===20&&b>=19)||(a===22&&b>=12)||a>22?0:1)'
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "Node.js ^20.19 veya >=22.12 gerekli. Node.js LTS sürümünü güncelleyin."
        }

        $packageLock = Join-Path $frontendDirectory "package-lock.json"
        if (Test-Path -LiteralPath $packageLock -PathType Leaf) {
            Invoke-Checked -FilePath $npmCommand.Source -Arguments @("--prefix", $frontendDirectory, "ci", "--no-audit", "--no-fund") -FailureMessage "Frontend paketleri kurulamadı. İnternet bağlantınızı kontrol edin."
        }
        else {
            Invoke-Checked -FilePath $npmCommand.Source -Arguments @("--prefix", $frontendDirectory, "install", "--no-audit", "--no-fund") -FailureMessage "Frontend paketleri kurulamadı. İnternet bağlantınızı kontrol edin."
        }
        Invoke-Checked -FilePath $npmCommand.Source -Arguments @("--prefix", $frontendDirectory, "run", "build") -FailureMessage "Arayüz derlenemedi."
    }

    New-Item -ItemType Directory -Force -Path $dataDirectory, $modelsDirectory *> $null

    if ($didCreateEnvironment -and (Test-PythonImports -PythonPath $venvPython -ImportCode "import faster_whisper, huggingface_hub")) {
        $localModel = Get-ChildItem -LiteralPath $modelsDirectory -Filter "model.bin" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $localModel) {
            Write-Host "`nYerel Türkçe transkripsiyon ve daha iyi klip seçimi için yaklaşık 150 MB Whisper base modeli önerilir." -ForegroundColor Yellow
            $modelReply = Read-Host "Model şimdi indirilsin mi? [E/h]"
            if ([string]::IsNullOrWhiteSpace($modelReply) -or $modelReply -match "^(e|evet|y|yes)$") {
                Write-Step "Whisper base modeli indiriliyor"
                $modelDestination = Join-Path $modelsDirectory "faster-whisper-base"
                $downloadCode = @'
from pathlib import Path
import sys
from huggingface_hub import snapshot_download

target = Path(sys.argv[1]).resolve()
target.mkdir(parents=True, exist_ok=True)
snapshot_download(repo_id="Systran/faster-whisper-base", local_dir=str(target))
if not (target / "model.bin").is_file():
    raise SystemExit("model.bin bulunamadı")
'@
                try {
                    Invoke-Checked -FilePath $venvPython -Arguments @("-c", $downloadCode, $modelDestination) -FailureMessage "Whisper modeli indirilemedi."
                    Write-Host "Whisper modeli hazır." -ForegroundColor Green
                }
                catch {
                    Write-Host "Uyarı: Model indirilemedi. Uygulama yine açılacak; ancak konuşma analizi ve altyazı sınırlı olacak." -ForegroundColor Yellow
                }
            }
            else {
                Write-Notice "Model indirilmedi. Uygulama heuristik analiz modunda çalışacak."
            }
        }
    }

    $bindAddress = [Environment]::GetEnvironmentVariable("KLIPFORGE_HOST", "Process")
    if ([string]::IsNullOrWhiteSpace($bindAddress)) {
        $bindAddress = "127.0.0.1"
    }
    if ($bindAddress -notmatch "^[A-Za-z0-9.:-]+$") {
        Stop-WithError "Geçersiz KLIPFORGE_HOST değeri: $bindAddress"
    }

    $portText = [Environment]::GetEnvironmentVariable("KLIPFORGE_PORT", "Process")
    if ([string]::IsNullOrWhiteSpace($portText)) {
        $portText = "3210"
    }
    $portNumber = 0
    if (-not [int]::TryParse($portText, [ref]$portNumber) -or $portNumber -lt 1 -or $portNumber -gt 65535) {
        Stop-WithError "Geçersiz KLIPFORGE_PORT değeri: $portText"
    }

    if ($bindAddress -eq "0.0.0.0" -or $bindAddress -eq "::") {
        $browserAddress = "127.0.0.1"
    }
    elseif ($bindAddress.Contains(":")) {
        $browserAddress = "[$bindAddress]"
    }
    else {
        $browserAddress = $bindAddress
    }

    $applicationUrl = "http://$($browserAddress):$portNumber"
    $healthUrl = "$applicationUrl/api/health"

    if (Test-KlipForgeHealth -HealthUrl $healthUrl) {
        Write-Host "KlipForge zaten çalışıyor: $applicationUrl" -ForegroundColor Green
        Start-Process $applicationUrl
        exit 0
    }

    Write-Step "KlipForge başlatılıyor"
    Write-Host "Adres: $applicationUrl" -ForegroundColor Green
    Write-Host "Sunucuyu durdurmak için bu pencerede Ctrl+C tuşlarına basın." -ForegroundColor Yellow

    $browserWatcher = $null
    $watcherScript = Join-Path $scriptDirectory "wait-and-open.ps1"
    if (Test-Path -LiteralPath $watcherScript -PathType Leaf) {
        $powerShellExecutable = (Get-Process -Id $PID).Path
        $watcherArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$watcherScript`" -Url `"$applicationUrl`""
        $browserWatcher = Start-Process -FilePath $powerShellExecutable -ArgumentList $watcherArguments -WindowStyle Hidden -PassThru
    }

    $serverExitCode = 0
    try {
        $env:PYTHONUNBUFFERED = "1"
        & $venvPython -m uvicorn app.main:app --host $bindAddress --port $portNumber --workers 1
        $serverExitCode = $LASTEXITCODE
    }
    finally {
        if ($null -ne $browserWatcher -and -not $browserWatcher.HasExited) {
            Stop-Process -Id $browserWatcher.Id -Force -ErrorAction SilentlyContinue
        }
    }

    if ($serverExitCode -ne 0) {
        Stop-WithError "Sunucu beklenmedik biçimde kapandı (çıkış kodu: $serverExitCode). Portun başka bir uygulama tarafından kullanılmadığını kontrol edin."
    }
}
catch {
    Write-Host "`nHATA: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

exit 0
