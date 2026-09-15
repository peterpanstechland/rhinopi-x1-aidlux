$ErrorActionPreference = "Stop"
$bin = "C:\Program Files (x86)\Qualcomm\QPST\bin"
$rom = "c:\Users\peter\Documents\robomon\aidlux\downloads\RhinoPi-X1.T04_LA.user.2026070119"
Set-Location $rom

$xmls = @(
    "rawprogram_unsparse0.xml",
    "patch0.xml",
    "rawprogram1.xml",
    "patch1.xml",
    "rawprogram2.xml",
    "patch2.xml",
    "rawprogram3.xml",
    "patch3.xml",
    "rawprogram4.xml",
    "patch4.xml",
    "rawprogram5.xml",
    "patch5.xml"
)

foreach ($xml in $xmls) {
    $path = Join-Path $rom $xml
    if (-not (Test-Path $path)) {
        throw "missing $xml"
    }
    Write-Host ""
    Write-Host "======== $xml ========"
    & "$bin\fh_loader.exe" `
        --port=\\.\COM11 `
        --sendxml=$xml `
        --search_path=$rom `
        --noprompt `
        --showpercentagecomplete `
        --zlpawarehost=1 `
        --memoryname=ufs
    if ($LASTEXITCODE -ne 0) {
        throw "fh_loader failed on $xml with exit $LASTEXITCODE"
    }
}

Write-Host ""
Write-Host "======== reset ========"
& "$bin\fh_loader.exe" --port=\\.\COM11 --noprompt --reset --memoryname=ufs --zlpawarehost=1
Write-Host "flash script finished, reset exit: $LASTEXITCODE"
