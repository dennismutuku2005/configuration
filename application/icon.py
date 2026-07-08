# save this as convert_icon.py
from PIL import Image

# Open the PNG
img = Image.open('kokonut.png')
# Save as ICO with multiple sizes (recommended)
img.save('kokonut.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])