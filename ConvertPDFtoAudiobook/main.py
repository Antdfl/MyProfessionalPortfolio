import os
import glob
import PyPDF2
from deep_translator import GoogleTranslator
from gtts import gTTS
import os
from pathlib import Path

db_path = Path(__file__).parent
#print(db_path)  

# # Ora (deep-translator)
# result = GoogleTranslator(source="en", target="it").translate("hello")
# print(result)

tts = gTTS('hello')
tts.save(db_path / 'hello.mp3')
