"""Conservative corner-background removal; original raster remains recoverable."""
import numpy as np
from PIL import Image
from scipy import ndimage


def clean_raster(image, tolerance=22):
    pixels=np.array(image.convert('RGBA'))
    h,w=pixels.shape[:2]
    corners=pixels[[0,0,h-1,h-1],[0,w-1,0,w-1],:3].astype(np.int16)
    background=np.median(corners,axis=0)
    # Only infer a flat background if all corners agree; never a generative cutout.
    if np.max(np.abs(corners-background))<=tolerance and np.all(pixels[:,:,3]==255):
        similar=np.max(np.abs(pixels[:,:,:3].astype(np.int16)-background),axis=2)<=tolerance
        seed=np.zeros((h,w),dtype=bool)
        seed[0,:]=similar[0,:]
        seed[-1,:]=similar[-1,:]
        seed[:,0]=similar[:,0]
        seed[:,-1]=similar[:,-1]
        outside=ndimage.binary_propagation(seed,mask=similar)
        # A solid-color swatch may itself be the logo. Never erase the entire input.
        if not outside.all():
            pixels[outside,3]=0
    labels,count=ndimage.label(pixels[:,:,3]>8)
    components=[]
    for index,slice_ in enumerate(ndimage.find_objects(labels),1):
        if slice_ is None:
            continue
        yy,xx=slice_
        area=int(np.sum(labels[slice_]==index))
        if area<2:
            continue
        components.append(dict(id=f'part-{index}',box=dict(x=xx.start,y=yy.start,w=xx.stop-xx.start,h=yy.stop-yy.start),label=f'图形 {len(components)+1}',mask_index=index))
    return Image.fromarray(pixels),components


def component_images(image,components):
    pixels=np.array(image.convert('RGBA'))
    labels,_=ndimage.label(pixels[:,:,3]>8)
    for component in components:
        box=component['box']
        x,y,w,h=[box[k] for k in ('x','y','w','h')]
        tile=pixels[y:y+h,x:x+w].copy()
        tile[labels[y:y+h,x:x+w]!=component['mask_index'],3]=0
        yield component,Image.fromarray(tile)
