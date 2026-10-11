import io
import textwrap
import traceback
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, ImageFont
import streamlit as st

st.set_page_config(page_title="Passport Photo & Signature Studio", page_icon="📸", layout="centered")
st.title("📸 Passport Photo & Signature Studio")
st.write("Create a passport-style photo, clean background, and add or type a signature.")
st.info("Tip: AI background removal is optional. First test with it OFF.")

def load_image(upload):
    im = Image.open(upload)
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
    return im

def make_background_transparent(im):
    try:
        from rembg import remove
        out = remove(im.convert("RGBA"))
        if not isinstance(out, Image.Image):
            out = Image.open(io.BytesIO(out))
        return out.convert("RGBA"), None
    except Exception as e:
        return im.convert("RGBA"), f"AI background removal failed: {type(e).__name__}: {e}"

def contain_crop(im, width, height):
    im = im.convert("RGB")
    target_ratio = width / height
    ratio = im.width / im.height
    if ratio > target_ratio:
        neww = int(im.height * target_ratio)
        left = (im.width-neww)//2
        im = im.crop((left,0,left+neww,im.height))
    else:
        newh = int(im.width / target_ratio)
        top = max(0, (im.height-newh)//2)
        im = im.crop((0,top,im.width,top+newh))
    return im.resize((width,height), Image.Resampling.LANCZOS)

def font_pick(size, italic=False):
    candidates = (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
                   "/usr/share/fonts/truetype/liberation2/LiberationSans-Italic.ttf"] if italic else
                  ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"])
    for p in candidates:
        try: return ImageFont.truetype(p, size)
        except Exception: pass
    return ImageFont.load_default()

def clean_signature(upload):
    sig = load_image(upload).convert("RGBA")
    # Convert near-white pixels to transparent while preserving dark ink.
    px = sig.load()
    for y in range(sig.height):
        for x in range(sig.width):
            r,g,b,a = px[x,y]
            lum = (r+g+b)//3
            if lum > 242:
                px[x,y] = (255,255,255,0)
            elif lum > 200:
                alpha = int(255*(242-lum)/42)
                px[x,y] = (r,g,b,alpha)
    bbox = sig.getbbox()
    return sig.crop(bbox) if bbox else sig

photo_file = st.file_uploader("1) Upload your photo", type=["jpg","jpeg","png","webp"])
if photo_file:
    try:
        original = load_image(photo_file)
        st.image(original, caption="Uploaded photo", use_container_width=True)
        st.subheader("2) Photo settings")
        remove_bg = st.checkbox("Remove background (AI model)", value=False)
        bg_choice = st.selectbox("Background", ["White", "Soft neutral", "Light blue", "Keep original"], index=0)
        size_choice = st.selectbox("Photo size", ["600 x 800 (3:4)", " passport 35 x 45 mm (600 x 771)", "Square 600 x 600"], index=0)
        straighten = st.checkbox("Try to straighten face tilt", value=False, help="This simple version does not use face-detection; keep off unless needed.")
        add_border = st.checkbox("Add white border and subtle shadow", value=True)
        st.subheader("3) Signature (optional)")
        sig_mode = st.radio("Signature method", ["No signature", "Upload signature", "Type signature"], horizontal=False)
        sig_img = None
        if sig_mode == "Upload signature":
            sig_file = st.file_uploader("Upload signature image (PNG/JPG)", type=["png","jpg","jpeg"], key="sigupload")
            if sig_file:
                try:
                    sig_img = clean_signature(sig_file)
                    st.image(sig_img, caption="Cleaned signature preview", width=260)
                except Exception as e:
                    st.error(f"Could not read signature: {e}")
        elif sig_mode == "Type signature":
            sig_text = st.text_input("Type the name/signature", placeholder="Your name")
            sig_style = st.selectbox("Typed signature style", ["Italic", "Simple bold"])
            if sig_text.strip():
                f = font_pick(72, italic=(sig_style=="Italic"))
                temp = Image.new("RGBA",(1600,220),(255,255,255,0))
                d = ImageDraw.Draw(temp)
                d.text((15,25), sig_text.strip(), font=f, fill=(20,20,35,255), stroke_width=1)
                bbox = temp.getbbox()
                sig_img = temp.crop(bbox) if bbox else temp
                st.image(sig_img, caption="Typed signature preview", width=300)
        sig_position = "Bottom right"
        if sig_mode != "No signature":
            sig_position = st.selectbox("Place signature", ["Bottom right", "Bottom center", "Bottom left"], index=0)
            sig_width = st.slider("Signature size", 10, 40, 22, 1, format="%d%% of photo width")
        st.caption("Use a signature only if you have permission to use it. Check your destination's official photo/signature requirements.")

        if st.button("✨ Generate passport photo", type="primary", use_container_width=True):
            try:
                status = st.status("Generating your photo…", expanded=True)
                work = original.copy()
                warning = None
                if remove_bg:
                    status.write("Removing background with AI…")
                    work, warning = make_background_transparent(work)
                else:
                    status.write("Skipping AI background removal…")
                if work.mode == "RGBA" and bg_choice != "Keep original":
                    bg_map = {"White": (255,255,255), "Soft neutral": (245,243,238), "Light blue": (220,235,250)}
                    bg = Image.new("RGBA", work.size, (*bg_map[bg_choice],255))
                    if work.getchannel("A").getextrema() != (255,255):
                        bg.alpha_composite(work)
                        work = bg.convert("RGB")
                    elif remove_bg:
                        bg.alpha_composite(work)
                        work = bg.convert("RGB")
                elif work.mode == "RGBA":
                    canvas = Image.new("RGBA", work.size, (255,255,255,255))
                    canvas.alpha_composite(work)
                    work = canvas.convert("RGB")
                else:
                    work = work.convert("RGB")
                status.write("Enhancing and sizing photo…")
                work = ImageEnhance.Contrast(work).enhance(1.04)
                work = ImageEnhance.Color(work).enhance(1.02)
                work = ImageEnhance.Sharpness(work).enhance(1.12)
                if size_choice.startswith("600 x 800"):
                    w,h=600,800
                elif size_choice.startswith(" passport"):
                    w,h=600,771
                else:
                    w,h=600,600
                out = contain_crop(work,w,h)
                if add_border:
                    frame = Image.new("RGB",(w+24,h+24),"white")
                    frame.paste(out,(12,12))
                    frame = frame.filter(ImageFilter.GaussianBlur(0.2))
                    out = frame
                if sig_img is not None:
                    status.write("Adding signature…")
                    sig = sig_img.copy().convert("RGBA")
                    maxw = int(w * sig_width / 100)
                    maxh = int(h * 0.13)
                    sig.thumbnail((maxw,maxh), Image.Resampling.LANCZOS)
                    # put signature within lower margin of the photo, dark ink over light background
                    if sig_position == "Bottom right":
                        x = max(0, w - sig.width - 22)
                    elif sig_position == "Bottom center":
                        x = max(0, (w-sig.width)//2)
                    else:
                        x = 22
                    y = max(0, h - sig.height - 24)
                    if add_border:
                        x += 12; y += 12
                    out_rgba = out.convert("RGBA")
                    out_rgba.alpha_composite(sig, (x,y))
                    out = out_rgba.convert("RGB")
                status.update(label="Photo ready!", state="complete", expanded=False)
                st.success("Generation complete.")
                st.image(out, caption="Generated passport-style photo", use_container_width=True)
                photo_bytes = io.BytesIO()
                out.save(photo_bytes, format="PNG")
                st.download_button("⬇️ Download photo (PNG)", data=photo_bytes.getvalue(), file_name="passport_photo.png", mime="image/png", use_container_width=True)
                if sig_img is not None:
                    sb = io.BytesIO(); sig_img.save(sb, format="PNG")
                    st.download_button("⬇️ Download cleaned signature (PNG)", data=sb.getvalue(), file_name="signature_clean.png", mime="image/png", use_container_width=True)
                if warning:
                    st.warning(warning + " Photo was created without AI background removal. Try leaving the AI checkbox off.")
            except Exception as e:
                st.error(f"Generation failed: {type(e).__name__}: {e}")
                with st.expander("Technical details"):
                    st.code(traceback.format_exc())
    except Exception as e:
        st.error(f"Could not open photo: {type(e).__name__}: {e}")
        st.code(traceback.format_exc())
else:
    st.write("Upload a photo to show photo settings and signature options.")
