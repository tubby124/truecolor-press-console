$ProgressPreference = "SilentlyContinue"
$psfNS = "http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework"

function Apply-Settings([string]$Queue, [hashtable]$Features) {
    $cfg = Get-PrintConfiguration -PrinterName $Queue
    [xml]$t = $cfg.PrintTicketXML
    foreach ($name in $Features.Keys) {
        $val = $Features[$name]
        $feat = $null
        foreach ($f in $t.PrintTicket.ChildNodes) { if ($f.LocalName -eq "Feature" -and $f.GetAttribute("name") -eq $name) { $feat = $f; break } }
        if ($feat -ne $null) {
            $opts = @($feat.ChildNodes | Where-Object { $_.LocalName -eq "Option" })
            foreach ($o in $opts) { [void]$feat.RemoveChild($o) }
        } else {
            $feat = $t.CreateElement("psf","Feature",$psfNS); $feat.SetAttribute("name",$name); [void]$t.PrintTicket.AppendChild($feat)
        }
        $newOpt = $t.CreateElement("psf","Option",$psfNS); $newOpt.SetAttribute("name",$val); [void]$feat.AppendChild($newOpt)
    }
    Set-PrintConfiguration -PrinterName $Queue -PrintTicketXml $t.OuterXml
}

Write-Host "--- Add C3070 Trifold + C3070 Halffold queues if missing ---"
foreach ($q in "C3070 Trifold","C3070 Halffold") {
    $existing = Get-Printer -Name $q -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  $q already exists"
    } else {
        try {
            Add-Printer -Name $q -DriverName "KONICA MINOLTA C3080/C3070PS" -PortName "172.16.1.149_1" -ErrorAction Stop
            Write-Host "  Added $q"
        } catch {
            Write-Host "  FAILED to add $q : $($_.Exception.Message)"
        }
    }
}

Write-Host "--- Configure Halffold (CenterFold only, no stitch) ---"
Apply-Settings "C3070 Halffold" @{
    "ns0000:DocumentKOFoldMode"   = "ns0000:CenterFold"
    "ns0000:DocumentKOFoldStitch" = "ns0000:None"
    "ns0000:DocumentKOStaple"     = "ns0000:None"
    "ns0000:DocumentKOPunch"      = "ns0000:None"
    "ns0000:DocumentKOLayout"     = "ns0000:None"
    "psk:JobInputBin"             = "psk:AutoSelect"
}
Write-Host "  Halffold configured"

Write-Host "--- Configure Trifold (LetterFold = tri-fold-in) ---"
Apply-Settings "C3070 Trifold" @{
    "ns0000:DocumentKOFoldMode"   = "ns0000:LetterFold"
    "ns0000:DocumentKOFoldStitch" = "ns0000:None"
    "ns0000:DocumentKOStaple"     = "ns0000:None"
    "ns0000:DocumentKOPunch"      = "ns0000:None"
    "ns0000:DocumentKOLayout"     = "ns0000:None"
    "psk:JobInputBin"             = "psk:AutoSelect"
}
Write-Host "  Trifold configured"

Write-Host "--- Declare SD-510 on both new queues ---"
foreach ($q in "C3070 Trifold","C3070 Halffold") {
    try {
        Set-PrinterProperty -PrinterName $q -PropertyName "Config:KOOpSaddleUnit" -Value "SD-510" -ErrorAction Stop
        Write-Host "  $q : KOOpSaddleUnit = SD-510"
    } catch {
        Write-Host "  $q : SaddleUnit FAILED: $($_.Exception.Message)"
    }
}

Write-Host "--- STOP queues first ---"
curl.exe -s -c "C:\Users\TrueC\Desktop\TrueColorSetup\.cookie" -X POST http://localhost:5273/login --data-urlencode "password=qwerty123" -o NUL | Out-Null
curl.exe -s -b "C:\Users\TrueC\Desktop\TrueColorSetup\.cookie" -X POST http://localhost:5273/api/stop | Out-Null
Start-Sleep -Seconds 2

$sumatra = "C:\Users\TrueC\AppData\Local\SumatraPDF\SumatraPDF.exe"
$pdf = "C:\Users\TrueC\Desktop\TrueColorSetup\booklet-test-5pg.pdf"

Write-Host "--- FIRE HALFFOLD at $(Get-Date -Format HH:mm:ss) ---"
& $sumatra -print-to "C3070 Halffold" -silent -exit-when-done $pdf 2>&1 | Out-Null
Write-Host "  Sumatra exit: $LASTEXITCODE"
Start-Sleep -Milliseconds 2000

Write-Host "--- FIRE TRIFOLD at $(Get-Date -Format HH:mm:ss) ---"
& $sumatra -print-to "C3070 Trifold" -silent -exit-when-done $pdf 2>&1 | Out-Null
Write-Host "  Sumatra exit: $LASTEXITCODE"

Start-Sleep -Seconds 5
Write-Host "--- Press state ---"
try {
  $tc = New-Object System.Net.Sockets.TcpClient; $tc.SendTimeout=5000; $tc.ReceiveTimeout=5000
  $tc.Connect("172.16.1.149",9100); $ns = $tc.GetStream()
  $uel = [byte[]]@(0x1B,0x25,0x2D,0x31,0x32,0x33,0x34,0x35,0x58)
  $q = $uel + [Text.Encoding]::ASCII.GetBytes("@PJL INFO STATUS`r`n") + $uel
  $ns.Write($q,0,$q.Length); Start-Sleep -Milliseconds 600
  $buf = New-Object byte[] 4096; $n = $ns.Read($buf,0,4096); $tc.Close()
  [Text.Encoding]::ASCII.GetString($buf,0,$n)
} catch { Write-Host "PJL: $($_.Exception.Message)" }
