# Reel "7 datos curiosos" (50 s, 1080x1920, 30 fps)

- **Video final:** `datos-curiosos-reel.mp4` (H.264 + AAC, -14 LUFS, listo para Reels/TikTok)
- **Guion y narración:** `script.json` (voz neural es-MX-JorgeNeural vía edge-tts, +18% velocidad y atempo 1.05)
- **Escenas:** gancho (0–6 s) → 7 datos (6–45 s) → cierre "Sígueme para más datos curiosos" (45–50 s)
- **Marca:** rojo mate #A61C24, negro #0A0A0A, blanco #F5F4F0 · tipografía Anton + Montserrat 900
- **Música y efectos:** compuestos por código (`tools/audio.py`), sin derechos de terceros

## Regenerar
```
python3 tools/plan.py .      # tiempos + pista de voz
python3 tools/audio.py .     # música, SFX, mezcla
python3 tools/render.py . video_only.mp4
```
(Necesita carpetas `vo/`, `img/` y `fonts/`, no incluidas en el repo.)

## Créditos de imágenes (Wikimedia Commons, licencias libres; revisar la atribución exacta en cada página)
- octopus_0: https://commons.wikimedia.org/wiki/File:Octopus_(28836592458).jpg
- honey_0: https://commons.wikimedia.org/wiki/File:Runny_hunny.jpg
- egypt_0: https://commons.wikimedia.org/wiki/File:Kheops-Pyramid.jpg
- venus_0: https://commons.wikimedia.org/wiki/File:Venus-real_color.jpg
- venus_1: https://commons.wikimedia.org/wiki/File:Venus_from_Mariner_10.jpg
- flamingo_0: https://commons.wikimedia.org/wiki/File:Flamingos_Laguna_Colorada.jpg
- eiffel_0: https://commons.wikimedia.org/wiki/File:Tour_Eiffel_Wikimedia_Commons.jpg
- eiffel_1: https://commons.wikimedia.org/wiki/File:Tour_Eiffel_Wikimedia_Commons_(cropped).jpg
- cow_0: https://commons.wikimedia.org/wiki/File:Cow_female_black_white.jpg
- brain_0: https://commons.wikimedia.org/wiki/File:Human_brain_NIH.png
- Galaxias del gancho: imágenes del telescopio Hubble (NASA/ESA, Wikimedia Commons)
- Red neuronal (dato 7): generada por código
