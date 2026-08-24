# BM Voice Studio v5.6.4 PERSONAL

BM Voice Studio — қазақша/орысша/ағылшынша мәтінді дыбысқа айналдыруға арналған Windows/Python жобасы.

## Негізгі мүмкіндіктер
- Edge TTS
- Soniox TTS интеграциясы
- ElevenLabs Eleven v3 — ресми API арқылы
- OmniVoice voice clone: Қазақша (`kk`), Русский (`ru`), English (`en`)
- Ұзын мәтінді бөліп генерациялау
- MP3/WAV және timecode режимдері
- Windows EXE жинауға арналған `BUILD_WINDOWS_PERSONAL.bat`

## Windows-та жинау
1. Python 3.12 x64 орнатыңыз.
2. Репозиторийді жүктеп алыңыз.
3. `BUILD_WINDOWS_PERSONAL.bat` файлын іске қосыңыз.
4. Скрипт dependency-лерді орнатып, тесттерді орындап, PyInstaller арқылы EXE жинайды.

Толық нұсқаулық: `README_KZ.md` және `BUILD_FIX_README_KZ.txt`.

## Ескерту
- ElevenLabs бөлімі ресми API key арқылы жұмыс істейді.
- Voice clone функциясын тек өз даусыңызға немесе қолдануға рұқсатыңыз бар дауысқа қолданыңыз.
- Үлкен Android native кітапханалары бұл репозиторийге салынбаған; Windows build үшін олар қажет емес.

Жеке қолдануға арналған v5.6.4 source snapshot.
