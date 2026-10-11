import io, traceback
import streamlit as st
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont

st.set_page_config(page_title="Passport Photo & Signature Studio", page_icon="📸", layout="centered")
st.title("📸 Passport Photo & Signature Studio")
st.caption("Upload a photo, adjust it, and optionally add a signature. For official applications, follow the authority's exact photo/signature rules.")

def to_png_bytes(img):
    buf=io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def crop_resize(img, size):
    img=img.convert("RGB")
    tw,th=size; sw,sh=img.size
    if sw/sh > tw/th:
        nw=int(sh*tw/th); left=(sw-nw)//2
        img=img.crop((left,0,left+nw,sh))
    else:
        nh=int(sw*th/tw); top=(sh-nh)//2
        img=img.crop((0,top,sw,top+nh))
    return img.resize(size, Image.Resampling.LANCZOS)

def frame(img):
    border=max(4,img.width//60); margin=max(6,img.width//50)
    x=border+margin; y=border+margin
    out=Image.new("RGB",(img.width+2*x,img.height+2*y),"white")
    shadow=Image.new("RGBA",out.size,(0,0,0,0))
    d=ImageDraw.Draw(shadow)
    d.rectangle((x+3,y+4,x+img.width+3,y+img.height+4),fill=(0,0,0,40))
    shadow=shadow.filter(ImageFilter.GaussianBlur(5))
    out=Image.alpha_composite(out.convert("RGBA"),shadow)
    out.paste(img,(x,y))
    return out.convert("RGB")

def remove_bg(img):
    from rembg import remove, new_session
    if "rembg_session" not in st.session_state:
        st.session_state.rembg_session=new_session("u2net")
    return remove(img.convert("RGBA"),session=st.session_state.rembg_session).convert("RGBA")

def signature_from_upload(file):
    sig=Image.open(file).convert("RGBA")
    # Make near-white paper transparent, retain dark ink.
    a=np.array(sig)
    rgb=a[:,:,:3]
    darkness=255-rgb.min(axis=2)
    alpha=np.clip((darkness.astype(float)-12)*5,0,255).astype("uint8")
    a[:,:,3]=np.minimum(a[:,:,3],alpha)
    return Image.fromarray(a,"RGBA")

def typed_signature(text, color):
    canvas=Image.new("RGBA",(1000,220),(255,255,255,0))
    draw=ImageDraw.Draw(canvas)
    font=None
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
              "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf"]:
        try:
            font=ImageFont.truetype(p,100); break
        except Exception:
            pass
    if font is None: font=ImageFont.load_default()
    draw.text((15,25),text,font=font,fill=color+(255,))
    bbox=canvas.getbbox()
    return canvas.crop(bbox) if bbox else canvas

uploaded=st.file_uploader("1) Upload photo",type=["jpg","jpeg","png","webp"])
if uploaded:
    try:
        original=ImageOps.exif_transpose(Image.open(uploaded)).convert("RGB")
        st.image(original,caption="Uploaded photo",use_container_width=True)
    except Exception as e:
        st.error(f"Could not open photo: {e}")
        st.stop()

    st.subheader("2) Photo settings")
    rotation=st.slider("Rotate photo (manual correction)",-15.0,15.0,0.0,0.5)
    use_ai=st.checkbox("Remove background (AI model)",value=False)
    bg_name=st.selectbox("Background",["Keep original","White","Soft neutral","Light grey","Blue"])
    size_name=st.selectbox("Output size",["600 x 800","413 x 531","300 x 400"])
    add_frame=st.checkbox("Add white border and subtle shadow",value=True)

    st.subheader("3) Optional signature")
    sig_mode=st.radio("Signature option",["No signature","Upload signature image","Type signature"],horizontal=False)
    sig_file=None; typed_text=""; sig_color_name="Black"
    if sig_mode=="Upload signature image":
        sig_file=st.file_uploader("Upload signature (prefer dark ink on white paper)",type=["png","jpg","jpeg","webp"],key="sig_upload")
    elif sig_mode=="Type signature":
        typed_text=st.text_input("Type name/signature")
        sig_color_name=st.selectbox("Signature ink",["Black","Blue"])
    place_sig=st.checkbox("Place signature on the photo output",value=False) if sig_mode!="No signature" else False
    if place_sig:
        sig_position=st.selectbox("Signature position",["Bottom centre","Bottom left","Bottom right"])
        sig_width=st.slider("Signature width (% of photo)",10,60,30)

    if st.button("✨ Generate passport photo",type="primary",use_container_width=True):
        try:
            st.info("STEP 1/4 — Button clicked. Processing started.")
            work=original.rotate(rotation,resample=Image.Resampling.BICUBIC,expand=False,fillcolor=(245,245,245))
            if use_ai:
                st.info("STEP 2/4 — Loading AI background removal. First run may take a few minutes.")
                work_rgba=remove_bg(work)
                colors={"Keep original":None,"White":(255,255,255),"Soft neutral":(245,245,242),"Light grey":(238,240,242),"Blue":(125,190,225)}
                color=colors[bg_name] or (245,245,245)
                bg=Image.new("RGBA",work_rgba.size,(*color,255))
                bg.alpha_composite(work_rgba)
                processed=bg.convert("RGB")
            else:
                processed=work
                if bg_name!="Keep original":
                    color={"White":(255,255,255),"Soft neutral":(245,245,242),"Light grey":(238,240,242),"Blue":(125,190,225)}[bg_name]
                    st.warning("AI background removal is OFF, so the original background cannot be cleanly replaced. Keeping the original photo background.")
            st.info("STEP 3/4 — Enhancing and resizing photo.")
            processed=ImageEnhance.Color(processed).enhance(1.03)
            processed=ImageEnhance.Contrast(processed).enhance(1.04)
            processed=ImageEnhance.Sharpness(processed).enhance(1.15)
            dims=(413,531) if size_name.startswith("413") else ((300,400) if size_name.startswith("300") else (600,800))
            result=crop_resize(processed,dims)
            if place_sig:
                if sig_mode=="Upload signature image":
                    if not sig_file: st.error("Please upload a signature image first."); st.stop()
                    sig=signature_from_upload(sig_file)
                else:
                    if not typed_text.strip(): st.error("Please type the signature first."); st.stop()
                    ink=(25,25,25) if sig_color_name=="Black" else (20,55,150)
                    sig=typed_signature(typed_text.strip(),ink)
                maxw=int(result.width*sig_width/100)
                maxh=int(result.height*0.16)
                sig.thumbnail((maxw,maxh),Image.Resampling.LANCZOS)
                pos={"Bottom centre":((result.width-sig.width)//2,result.height-sig.height-8),
                     "Bottom left":(8,result.height-sig.height-8),
                     "Bottom right":(result.width-sig.width-8,result.height-sig.height-8)}[sig_position]
                result_rgba=result.convert("RGBA")
                result_rgba.alpha_composite(sig,pos)
                result=result_rgba.convert("RGB")
            st.info("STEP 4/4 — Finishing output.")
            if add_frame: result=frame(result)
            st.success("Photo generated successfully.")
            st.image(result,caption="Generated photo",use_container_width=True)
            st.download_button("⬇️ Download photo PNG",to_png_bytes(result),"passport_photo.png","image/png",use_container_width=True)
            if sig_mode=="Upload signature image" and sig_file:
                st.download_button("⬇️ Download cleaned signature PNG",to_png_bytes(signature_from_upload(sig_file)),"cleaned_signature.png","image/png")
            elif sig_mode=="Type signature" and typed_text.strip():
                ink=(25,25,25) if sig_color_name=="Black" else (20,55,150)
                st.download_button("⬇️ Download typed signature PNG",to_png_bytes(typed_signature(typed_text.strip(),ink)),"typed_signature.png","image/png")
        except Exception as e:
            st.error(f"PROCESSING FAILED: {type(e).__name__}: {e}")
            with st.expander("Technical details"):
                st.code(traceback.format_exc())
else:
    st.info("Upload a photo first. Then photo and signature options will appear.")
