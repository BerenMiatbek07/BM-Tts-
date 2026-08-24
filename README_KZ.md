# BM Voice Studio — v5.6.4 PERSONAL (Windows)

Осы жеке Windows нұсқасында алдыңғы Soniox және OmniVoice мүмкіндіктеріне
қоса **ElevenLabs Eleven v3** ресми API интеграциясы бар.

- Қазақша / Русский / English тілдерінде Eleven v3 генерациясы.
- `eleven_v3` model id ресми Text-to-Speech endpoint арқылы қолданылады.
- Jessica, Liam, Announcer, Sammara, Sergeant, Spuds voice ID үлгілері қосылған.
- ElevenLabs дауысы таңдалғанда API key енгізу өрісі ашылады.
- `[happy]`, `[whispers]`, `[laughs]` секілді Eleven v3 audio tags мәтін ішінде
  сол күйі беріледі.
- Ұзын мәтін chunk-тарға бөлініп, бір MP3 файлға біріктіріледі.
- API key exe ішіне тігілмейді; пайдаланушы енгізген key жергілікті settings.json
  файлына сақталады.
- `elevenlabs-alpha-v3` жобасындағы bypass тәсілдері көшірілмеген; ресми API ғана.

---

# BM Voice Studio — v5.6.1

Бұл — BM Text to Voice Android қолданбасының толық бастапқы коды.

## Негізгі мүмкіндіктер

- Қазақша, орысша, ағылшынша және басқа тілдердегі онлайн дауыстар.
- Исеке және Рая секілді жүктелетін офлайн ONNX дауыстары.
- Қолмен мәтін енгізу, толық clipboard қою, TXT және Excel оқу.
- TXT/Excel үшін 1 000 000 таңбаға дейін ішкі бөліктермен өңдеу.
- Таймкод режимі және соңында бір толық WAV/MP3 нәтижесі.
- Дауыс үлгісін тыңдау, дайын нәтижені тыңдау, сақтау және жою.
- Үш тілдік интерфейс, жарық/қараңғы режим және portrait бағдарлау.
- Android 16 / API 36 және 16 KB page-size тексерісі.

## Нұсқа

- Version name: `5.6.1`
- Version code: `102640933`
- Package: `org.bmtts.bmtextspeech`
- Minimum Android: API 26
- Target Android: API 36

## Тексерілген түзету

Android bridge әдістері generated `PythonActivity` ішіне build кезінде қосылады. Соның арқасында модель архивін ашу, офлайн Исеке/Рая генерациясы, preview, voice verification және Дәулет таймкодындағы MP3→WAV түрлендіру әр worker thread ішінде тұрақты жұмыс істейді.

## Desktop іске қосу

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-desktop.txt
python main.py
```

## Android build (WSL/Ubuntu)

1. Android SDK/NDK, Java 17 және Buildozer орнатыңыз.
2. Қажет орта жолдарын build скрипттерінде немесе environment арқылы баптаңыз.
3. Keystore паролін shell тарихына жазбай, environment арқылы беріңіз.
4. Толық build:

```bash
export KS_PASS='your-keystore-password'
bash tools/run_final_build.sh
```

Телефонға арналған жылдам production APK build:

```bash
bash tools/build_production_apk.sh
```

Release алдында APK қолтаңбасын, package/version мәндерін және `zipalign -c -P 16 -v 4` нәтижесін міндетті түрде тексеріңіз.
