# UVC Capability Evidence

PitchTracker records what each selected camera and backend actually report. A
capability observation is setup evidence, not proof of image quality or tracking
accuracy.

## How discovery works

On Windows release builds, PitchTracker first attempts a read-only native
DirectShow query for camera controls and advertised stream modes. If the
optional native provider is unavailable or a query fails, validated OpenCV
DirectShow readback supplies only the facts it can verify. Discovery never
changes a control merely to learn whether it exists.

Every standard control has one status:

| Status | Meaning |
|---|---|
| `supported` | A native query succeeded or a requested value had valid, matching readback. |
| `unsupported` | DirectShow explicitly reported that the interface or property is absent. |
| `permission_denied` | Windows or the driver refused the query. |
| `query_failed` | The query ran but failed, returned invalid data, or did not verify readback. |
| `unavailable` | No applicable provider could attempt the query. |

Zero, `-1`, NaN, an invalid FOURCC, and a successful write without matching
readback are not treated as proof of support. Requested and negotiated modes
remain separate in the setup snapshot.

Source installations can add the native provider with:

```powershell
python -m pip install -r requirements-uvc-native.txt
```

The application continues with conservative OpenCV evidence when this optional
provider cannot load. Windows installer builds include it through
`requirements-build.txt`.

## Before field use

Exercise both cameras under each applicable condition and retain the resulting
setup snapshot locally:

- Standard Windows account and, separately, an administrator account.
- Camera free and camera already opened by another application.
- Fixed-focus camera or camera without an autofocus interface.
- Grayscale capture where white balance is not applicable.
- Unsupported requested resolution, frame rate, or pixel format.
- Unplug/reconnect while preserving stable camera identity.
- Two matching global-shutter cameras on the intended USB controllers.

Confirm that the status, query method, reason, requested mode, negotiated mode,
driver metadata, and advertised modes match the observed condition. Redact
serials, device paths, usernames, and facility details before sharing reports.

Passing this checklist qualifies discovery and persistence behavior only. Use
[Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md) for speed
or plate-location claims.
