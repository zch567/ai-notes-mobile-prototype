# Android WebView Shell

This native Android shell packages the Vite frontend as local WebView assets for an offline demo.

## Build Flow

From the frontend project root:

```powershell
npm run build:webview
```

From this `android-shell` directory, open the project in Android Studio or run Gradle after the Android SDK is installed:

```powershell
.\gradlew.bat assembleDebug
```

The generated debug APK is:

```text
app/build/outputs/apk/debug/app-debug.apk
```

APK/AAB files are build artifacts. They are ignored by git and should be rebuilt from source instead of committed.

The Android Gradle build also runs `npm run build:webview` before merging assets, so the APK uses:

```text
VITE_DEMO_MODE=true
VITE_APP_SHELL_MODE=webview
```

The app loads:

```text
file:///android_asset/web/index.html
```

## Validation Path

Use an emulator or physical device to verify:

- Home -> AI -> result -> note -> citation -> review -> mind map directory -> landscape mind map.
- Full-screen WebView layout.
- Status bar and bottom gesture safe area.
- WebView hardware back behavior.
- Text input keyboard resizing.
- System file chooser for PDF, PPTX, DOC, and DOCX uploads.
- Local JS/CSS asset loading without network.
- Mind map detail should request landscape orientation.
- If the mind map detail is still portrait, it should show the "switch to landscape" prompt instead of the map content.
