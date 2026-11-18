# Build app Android từ dòng lệnh (không cần mở Android Studio):
#   powershell -ExecutionPolicy Bypass -File mobile\android\build_apk.ps1            # APK release -> mobile\android\dist\ADAS_CaoToc.apk
#   powershell -ExecutionPolicy Bypass -File mobile\android\build_apk.ps1 -Test      # thêm unit test (khớp fixture Python)
#   powershell -ExecutionPolicy Bypass -File mobile\android\build_apk.ps1 -Install   # cài lên điện thoại đang cắm USB
#
# Vì sao không gọi thẳng gradlew.bat: java.exe đọc tham số dòng lệnh theo bảng mã ANSI của Windows nên đường dẫn
# có chữ "Đ" ("Đồ án") bị hỏng -> không tìm thấy gradle-wrapper.jar. Script chép wrapper sang %LOCALAPPDATA%
# (ASCII) rồi chạy từ thư mục dự án (thư mục làm việc không đi qua tham số). Thư mục build cũng nằm ở
# %LOCALAPPDATA%\adas_android_build (xem build.gradle.kts gốc). Android Studio không gặp vấn đề này.
param([switch]$Test, [switch]$Install)
$ErrorActionPreference = 'Stop'

$project = $PSScriptRoot
if (-not $env:JAVA_HOME) { $env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr' }
$java = Join-Path $env:JAVA_HOME 'bin\java.exe'
$wrap = Join-Path $env:LOCALAPPDATA 'adas_gradle_wrapper\gradle\wrapper'
New-Item -ItemType Directory -Force $wrap | Out-Null
Copy-Item (Join-Path $project 'gradle\wrapper\*') $wrap -Force

$tasks = @('assembleRelease')
if ($Test) { $tasks = @('testDebugUnitTest') + $tasks }
Push-Location $project
try {
    & $java -cp (Join-Path $wrap 'gradle-wrapper.jar') org.gradle.wrapper.GradleWrapperMain @tasks
    if ($LASTEXITCODE -ne 0) { throw "Gradle lỗi ($LASTEXITCODE)" }
} finally { Pop-Location }

$apk = Join-Path $env:LOCALAPPDATA 'adas_android_build\app\outputs\apk\release\app-release.apk'
$dist = Join-Path $project 'dist'
New-Item -ItemType Directory -Force $dist | Out-Null
Copy-Item $apk (Join-Path $dist 'ADAS_CaoToc.apk') -Force
Write-Host "[OK] $(Join-Path $dist 'ADAS_CaoToc.apk')"

if ($Install) {
    $adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
    & $adb install -r (Join-Path $dist 'ADAS_CaoToc.apk')
}
