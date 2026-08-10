$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$version = uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
$platform = uv run python -c "import platform; print(platform.system().lower())"
$architecture = uv run python -c "import platform; print(platform.machine().lower())"
$isccPath = Join-Path $env:LOCALAPPDATA "Programs/Inno Setup 6/ISCC.exe"

& $isccPath "/DSpectraVersion=$version" "/DSpectraPlatform=$platform" "/DSpectraArchitecture=$architecture" "packaging/Spectra.iss"
