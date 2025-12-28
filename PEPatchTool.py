import struct
import os
import glob
import shutil
import zipfile
import subprocess
import sys

MAGIC = bytes([0xFF, 0x50, 0x54, 0x50])


class PTPatch:
    def __init__(self, patch_path):
        self.patch_path = patch_path
        self.patch_array = None
        self.count = 0
        self.minecraft_ver = 0
        self.num_patches = 0
        self.indices = b""

    def load_patch(self):
        with open(self.patch_path, "rb") as f:
            self.patch_array = f.read()
        self.minecraft_ver = self.patch_array[4]
        self.num_patches = self.patch_array[5]
        self.indices = self.patch_array[6:6 + self.num_patches * 4]
        self.count = 0

    def check_magic(self):
        if self.patch_array[:4] != MAGIC:
            raise ValueError(f"Invalid patch file: {self.patch_path}")

    def get_current_index(self):
        i = self.indices[self.count * 4:(self.count + 1) * 4]
        return struct.unpack(">I", i)[0]

    def get_next_addr(self):
        index = self.get_current_index()
        return struct.unpack(">I", self.patch_array[index:index + 4])[0]

    def get_data_length(self):
        start_index = self.get_current_index() + 4
        if self.count != self.num_patches - 1:
            next_index = struct.unpack(">I", self.indices[(self.count + 1) * 4:(self.count + 2) * 4])[0]
            end = next_index
        else:
            end = len(self.patch_array)
        return end - start_index

    def get_next_data(self):
        index = self.get_current_index()
        length = self.get_data_length()
        return self.patch_array[index + 4:index + 4 + length]

    def apply_patch(self, so_path):
        print(f"Applying patch: {os.path.basename(self.patch_path)}")
        with open(so_path, "rb") as f:
            data = bytearray(f.read())
        for self.count in range(self.num_patches):
            addr = self.get_next_addr()
            patch_bytes = self.get_next_data()
            data[addr:addr + len(patch_bytes)] = patch_bytes
            print(f"  Patch {self.count + 1}/{self.num_patches} applied at address {addr}")
        with open(so_path, "wb") as f:
            f.write(data)
        print("Patch applied successfully.")


def merge_assets(assets_src, assets_dest):
    print(f"Merging assets from {assets_src} into APK assets folder...")
    for root, dirs, files in os.walk(assets_src):
        rel_path = os.path.relpath(root, assets_src)
        target_root = os.path.join(assets_dest, rel_path)
        os.makedirs(target_root, exist_ok=True)
        for file in files:
            src_file = os.path.join(root, file)
            dst_file = os.path.join(target_root, file)
            shutil.copy2(src_file, dst_file)
            print(f"  Asset merged: {os.path.join(rel_path, file)}")
    print("Assets merged successfully.")


def patch_apk(apk_path, patch_folder):
    if not os.path.isfile(apk_path):
        print("APK file not found.")
        return
    if not os.path.isdir(patch_folder):
        print("Patch folder not found.")
        return

    resources_dir = os.path.join(os.path.dirname(__file__), "resources")

    apksigner_jar_files = glob.glob(os.path.join(resources_dir, "*.jar"))
    if not apksigner_jar_files:
        print("ApkSigner.jar not found in the resources folder.")
        return
    apksigner_jar = apksigner_jar_files[0]

    temp_dir = os.path.join(os.path.dirname(__file__), "temp_apk")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try:
        print("Extracting APK...")
        with zipfile.ZipFile(apk_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        so_path = os.path.join(temp_dir, "lib", "armeabi-v7a", "libminecraftpe.so")
        if not os.path.isfile(so_path):
            print("libminecraftpe.so not found in APK.")
            return

        mod_files = sorted(glob.glob(os.path.join(patch_folder, "*.mod")))
        if mod_files:
            print(f"Applying {len(mod_files)} patch(es) to libminecraftpe.so...")
            for mod_file in mod_files:
                patch = PTPatch(mod_file)
                patch.load_patch()
                patch.check_magic()
                patch.apply_patch(so_path)
        else:
            print("No .mod patch files found.")

        assets_src = os.path.join(patch_folder, "assets")
        if os.path.isdir(assets_src):
            assets_dest = os.path.join(temp_dir, "assets")
            os.makedirs(assets_dest, exist_ok=True)
            merge_assets(assets_src, assets_dest)

        unsigned_apk = os.path.join(temp_dir, "unsigned.apk")
        print("Repacking APK...")
        with zipfile.ZipFile(unsigned_apk, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    if arcname != "unsigned.apk":
                        zipf.write(file_path, arcname)
        print("APK repacked successfully.")

        pk8_files = glob.glob(os.path.join(resources_dir, "*.pk8"))
        pem_files = glob.glob(os.path.join(resources_dir, "*.pem"))
        if not pk8_files or not pem_files:
            print("No key or cert files found in resources folder for signing.")
            return

        pk8_file = pk8_files[0]
        pem_file = pem_files[0]

        signed_apk = os.path.join(os.path.dirname(apk_path),
                                  os.path.splitext(os.path.basename(apk_path))[0] + "-patched.apk")
        print("Signing APK...")
        subprocess.run([
            "java", "-jar", apksigner_jar, "sign",
            "--key", pk8_file,
            "--cert", pem_file,
            "--out", signed_apk,
            unsigned_apk
        ], check=True)
        print(f"APK signed successfully: {os.path.basename(signed_apk)}")

        for apk_file in [unsigned_apk, signed_apk]:
            idsig_file = apk_file + ".idsig"
            if os.path.exists(idsig_file):
                os.remove(idsig_file)

        print("APK patching complete!")

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    if len(sys.argv) == 3:
        patch_apk(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python PEPatchTool.py <apk_path> <folder_with_patches>")
