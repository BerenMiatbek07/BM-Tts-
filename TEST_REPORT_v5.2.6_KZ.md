# BM Text to Voice v5.2.6 — USB телефон сынағы

## Құрылғы мен build

- Құрылғы: vivo V2419
- ABI: `arm64-v8a, armeabi-v7a, armeabi`
- Package: `org.bmtts.bmtextspeech`
- Version: `5.2.6`
- Version code: `102640920`
- Орнату: USB debugging арқылы `adb install -r`

## Табылған себеп

Қате интернеттен болған жоқ. Бұрын сақталған модель:

`vits-piper-kk_KZ-iseke-x_low-fp16`

Телефондағы ONNX Runtime CPU provider `com.microsoft.Gelu` операциясын
`tensor(float16)` түрінде орындай алмады. Сондықтан модель жүктелгенімен,
құрылғыда дауыс іске қосылмайтын.

## Түзету

- Android-та үйлеспейтін қазақша FP16 модельдер каталогтан сүзілді.
- Бұрын сақталған FP16 дауыс сәйкес стандарт нұсқаға автоматты көшірілді.
- Қолданушыға raw JVM traceback көрсетілмейді.
- Каталог, жүктеу және генерация деңгейлерінде бөлек қорғаныс тексерістері қосылды.
- Қазақ тілінде UI-да тек 8 үйлесімді модель қалды.

## Нақты телефондағы нәтижелер

### Исәке — стандарт

- Model ID: `vits-piper-kk_KZ-iseke-x_low`
- Sherpa threads: 2
- Model load: 5 866 ms (ADB self-test), 4 754 ms (main UI)
- Generation: 1 261 ms / 40 таңба
- WAV: 100 588 байт, mono, 16 kHz, 16-bit, 3,142 секунд
- Main UI preview: 110 192 байт
- Main UI «Аудио жасау»: сәтті
- MediaStore: `Music/BM Text to Voice` ішіне сақталды

### Рая — стандарт

- Model ID: `vits-piper-kk_KZ-raya-x_low`
- Sherpa threads: 2
- Model load: 2 532 ms (ADB self-test), 2 333 ms (main UI)
- Generation: 651 ms / 40 таңба
- WAV: 74 796 байт, mono, 16 kHz, 16-bit, 2,336 секунд
- Main UI preview: 124 880 байт
- Main UI «Дауысты тексеру»: сәтті

## Қорытынды

Исәке және Раяның стандарт модельдері USB арқылы қосылған нақты ARM64
телефонда жүктелді, іске қосылды, дыбыс жасады және сақталды. FP16 Gelu қатесі
қайталанбады. Модель бір рет жүктелгеннен кейін дыбыстау офлайн орындалады.

## Production release тексерісі

- Production APK release keystore арқылы v2/v3 схемаларымен қол қойылды.
- Production AAB release keystore арқылы JAR қолтаңбасымен қол қойылды.
- APK/AAB ішіндегі 14 негізгі ELF және Python bundle ішіндегі 106 ELF 16 KB alignment тексерісінен өтті.
- APK manifest: min API 26, target API 36, version code 102640920.
- `com.google.android.gms.permission.AD_ID` бар.
- Live AdMob App ID қолданылды, `BM_USE_TEST_ADS=false`.
- Production APK USB телефонға `adb install -r` арқылы орнатылды.
- App-open live жарнамасы шықты, одан кейін негізгі v5.2.6 экран ашылды.
- Қолданба процесі тірі қалды; fatal crash табылған жоқ.
