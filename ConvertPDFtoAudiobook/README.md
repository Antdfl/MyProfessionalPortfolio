# ANALYSIS AND DESIGN DOCUMENT

## Requirements

Too tired to read? Build a python script that takes a PDF file, identifies the text and converts the text to speech. Effectively creating a free audiobook.

AI text-to-speech has come so far. They can sound more lifelike than a real audiobook.


Using what you've learnt about HTTP requests, APIs and Python scripting, create a program that can convert PDF files to speech.

You right want to choose your own Text-To-Speech (TTS) API. But here are some you can consider:

http://www.ispeech.org/api/#introduction
https://cloud.google.com/text-to-speech/docs/basics
https://aws.amazon.com/polly/

## FUNCTIONAL ANALYSIS

At the beginning, I'm evaluating the different libraries and their ease to use and maintain. So, even though the trainer has suggested to use the cloud and API library, why can't I use simpler and effective Python libraries instead of invoking a web API?

### TTS Python libraries 
In reality I found some easier to use TTS(Text To Speech) libraries and source of inspiration to build this Python script.

- https://pypi.org/project/gTTS/ 
https://gtts.readthedocs.io/en/latest/ --> gTTS (Google Text-to-Speech), a Python library and CLI tool to interface with Google Translate's text-to-speech API. Write spoken mp3 data to a file, a file-like object (bytestring) for further audio manipulation, or stdout. https://gtts.readthedocs.io/

### PDF reading library
- https://pypi.org/project/PyPDF2/ --> PyPDF2 is a free and open-source pure-python PDF library capable of splitting, merging, cropping, and transforming the pages of PDF files. It can also add custom data, viewing options, and passwords to PDF files. PyPDF2 can retrieve text and metadata from PDFs as well.

### A full example of multi PDF script 
A complete tool with source code that can help and be an example of how to use PDF and TTS libraries
- https://github.com/lazycatcoder/pdf-to-mp3/blob/main/pdf-to-mp3.py  

### How will my Python script work and what functionalities offer?

The script will take in input the following data:
1. pdf filename 
2. PDF language (e.g English, Italian, etc.)
3. Output language 
4. Output filename
After the user will have provided all the data the program will proceed this way:
- Extract  
 

