# Apply Konica AccurioPress C3070 finishing defaults to all 4 queues.
# v2: adds DocumentKOLayout=Booklet (BM-660 trigger) + JobOutputBin overrides.

function Set-KOFeatures {
    param(
        [string]$PrinterName,
        [hashtable]$Features
    )
    $cfg = Get-PrintConfiguration -PrinterName $PrinterName
    [xml]$ticket = $cfg.PrintTicketXML
    $psfNS = "http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework"
    foreach ($featName in $Features.Keys) {
        $optName = $Features[$featName]
        $feat = $null
        foreach ($f in $ticket.PrintTicket.ChildNodes) {
            if ($f.LocalName -eq "Feature" -and $f.GetAttribute("name") -eq $featName) { $feat = $f; break }
        }
        if ($feat -ne $null) {
            $existingOpts = @($feat.ChildNodes | Where-Object { $_.LocalName -eq "Option" })
            foreach ($o in $existingOpts) { [void]$feat.RemoveChild($o) }
            $newOpt = $ticket.CreateElement("psf","Option",$psfNS)
            $newOpt.SetAttribute("name",$optName)
            [void]$feat.AppendChild($newOpt)
        } else {
            $newFeat = $ticket.CreateElement("psf","Feature",$psfNS)
            $newFeat.SetAttribute("name",$featName)
            $newOpt = $ticket.CreateElement("psf","Option",$psfNS)
            $newOpt.SetAttribute("name",$optName)
            [void]$newFeat.AppendChild($newOpt)
            [void]$ticket.PrintTicket.AppendChild($newFeat)
        }
    }
    try {
        Set-PrintConfiguration -PrinterName $PrinterName -PrintTicketXml $ticket.OuterXml -ErrorAction Stop
        return $true
    } catch {
        Write-Host ("  FAILED " + $PrinterName + " : " + $_.Exception.Message)
        return $false
    }
}

Write-Host "=== Plain : all finishers off, default output ==="
$ok = Set-KOFeatures -PrinterName "C3070 Plain" -Features @{
    "ns0000:DocumentKOLayout"    = "ns0000:None"
    "ns0000:DocumentKOStaple"    = "ns0000:None"
    "ns0000:DocumentKOPunch"     = "ns0000:None"
    "ns0000:DocumentKOFoldMode"  = "ns0000:None"
    "ns0000:DocumentKOFoldStitch"= "ns0000:None"
    "psk:JobOutputBin"           = "ns0000:Auto"
}
Write-Host "  C3070 Plain saved: $ok"

Write-Host "=== Booklet : Layout=Booklet + half-fold + 2-staple saddle + Saddle tray ==="
$ok = Set-KOFeatures -PrinterName "C3070 Booklet" -Features @{
    "ns0000:DocumentKOLayout"    = "ns0000:Booklet"
    "ns0000:DocumentKOFoldMode"  = "ns0000:CenterFold"
    "ns0000:DocumentKOFoldStitch"= "ns0000:_2Positions"
    "ns0000:DocumentKOFoldTrim"  = "ns0000:False"
    "ns0000:DocumentKOStaple"    = "ns0000:None"
    "ns0000:DocumentKOPunch"     = "ns0000:None"
    "psk:JobOutputBin"           = "ns0000:SaddleSub"
}
Write-Host "  C3070 Booklet saved: $ok"

Write-Host "=== Stapled : corner staple upper-left, Stapler main tray ==="
$ok = Set-KOFeatures -PrinterName "C3070 Stapled" -Features @{
    "ns0000:DocumentKOLayout"    = "ns0000:None"
    "ns0000:DocumentKOStaple"    = "ns0000:_1Staple_Left_"
    "ns0000:DocumentKOPunch"     = "ns0000:None"
    "ns0000:DocumentKOFoldMode"  = "ns0000:None"
    "ns0000:DocumentKOFoldStitch"= "ns0000:None"
    "psk:JobOutputBin"           = "ns0000:StaplerMain"
}
Write-Host "  C3070 Stapled saved: $ok"

Write-Host "=== Punched : 3-hole left edge, Stapler main tray ==="
$ok = Set-KOFeatures -PrinterName "C3070 Punched" -Features @{
    "ns0000:DocumentKOLayout"    = "ns0000:None"
    "ns0000:DocumentKOPunch"     = "ns0000:_3holes"
    "ns0000:DocumentKOStaple"    = "ns0000:None"
    "ns0000:DocumentKOFoldMode"  = "ns0000:None"
    "ns0000:DocumentKOFoldStitch"= "ns0000:None"
    "psk:JobOutputBin"           = "ns0000:StaplerMain"
}
Write-Host "  C3070 Punched saved: $ok"

Write-Host ""
Write-Host "=== Verification: finishing options on each queue ==="
foreach ($q in "C3070 Plain","C3070 Booklet","C3070 Stapled","C3070 Punched") {
    Write-Host "--- $q ---"
    $cfg = Get-PrintConfiguration -PrinterName $q
    [xml]$t = $cfg.PrintTicketXML
    foreach ($f in $t.PrintTicket.ChildNodes) {
        if ($f.LocalName -eq "Feature" -and $f.GetAttribute("name") -match "Staple|Punch|FoldMode|FoldStitch|FoldTrim|Layout|JobOutputBin") {
            $featN = $f.GetAttribute("name")
            $optEl = $f.ChildNodes | Where-Object { $_.LocalName -eq "Option" } | Select-Object -First 1
            if ($optEl) { $optN = $optEl.GetAttribute("name") } else { $optN = "(none)" }
            Write-Host ("  " + $featN + " = " + $optN)
        }
    }
}
