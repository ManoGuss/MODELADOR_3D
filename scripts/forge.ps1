param([ValidateSet('install','run','dev','test','build','diagnostics')][string]$Action='run')
$ErrorActionPreference='Stop'
$repoRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoRoot
function Invoke-Checked([string]$Executable,[string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Comando falhou: $Executable ($LASTEXITCODE)" }
}
$runtimeRoot=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
$pythonCommand=Get-Command python -ErrorAction SilentlyContinue
$pythonBase=if($env:FORGE_PYTHON){$env:FORGE_PYTHON}elseif($pythonCommand){$pythonCommand.Source}else{Join-Path $runtimeRoot 'python\python.exe'}
$nodeCommand=Get-Command node -ErrorAction SilentlyContinue
$nodeExe=if($env:FORGE_NODE){$env:FORGE_NODE}elseif($nodeCommand){$nodeCommand.Source}else{Join-Path $runtimeRoot 'node\bin\node.exe'}
if(Test-Path -LiteralPath $nodeExe){$env:PATH=(Split-Path $nodeExe -Parent)+';'+$env:PATH}
$pnpmCommand=Get-Command pnpm -ErrorAction SilentlyContinue
$pnpmExe=if($pnpmCommand){$pnpmCommand.Source}else{Join-Path $runtimeRoot 'bin\fallback\pnpm.cmd'}
$pythonExe=Join-Path $repoRoot '.venv\Scripts\python.exe'
$env:FORGE_LOCAL_ONLY='true'
switch($Action){
 'install' {
    Invoke-Checked $pythonBase @('-m','venv','.venv')
    Invoke-Checked $pythonExe @('-m','pip','install','-r','backend/requirements.lock.txt')
    Push-Location frontend
    try { Invoke-Checked $pnpmExe @('install','--frozen-lockfile') } finally { Pop-Location }
 }
 'build' { Push-Location frontend; try { Invoke-Checked $pnpmExe @('run','build') } finally { Pop-Location } }
 'test' {
    Invoke-Checked $pythonExe @('-m','pytest','tests','-q')
    Push-Location frontend
    try { Invoke-Checked $pnpmExe @('test') } finally { Pop-Location }
 }
 'run' {
    if(!(Test-Path frontend/dist/index.html)){throw 'Execute .\scripts\forge.ps1 build primeiro.'}
    Write-Host 'FORGE: http://127.0.0.1:8765 · Ctrl+C para encerrar'
    Invoke-Checked $pythonExe @('-m','uvicorn','backend.main:create_app','--factory','--host','127.0.0.1','--port','8765')
 }
 'dev' {
    $server=Start-Process -FilePath $pythonExe -ArgumentList '-m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8765' -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden
    try { Push-Location frontend; Invoke-Checked $pnpmExe @('dev') } finally { Pop-Location; if(!$server.HasExited){Stop-Process -Id $server.Id} }
 }
 'diagnostics' { Invoke-Checked $pythonExe @('-c','from pathlib import Path; from backend.diagnostics import diagnostics; import json; print(json.dumps(diagnostics(Path.cwd()), indent=2, ensure_ascii=False))') }
}
