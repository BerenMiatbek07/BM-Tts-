# BM Voice Studio v5.6.4 PERSONAL

Бұл нұсқа v5.6.3 PERSONAL негізінде дайындалды.

## Жаңа: ElevenLabs Eleven v3
- Ресми ElevenLabs Text-to-Speech API қосылды.
- Model: `eleven_v3`.
- Қазақша (`kk`), орысша (`ru`), ағылшынша (`en`) тілдері.
- 6 дайын voice ID: Jessica, Liam, Announcer, Sammara, Sergeant, Spuds.
- ElevenLabs дауысы таңдалғанда жеке API key өрісі көрсетіледі.
- API key source/EXE ішіне тігілмейді.
- Preview және ұзын мәтінді resumable chunk generation қолдайды.
- Timecode режимінде Eleven v3 MP3 -> WAV түрлендіруі қосылды.
- Pause/resume/retry merge сессиясы сақталады.

## Қауіпсіз интеграция
Пайдаланушы берген `davidsuragan/elevenlabs-alpha-v3` репозиторийі қаралды.
Онда ерте alpha қолжетімділігін browser headers/Firebase/Playwright арқылы
айналып өту әдістері бар. Олар бұл source-қа көшірілген жоқ. Қазіргі ресми
ElevenLabs құжаттамасында Eleven v3 API қолжетімді болғандықтан, тек ресми
endpoint және API key қолданылады.

## Алдыңғы мүмкіндіктер
- Soniox TTS (personal compatibility integration).
- Windows OmniVoice voice clone: Қазақша / Русский / English.
- Edge TTS және Sherpa/Piper offline дауыстары.

## Validation
- Python compileall: PASS
- ElevenLabs + Soniox + clone selected tests: 45 PASS
- Толық Windows runtime/EXE smoke test: Windows-та build жасағаннан кейін.
