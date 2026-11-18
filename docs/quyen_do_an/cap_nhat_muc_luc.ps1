# Mở file .docx bằng Word, cập nhật mục lục / danh mục hình / danh mục bảng (điền số trang), lưu lại.
#   powershell -ExecutionPolicy Bypass -File cap_nhat_muc_luc.ps1 <file.docx> [file.pdf]
param([Parameter(Mandatory = $true)][string]$Docx, [string]$Pdf)
$Docx = (Resolve-Path $Docx).Path
$w = New-Object -ComObject Word.Application
$truoc = $w.Documents.Count          # Word đang mở sẵn tài liệu khác thì không đóng Word
$d = $w.Documents.Open($Docx, $false, $false, $false)
$d.Repaginate()
foreach ($t in $d.TablesOfContents) { $t.Update() }
$d.Fields.Update() | Out-Null
foreach ($t in $d.TablesOfContents) { $t.Update() }   # lần 2: số trang ổn định sau khi mục lục dài ra
$d.Save()
if ($Pdf) { $d.SaveAs([ref]$Pdf, [ref]17) }
$d.Close($false)
if ($truoc -eq 0) { $w.Quit() }
Write-Output "Đã cập nhật: $Docx"
