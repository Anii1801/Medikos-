from PIL import Image, ImageDraw
import pytesseract

image = Image.new("RGB", (800, 180), "white")
draw = ImageDraw.Draw(image)
draw.text(
    (20, 50),
    "Patient: Rahul | Hemoglobin: 12.5 g/dL",
    fill="black"
)

text = pytesseract.image_to_string(image, lang="eng")

print("OCR RESULT:")
print(text)
