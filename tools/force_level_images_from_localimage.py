from pathlib import Path
import re

levels_path = Path('src/levels.js')
if not levels_path.exists():
    raise SystemExit('ERROR: Run this from your PuzzleVerse root folder. src/levels.js was not found.')

text = levels_path.read_text(encoding='utf-8')
original = text

# For every level object, if image is a placeholder and localImage points to a real image,
# copy localImage into image so even old app.js builds will display the real image.
pattern = re.compile(
    r'("image"\s*:\s*")([^"\n]*placeholder\.svg)(",\s*\n\s*"localImage"\s*:\s*")([^"\n]+\.(?:jpg|jpeg|png|webp))(")',
    re.IGNORECASE
)

count = 0

def repl(match):
    global count
    local_image = match.group(4).replace('\\\\', '/')
    if 'placeholder.svg' in local_image:
        return match.group(0)
    count += 1
    return f'{match.group(1)}{local_image}{match.group(3)}{local_image}{match.group(5)}'

text = pattern.sub(repl, text)

# Also normalize accidental backslashes to web-safe forward slashes in asset paths.
text = text.replace('assets\\\\puzzle-library', 'assets/puzzle-library')
text = text.replace('assets\\puzzle-library', 'assets/puzzle-library')

if text == original:
    print('No placeholder image fields needed fixing. If cards are still wrong, clear browser cache or check that you pushed src/levels.js.')
else:
    backup = levels_path.with_suffix('.js.bak')
    backup.write_text(original, encoding='utf-8')
    levels_path.write_text(text, encoding='utf-8')
    print(f'Fixed {count} level image fields.')
    print(f'Backup saved as: {backup}')
    print('Now run: python -m http.server 8000')
