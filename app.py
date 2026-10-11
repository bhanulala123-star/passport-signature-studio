import io
import math
import numpy as np
import streamlit as st
import cv2
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont

st.set_page_config(page_title="Passport Photo & Signature Studio", page_icon="📸", layout="centered")

st.title("📸 Passport Photo & Signature Studio")
st.caption("Mobile-friendly photo cleanup, background replacement, passport crops, and signature tools.")

st.info("Privacy note: Images are processed by this Streamlit app. If you deploy it publicly, uploads may be processed on the hosting server. Avoid uploading sensitive documents to a public app.")

def pil_to_cv(img):
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)

def cv_to_pil(img):
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

def straighten_face(image):
    """Try to estimate head tilt from detected eyes. This does not correct perspective or every head angle."""
    img = image.convert("RGB")
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    eye_path = cv2.data.haarcascades + "haarcascade_eye.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    eye_cascade = cv2.CascadeClassifier(eye_path)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return img, "No face detected; kept the original orientation."
    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
    roi = gray[y:y+int(h*0.65), x:x+w]
    eyes = eye_cascade.detectMultiScale(roi, scaleFactor=1.1, minNeighbors=5, minSize=(12, 12))
    if len(eyes) < 2:
        return img, "Face detected, but both eyes were not found reliably; kept the original orientation."
    # Choose two largest eye candidates and calculate the tilt.
    eyes = sorted(eyes, key=lambda r: r[2] * r[3], reverse=True)[:2]
    centers = sorted([(x + ex + ew/2, y + ey + eh/2) for ex, ey, ew, eh in eyes], key=lambda p: p[0])
    (x1, y1), (x2, y2) = centers
    angle = math.degrees(math.atan2(y2-y1, x2-x1))
    if abs(angle) > 25:
        return img, f"Face found, but estimated tilt ({angle:.1f}°) was too large for a safe automatic correction."
    if abs(angle) < 0.6:
        return img, "Face is already approximately level."
    h0, w0 = arr.shape[:2]
    matrix = cv2.getRotationMatrix2D((w0/2, h0/2), angle, 1.0)
    rotated = cv2.warpAffine(arr, matrix, (w0, h0), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(rotated), f"Applied an estimated {angle:.1f}° tilt correction."

def remove_bg(img):
    from rembg import remove, new_session
    # Session is cached for repeated processing in the same app session.
    if "rembg_session" not in st.session_state:
        st.session_state.rembg_session = new_session("u2net")
    result = remove(img.convert("RGBA"), session=st.session_state.rembg_session)
    return result.convert("RGBA")

def enhance_image(img, sharpness=1.25, contrast=1.06, color=1.03, brightness=1.02):
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    rgb = ImageEnhance.Color(rgb).enhance(color)
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    rgb = ImageEnhance.Sharpness(rgb).enhance(sharpness)
    # Gentle unsharp mask adds definition without aggressive skin smoothing.
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.2, percent=90, threshold=3))
    return rgb

def fit_portrait(img, size=(600, 800), bg=(245, 245, 242)):
    """Center-crop to 3:4-ish portrait and resize. Uses a simple contain/cover crop."""
    img = img.convert("RGB")
    target_w, target_h = size
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = max(0, (src_w - new_w)//2)
        img = img.crop((left, 0, left+new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = max(0, (src_h - new_h)//2)
        img = img.crop((0, top, src_w, top+new_h))
    return img.resize(size, Image.Resampling.LANCZOS)

def composite_on_bg(fg, bg_color):
    bg = Image.new("RGBA", fg.size, (*bg_color, 255))
    bg.alpha_composite(fg)
    return bg.convert("RGB")

def add_border_shadow(img, border=10, shadow=12):
    img = img.convert("RGB")
    # Canvas includes a subtle shadow margin and a crisp white frame.
    canvas = Image.new("RGB", (img.width + 2*(border+shadow), img.height + 2*(border+shadow)), (255,255,255))
    shadow_layer = Image.new("RGBA", canvas.size, (0,0,0,0))
    draw = ImageDraw.Draw(shadow_layer)
    x0 = shadow + border
    y0 = shadow + border
    draw.rectangle([x0+3, y0+4, x0+img.width+3, y0+img.height+4], fill=(0,0,0,45))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(7))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow_layer)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([x0-border, y0-border, x0+img.width+border, y0+img.height+border], fill=(255,255,255,255))
    canvas.paste(img, (x0, y0))
    return canvas.convert("RGB")

def font_for(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def typed_signature(text, width=1000, height=260, ink=(18, 18, 24), font_size=120):
    canvas = Image.new("RGBA", (width, height), (255,255,255,0))
    draw = ImageDraw.Draw(canvas)
    font = font_for(font_size)
    bbox = draw.textbbox((0,0), text, font=font, stroke_width=1)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    scale = min((width-40)/max(tw,1), (height-35)/max(th,1), 1.0)
    if scale < 1:
        font = font_for(max(18, int(font_size*scale)))
        bbox = draw.textbbox((0,0), text, font=font, stroke_width=1)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text(((width-tw)//2, (height-th)//2-bbox[1]), text, font=font, fill=(*ink,255), stroke_width=1, stroke_fill=(*ink,255))
    return canvas

def clean_signature(upload):
    """Convert dark ink on a light paper background to transparent pixels."""
    im = upload.convert("RGB")
    gray = np.array(ImageOps.grayscale(im))
    # Estimate ink opacity from darkness; white paper becomes transparent.
    alpha = np.clip((245.0 - gray.astype(np.float32)) * 3.0, 0, 255).astype(np.uint8)
    # Reduce faint paper texture/noise.
    alpha[alpha < 28] = 0
    rgba = np.zeros((gray.shape[0], gray.shape[1], 4), dtype=np.uint8)
    rgba[:, :, :3] = 15
    rgba[:, :, 3] = alpha
    out = Image.fromarray(rgba, "RGBA")
    bbox = out.getbbox()
    return out.crop(bbox) if bbox else out

def rotate_rgba(img, degrees):
    return img.rotate(degrees, expand=True, resample=Image.Resampling.BICUBIC)

def download_png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

tab_photo, tab_sign = st.tabs(["Passport photo", "Signature studio"])

with tab_photo:
    uploaded = st.file_uploader("Upload a face photo", type=["jpg", "jpeg", "png", "webp"], key="photo")
    if uploaded:
        original = Image.open(uploaded).convert("RGB")
        st.image(original, caption="Original photo", use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            do_straighten = st.checkbox("Try automatic face straightening", value=True)
            do_bg = st.checkbox("Remove background automatically", value=True)
            do_enhance = st.checkbox("Enhance detail and lighting", value=True)
        with col2:
            bg_choice = st.selectbox("Background color", ["Soft neutral (reference style)", "White", "Light grey", "Blue", "Custom"])
            if bg_choice == "White":
                bg = (255,255,255)
            elif bg_choice == "Light grey":
                bg = (238,240,242)
            elif bg_choice == "Blue":
                bg = (125,190,225)
            elif bg_choice == "Custom":
                hex_color = st.color_picker("Choose background", "#F5F5F2")
                bg = tuple(int(hex_color[i:i+2], 16) for i in (1,3,5))
            else:
                bg = (245,245,242)
            size_choice = st.selectbox("Output size", ["600 × 800 px (3:4 portrait)", "413 × 531 px (common passport-style crop)", "300 × 400 px"])
            sharpness = st.slider("Detail / sharpness", 0.8, 1.8, 1.15, 0.05)
        if st.button("✨ Create passport photo", type="primary", use_container_width=True):
            work = original
            note = ""
            if do_straighten:
                with st.spinner("Checking face alignment..."):
                    work, note = straighten_face(work)
                st.caption(note)
            if do_bg:
                try:
                    with st.spinner("Removing background (first run may take a little while)..."):
                        foreground = remove_bg(work)
                    processed = composite_on_bg(foreground, bg)
                except Exception as e:
                    st.error("Background removal failed. Install dependencies correctly and try again. Details: " + str(e))
                    st.stop()
            else:
                processed = work
            if do_enhance:
                processed = enhance_image(processed, sharpness=sharpness)
            if "413" in size_choice:
                dims = (413, 531)
            elif "300" in size_choice:
                dims = (300, 400)
            else:
                dims = (600, 800)
            cropped = fit_portrait(processed, dims, bg)
            framed = add_border_shadow(cropped, border=max(4, dims[0]//60), shadow=max(5, dims[0]//50))
            st.session_state["last_photo"] = framed
            st.image(framed, caption="Generated portrait preview", use_container_width=True)
            st.download_button("⬇️ Download passport photo (PNG)", data=download_png(framed), file_name="passport_photo.png", mime="image/png", use_container_width=True)
            st.caption("Tip: Review head size, shoulders, background and crop manually before using the image for an official document.")

with tab_sign:
    st.subheader("Make a clean signature")
    sign_mode = st.radio("Signature source", ["Upload signature image", "Type a name"], horizontal=True)
    signature = None
    if sign_mode == "Upload signature image":
        sign_file = st.file_uploader("Upload signature on paper or plain background", type=["jpg","jpeg","png","webp"], key="signature")
        if sign_file:
            signature = clean_signature(Image.open(sign_file))
            st.caption("The tool removes light paper pixels; dark paper or colored ink may need a cleaner scan.")
    else:
        typed = st.text_input("Type the name/signature", placeholder="e.g. Pankaj Yadav")
        ink_hex = st.color_picker("Ink color", "#111118")
        if typed.strip():
            ink_rgb = tuple(int(ink_hex[i:i+2], 16) for i in (1,3,5))
            signature = typed_signature(typed.strip(), ink=ink_rgb)
            signature = signature.crop(signature.getbbox()) if signature.getbbox() else signature
    if signature:
        c1, c2 = st.columns(2)
        with c1:
            rotation = st.slider("Rotate / straighten (degrees)", -45, 45, 0)
            scale = st.slider("Signature size (%)", 20, 180, 100)
        with c2:
            bold = st.slider("Ink boldness", 0, 3, 1)
            place_on_photo = st.checkbox("Place signature on last generated passport photo", value=False)
        signature = rotate_rgba(signature, rotation)
        if bold > 0:
            alpha = signature.getchannel("A")
            for _ in range(bold):
                alpha = alpha.filter(ImageFilter.MaxFilter(3))
            signature.putalpha(alpha)
        new_w = max(1, int(signature.width * scale/100))
        new_h = max(1, int(signature.height * scale/100))
        signature = signature.resize((new_w, new_h), Image.Resampling.LANCZOS)
        st.image(signature, caption="Transparent signature preview", use_container_width=True)
        st.download_button("⬇️ Download transparent signature (PNG)", data=download_png(signature), file_name="signature_transparent.png", mime="image/png", use_container_width=True)
        if place_on_photo:
            base_img = st.session_state.get("last_photo")
            if base_img is None:
                st.warning("First create a passport photo in the Passport photo tab.")
            else:
                composite = base_img.convert("RGBA")
                margin = max(12, composite.width//30)
                max_w = int(composite.width*0.48)
                if signature.width > max_w:
                    h = int(signature.height*max_w/signature.width)
                    signature = signature.resize((max_w, h), Image.Resampling.LANCZOS)
                x = composite.width - signature.width - margin
                y = composite.height - signature.height - margin
                composite.alpha_composite(signature, (max(0,x), max(0,y)))
                st.image(composite.convert("RGB"), caption="Photo with signature", use_container_width=True)
                st.download_button("⬇️ Download photo with signature", data=download_png(composite), file_name="passport_photo_with_signature.png", mime="image/png", use_container_width=True)

st.divider()
st.caption("This is an image-editing helper, not an official passport authority. Automatic face alignment only corrects estimated roll/tilt; it cannot reliably turn every side-facing or strongly angled face into a true frontal portrait.")
