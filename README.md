# Assistly

Assistly is a desktop AI assistant that acts as a deeply integrated software mentor directly on your screen. It features a transparent, unobtrusive interface that sits over your applications to offer real-time guidance without interrupting your normal workflow.

## Key Features

*   **Interactive Guided Cursor:** When you ask for help (for example, finding a specific setting or locating an application), the AI doesn't just explain what to do—it physically moves a custom cursor to point exactly at the button or UI element you need to interact with.
*   **Context Aware:** Assistly uses background UI scanning and screen analysis to understand what is currently visible on your screen. It can adapt to the layout of various applications, including web browsers, code editors, and design tools.
*   **Customizable Cursors:** You can change the appearance of the guided cursor to different themes to suit your preference.
*   **Voice Integration:** Includes a built-in voice engine that can read responses back to you for hands-free guidance.
*   **Persistent Overlay:** The interface is guaranteed to stay visible over your active applications and windows.

## Setup Instructions

1.  Run the `setup.bat` file located in the `app/` folder. This script automatically creates a Python virtual environment and installs all the required dependencies.
2.  Duplicate or rename the `app/.env.example` file to `app/.env`.
3.  Add your [Gemini API Key](https://aistudio.google.com/app/apikey) to the new `.env` file.
4.  Launch the application by running `python main.py` from inside the `app/` directory.

## Usage

*   Press **Ctrl+Space** anywhere in Windows to toggle the Assistly interface on or off.
*   Click the notch bar at the top of your screen to access the settings panel and change your cursor style.
*   Type your question into the conversation panel and allow the AI to guide you.
