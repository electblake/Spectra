#Requires -Version 7.0
param(
    [string]$IsccPath = "$env:LOCALAPPDATA/Programs/Inno Setup 6/ISCC.exe"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

Set-Location (Split-Path $PSScriptRoot -Parent)
$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"$').Matches.Groups[1].Value
New-Item -ItemType Directory -Force build/bootstrap | Out-Null
Invoke-WebRequest 'https://github.com/astral-sh/uv/releases/download/0.11.11/uv-x86_64-pc-windows-msvc.zip' -OutFile build/bootstrap/uv.zip
Expand-Archive -LiteralPath build/bootstrap/uv.zip -DestinationPath build/bootstrap/uv -Force
Invoke-WebRequest 'https://raw.githubusercontent.com/astral-sh/uv/0.11.11/LICENSE-MIT' -OutFile build/bootstrap/LICENSE-MIT
Invoke-WebRequest 'https://raw.githubusercontent.com/astral-sh/uv/0.11.11/LICENSE-APACHE' -OutFile build/bootstrap/LICENSE-APACHE

& $IsccPath "/DSpectraVersion=$version" "/DSpectraPlatform=windows" "/DSpectraArchitecture=amd64" "packaging/Spectra.iss"
