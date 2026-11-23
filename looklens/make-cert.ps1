# Makes cert.pem + key.pem (a self-signed certificate for this PC's Wi-Fi address) so phones can open
# LookLens over https. https is needed for the phone's camera and microphone (video call).
# Run once:   powershell -ExecutionPolicy Bypass -File .\make-cert.ps1     then restart server.py
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$ips = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^(127|169)' } | ForEach-Object { $_.IPAddress })
$san = '2.5.29.17={text}DNS=localhost&DNS=' + $env:COMPUTERNAME
foreach ($ip in $ips) { $san += '&IPAddress=' + $ip }
$san += '&IPAddress=127.0.0.1'

$cert = New-SelfSignedCertificate -Subject 'CN=LookLens' -TextExtension @($san) -KeyAlgorithm RSA -KeyLength 2048 `
    -KeyExportPolicy Exportable -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(3) -CertStoreLocation 'Cert:\CurrentUser\My'

function Wrap([string]$b64) { ($b64 -replace '.{64}', "`$&`n").TrimEnd() }
$certPem = "-----BEGIN CERTIFICATE-----`n" + (Wrap ([Convert]::ToBase64String($cert.RawData))) + "`n-----END CERTIFICATE-----`n"

# --- private key -> PKCS#1 DER (RSAPrivateKey), written by hand because Windows PowerShell has no PEM export
function Len([int]$n) {
    if ($n -lt 128) { return [byte[]]@([byte]$n) }
    $bytes = @(); while ($n -gt 0) { $bytes = @([byte]($n -band 0xFF)) + $bytes; $n = $n -shr 8 }
    return [byte[]](@([byte](0x80 + $bytes.Count)) + $bytes)
}
function Der([byte]$tag, [byte[]]$body) { $out = New-Object System.Collections.Generic.List[byte]; $out.Add($tag); $out.AddRange([byte[]](Len $body.Length)); $out.AddRange($body); return ,$out.ToArray() }
function Int([byte[]]$v) { $i = 0; while ($i -lt $v.Length - 1 -and $v[$i] -eq 0) { $i++ }; $v = $v[$i..($v.Length - 1)]; if ($v[0] -ge 0x80) { $v = [byte[]](@(0) + $v) }; return ,(Der 0x02 $v) }
$rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
$p = $rsa.ExportParameters($true)
$body = New-Object System.Collections.Generic.List[byte]
foreach ($part in @([byte[]]@(0), $p.Modulus, $p.Exponent, $p.D, $p.P, $p.Q, $p.DP, $p.DQ, $p.InverseQ)) { $body.AddRange([byte[]](Int $part)) }
$der = Der 0x30 $body.ToArray()
$keyPem = "-----BEGIN RSA PRIVATE KEY-----`n" + (Wrap ([Convert]::ToBase64String($der))) + "`n-----END RSA PRIVATE KEY-----`n"

[IO.File]::WriteAllText((Join-Path $here 'cert.pem'), $certPem, (New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllText((Join-Path $here 'key.pem'), $keyPem, (New-Object Text.UTF8Encoding($false)))
Remove-Item "Cert:\CurrentUser\My\$($cert.Thumbprint)" -ErrorAction SilentlyContinue
Write-Host "Done: cert.pem and key.pem created for: $($ips -join ', ')"
Write-Host "Restart server.py, then on the phone open  https://<this PC's address>:8443/family.html  and accept the warning."
