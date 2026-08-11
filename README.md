<center>
<img src="Spectra.png" alt="Spectra" width="350">
<h3>Intelligent image/video sorting by visual similarity</h3>
<p>Spectra automatically organizes your image collections by analyzing color, texture, and content similarity. Say goodbye to chaotic folders — let your images flow in visual harmony.</p>
</center>


<p align="center">
  <img src="https://img.shields.io/github/v/release/electblake/Spectra" alt="Latest release">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows-lightgrey.svg" alt="Platform">
</p>

![Spectra application demo](demo.png)

---

## ✨ Features

- **🔍 Multi-dimensional visual analysis**: Extracts color histograms, spatial patterns, texture features, brightness metrics, and aspect ratio
- **🧩 Smart clustering**: Uses DBSCAN algorithm to group visually similar images
- **🔄 Nearest-neighbor sorting**: Creates smooth visual transitions within and between clusters
- **🖥️ User-friendly GUI**: Clean Tkinter interface—no command line needed
- **🛡️ Safe operations**: Dry-run mode and automatic backups protect your files
- **📊 Detailed logging**: Real-time progress tracking and CSV mapping of all changes
- **⚙️ Customizable**: Adjustable similarity thresholds and filename prefixes

---

## 🚀 Quick start

### Install Spectra on Windows (recommended)

No Python, PowerShell, or other development tools are required.

1. Open the [latest Spectra release](https://github.com/electblake/Spectra/releases/latest).
2. Download the file ending in `windows-amd64-Setup.exe`.
3. Run the downloaded Setup executable.
4. Review the license, choose whether to create a desktop shortcut, and select **Install**.
5. Launch Spectra from the Start Menu, the optional desktop shortcut, or the final Setup page.

Setup installs Spectra for the current Windows user and supports upgrades and uninstall through Windows **Installed apps**.

After installation, use **Extras > Install > Check for Updates** to download and open the latest GitHub release Setup executable.

### Portable version

For an installation-free copy, download the file ending in `windows-amd64-portable.zip` from the [latest release](https://github.com/electblake/Spectra/releases/latest), extract the entire archive, and run the Spectra executable inside the extracted folder.

---

## 📖 How it works

### 1. Feature extraction

Spectra analyzes each image across multiple dimensions:

- **RGB & HSV color histograms**: Captures overall color distribution
- **Spatial color features**: Tracks color placement in a 4×4 grid
- **Texture analysis**: Detects edges, patterns, and variance
- **Brightness & contrast**: Measures tonal characteristics

### 2. Intelligent clustering

Uses DBSCAN (Density-Based Spatial Clustering) to:
- Group images with similar visual characteristics
- Automatically determine optimal cluster count
- Handle outliers gracefully

### 3. Sequential ordering

- Sorts images within clusters using nearest-neighbor algorithm
- Orders clusters for smooth visual transitions
- Optimizes connections between cluster boundaries

### 4. Safe renaming

- Renames files sequentially (e.g., `001.jpg`, `002.jpg`, `003.jpg`)
- Creates backup of originals (optional)
- Generates CSV mapping file for reference

---

## 🎯 Use cases

- **📸 Photo collections**: Organize vacation photos by scene and color
- **🎨 Design assets**: Sort product images, textures, or color palettes
- **🖼️ Digital art**: Arrange artwork by style and composition
- **📱 Screenshots**: Group similar UI states or app screens
- **🏠 Home organization**: Sort scanned documents or family photos

---

## 🛠️ Usage guide

### Basic workflow

1. **Launch Spectra** from the Start Menu or desktop shortcut.

2. **Select your image folder**
   - Click "Browse..." to choose your image directory
   - Supported formats: JPG, JPEG, PNG, BMP, GIF, TIFF, WEBP

3. **Configure settings**
   - **File prefix**: Add a prefix to sorted filenames (optional)
   - **Similarity threshold**: Lower values = tighter grouping (0.005-0.05 typical)
   - **Auto-determine**: Let Spectra calculate optimal threshold
   - **Dry run**: Preview changes without modifying files
   - **Create backup**: Saves originals to `backup_originals/` folder

4. **Start sorting**
   - Click "Start Sorting"
   - Monitor progress in the log window
   - Review results and mapping file

---

## 📊 Output files

After processing, Spectra generates:

```
your-image-folder/
├── sorted_001.jpg          # Renamed images in order
├── sorted_002.jpg
├── sorted_003.jpg
├── ...
├── rename_mapping.csv      # Original → New name mapping
└── backup_originals/       # Original files (if backup enabled)
    ├── original_name1.jpg
    ├── original_name2.jpg
    └── ...
```

### Mapping file format

```csv
Original Name,New Name
"IMG_5234.jpg","sorted_001.jpg"
"DSC_0891.jpg","sorted_002.jpg"
"photo.png","sorted_003.png"
```

---

## 🎛️ Configuration

### Similarity threshold guidelines

| Threshold | Clustering behavior |
|-----------|---------------------|
| 0.005-0.01 | Very tight—only nearly identical images grouped |
| 0.01-0.02 | Moderate—similar colors and compositions |
| 0.02-0.05 | Loose—broader visual themes |
| Auto | Spectra calculates based on your dataset |

### Performance notes

- **Processing time**: ~0.5-1 second per image (depends on resolution)
- **Memory usage**: ~50-100MB per 1000 images
- **Optimal batch size**: Up to 5000 images per folder

---

## 🔒 Safety features

- ✅ **Dry run mode**: Preview all changes before committing
- ✅ **Automatic backups**: Original files preserved in separate folder
- ✅ **Mapping file**: CSV log of all filename changes
- ✅ **Non-destructive**: Images are renamed, never modified
- ✅ **Error handling**: Skips problematic images with warnings

---

## 🤝 Contributing

Contributions are welcome!

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [Pillow](https://python-pillow.org/) for image processing
- Powered by [scikit-learn](https://scikit-learn.org/) for clustering algorithms
- UI created with [Tkinter](https://docs.python.org/3/library/tkinter.html)

---

## 📧 Contact

**Questions? Suggestions? Issues?**

- 🐛 [Report a bug](https://github.com/electblake/Spectra/issues)
- 💡 [Request a feature](https://github.com/electblake/Spectra/issues)
- 📖 [Documentation](https://github.com/electblake/Spectra/wiki)

---

<p align="center">
  Made with ❤️ for photographers, designers, and digital hoarders everywhere
</p>

<p align="center">
  <sub>Star ⭐ this repo if you find it useful!</sub>
</p>
