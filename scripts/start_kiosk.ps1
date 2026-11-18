param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5173,
    [switch]$Camera
)

$chrome = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1

if (-not $chrome) {
    throw 'Google Chrome 설치 경로를 찾지 못했습니다.'
}

$caifeProfile = Join-Path $env:LOCALAPPDATA 'CAIFE\ChromeProfile'
$caifeUrl = "http://127.0.0.1:$Port/"
if ($Camera) { $caifeUrl += '?approach=camera' }

& $chrome "--user-data-dir=$caifeProfile" '--autoplay-policy=no-user-gesture-required' "--app=$caifeUrl"
