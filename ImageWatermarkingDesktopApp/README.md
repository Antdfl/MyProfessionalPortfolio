# ANALYSIS AND DESIGN DOCUMENT

## Requirements

Using what you have learnt about Tkinter, you will create a desktop application with a Graphical User Interface (GUI) where you can upload an image and use Python to add a watermark logo/text.

Normally, you would have to use an image editing software like Photoshop to add the watermark, but your program is going to do it automatically.

Use case: e.g you want to start posting your photos to Instagram but you want to add your website to all the photos, you can now use your software to add your website/logo automatically to any image.

A similar online service is: https://watermarkly.com/

You might need:
https://pypi.org/project/Pillow/
https://docs.python.org/3/library/tkinter.html
and some Googling.

## ANALYSYS

What is Pillow?
he Python Imaging Library adds image processing capabilities to your Python interpreter.

This library provides extensive file format support, an efficient internal representation, and fairly powerful image processing capabilities.

The core image library is designed for fast access to data stored in a few basic pixel formats. It should provide a solid foundation for a general image processing tool.

### USER INTERFACE

I imagine a text on the center top of the app:

- Add Watermark
- Button to upload the file with "Upload the file"
- After the elaboration will appear a square button with the label "Download", so that you can download the file containing your watermark.

The question is: when I have a file, how can I add a watermark?
See the Design in the implement watermark detail.

## DESIGN

We need import Pillow and some other utilities.

1. Import necessary library
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade Pillow

2. Prepare a skeleton of the app.

3. Implement the watermarking
https://blog.pythonlibrary.org/2017/10/17/how-to-watermark-your-photos-with-python/

Here's the suggested code
from PIL import Image

def watermark_with_transparency(input_image_path,
                                output_image_path,
                                watermark_image_path,
                                position):
    base_image = Image.open(input_image_path)
    watermark = Image.open(watermark_image_path)
    width, height = base_image.size

    transparent = Image.new('RGBA', (width, height), (0,0,0,0))
    transparent.paste(base_image, (0,0))
    transparent.paste(watermark, position, mask=watermark)
    transparent.show()
    transparent.save(output_image_path)


if __name__ == '__main__':
    img = 'lighthouse.jpg'
    watermark_with_transparency(img, 'lighthouse_watermarked3.jpg',
                                'watermark.png', position=(0,0))

At the beginning test the watermarking color with your watermarking file and a fixed image in your code.
When you realise that your code works, you can use the uploaded image and use your algorithm in a more generic way for whatever image file you want.

4. Put all together and test to obtain the desired results.
