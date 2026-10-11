import io, math
import numpy as np
import streamlit as st
import cv2
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont

st.set_page_config(page_title='Passport Photo Studio', page_icon='📸', layout='centered')
st.title('📸 Passport Photo & Signature Studio')
st.caption('Upload a photo, create a portrait crop, and download a PNG.')

def png_bytes(img):
    b=io.BytesIO(); img.save(b, format='PNG'); return b.getvalue()

def straighten(img):
    arr=np.array(img.convert('RGB')); gray=cv2.cvtColor(arr,cv2.COLOR_RGB2GRAY)
    fc=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    ec=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_eye.xml')
    faces=fc.detectMultiScale(gray,1.1,5,minSize=(60,60))
    if len(faces)==0: return Image.fromarray(arr),'Face not detected; original angle kept.'
    x,y,w,h=max(faces,key=lambda r:r[2]*r[3]); roi=gray[y:y+int(h*.65),x:x+w]
    eyes=ec.detectMultiScale(roi,1.1,5,minSize=(12,12))
    if len(eyes)<2: return Image.fromarray(arr),'Eyes not detected reliably; original angle kept.'
    eyes=sorted(eyes,key=lambda r:r[2]*r[3],reverse=True)[:2]
    pts=sorted([(x+ex+ew/2,y+ey+eh/2) for ex,ey,ew,eh in eyes])
    (x1,y1),(x2,y2)=pts; angle=math.degrees(math.atan2(y2-y1,x2-x1))
    if abs(angle)<.6 or abs(angle)>20: return Image.fromarray(arr),f'Auto rotation skipped (estimated tilt {angle:.1f}°).'
    hh,ww=arr.shape[:2]; M=cv2.getRotationMatrix2D((ww/2,hh/2),angle,1)
    out=cv2.warpAffine(arr,M,(ww,hh),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(out),f'Corrected estimated tilt {angle:.1f}°.'

def remove_background(img):
    from rembg import remove, new_session
    if 'bg_session' not in st.session_state: st.session_state.bg_session=new_session('u2net')
    return remove(img.convert('RGBA'),session=st.session_state.bg_session).convert('RGBA')

def composite(fg,color):
    bg=Image.new('RGBA',fg.size,(*color,255)); bg.alpha_composite(fg); return bg.convert('RGB')

def crop_portrait(img,size):
    img=img.convert('RGB'); tw,th=size; sw,sh=img.size
    if sw/sh>tw/th:
        nw=int(sh*tw/th); left=(sw-nw)//2; img=img.crop((left,0,left+nw,sh))
    else:
        nh=int(sw*th/tw); top=(sh-nh)//2; img=img.crop((0,top,sw,top+nh))
    return img.resize(size,Image.Resampling.LANCZOS)

def frame(img):
    border=max(5,img.width//60); pad=max(7,img.width//45)
    canvas=Image.new('RGBA',(img.width+2*(border+pad),img.height+2*(border+pad)),'white')
    shadow=Image.new('RGBA',canvas.size,(0,0,0,0)); d=ImageDraw.Draw(shadow); x=y=border+pad
    d.rectangle((x+3,y+4,x+img.width+3,y+img.height+4),fill=(0,0,0,45))
    canvas=Image.alpha_composite(canvas,shadow.filter(ImageFilter.GaussianBlur(6)))
    ImageDraw.Draw(canvas).rectangle((x-border,y-border,x+img.width+border,y+img.height+border),fill='white')
    canvas.paste(img.convert('RGBA'),(x,y)); return canvas.convert('RGB')

photo_tab, sig_tab = st.tabs(['Passport photo','Signature studio'])
with photo_tab:
    file=st.file_uploader('Upload face photo',type=['jpg','jpeg','png','webp'],key='facefile')
    if file:
        try: original=Image.open(file).convert('RGB')
        except Exception as e: st.error(f'Cannot open image: {e}'); st.stop()
        st.image(original,caption='Uploaded photo',use_container_width=True)
        c1,c2=st.columns(2)
        with c1:
            do_straighten=st.checkbox('Try face straightening',True)
            do_remove=st.checkbox('Remove background',True)
            do_enhance=st.checkbox('Enhance details',True)
        with c2:
            bg_choice=st.selectbox('Background',['Soft neutral','White','Light grey','Blue','Custom'])
            if bg_choice=='White': bg=(255,255,255)
            elif bg_choice=='Light grey': bg=(238,240,242)
            elif bg_choice=='Blue': bg=(125,190,225)
            elif bg_choice=='Custom':
                hx=st.color_picker('Choose color','#F5F5F2'); bg=tuple(int(hx[i:i+2],16) for i in (1,3,5))
            else: bg=(245,245,242)
            size_label=st.selectbox('Output size',['600 × 800 portrait','413 × 531 passport-style','300 × 400 small'])
        sharp=st.slider('Sharpness',.8,1.8,1.15,.05)
        if st.button('✨ Create passport photo',type='primary',use_container_width=True):
            st.info('Started: preparing your image...')
            work=original.copy()
            if do_straighten:
                with st.spinner('Step 1/4: Checking face alignment...'):
                    work,msg=straighten(work)
                st.caption(msg)
            if do_remove:
                st.info('Step 2/4: Removing background. First run may take a few minutes.')
                try:
                    with st.spinner('Removing background...'):
                        fg=remove_background(work)
                    processed=composite(fg,bg)
                except Exception as e:
                    st.error('Background removal failed. Open Streamlit → Manage app → Logs for details.')
                    st.exception(e); st.stop()
            else: processed=work
            if do_enhance:
                with st.spinner('Step 3/4: Enhancing photo...'):
                    processed=ImageEnhance.Brightness(processed).enhance(1.02)
                    processed=ImageEnhance.Contrast(processed).enhance(1.05)
                    processed=ImageEnhance.Color(processed).enhance(1.03)
                    processed=ImageEnhance.Sharpness(processed).enhance(sharp)
                    processed=processed.filter(ImageFilter.UnsharpMask(radius=1,percent=70,threshold=3))
            dims=(413,531) if size_label.startswith('413') else ((300,400) if size_label.startswith('300') else (600,800))
            with st.spinner('Step 4/4: Cropping and adding white border...'):
                result=frame(crop_portrait(processed,dims))
            st.success('Photo created!')
            st.image(result,caption='Generated passport-style photo',use_container_width=True)
            st.download_button('⬇️ Download photo PNG',data=png_bytes(result),file_name='passport_photo.png',mime='image/png',use_container_width=True)
    else: st.info('Upload a photo first; then the Create button will appear.')

with sig_tab:
    st.subheader('Signature studio')
    mode=st.radio('Signature source',['Upload signature image','Type a name'],horizontal=True)
    sig=None
    if mode=='Upload signature image':
        sf=st.file_uploader('Upload signature on light paper',type=['jpg','jpeg','png','webp'],key='signfile')
        if sf:
            im=Image.open(sf).convert('RGB'); gray=np.array(ImageOps.grayscale(im))
            alpha=np.clip((245-gray.astype(np.float32))*3,0,255).astype(np.uint8); alpha[alpha<28]=0
            rgba=np.zeros((gray.shape[0],gray.shape[1],4),dtype=np.uint8); rgba[:,:,:3]=(15,15,20); rgba[:,:,3]=alpha
            sig=Image.fromarray(rgba,'RGBA'); bbox=sig.getbbox()
            if bbox: sig=sig.crop(bbox)
    else:
        text=st.text_input('Type a name')
        if text.strip():
            try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf',100)
            except Exception: font=ImageFont.load_default()
            sig=Image.new('RGBA',(1000,220),(255,255,255,0)); d=ImageDraw.Draw(sig); d.text((20,35),text.strip(),font=font,fill=(15,15,20,255)); bbox=sig.getbbox()
            if bbox: sig=sig.crop(bbox)
    if sig is not None:
        deg=st.slider('Rotate signature',-45,45,0); bold=st.slider('Boldness',0,3,1)
        sig=sig.rotate(deg,expand=True,resample=Image.Resampling.BICUBIC)
        alpha=sig.getchannel('A')
        for _ in range(bold): alpha=alpha.filter(ImageFilter.MaxFilter(3))
        sig.putalpha(alpha)
        st.image(sig,caption='Signature preview',use_container_width=True)
        st.download_button('⬇️ Download transparent signature PNG',data=png_bytes(sig),file_name='signature.png',mime='image/png',use_container_width=True)

st.caption('This tool edits an existing image; it cannot reliably turn every side-facing face into a true front-facing portrait. Verify official document photo rules.')
