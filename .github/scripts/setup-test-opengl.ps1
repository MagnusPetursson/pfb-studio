param(
    [Parameter(Mandatory = $true)]
    [string]$BinaryDirectory
)

$ErrorActionPreference = 'Stop'

# GitHub's Windows runners expose GDI OpenGL 1.1 without shaders and with a
# 1024px texture limit. Use a pinned software driver for rendering tests only.
# https://github.com/pal1000/mesa-dist-win/releases/tag/26.2.3
$mesaVersion = '26.2.3'
$mesaHash = '3f3613adb43cfd0f2e665ce2400b130c275f0b3317cb3a05566320a3a67589ed'
$binaryPath = (Resolve-Path -LiteralPath $BinaryDirectory).ProviderPath
$mesaDirectory = Join-Path $binaryPath "mesa-test-driver-$mesaVersion"
New-Item -ItemType Directory -Force -Path $mesaDirectory | Out-Null
$archive = Join-Path $mesaDirectory 'mesa.7z'
if (!(Test-Path -LiteralPath $archive) -or
    (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $mesaHash) {
    Invoke-WebRequest -Uri "https://github.com/pal1000/mesa-dist-win/releases/download/$mesaVersion/mesa3d-$mesaVersion-release-msvc.7z" -OutFile $archive
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $mesaHash) {
    throw 'Mesa archive SHA256 does not match the pinned release.'
}

Push-Location -LiteralPath $mesaDirectory
try {
    & cmake -E tar xf $archive -- x64/opengl32.dll x64/libgallium_wgl.dll
    if ($LASTEXITCODE -ne 0) { throw 'Could not extract the Mesa test driver.' }
} finally {
    Pop-Location
}
foreach ($library in @('opengl32.dll', 'libgallium_wgl.dll')) {
    Copy-Item -LiteralPath (Join-Path $mesaDirectory "x64/$library") -Destination $binaryPath
}
$env:GALLIUM_DRIVER = 'llvmpipe'
if ($env:GITHUB_ENV) {
    Add-Content -LiteralPath $env:GITHUB_ENV -Value 'GALLIUM_DRIVER=llvmpipe'
}
Write-Output "Mesa $mesaVersion software OpenGL installed for tests in $binaryPath."
