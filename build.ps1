$ErrorActionPreference = 'Stop'
$sourceRoot = $PSScriptRoot
$buildDependencies = Join-Path $sourceRoot '.build-deps'
python -m pip install --target $buildDependencies -r (Join-Path $sourceRoot 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'Build dependencies failed.' }
$env:PYTHONPATH = $buildDependencies
python -m PyInstaller --noconfirm --clean --onefile --windowed --name MalHani-Launcher-Setup --icon (Join-Path $sourceRoot 'launcher/icon.png') --add-data ((Join-Path $sourceRoot 'launcher') + ';launcher') --add-data ((Join-Path $sourceRoot 'bundled-tools') + ';bundled-tools') --add-data ((Join-Path $sourceRoot 'LICENSE') + ';.') --add-data ((Join-Path $sourceRoot 'NOTICE.md') + ';.') --distpath (Join-Path $sourceRoot 'dist') --workpath (Join-Path $sourceRoot '.build') --specpath (Join-Path $sourceRoot '.build') (Join-Path $sourceRoot 'installer.py')
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Get-FileHash -LiteralPath (Join-Path $sourceRoot 'dist/MalHani-Launcher-Setup.exe') -Algorithm SHA256
