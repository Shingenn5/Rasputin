const { execFile } = require("node:child_process");
const path = require("node:path");

// electron-updater 6 can accept an update when PowerShell verification is
// unavailable. Treat every verification failure as rejection instead.
function verifyWindowsSignature(publishers, file, run = execFile) {
  if (!publishers?.length) return Promise.resolve("Missing trusted update publisher");
  return new Promise((resolve) => {
    run("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command",
      "$s = Get-AuthenticodeSignature -LiteralPath $env:RASPUTIN_UPDATE_FILE -ErrorAction Stop; " +
      "[pscustomobject]@{ status = [int]$s.Status; path = $s.Path; publisher = $(if ($s.SignerCertificate) { " +
      "$s.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) } else { '' }) } | ConvertTo-Json -Compress",
    ], {
      env: { ...process.env, RASPUTIN_UPDATE_FILE: file },
      windowsHide: true,
      timeout: 20_000,
    }, (error, stdout, stderr) => {
      try {
        if (error || stderr) return resolve("Windows could not verify the update signature");
        const signature = JSON.parse(stdout.replace(/^\uFEFF/, ""));
        const sameFile = path.resolve(signature.path).toLowerCase() === path.resolve(file).toLowerCase();
        resolve(signature.status === 0 && sameFile && publishers.includes(signature.publisher)
          ? null : "Update signature or publisher is not trusted");
      } catch {
        resolve("Windows returned invalid signature verification data");
      }
    });
  });
}

module.exports = { verifyWindowsSignature };
