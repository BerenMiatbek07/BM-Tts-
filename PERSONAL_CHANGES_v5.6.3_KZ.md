# BM Voice Studio v5.6.3 PERSONAL

Бұл жеке Windows build v5.6.2 негізінде дайындалды.

## Қосылғаны
- Soniox web TTS: API key өрісінсіз жеке қолдануға арналған compatibility client.
- Soniox-та 35 дауыс: әйел/ер дауыс каталогы.
- Қазақша (`kk`) Soniox дауысын негізгі дауыс таңдағыштан қолдану.
- Soniox preview және ұзын мәтінді chunk арқылы бір MP3-ке шығару.
- Windows OmniVoice clone үшін үлгі тілін таңдау: Қазақша / Русский / English.
- OmniVoice генерациясына target language (`kk`, `ru`, `en`) нақты беріледі.

## Аудиттен кейін түзетілгені
- Орысша clone reference таңдалғанда verifier оны ағылшынға ауыстырып жіберетін қате түзетілді.
- Орысша live challenge қысқа, 5–10 секундқа лайық мәтінге өзгертілді.
- Soniox Session бір уақытта бірнеше thread қолданбауы үшін generation 1 worker-ге бекітілді.
- Sherpa/Piper download кезіндегі кодировкасы бұзылған қазақша error мәтіндері түзетілді.
- Timecode үшін MP3→WAV Windows-та алдымен `soundfile`, қажет болса FFmpeg арқылы ашылады.
- Windows build `.bat` Python 3.12-ні тексереді және EXE жинамай тұрып unit tests іске қосады.

## Validation
- `compileall`: PASS
- unit tests: 44 PASS
- Windows platform stub: 44 PASS

Нақты Soniox live HTTP және нақты OmniVoice model inference Windows-та EXE smoke test кезінде соңғы рет тексеріледі.
