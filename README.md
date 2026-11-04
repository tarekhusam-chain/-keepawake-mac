# KeepAwakeMac — GitHub Actions build

Build **KeepAwakeMac.app** on GitHub's Mac computers, without installing Python, VS Code or Xcode locally.

This repository contains only the app source and GitHub Actions workflow. Never upload API keys, `token.txt`, `.env`, or unrelated private files.

## 1. Create a GitHub repository

1. Sign in at https://github.com and visit https://github.com/new.
2. Name it `keepawake-mac` and create it. A **public** repository typically avoids GitHub Actions usage charges for standard hosted runners; private repository quotas and billing rules differ.
3. Upload `KeepAwakeMac.py`, `README.md`, and the `.github/workflows/build-macos.yml` file **keeping exactly that directory path**. If GitHub's browser uploader doesn't preserve the hidden `.github` folder, create the workflow separately as described below.
4. Commit the files to your default branch (usually `main`).

**Web UI alternative for the workflow:** In your repository select **Add file → Create new file**. In the filename box enter `.github/workflows/build-macos.yml`, paste the workflow content, and commit it. Upload `KeepAwakeMac.py` in the repository root.

## 2. Build the Mac app

1. Open your repository's **Actions** tab.
2. Select **Build KeepAwake for macOS** on the left.
3. Click **Run workflow → Run workflow** (on the default branch).
4. Open the workflow run when it completes. It must show both builds green.
5. Under **Artifacts**, download:
   - **KeepAwakeMac-AppleSilicon** — Macs with M1, M2, M3, M4 or newer Apple chips.
   - **KeepAwakeMac-Intel** — older Intel-based Macs.
6. Each GitHub artifact download is itself a ZIP containing `KeepAwakeMac-AppleSilicon.zip` or `KeepAwakeMac-Intel.zip`. Extract the outer ZIP, then extract the inner ZIP to obtain `KeepAwakeMac.app`.

The app includes its own Python runtime. **Recipients need no Python installation.**

## 3. Open the app

1. Copy `KeepAwakeMac.app` into **Applications** (recommended).
2. Double-click it, then click **Start**.
3. Allow the app in **System Settings → Privacy & Security → Accessibility** to let it move the pointer. Fully quit and reopen the app after granting permission if required.
4. As this is an **unsigned/unnotarized** app, macOS may block its first launch. If you trust its source, try to open it, then go to **System Settings → Privacy & Security → Open Anyway**, as described in Apple guidance. Do not bypass security warnings for untrusted software.

The application runs while its window remains open. Use **Pause**, **Stop** or **Exit** to stop pointer movement and release the sleep prevention assertion.

## What it does

- While running, calls macOS `caffeinate -d -i -w <pid>` to prevent idle display/system sleep.
- After 8 seconds of **mouse pointer** inactivity (customizable), moves the cursor up to 25 pixels (customizable).
- Aborts its automated movement if the mouse moves manually by more than the threshold; avoids the screen edges.
- Never clicks or types. Sleep-prevention assertion is released on Stop/Pause/Exit; on unexpected termination, `caffeinate -w` also stops when the app process ends.
- Does **not** override screen locks, company policies or lid-close sleep. Keyboard-only activity is not monitored; this is a pointer-inactivity timer.

## Known limitations

- macOS Accessibility permission is required for mouse movement.
- These are **separate architecture-specific builds**, not a universal binary.
- GitHub Actions can build the bundle, but this package has **not been run/tested on an actual Mac** here. First test on a Mac of each architecture you intend to support.
- Unsigned/unnotarized distribution may trigger Gatekeeper warnings; for wider public distribution, use Apple Developer ID signing and notarization.
- GitHub Actions artifacts expire after the configured retention period (30 days). Save your downloads elsewhere for later sharing.

## Files

```
keepawake-mac/
├── KeepAwakeMac.py
├── README.md
├── .gitignore
└── .github/
    └── workflows/
        └── build-macos.yml
```
