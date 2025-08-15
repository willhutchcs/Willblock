
# Willblock

Willblock is a real-time ad-blocker for live NBA broadcasts. The script will take a screenshot of your window every few seconds and use a tensorflow model to decide if it's basketball or an ad. If it's an ad, it'll display an overlay image with music! I've included both, but they can be swapped out if you'd like.

All the training data was collected from official reuploads on YouTube so you can go to sleep at night knowing your ad-block is 100% in the clear!

## Example
![Logo](https://github.com/willhutchcs/Willblock/blob/main/example.png)

## Installation and Usage

To run on your own machine you need the following packages:
```bash
  pip install pywin32 tkinter torch torchvision keyboard threading python-vlc pyopengl pygetwindow pycaw comtypes ctypes PIL
```

This program is designed to capture Firefox. If you want to use another broswer/application you can manually change it in the script.
*If you're using a web browser, you have to disable Hardware Acceleration.*

By default, the hotkey to disable the real-time detection is ```esc``` and you can turn it back on with ```q```.

The program will utilize CUDA cores if available and use CPU cores if not.

    
## Authors

- Me and ChatGPT :)

