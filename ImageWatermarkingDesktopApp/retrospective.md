# Lesson Learned

## Difficulties encountered during the design

### Prototyping
I tried to use Figma to prototype the Tkinter final layout but I'm not so into Figma. Initially I thought that I needed to search for some Tkinter template to adapt and personalise, but I soon realised that I needed something really specific for my app.

### Drawing the skeleton of the app. 
As well as in the prototype I struggled to prepare a Layout with frames as in the practice I didn't come across with some specific examples and the Tkinter documentation is not so rich of them.

## How I overcame those difficulties

### Prototyping

For the prototyping, I installed the Free Figma Desktop app and came across an AI assisted prototype feature called "Figma Make". So I gave it the following prompt:
"I've created a watermarking application styled to look like a classic Tkinter desktop interface. It features the traditional Windows 98 aesthetic with gray beveled borders, a blue title bar, and classic desktop controls. You can upload images, customize the watermark text (defaulted to "www.mywebsite.com"), adjust position, font size, and opacity, then download the watermarked result."
 Figma created a fully-fledged app with other features that were out of scope, so I asked to eliminate the ones I didn't need so I reached the desired result for my prototype.

### Layout
As for the Tkinter layout skeleton I gave the layout picture prototype to Claude that wrote the code necessary. 

## Final touch
Finally I innested the code necessary for adding the watermarked in the main program and tested thorougly with the new found feature "Watermark position". At the beginning, I received an error in the paste pillow command as I passed the string "Bottom Right" when I needed to pass the position (x,y) where to embed my watermark. So, I did all the calculation needed within the watermardk adding procedure and tested all the possible combinations of positions. 