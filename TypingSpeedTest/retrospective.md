# Lesson Learned

## Difficulties encountered during the design.

No particular difficulty found during prototyping as I used some screenshots of the real game taken from the suggested website.

## Programming the skeleton of the app and code the entire game in Python.

This time coding the entire game would have been quite difficult and complex. 
I overcame this difficulty by detailing the README.md as much as possible so that Claude could do the work with precision. Then, I refined/reiterated the result to fix the bugs. 

## How I thought to broke down the work:

-  Create the GUI layout using Tkinter.
-  Add a text display area with sample typing content.
-  Create an input field for the user to type.
-  Implement a timer to track typing duration.
-  Calculate typing speed in words per minute (WPM).
-  Add accuracy checking by comparing typed text with the original sample.
-  Display results such as WPM and accuracy after completion.
-  Improve the interface and user experience with labels and formatting.

The most difficult part was handling real-time typing analysis and accuracy checking. Some challenges included:
-  tracking typing speed dynamically,
-  handling timing correctly,
-  comparing typed characters accurately,
-  and managing user mistakes without breaking the flow.

Another challenge was ensuring the interface remained responsive while the timer and typing detection worked continuously.
I also spent time debugging issues related to:
-  incorrect WPM calculations,
-  timing synchronization,
-  and text comparison logic.

## Final notes

In the end, I asked Claude to comment the main.py as much as possible for a junior Python programmer, so that, in the future, the code could be maintained and fixed more easily. 