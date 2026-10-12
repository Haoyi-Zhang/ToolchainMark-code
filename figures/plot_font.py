"""Find the manuscript's Linux Libertine regular TrueType face without substitution."""
from pathlib import Path
import shutil
import subprocess
from matplotlib import font_manager

PDF_METADATA = {'Creator': None, 'Producer': None, 'CreationDate': None, 'ModDate': None}


def regular_libertine(here, explicit=None):
    here = Path(here)
    candidates = [Path(explicit)] if explicit else []
    if not explicit:
        for folder in (here/'fonts', here.parent/'fonts', here.parent.parent/'artifact/fonts'):
            candidates.extend(folder/name for name in ('LinLibertine_Rah.ttf', 'LinLibertine_R.ttf'))
        executable = shutil.which('kpsewhich')
        if executable:
            for name in ('LinLibertine_Rah.ttf', 'LinLibertine_R.ttf'):
                result = subprocess.run([executable, name], capture_output=True, text=True, check=False)
                if result.returncode == 0 and result.stdout.strip():
                    candidates.append(Path(result.stdout.strip()))
        candidates.extend(Path(f.fname) for f in font_manager.fontManager.ttflist
                          if f.name.casefold() == 'linux libertine' and f.style == 'normal'
                          and f.weight in ('normal', 400))
        candidates.extend(Path(p) for p in font_manager.findSystemFonts(fontext='ttf')
                          if 'libertine' in Path(p).name.lower())
    for path in candidates:
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            if stream.read(4) not in (b'\x00\x01\x00\x00', b'true'):
                continue
        face = font_manager.get_font(str(path))
        if face.family_name.casefold() == 'linux libertine' and face.style_name.casefold() == 'regular':
            font_manager.fontManager.addfont(str(path))
            return path
    raise RuntimeError('Linux Libertine regular TrueType is required. Use the bundled OFL font, install that face for Matplotlib/TeX, or supply --font. No substitute is selected.')
