# Test PortraitLab on your phone

## Expo Go or a development build?

**Use a development build.** That is the path this project is set up and checked for: it uses `expo-dev-client`, and the spec calls for custom development builds.

Expo Go *might* open the app for a quick look, since every native library it uses is in Expo SDK 57's own set. This has not been tried, though. Expo Go also only runs the newest SDK, so it can stop working when Expo releases the next one. If you want to try it anyway, run `npx expo start --go` from `apps/mobile` and scan the QR code with Expo Go. If you see a red error screen, use a development build instead.

Editing happens on the phone. You do **not** need the backend, Docker or any server running.

## 1. Set up your computer (once)

1. Install **Node.js 22 LTS** and **Git**.
2. Get the code:
   ```sh
   git clone https://github.com/subashspeaks1m-create/Faceapp.git
   cd Faceapp
   git checkout claude/faceapp-initial-build-wmcbbx
   npm ci
   cd apps/mobile
   ```

## 2. Install the development build

Pick the row that matches your phone and computer.

| Phone | Computer | Route |
|---|---|---|
| Android | any (Windows, Mac, Linux) | **A. EAS cloud build** (easiest; no Android Studio) |
| Android | has Android Studio | B. Local build over USB |
| iPhone | Mac with Xcode | C. Local build over USB |
| iPhone | no Mac | EAS cloud build, but it needs a paid Apple Developer account ($99/yr) |

### A. Android with an EAS cloud build

1. Create a free account at expo.dev.
2. In `apps/mobile`:
   ```sh
   npx eas-cli login
   npx eas-cli init          # links the project; it adds a projectId to app.json, keep it
   npx eas-cli build --profile development --platform android
   ```
3. When the build finishes (it runs on Expo's servers), open the link it prints on your phone and install the APK. Android will ask you to allow installs from your browser; allow it.
4. On the computer, start the dev server: `npx expo start --dev-client`
5. Open **PortraitLab** on the phone and scan the QR code, or pick the server from the list.

### B. Android with Android Studio

1. On the phone, turn on Developer options and **USB debugging**, then plug it in and accept the prompt.
2. In `apps/mobile`, run `npx expo run:android --device` and pick your phone. The app builds, installs and opens.

### C. iPhone with a Mac

1. Install Xcode, open it once, and sign in with your Apple ID (Xcode > Settings > Accounts).
2. On the iPhone, turn on **Developer Mode** (Settings > Privacy & Security), then plug it in and tap "Trust".
3. In `apps/mobile`, run `npx expo run:ios --device` and pick your iPhone.
4. If Xcode says the bundle ID is taken, change `ios.bundleIdentifier` in `app.json` to something unique, like `com.yourname.portraitlab`.
5. With a free Apple ID, the app stops opening after 7 days; run the command again to reinstall.

### If the phone can't reach the dev server

Put the phone and computer on the same Wi-Fi. If that still fails, run `npx expo start --dev-client --tunnel` (it offers to install the tunnel package the first time).

## 3. Test checklist

Mark each item pass or fail. Expected results follow each step.

**Camera access**
- [ ] Tap **Take photo** for the first time. The system asks for camera permission. Allow it, and the camera opens. After you take a photo, the editor opens with it.
- [ ] Cancel the camera without taking a photo. You return to the home screen with no error.
- [ ] Turn camera access off in the phone's Settings and tap **Take photo**. A message explains camera access is off. If an **Open Settings** button appears, it opens PortraitLab's settings.

**Photo selection**
- [ ] Tap **Choose photo**. The system photo picker opens without asking for library permission.
- [ ] Pick a portrait (vertical) photo. It shows upright in the editor, not sideways.
- [ ] Pick a very large photo (48 or 50 MP camera mode, if your phone has one). The editor shows "Resized from … to stay within 24 MP".
- [ ] Pick a screenshot (PNG). It opens normally.

**Editing**
- [ ] Move each slider (Brightness, Contrast, Saturation, Warmth). The photo updates as you drag, and each slider shows its number.
- [ ] In **Looks**, try all four looks and the **Look strength** slider.
- [ ] In **Crop**, try Square, 4:5 and 9:16. The frame changes shape.
- [ ] While a change is pending, an **Apply / Discard** bar is shown. **Discard** reverts the change, and **Apply** keeps it.

**Undo / redo**
- [ ] Apply three separate edits. **Undo** steps back one edit at a time, and **Redo** steps forward again.
- [ ] Undo once, then make and apply a new edit. **Redo** is now greyed out.
- [ ] Make a change but don't apply it, then tap **Undo**. Only that unapplied change is dropped.
- [ ] Tap **Reset**. The original shows as a pending change, and you must tap Apply to keep it.

**Before / After**
- [ ] Tap **Before**. The original photo shows with a "Before" badge. Tap **After**, and the edit returns.
- [ ] Press and hold the photo. The original shows while you hold and the edit returns when you let go.

**Full-size export**
- [ ] With an unapplied change, **Export** (top right) is greyed out.
- [ ] Apply, then tap **Export**. "Preparing full-size photo…" shows, then the share sheet opens. Save the image to Photos or Files.
- [ ] Open the saved photo's details (iOS Photos: swipe up; Google Photos: ⋮ > Details). The size matches the **Export size** shown in the editor. With no crop it is the original photo's size. With Square on a 4000×3000 photo it is 3000×3000.
- [ ] Colours in the saved photo match the preview.

## 4. What to send back

- Phone model, OS version, and which route you used (A, B or C).
- Pass or fail for each item above.
- For a failure: a screenshot or screen recording, and the exact text of any red error screen. Also send the text from the terminal running `expo start`.
