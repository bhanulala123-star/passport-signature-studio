import io, math, traceback
import streamlit as st
import numpy as np
import cv2
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw

st.set_page_config(page_title="Passport Photo Studio", page_icon="📸", layout="centered")
st.title("📸 Passport Photo Studio")
st.write("Diagnostic build — button status and errors are shown on this page.")

def png_bytes(img):
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()

def tilt_correct(img):
    arr = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    eyes_c = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    faces = face.detectMultiScale(gray, 1.1, 5, minSize=(60,60))
    if len(faces) == 0:
        return Image.fromarray(arr), "Face not detected; kept original angle."
    x,y,w,h = max(faces, key=lambda r:r[2]*r[3])
    eyes = eyes_c.detectMultiScale(gray[y:y+int(h*.65), x:x+w], 1.1, 5, minSize=(12,12))
    if len(eyes) < 2:
        return Image.fromarray(arr), "Eyes not detected reliably; kept original angle."
    eyes = sorted(eyes, key=lambda e:e[2]*e[3], reverse=True)[:2]
    centers = sorted([(x+ex+ew/2, y+ey+eh/2) for ex,ey,ew,eh in eyes])
    (x1,y1),(x2,y2)=centers
    angle=math.degrees(math.atan2(y2-y1,x2-x1))
    if abs(angle) > 20 or abs(angle) < .5:
        return Image.fromarray(arr), f"Auto-rotation skipped (estimated tilt {angle:.1f}°)."
    h0,w0=arr.shape[:2]
    m=cv2.getRotationMatrix2D((w0/2,h0/2),angle,1.0)
    out=cv2.warpAffine(arr,m,(w0,h0),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(out), f"Tilt correction applied ({angle:.1f}°)."

def crop_portrait(img, dims):
    img=img.convert("RGB")
    tw,th=dims; sw,sh=img.size
    if sw/sh > tw/th:
        nw=int(sh*tw/th); left=(sw-nw)//2
        img=img.crop((left,0,left+nw,sh))
    else:
        nh=int(sw*th/tw); top=(sh-nh)//2
        img=img.crop((0,top,sw,top+nh))
    return img.resize(dims, Image.Resampling.LANCZOS)

def frame(img):
    border=max(4,img.width//60); margin=max(6,img.width//50)
    out=Image.new("RGB",(img.width+2*(border+margin),img.height+2*(border+margin)), "white")
    x=border+margin; y=border+margin
    shade=Image.new("RGBA",out.size,(0,0,0,0))
    d=ImageDraw.Draw(shade); d.rectangle((x+3,y+4,x+img.width+3,y+img.height+4),fill=(0,0,0,35))
    shade=shade.filter(ImageFilter.GaussianBlur(6))
    out=Image.alpha_composite(out.convert("RGBA"),shade)
    out.paste(img,(x,y))
    return out.convert("RGB")

def remove_background(img):
    from rembg import remove, new_session
    if "bg_session" not in st.session_state:
        st.session_state.bg_session = new_session("u2net")
    return remove(img.convert("RGBA"), session=st.session_state.bg_session).convert("RGBA")

uploaded=st.file_uploader("1) Upload photo", type=["jpg","jpeg","png","webp"])
if uploaded:
    try:
        original=Image.open(uploaded).convert("RGB")
        st.image(original, caption="Uploaded photo", use_container_width=True)
    except Exception as e:
        st.error(f"Could not read uploaded image: {e}")
        st.stop()

    c1,c2=st.columns(2)
    with c1:
        straighten=st.checkbox("Try to straighten face tilt", True)
        bg_remove=st.checkbox("Remove background (AI model)", True)
    with c2:
        bg_name=st.selectbox("Background",["Soft neutral","White","Light grey","Blue"])
        size=st.selectbox("Size",["600 x 800","413 x 531","300 x 400"])
    colors={"Soft neutral":(245,245,242),"White":(255,255,255),"Light grey":(238,240,242),"Blue":(125,190,225)}
    if st.button("✨ Create passport photo", type="primary", use_container_width=True):
        st.session_state["last_status"]="Button clicked"
        st.info("STEP 1/4 — Button clicked. Processing started.")
        try:
            work=original.copy()
            if straighten:
                with st.spinner("STEP 1/4 — Checking face alignment..."):
                    work, note=tilt_correct(work)
                st.write(note)
            if bg_remove:
                st.info("STEP 2/4 — AI background removal started. First run can take a few minutes.")
                with st.spinner("Removing background. Please wait..."):
                    fg=remove_background(work)
                bg=Image.new("RGBA",fg.size,(*colors[bg_name],255))
                bg.alpha_composite(fg)
                processed=bg.convert("RGB")
            else:
                processed=work
                st.info("STEP 2/4 — Background removal skipped.")
            with st.spinner("STEP 3/4 — Enhancing image..."):
                processed=ImageEnhance.Color(processed).enhance(1.03)
                processed=ImageEnhance.Contrast(processed).enhance(1.05)
                processed=ImageEnhance.Sharpness(processed).enhance(1.2)
                processed=processed.filter(ImageFilter.UnsharpMask(radius=1,percent=70,threshold=3))
            dims=(413,531) if size.startswith("413") else ((300,400) if size.startswith("300") else (600,800))
            with st.spinner("STEP 4/4 — Cropping and adding white border..."):
                result=frame(crop_portrait(processed,dims))
            st.success("SUCCESS — Photo created.")
            st.image(result,caption="Generated passport-style photo",use_container_width=True)
            st.download_button("⬇️ Download PNG",png_bytes(result),"passport_photo.png","image/png",use_container_width=True)
        except Exception as e:
            st.error("PROCESSING FAILED — The exact error is shown below. Copy the error text if possible.")
            st.code(f"{type(e).__name__}: {e}")
            with st.expander("Technical details"):
                st.code(traceback.format_exc())
else:
    st.info("Upload a photo first. The Generate button appears after you upload an image.")

st.divider()
st.subheader("Quick test without AI background removal")
st.caption("If generation does not work, uncheck AI background removal and try again. This tests the button and photo pipeline without loading the AI model.")
