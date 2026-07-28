# Start FinAlly. Builds the image only when it is missing or -Build is passed.
param([switch]$Build)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$image = "finally"
$container = "finally"
$volume = "finally-data"
$port = "8001"

$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "No .env found at $envFile"
    Write-Host "Copy .env.example to .env and add your OPENROUTER_API_KEY."
    exit 1
}

docker image inspect $image *> $null
$imageMissing = $LASTEXITCODE -ne 0

if ($Build -or $imageMissing) {
    Write-Host "Building image $image ..."
    docker build -t $image $root
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# Idempotent: drop any previous container, keep the data volume.
docker rm -f $container *> $null

docker run -d --name $container -p "${port}:8001" -v "${volume}:/app/db" --env-file $envFile $image *> $null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "FinAlly is starting at http://localhost:$port"
Write-Host "Logs:  docker logs -f $container"
Write-Host "Stop:  scripts\stop_windows.ps1"
