# REQUIREMENTS

Using Tkinter and what you have learnt about building GUI applications with Python, build a desktop app that assesses your typing speed. Give the user some sample text and detect how many words they can type per minute.

The average typing speed is 40 words per minute. But with practice, you can speed up to 100 words per minute.

You can try out a web version here:
https://typing-speed-test.aoeu.eu/

If you have more time, you can build your typing speed test into a typing trainer, with high scores and more text samples. You can design your program any way you want.


# ANALYSIS

We will need a tkinter interface structured this way.

## Layout mapping 

1. In the fist row we wil have the following fields:
   - instant "Corrected CPM"(label) (characters per minute) with a text field indicating the number of character typed.
   - WPM (Words per minute) as the label plus the text field indicating the instantaneous words per minute.
   - Time Left(label) with a text field updated in real time containing the remaining seconds to the end of the game.  
   - A Clickable link called Restart that reset all the variable and put the game in its initial state
   - Two flags: UK flag(default language) and Italian flag.

2. The second Tkinter row will be the main text. In this case, we will extract based on the choice of language elected in the first row of the user interface.
We will need a rotation of texts to present to our gamers both in Italian and in English (10+10). To store and use these texts, we can use a list or a dictionary. 
Where we can get the texts we need? We will extract a variety of text from Lorem Ispum multilanguage website for free.
I really appreciated this multilanguage Lorem Ispum website:
https://loremipsummultilang.com/

3. The third row is where the user needs to type that we need to monitor.
For each keystroke we will check:
  - Whether we have formed one word
  - the number of caracters of the word we are typing: the number of characters of the word we are typing exceed 10 characters more than we expected we will show a popup that will specify "Er...The word "X" is made of y characters. Don't forget to press the bar space after each word. (You have to start over now)".
Highlight the characters user is typing in the text given in the second row uf the Tkinter app.  
  - If we use the Enter batton instead of the space bar display a popu with the following message "Use bar space instead of enter. I'ts faster. Use the Restart Link to start over." 

The countdown should start as the user starts typing in the proper line of the app. 
After the time is zero dislay in the time text "Last word" e wait for the user insert the word plus a space.

In the end. Clean the screen and in the central part display:
Average CPM, average WPM.
On the line below all the error the user made with the correct word.
For example:
You typed "dfsdsfdss" instead of "way"
You typed "pippo" instead of "switch"
etc.
Finally, if the user has used the Enter button instead of spece bar at least once write:
"By the way, you used enter instead of the space bar. Try using space next time; this will probably result in a greater overall typing speed." 


# DESIGN 

The program layout should be based on the three image present in the folder:

## main_app.png
It represents the start or the restart of the game.
The content of this layout is defined in the previous section ANALYSIS

## too_many_wrong_chars.png 
It represents the situation where the user gets wrong more than 10 characthers compared to the current word or it use the enter button instead of a space. 

## game_summary.png
This layout represents the game statistics visualization at the end of the game.
For the content and the behaviour of this part please refer to the specific section on the ANALYSIS.






