# MalHani Launcher Setup

Version 0.1.0 · Windows x64 preview · includes Samsung tools

A guided, local installer for a simpler Samsung TV home screen. First setup needs Developer Mode on the TV and completion of Samsung's sign-in/certificate window; after successful setup, **Update saved TV** backs up, signs, installs and verifies the bundled launcher in one action.

## Use

1. Download and open `MalHani-Launcher-Setup.exe` from this project's release. No Python or Node installation is required.
2. Keep the Windows PC and TV on the same home network. Discovery starts automatically. A single TV is selected automatically; choose one only if several are found.
3. The required Samsung tools are bundled, checked and extracted automatically. Progress is shown while they are prepared. There are no tool-folder or component choices in the normal flow. Existing complete tools can be reused.
4. If Developer Mode is needed, follow the instructions shown on the TV. Enter the PC address displayed by the installer and restart the TV. Ready checks continue automatically.
5. Samsung Certificate Manager opens when needed. Complete Samsung sign-in and the TV certificate steps, choosing Partner for the distributor certificate. The installer detects completion and continues automatically. Technical recovery controls are under Advanced setup.
   In Certificate Manager:
   - Click **+ → Samsung → TV**.
   - Name the profile, for example **MalHaniTV**.
   - Create an author certificate using your name and a password you keep. For updates, reuse the existing author certificate.
   - Sign in to Samsung and choose a certificate backup folder.
   - Create a distributor certificate with **Partner** privileges.
   - Click **+** beside your connected TV to add its **DUID**, then finish the wizard.
   - Return to MalHani Launcher Setup; it detects the profile and continues automatically.
6. Available TV information, app inventory and encrypted signing credentials are backed up and checked automatically. A backup report explains what is missing. You can import Samsung's USB settings export if your model supports one; the program cannot create that export itself.
7. Choose app shortcuts and clock/prayer preferences. Netflix, YouTube, Unifi TV, Prime Video, Disney+, Spotify and Stremio are offered. Existing apps are detected. Missing apps require installation by the owner in Samsung Apps; the installer opens that store and can recheck. Availability varies by region/model. No third-party app binaries are bundled or silently installed.
8. Click **Install Launcher**. A fresh verified backup is captured before TV changes. The launcher is signed with your own profile, installed and checked through the TV's local API.
9. Finish automatic reopening: open TV settings, turn **Start with Smart Hub Home OFF** and enable **Autorun Last App** if available. Return to MalHani Launcher, switch the TV off with its remote for 10 seconds, then switch it on. Keep the PC installer open during the TV restart. Back on the PC, confirm what appeared on the TV. After a successful test, the installer finishes setup and shows the welcome message as the final TV screen. Press Let’s go on the TV remote to enter the launcher. No PC helper launches the app during the startup check.



## What it can and cannot back up

Local data lives under `%LOCALAPPDATA%\OpenHomeTV`. Do not publish or upload this directory.

- Captured: TV-reported device details, app inventory, SDK capabilities, selected signing profile/certificates encrypted with Windows DPAPI, previous packages/configurations produced by this installer, and any USB export explicitly imported by the owner.
- Verified: backup files are hashed and checked before installation. The encrypted signing bundle is decrypted in memory to verify round-trip integrity.
- Not captured: a full TV recovery image, third-party application binaries/data, account logins, and most protected picture/sound settings. Developer Mode is already enabled by the owner before the SDK inventory is available.
- Configuration archives are the last installer-generated configuration; later edits made only on the TV are not exported.
- A first install cannot recover a package installed by another tool. **Restore a previous MalHani Launcher version** only works when a verified backup contains a previous installer-managed package for that same TV.
- DPAPI signing backups are tied to the same Windows user and machine. Preserve your certificate passwords separately. Re-signing or moving to another machine may require Samsung Certificate Manager and the owner's certificate password.
- The USB import has a 4 GB limit and accepts the exported folder, not an entire drive. Keep larger exports separately.

## Automatic startup and compatibility

MalHani Startup is bundled inside the launcher package. It requests boot startup and automatic service restart, opens MalHani Launcher once, retries temporary launch failures up to 15 times, then stays idle. The installer checks the actual distributor certificate issuer for Partner/Platform privileges before installing; a Public certificate stops setup with instructions. The TV still validates signatures and device authorization. It requires no PC helper or network service.

The separate startup-helper variant passed one owner-observed full-restart test on the U8000H/Tizen 10: the TV went offline, returned, and the existing launcher became visible without a PC launch command. The combined public launcher/service package has passed real SDK signing and simulated lifecycle checks, but has not yet been installed on a second TV. Other firmware/models and repeated cold boots remain unverified. The installer asks the owner to check startup on their TV before marking setup complete.

Only the customized launcher base has been exercised on a Samsung U8000H with Tizen 10. The public installer itself has offline/UI tests and real Samsung SDK signing validation; its complete fresh-PC/Samsung-sign-in/install flow has not yet been validated on a second TV. Bundled tool extraction and signing have been exercised from a separate relocated directory; first-time Samsung authentication on a clean PC still needs end-to-end validation. The program rejects unverified Tizen versions below 3.0; newer/other models remain compatibility candidates, not certified support.

Clock is Malaysia time (UTC+8). Optional prayer times use the entered Malaysian JAKIM zone and require Internet. The installer has no analytics and does not send backups, passwords or TV credentials to a server. Runtime launcher requests are the configured JAKIM timetable and owner-triggered services/apps. The launcher does not provide free subscriptions or streaming content.

## Updates and rollback

Download a newer installer executable and select **Update saved TV**. It uses the saved local preferences and your own existing profile, captures a new backup and installs the newer bundled source. It does not fetch unsigned launchers from an unconfigured GitHub repository.

To roll back, select the backup folder containing `previous-installer-version/Launcher.wgt`. The backup must pass hash verification and belong to the same TV. This restores the launcher package, not Samsung settings or other apps. Restore Samsung's USB export separately using its supported TV menu.

## Build and test

Use Python 3.12 on Windows. Runtime installer code uses the standard library only.

```powershell
python -m unittest discover -s tests -v
python installer.py --self-test
.\build.ps1
```

`--self-test --report path.txt` runs without connecting to a TV. `--ui-smoke-test --test-home path` opens a short test window with no device discovery or tool downloads.

The generated executable is not Authenticode-signed. Windows may show an unknown-publisher or reputation warning; verify the release checksum and source rather than treating it as a signed Samsung product. It is not affiliated with Samsung or the app publishers.

## Provenance

Launcher base: [Dylan Fernandez de Lara's Samsung TV Launcher](https://github.com/dylanfernandezdelara/samsung-tv-launcher), MIT, original base commit `478b8c0b681c98a4b254cf2483b9793913cc5d5f`. Original copyright and licence are retained in LICENSE.

Official setup reference: https://developer.samsung.com/smarttv/develop/getting-started/setting-up-sdk/installing-tv-sdk.html

Pinned SDK download: https://download.tizen.org/sdk/Installer/tizen-sdk_10.0/web-cli_Tizen_SDK_10.0_windows-64.exe

SHA-256: `ad373548a261b4383b6f74d4a74eb853b439c726ceca331a451d89081b7f7920`.

See NOTICE.md and launcher/wallpapers/CREDITS.txt for included artwork information.
