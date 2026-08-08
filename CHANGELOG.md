# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-08-08

### Added

- Added a tabbed interface with an Extras tab for File Explorer integration.

### Changed

- Expanded the main window and displayed log output beside the sorting controls.
- Reorganized video, run-option, progress, and action controls.
- Moved File Explorer integration into the packaged `app.tabs` module.

## [0.3.3] - 2026-08-08

### Changed

- Optimized video frame extraction and weighted visual feature computation.

## [0.3.2] - 2026-08-05

### Added

- Added project branding images.

### Changed

- Isolated video frame extraction from the sorting pipeline.
- Queued GUI output updates for thread-safe progress reporting.
- Updated launch behavior and documentation for windowed execution.

## [0.3.1] - 2026-08-04

### Added

- Added aspect ratio to image similarity analysis.
- Added a Windows File Explorer integration installer.

### Changed

- Persisted the selected folder and filename prefix between sessions.
- Centralized application metadata in the configuration module.
- Improved video proxy names and completion dialogs.

## [0.3.0] - 2026-08-04

### Added

- Added configurable video handling and date-based renaming.
- Added persistent clustering threshold settings.

### Changed

- Expanded settings for video processing, renaming, scrolling, and command entry.

### Fixed

- Skipped videos whose frame extraction failed.

## [0.2.0] - 2026-08-04

### Added

- Added visual image analysis, clustering, sequential ordering, and safe renaming.
- Added the Tkinter interface, CSV rename mapping, dry-run mode, and automatic backups.
- Added frame-based video sorting with configurable temporary image proxies.
- Added dry-run, backup, and persisted feature and video-frame settings.
- Added OpenCV and packaged its runtime dependencies.
- Added project packaging, build, editor, and runtime configuration.

### Changed

- Migrated the application entry point into the `app` package.
- Made `pyproject.toml` the sole source of the application version.
- Refined application metadata, typing, formatting, and documentation.

[Unreleased]: https://github.com/electblake/Spectra/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/electblake/Spectra/compare/v0.3.3...v0.4.0
[0.3.3]: https://github.com/electblake/Spectra/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/electblake/Spectra/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/electblake/Spectra/compare/36eec17...v0.3.1
[0.3.0]: https://github.com/electblake/Spectra/compare/v0.2.0...36eec17
[0.2.0]: https://github.com/electblake/Spectra/releases/tag/v0.2.0
