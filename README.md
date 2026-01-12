# PitchTracker Quick Start (Windows)

## Setup
```powershell
cd C:\Users\bergi\App\PitchTracker
.\setup.ps1
```

## Run
```powershell
.\run.ps1 -Backend uvc
```

If you only have an internal camera, use:
```powershell
.\run.ps1 -Backend opencv
```

## Notes
- Use the “Refresh Devices” button to populate cameras.
- Configure ROIs and strike zone settings before recording.
