$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$root = Split-Path -Parent $PSScriptRoot
$assets = Join-Path $root 'dist/store-resources/appx'
New-Item -ItemType Directory -Path $assets -Force | Out-Null
$source = [System.Drawing.Image]::FromFile((Join-Path $root 'desktop/assets/rasputin-logo.png'))
try {
    foreach ($asset in @(
        @{ Name = 'StoreLogo.png'; Width = 50; Height = 50 },
        @{ Name = 'Square150x150Logo.png'; Width = 150; Height = 150 },
        @{ Name = 'Square44x44Logo.png'; Width = 44; Height = 44 },
        @{ Name = 'Wide310x150Logo.png'; Width = 310; Height = 150 }
    )) {
        $bitmap = New-Object System.Drawing.Bitmap($asset.Width, $asset.Height)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.Clear([System.Drawing.Color]::FromArgb(11, 13, 17))
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $scale = [Math]::Min($asset.Width / $source.Width, $asset.Height / $source.Height)
            $width = [int]($source.Width * $scale)
            $height = [int]($source.Height * $scale)
            $graphics.DrawImage($source, [int](($asset.Width - $width) / 2), [int](($asset.Height - $height) / 2), $width, $height)
            $bitmap.Save((Join-Path $assets $asset.Name), [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
} finally {
    $source.Dispose()
}
Write-Host 'Prepared Store tiles from the existing Rasputin logo'
