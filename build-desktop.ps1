# Construieste aplicatia Windows de sine statatoare.
#
#   .\build-desktop.ps1
#
# Rezultatul: dist-desktop\Argus Custode\  (folder cu .exe) si Argus-Custode-windows.zip
#
# Mod one-folder cu buna stiinta: --onefile dezarhiveaza ~300MB in temp la FIECARE pornire,
# adica 10-20s de asteptare de fiecare data, si e forma care declanseaza cel mai des
# euristica antivirusului.

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$frontend = Join-Path $root 'app\frontend'
$iesire = Join-Path $root 'dist-desktop'

if (-not (Test-Path $python)) {
    Write-Error "Nu gasesc mediul virtual la $python. Creeaza-l intai: python -m venv .venv"
}

Write-Host "1/4  Verific dependentele de impachetare..." -ForegroundColor Cyan
& $python -c "import PyInstaller, webview" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "     lipsesc, le instalez..."
    & $python -m pip install -r (Join-Path $root 'app\requirements-desktop.txt') | Out-Null
}

Write-Host "2/4  Construiesc frontendul in modul desktop (aceeasi origine)..." -ForegroundColor Cyan
Push-Location $frontend
try {
    if (-not (Test-Path 'node_modules')) { npm install | Out-Null }
    # --mode desktop fixeaza VITE_API_BASE pe sirul gol. Fara el, aplicatia ar cere de la
    # 127.0.0.1:8000 in loc de portul pe care ruleaza chiar ea, si harta ar ramane goala.
    npx vite build --mode desktop | Out-Null
}
finally { Pop-Location }

$bundle = Get-ChildItem (Join-Path $frontend 'dist\assets') -Filter '*.js' | Select-Object -First 1
if ($bundle -and (Select-String -Path $bundle.FullName -Pattern '127\.0\.0\.1:8000' -Quiet)) {
    Write-Error "Bundle-ul contine adresa absoluta de dezvoltare: modul desktop nu a prins."
}
Write-Host "     frontend gata, fara adrese absolute." -ForegroundColor Green

Write-Host "3/4  Impachetez cu PyInstaller (dureaza cateva minute)..." -ForegroundColor Cyan
& $python -m PyInstaller (Join-Path $root 'desktop\argus.spec') --noconfirm `
    --distpath $iesire --workpath (Join-Path $root 'build-desktop')
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller a esuat." }

Write-Host "4/4  Verific pachetul construit..." -ForegroundColor Cyan
# Nu se raporteaza succes fara proba: testul porneste executabilul si ii cere un TILE, ceea
# ce trece prin rasterio, DLL-urile de GDAL si proj.db. Un build care porneste dar nu poate
# reproiecta arata identic cu unul bun pana la primul tile.
& $python -m pytest (Join-Path $root 'tests\test_desktop_bundle.py') -q
if ($LASTEXITCODE -ne 0) { Write-Error "Pachetul s-a construit dar nu trece testele." }

$zip = Join-Path $root 'Argus-Custode-windows.zip'
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $iesire 'Argus Custode') -DestinationPath $zip

$mb = [Math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host ""
Write-Host "Gata." -ForegroundColor Green
Write-Host "  Folder:  $iesire\Argus Custode"
Write-Host "  Arhiva:  $zip  ($mb MB)"
Write-Host ""
Write-Host "Prima rulare arata un avertisment SmartScreen (executabil nesemnat):" -ForegroundColor Yellow
Write-Host "  Mai multe informatii -> Executati oricum"
