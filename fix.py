import glob
files = glob.glob('d:/SHASTRA/crime_frontend/src/services/*.ts')
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    content = content.replace("\\'true\\'", "'true'")
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
