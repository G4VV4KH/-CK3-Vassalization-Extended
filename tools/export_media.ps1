param(
    [Parameter(Mandatory = $true)][string]$SquareSource,
    [Parameter(Mandatory = $true)][string]$WideSource,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$veOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $veOutput) { throw "Refusing to overwrite media export: $veOutput" }
[System.IO.Directory]::CreateDirectory($veOutput) | Out-Null

# Mechanical publication-size exports only: retain the complete generated image.
function Export-VePng([string]$Source, [string]$Name, [int]$Width, [int]$Height) {
    $veImage = [System.Drawing.Image]::FromFile([System.IO.Path]::GetFullPath($Source))
    $veBitmap = [System.Drawing.Bitmap]::new($Width, $Height)
    $veGraphics = [System.Drawing.Graphics]::FromImage($veBitmap)
    try {
        $veGraphics.Clear([System.Drawing.Color]::Black)
        $veGraphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
        $veGraphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $veGraphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $veGraphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $veScale = [Math]::Min($Width / [double]$veImage.Width, $Height / [double]$veImage.Height)
        $veWidth = [int][Math]::Round($veImage.Width * $veScale)
        $veHeight = [int][Math]::Round($veImage.Height * $veScale)
        $veX = [int][Math]::Floor(($Width - $veWidth) / 2)
        $veY = [int][Math]::Floor(($Height - $veHeight) / 2)
        $veGraphics.DrawImage($veImage, [System.Drawing.Rectangle]::new($veX, $veY, $veWidth, $veHeight))
        $veTarget = Join-Path $veOutput $Name
        $veBitmap.Save($veTarget, [System.Drawing.Imaging.ImageFormat]::Png)
        [pscustomobject]@{ Name = $Name; Width = $Width; Height = $Height; SourceWidth = $veImage.Width; SourceHeight = $veImage.Height; Cropped = $false; SHA256 = (Get-FileHash -LiteralPath $veTarget -Algorithm SHA256).Hash.ToLowerInvariant() }
    } finally {
        $veGraphics.Dispose()
        $veBitmap.Dispose()
        $veImage.Dispose()
    }
}
$veExports = @(
    Export-VePng $SquareSource 'cover-square-1024.png' 1024 1024
    Export-VePng $SquareSource 'thumbnail.png' 512 512
    Export-VePng $WideSource 'cover-paradox-1920x1080.png' 1920 1080
)
$veExports | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $veOutput 'export-manifest.json') -Encoding utf8
$veExports | Format-Table -AutoSize
