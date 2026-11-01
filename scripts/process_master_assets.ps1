Add-Type -AssemblyName System.Drawing

Write-Host "=== Processing Master Assets to 512x512 Lossless PNGs ==="

# 1. Process HSR Light Cones (avatars/1/*.master.png)
$hsrMasters = Get-ChildItem "data-automation\avatars\1\*.master.png" -ErrorAction SilentlyContinue
Write-Host "Found $($hsrMasters.Count) HSR master assets to process."

foreach ($m in $hsrMasters) {
    $targetName = $m.Name.Replace(".master.png", "")
    $targetPath = Join-Path $m.DirectoryName $targetName

    try {
        $src = [System.Drawing.Bitmap]::FromFile($m.FullName)
        
        # Crop inner area inside the card frame (avoid borders)
        $cropX = [int]($src.Width * 0.025)
        $cropY = [int]($src.Height * 0.05)
        $cropW = $src.Width - ($cropX * 2)
        $cropH = $cropW
        if ($cropY + $cropH -gt $src.Height) {
            $cropH = $src.Height - $cropY
            $cropW = $cropH
            $cropX = [int](($src.Width - $cropW) / 2)
        }

        $rect = [System.Drawing.Rectangle]::new($cropX, $cropY, $cropW, $cropH)
        $cropped = $src.Clone($rect, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $src.Dispose()

        # Render onto 512x512 with bicubic interpolation
        $dst = [System.Drawing.Bitmap]::new(512, 512, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $g = [System.Drawing.Graphics]::FromImage($dst)
        $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $g.DrawImage($cropped, 0, 0, 512, 512)
        $g.Dispose()
        $cropped.Dispose()

        $tmpOut = "$targetPath.tmp"
        $dst.Save($tmpOut, [System.Drawing.Imaging.ImageFormat]::Png)
        $dst.Dispose()

        Move-Item -Path $tmpOut -Destination $targetPath -Force
        Remove-Item -Path $m.FullName -Force
        Write-Host " [+] Processed HSR Light Cone: $targetName (512x512)"
    } catch {
        Write-Host " [X] Failed to process $($m.Name): $_"
    }
}

# 2. Process ZZZ Assets (avatars/2/*.master.png)
$zzzMasters = Get-ChildItem "data-automation\avatars\2\*.master.png" -ErrorAction SilentlyContinue
Write-Host "Found $($zzzMasters.Count) ZZZ master assets to process."

foreach ($m in $zzzMasters) {
    $targetName = $m.Name.Replace(".master.png", "")
    $targetPath = Join-Path $m.DirectoryName $targetName

    try {
        $src = [System.Drawing.Bitmap]::FromFile($m.FullName)
        
        $dst = [System.Drawing.Bitmap]::new(512, 512, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $g = [System.Drawing.Graphics]::FromImage($dst)
        $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

        # Calculate aspect-ratio fit
        $scale = [Math]::Min(512.0 / $src.Width, 512.0 / $src.Height)
        $drawW = [int]($src.Width * $scale)
        $drawH = [int]($src.Height * $scale)
        $drawX = [int]((512 - $drawW) / 2)
        $drawY = [int]((512 - $drawH) / 2)

        $g.DrawImage($src, $drawX, $drawY, $drawW, $drawH)
        $g.Dispose()
        $src.Dispose()

        $tmpOut = "$targetPath.tmp"
        $dst.Save($tmpOut, [System.Drawing.Imaging.ImageFormat]::Png)
        $dst.Dispose()

        Move-Item -Path $tmpOut -Destination $targetPath -Force
        Remove-Item -Path $m.FullName -Force
        Write-Host " [+] Processed ZZZ Asset: $targetName (512x512)"
    } catch {
        Write-Host " [X] Failed to process $($m.Name): $_"
    }
}

Write-Host "Master asset processing complete."
