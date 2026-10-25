# Using Spectra

## Sort a folder

- Select a folder with **Browse**.
- Set a filename prefix, starting counter, and similarity threshold. Lower thresholds produce tighter groups; **Auto-determine threshold** estimates a value from the selected files.
- Adjust the visual feature weights to control which characteristics influence sorting.
- Leave **Dry run** enabled to preview filename changes in the log.
- Disable **Dry run** to apply the changes. Enable backups to copy originals into `backup_originals/`.
- Select **Start Sorting** and monitor the progress and log.

## Supported media

- Images: JPG, JPEG, PNG, BMP, TIFF, and WEBP.
- Videos: MP4, AVI, GIF, WMV, MPEG, MOV, and M4V, with video inclusion enabled.
- Videos are compared using extracted frames. The frame position is configurable in **Settings**; cached frames are reused.

## Output files

- Files are renamed sequentially without re-encoding their contents.
- Number padding follows the final counter value. Three files starting at 1 with prefix `sorted` become `sorted_1.jpg`, `sorted_2.jpg`, and `sorted_3.png`, preserving each extension.
- Optional backups are stored in `backup_originals/` inside the selected folder.
- Applied runs write `rename_mapping.csv` with columns `Original Name,New Name`.
- The mapping destination is configurable; `{workFolder}` refers to the selected folder.
- Existing mappings receive numbered filenames unless overwriting is enabled.
- Dry runs do not rename files or write backups or mapping CSVs.

## Performance settings

- **Image feature workers:** concurrent image analysis threads; default 4.
- **Video frame workers:** concurrent video extraction processes; default 1, with one decoder thread per worker.
- **PNG compression level:** compression for extracted frames, from 0 to 9; default 1. Lower levels encode faster and produce larger files without changing pixels.
- **Resize optimization:** Default uses LANCZOS; Low, Medium, and High use Pillow `reducing_gap` values of 3.0, 2.0, and 1.0. Stronger optimization may change similarity scores and ordering. Analysis uses 100 × 100 pixels without modifying originals.
- Changes apply to the next run. Use **Save Settings** to persist options and **Restore Defaults** to reset them.
- **Config path** selects the configuration folder; **Open Config Folder** opens it. Settings are stored in `Spectra.ini`.

## How sorting works

- RGB and HSV histograms measure color distribution; a 4 × 4 grid measures spatial color placement.
- Texture, brightness, contrast, and aspect ratio contribute to the weighted feature vector.
- DBSCAN groups similar media using the selected threshold.
- Nearest-neighbor ordering arranges items within groups and connects groups by visual similarity.

## Installation and updates

- The Windows installer installs for the current user and offers an optional desktop shortcut.
- Use **Extras > Check for Updates** to check for a newer release and download its installer.
- Uninstall through Windows **Installed apps**.
- For a portable copy, download `Spectra-*-windows-amd64-portable.zip` from the [latest release](https://github.com/electblake/Spectra/releases/latest), extract the entire archive, and run its executable.
