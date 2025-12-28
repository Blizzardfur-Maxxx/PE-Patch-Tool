# PE Patch Tool

A Python-based tool to patch **Minecraft Pocket Edition APKs** (up to 0.7.6 so far based off https://github.com/machinamentum/PocketTool) with `.mod` patches (PocketTool patches) and modified assets. This tool allows you to apply code modifications to `libminecraftpe.so` and merge custom assets into the APK while keeping all existing assets intact and then rebuilds the apk.

---

## Features

- Applies `.mod` patches from a `patches` folder to `libminecraftpe.so` inside the APK.
- Merges modified assets from a `patches/assets` folder into the APK.
- Preserves unmodified assets — does **not delete existing assets**.
- Automatically repacks the APK after patching.
- Signs the APK using provided `.pk8` and `.pem` keys.
---

## Requirements

- Python 3.x
- Java Runtime Environment (JRE) for signing the APK
- `ApkSigner.jar`, `.pk8`, and `.pem` signing files located in the `resources` folder.
- `.mod` patch files and optional `assets` folder inside your `patches` folder for modifications.

---

## Usage

```bash
python PEPatchTool.py <apk_path> <patch_folder>
