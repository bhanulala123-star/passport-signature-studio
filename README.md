# Passport Photo & Signature Studio

A mobile-friendly Streamlit app for:
- attempting automatic face tilt correction using OpenCV face/eye detection
- removing the background using `rembg`
- replacing the background with soft neutral, white, grey, blue, or a custom color
- gentle sharpness, contrast, color and lighting enhancement
- passport-style portrait crop with a white frame and subtle shadow
- cleaning a handwritten signature into transparent PNG
- typing a name as a signature-style graphic, then rotating/resizing/bolding it
- optionally placing a signature on the last generated photo

## Run locally

Python 3.10 or 3.11 recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown by Streamlit. On a phone, both the phone and computer should be on the same network if you want to open the local app from your phone; alternatively deploy it online.

## Deploy using GitHub + Streamlit Community Cloud

1. Create a GitHub repository, e.g. `passport-signature-studio`.
2. Upload `app.py`, `requirements.txt`, and `README.md`.
3. Open https://share.streamlit.io/ and sign in with GitHub.
4. Choose **Create app**, select the repository and branch, set main file path to `app.py`, then deploy.
5. The first background-removal run may take time while the model downloads.

## Important limitations

- Automatic straightening estimates tilt from eye positions. It does not reliably correct perspective, profile faces, closed eyes, heavy occlusion, or every camera angle.
- Background removal may have errors around hair, veils, earrings, glasses and fine edges.
- Enhancement improves the existing pixels; it does not truly restore detail that was never captured.
- Typed text is a signature-like graphic, not the person's legal handwritten signature. Use a real signature image where a genuine signature is required.
- Review official photo rules for the intended document before submitting.
- Free hosting has CPU, memory, sleep and usage limits. `rembg` models may make the first run slow.
- Do not use a public deployment for sensitive photos unless you understand the hosting and privacy implications.

## Suggested repository structure

```text
passport-signature-studio/
├── app.py
├── requirements.txt
└── README.md
```
