Passport Studio OpenCV fix

IMPORTANT: In Streamlit Cloud app settings, change Python version from 3.14 to 3.12, then save/reboot the app.

In the GitHub repository used by the live app (passport-studio):
1. Replace requirements.txt with the requirements.txt in this ZIP.
2. Commit the change to main.
3. In Streamlit Cloud, reboot the app and wait for dependency installation to finish.
4. Test photo generation. The error `cv2 has no attribute CascadeClassifier` should be fixed by installing a compatible OpenCV version.

Do not replace app.py for this fix; the screenshot shows the immediate error is the installed OpenCV package.
