# MH Launcher Setup 0.1.1

- Rename the TV app, setup screens and public documentation to MH Launcher.
- Replace the placeholder TV icon with a matching MH monogram; include SVG/PNG and multi-size Windows ICO assets.
- Keep application IDs, the OpenHomeTV data folder and existing certificate/backup compatibility unchanged.

This update contains branding changes. The experimental animated window is not part of this public installer release.

## Initial preview

First Windows x64 preview of MH Launcher Setup, with bundled Samsung tools and a customizable Samsung TV launcher.

- Automatic TV discovery and tool preparation with progress.
- Guided Developer Mode and Samsung certificate setup.
- Local verified backups, optional USB backup import and launcher updates.
- App shortcuts, nature backgrounds, clock and optional Malaysian waktu solat.
- Included startup service and a guided TV restart check.

## Downloads

- **MH-Launcher-Setup.exe**: Windows installer. No Python installation needed.
- **MH-Launcher-Source-v0.1.1.zip**: full source bundle including the Samsung tool archive.
- **SHA256SUMS.txt**: SHA-256 checksums for verifying downloads.

This is a testing preview. Offline tests, GUI checks, tool relocation and real Samsung SDK signing passed. The complete first-time setup on a clean PC and public package installation on a second TV remain unverified. Automatic startup varies by model and firmware. See VALIDATION.json and the installation guide for details.

The executable is not Authenticode-signed. Samsung/Tizen tools retain their own licences; the launcher and installer source use MIT with upstream attribution preserved.
