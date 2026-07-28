# Stop FinAlly. Removes the container, never the finally-data volume.
$ErrorActionPreference = "Stop"

$container = "finally"

docker container inspect $container *> $null
if ($LASTEXITCODE -eq 0) {
    docker rm -f $container *> $null
    Write-Host "Stopped and removed container $container"
} else {
    Write-Host "Container $container is not running"
}

Write-Host "Volume finally-data kept - your portfolio survives."
