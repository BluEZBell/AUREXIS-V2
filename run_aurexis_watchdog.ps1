$logDir = "logs"
if (-not (Test-Path -Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logFile = "$logDir\watchdog.log"
$pythonExe = "python.exe"
$mainScript = "main.py"

Write-Output "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - AUREXIS Watchdog Started." | Out-File -FilePath $logFile -Append

while ($true) {
    Write-Output "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Launching AUREXIS Engine..." | Out-File -FilePath $logFile -Append
    
    # Start the python process and wait for it to exit
    $process = Start-Process -FilePath $pythonExe -ArgumentList $mainScript -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$logDir\aurexis_out.log" -RedirectStandardError "$logDir\aurexis_err.log"
    
    $exitCode = $process.ExitCode
    
    if ($exitCode -eq 0) {
        Write-Output "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - AUREXIS Engine exited gracefully (Code 0). Stopping watchdog." | Out-File -FilePath $logFile -Append
        break
    } else {
        Write-Output "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - 🚨 CRITICAL: AUREXIS Engine crashed with Exit Code $exitCode." | Out-File -FilePath $logFile -Append
        Write-Output "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Restarting in 5 seconds..." | Out-File -FilePath $logFile -Append
        Start-Sleep -Seconds 5
    }
}
