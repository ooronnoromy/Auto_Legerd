param([string]$Python = '', [int]$Port = 8000)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if (-not $Python) {
        $python312 = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
        $Python = if (Test-Path -LiteralPath $python312) { $python312 } else { 'python' }
    }
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install project dependencies.' }
& $venvPython manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Database setup failed. Check your .env database settings.' }
& $venvPython manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Project checks failed.' }
& $venvPython manage.py collectstatic --noinput
if ($LASTEXITCODE -ne 0) { throw 'Static asset setup failed.' }
Write-Host "Open http://127.0.0.1:$Port/"
Write-Host 'To create an administrator in another terminal: .\.venv\Scripts\python.exe manage.py createsuperuser'
& $venvPython manage.py runserver "127.0.0.1:$Port"
