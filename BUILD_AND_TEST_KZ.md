# BM Text to Voice v5.2.6 — жинау және тексеру

## Нұсқа

- Package: `org.bmtts.bmtextspeech`
- Version: `5.2.6`
- Version code: `102640920`
- Minimum Android: API 26
- Target Android: API 36
- Негізгі ABI: `arm64-v8a`
- Native кітапханалар: 16 KB page-size compatible

## Түзетілген негізгі ақау

Исәке және Рая модельдері жүктелгенімен, BlueStacks сияқты x86/x86_64
эмулятор ARM translation арқылы Sherpa ONNX-ті екі ағынмен іске қосқанда генерация
тұрып қалатын. Python жағы оны қате түрде желі ақауы деп көрсетуі мүмкін еді.

`BmSherpaTtsBridge.java` енді:

- x86/x86_64 эмулятор анықталса, Sherpa-ны бір ағынмен іске қосады;
- нақты ARM64 телефонда қолданушы таңдаған ағын санын сақтайды;
- модельді жүктеу, генерация және WAV сақтау уақытын logcat-ке жазады.

Бұл интернет жылдамдығын шектемейді. 5G/Wi-Fi тек модель архивін жүктеуге
қатысады; орнатылған Исәке/Рая дауыстары офлайн генерацияланады.

### Нақты ARM телефондағы FP16 қатесі

USB debugging арқылы vivo V2419 ARM64 телефонынан алынған logcat бұрын таңдалған
`*-fp16` модельдерінде ONNX Runtime CPU provider-і `Gelu tensor(float16)`
операциясын орындай алмайтынын көрсетті. Бұл желі ақауы емес және 5G сигналына
қатысы жоқ.

v5.2.6 ішінде:

- Android-та жұмыс істемейтін үш қазақша FP16 нұсқа каталогтан алынды;
- remote/cache каталогынан келген FP16 модельдер де UI-ға жіберілмейді;
- бұрын сақталған FP16 таңдау сәйкес FP32/стандарт нұсқаға көшіріледі;
- raw JVM/ONNX мәтінінің орнына үш тілдегі түсінікті хабар көрсетіледі;
- қорғаныс тексерісі жүктеу кезінде де, генерация басталғанда да орындалады.

## Тексерілген қазақша модельдер

- `vits-piper-kk_KZ-iseke-x_low`
- `vits-piper-kk_KZ-raya-x_low`

UI ішінде техникалық ID көрсетілмейді. Қолданушы толық атауды көреді, ал ID
тек ішкі мән ретінде қолданылады.

## Осы компьютердегі дайын орта

- WSL таралымы: Ubuntu
- JDK: `/usr/lib/jvm/java-17-openjdk-amd64`
- Gradle cache: `/mnt/d/BM_TTS_BUILD_CACHE/gradle-bmtts-sherpa`
- Cached Android dist:
  `/home/beren/bmtts_sherpa_16kb_clean_storage/dists/bmtextspeech16kb510sherpa`
- Android SDK:
  `/home/beren/.buildozer/android/platform/android-sdk`
- 16 KB NDK:
  `/home/beren/android-ndk-r25b-16kb-v510-clean`
- Keystore жолы: `/mnt/d/keystore/bmquiz.keystore`

Keystore құпиясөзі source кодта сақталмайды. Build script оны іске қосылған
кезде сұрайды.

## Толық APK және AAB жинау

PowerShell ашып, project папкасына кіріңіз:

```powershell
cd "C:\Users\Берен\Documents\Codex\2026-06-30\new-chat-2\work\bm_text_to_voice_v520\BM_Text_to_Voice_v5.2.0_SOURCE\project"
wsl -e bash ./build_bmtts_v520_complete_cached.sh
```

Script мынаны автоматты жасайды:

1. Python файлдарын синтаксиске тексереді.
2. `private.tar` runtime архивін жаңартады.
3. Sherpa JAR және ARM64 native кітапханаларын қосады.
4. PyJNIus қолданатын generated `org.kivy.android.PythonActivity` класына
   тұрақты bridge API енгізеді.
5. API 36 және version code 102640920 орнатады.
6. Test APK және production AAB жинайды.
7. Keystore арқылы қол қояды.
8. APK/AAB ішіндегі DEX, runtime модульдері және 16 KB ELF alignment-ті
   тексереді.

## Тек debug APK жинау

```powershell
wsl -e env JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 `
  GRADLE_USER_HOME=/mnt/d/BM_TTS_BUILD_CACHE/gradle-bmtts-sherpa `
  /home/beren/bmtts_sherpa_16kb_clean_storage/dists/bmtextspeech16kb510sherpa/gradlew `
  -p /home/beren/bmtts_sherpa_16kb_clean_storage/dists/bmtextspeech16kb510sherpa `
  assembleDebug --offline --no-daemon --rerun-tasks
```

## BlueStacks эмуляторына орнату

BlueStacks ADB порты осы компьютерде `127.0.0.1:5556`:

```powershell
D:\platform-tools\adb.exe connect 127.0.0.1:5556
D:\platform-tools\adb.exe -s 127.0.0.1:5556 install -r "C:\path\to\BM_Text_to_Voice.apk"
D:\platform-tools\adb.exe -s 127.0.0.1:5556 shell monkey -p org.bmtts.bmtextspeech -c android.intent.category.LAUNCHER 1
```

Таза орнату үшін бұрынғы нұсқаны өшіріңіз:

```powershell
D:\platform-tools\adb.exe -s 127.0.0.1:5556 uninstall org.bmtts.bmtextspeech
```

## Sherpa диагностикасын көру

```powershell
D:\platform-tools\adb.exe -s 127.0.0.1:5556 logcat -c
D:\platform-tools\adb.exe -s 127.0.0.1:5556 logcat -s BMSherpaTts
```

Сәтті генерацияда мына белгілер шығады:

- `LOAD_BEGIN`
- `LOAD_OK`
- `GENERATE_BEGIN`
- `GENERATE_OK`
- `SAVE_OK`

## Осы release-та орындалған тексерістер

- Signed test APK USB арқылы vivo V2419 ARM64 телефонына жаңарту ретінде орнатылып ашылды.
- Бұрынғы FP16 таңдау автоматты түрде стандарт модельге көшті; қазақша дауыстар саны 11-ден 8-ге түсті.
- Исәке ADB self-test: 40 таңба, WAV 100 588 байт, 16 kHz, 3,142 секунд.
- Рая ADB self-test: 40 таңба, WAV 74 796 байт, 16 kHz, 2,336 секунд.
- Исәке негізгі UI preview: 46 таңба, WAV 110 192 байт.
- Исәке негізгі «Аудио жасау»: 46 таңба дыбысталып, файл `Music/BM Text to Voice` ішіне сақталды.
- Рая негізгі UI preview: 46 таңба, WAV 124 880 байт.
- Исәке мен Рая нақты ARM64 телефонда екі ағынмен жұмыс істеді; `Gelu float16` қатесі қайталанбады.
- APK және AAB ішінде Исәке/Рая ID, Sherpa bridge және v5.2.6 runtime бар.
- APK қолтаңбасы v2/v3 арқылы тексерілді.
- AAB JAR қолтаңбасы тексерілді.
- API 36 және `com.google.android.gms.permission.AD_ID` тексерілді.
- Production AAB ішінде live AdMob App ID және `BM_USE_TEST_ADS=false` бар.
- APK және AAB: 14 жоғарғы native ELF және Python bundle ішіндегі 106 ELF
  файлы 16 KB alignment тексерісінен өтті.

## Маңызды файлдар

- `main.py` — UI, модель таңдау, мәтін және генерация логикасы.
- `offline_voice_catalog.py` — дауыстар каталогы.
- `offline_voice_manager.py` — модель жүктеу/орнату.
- `sherpa_generation.py` — ұзақ мәтінді Sherpa арқылы дыбыстау.
- `android_src/.../BmSherpaTtsBridge.java` — Sherpa ONNX Android bridge.
- `android_src/.../BmPythonActivity.java` — Android lifecycle және SDL resume fix.
- `android_src/.../BmAdMobBridge.java` — баннер/интерстициал орналасуы.
- `build_bmtts_v520_complete_cached.sh` — толық reproducible build.
