# Build APK cho Android.
#
# CMake/Ninja (bước biên dịch native của Flutter) không chạy được với đường dẫn có ký tự Unicode
# ("Đồ án"), nên script đồng bộ mã nguồn sang một thư mục ASCII, build ở đó rồi chép APK về
# mobile\dist\ADAS_CaoToc.apk.
#
#   powershell -ExecutionPolicy Bypass -File mobile\build_apk.ps1            # bản release
#   powershell -ExecutionPolicy Bypass -File mobile\build_apk.ps1 -Run       # cài và chạy trên điện thoại đang cắm
param(
    [switch]$Run,
    [string]$Flutter = "$env:USERPROFILE\flutter\bin\flutter.bat",
    [string]$BuildDir = "$env:LOCALAPPDATA\adas_mobile_build"
)
$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'app'
$dist = Join-Path $PSScriptRoot 'dist'

# /MIR: bản sao giống hệt nguồn; bỏ qua thư mục sinh ra khi build để không xóa cache Gradle
robocopy $src $BuildDir /MIR /XD build .dart_tool .gradle .idea /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy lỗi ($LASTEXITCODE)" }

Push-Location $BuildDir
try {
    & $Flutter pub get
    if ($Run) {
        & $Flutter run --release
    } else {
        & $Flutter build apk --release
        if ($LASTEXITCODE -ne 0) { throw 'flutter build apk thất bại' }
        New-Item -ItemType Directory -Force $dist | Out-Null
        Copy-Item 'build\app\outputs\flutter-apk\app-release.apk' (Join-Path $dist 'ADAS_CaoToc.apk') -Force
        Write-Host "APK: $(Join-Path $dist 'ADAS_CaoToc.apk')"
    }
} finally {
    Pop-Location
}
