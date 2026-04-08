$certs = Get-ChildItem -Path Cert:\LocalMachine\Root | Where-Object { $_.Subject -like "*Zscaler*" }
foreach ($cert in $certs) {
    Write-Host "Found: $($cert.Subject)"
    $pem = "-----BEGIN CERTIFICATE-----`n" + [Convert]::ToBase64String($cert.RawData, "InsertLineBreaks") + "`n-----END CERTIFICATE-----"
    Add-Content -Path "zscaler_root.pem" -Value $pem
}
Write-Host "Done. Certs exported to zscaler_root.pem"
