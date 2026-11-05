param([switch]$Once)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw '먼저 README의 가상환경 설치를 진행하세요.' }
if (!(Test-Path -LiteralPath 'models\final-stockpilot-news-v1\model.safetensors')) { throw '별도 모델을 models\final-stockpilot-news-v1에 배치하세요.' }
$temporarySecrets=@()
try {
    foreach ($name in @('NAVER_CLIENT_ID','NAVER_CLIENT_SECRET','STOCKPILOT_DB_PASSWORD')) {
        if (![Environment]::GetEnvironmentVariable($name,'Process')) {
            $secret=Read-Host "$name 입력 (화면에 표시되지 않음)" -AsSecureString
            $credential=New-Object System.Management.Automation.PSCredential('input',$secret)
            [Environment]::SetEnvironmentVariable($name,$credential.GetNetworkCredential().Password,'Process')
            $temporarySecrets+=$name
        }
    }
    $env:PYTHONUTF8='1'
    & $python check_db.py
    if ($LASTEXITCODE -ne 0) { throw 'DB 연결 또는 테이블 확인 실패. 환경변수와 sql/schema.sql을 확인하세요.' }
    $workerArguments=@('multi_worker.py','--model','models/final-stockpilot-news-v1','--interval-minutes','15','--pages','1')
    if ($Once) { $workerArguments+='--once' }
    & $python @workerArguments
    if ($LASTEXITCODE -ne 0) { throw '실행 실패. data/live200/status.json을 확인하세요.' }
} finally {
    foreach ($name in $temporarySecrets) { [Environment]::SetEnvironmentVariable($name,$null,'Process') }
}
