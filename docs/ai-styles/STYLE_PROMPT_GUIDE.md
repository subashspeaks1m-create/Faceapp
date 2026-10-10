# Style prompt guide

All prompt text lives in `apps/style-api/styleapi/catalog.json` and never leaves the server. `build_prompt()` in `styleapi/catalog.py` assembles one prompt per request.

## Prompt order

1. **Task**: edit the supplied photograph of real people and restyle it.
2. **Identity**: keep each person recognisably the same (face shape, eyes, nose, lips, skin tone, marks, facial hair, apparent age, hairline and colour, expression); no beautifying, slimming, skin lightening or darkening, or changes to ethnicity, age, gender or body shape.
3. **Composition**: same framing, angle, pose, hands, clothing silhouette and position; exactly the same number of people.
4. **Style**: the style's `prompt.style` text.
5. **Strength**: `Strength N/100 (Band).` plus the band's instruction.
6. **High-strength extras**: the style's `prompt.high_intensity`, only when strength is 76 or more.
7. **Allowed changes** (optional): for styles that must alter something, such as elf ears or fairy wings.
8. **Quality**: coherent anatomy, hands and eyes, consistent lighting.
9. **Safety**: non-sexual, clothing kept as in the original; no text, logos, watermarks, borders or frames.
10. **Avoid**: global avoid list plus the style's own `prompt.avoid`.

Example for Ghibli-Inspired Storybook at strength 80 (abridged):

```
Edit the supplied photograph. It shows one or more real people. Restyle the whole image as described below.
Keep every person recognisably the same individual: preserve face shape, …
Keep the original framing, camera angle, head pose, … Keep exactly the same number of people.
Style: an original hand-drawn animated-film illustration in a gentle storybook anime manner: …
Strength 80/100 (Full). Apply the style fully: render the entire image in this style, including the face, …
Repaint the whole background as a detailed hand-painted pastoral or town scene that fits the original setting.
Produce a clean, coherent, high-detail result …
Keep the result non-sexual and fully clothed as in the original; … Do not add text, letters, numbers, logos, …
Avoid: extra people or faces; …; any existing animated character; copying a specific film frame or scene; …
```

## Strength bands

| Strength | Band | Instruction |
|---|---|---|
| 0 to 25 | Subtle | Mainly colour grading, lighting and texture; still reads as a photograph |
| 26 to 50 | Moderate | Clearly visible changes, light background stylisation, face close to photographic |
| 51 to 75 | Strong | Background, clothing and rendering restyled; face stylised but recognisable |
| 76 to 100 | Full | Whole image in the style, including the face; adds the style's high-strength extras |

OpenAI's image edit endpoint has no numeric strength parameter, so strength is expressed in the prompt. `input_fidelity=high` is sent only to `gpt-image-1` and `gpt-image-1.5`; OpenAI's guide says to omit it for `gpt-image-2`, which always uses high input fidelity.

## The 25 styles

| # | ID | Name | Category | Default strength |
|---|---|---|---|---|
| 1 | `seventies-film` | 70s Retro Film | Retro | 60 |
| 2 | `eighties-neon` | 80s Neon | Retro | 65 |
| 3 | `nineties-flash` | 90s Flash Photograph | Retro | 55 |
| 4 | `vintage-polaroid` | Vintage Polaroid | Retro | 55 |
| 5 | `storybook-anime` | Ghibli-Inspired Storybook | Animation & Illustration | 75 |
| 6 | `animated-3d` | 3D Animated Character | Animation & Illustration | 75 |
| 7 | `manga-ink` | Manga Ink | Animation & Illustration | 75 |
| 8 | `comic-book` | Comic Book | Animation & Illustration | 70 |
| 9 | `watercolor` | Watercolor Painting | Animation & Illustration | 65 |
| 10 | `oil-painting` | Oil Painting | Animation & Illustration | 65 |
| 11 | `pop-art` | Pop Art | Animation & Illustration | 70 |
| 12 | `pixel-art` | Pixel Art | Animation & Illustration | 70 |
| 13 | `cyberpunk` | Cyberpunk | Cinematic & Fantasy | 70 |
| 14 | `film-noir` | Film Noir | Cinematic & Fantasy | 65 |
| 15 | `cinematic-poster` | Cinematic Poster | Cinematic & Fantasy | 70 |
| 16 | `fantasy-elf` | Fantasy Elf | Cinematic & Fantasy | 70 |
| 17 | `fairycore` | Dreamy Fairycore | Cinematic & Fantasy | 65 |
| 18 | `pro-headshot` | Professional Headshot | Professional & Editorial | 50 |
| 19 | `fashion-editorial` | Fashion Editorial | Professional & Editorial | 65 |
| 20 | `wedding-glow` | Wedding Glow | Professional & Editorial | 55 |
| 21 | `streetwear` | Streetwear Campaign | Professional & Editorial | 65 |
| 22 | `renaissance` | Renaissance Portrait | Artistic & Lighting | 70 |
| 23 | `clay-figure` | Clay Figure | Artistic & Lighting | 75 |
| 24 | `golden-hour` | Golden Hour | Artistic & Lighting | 50 |
| 25 | `fine-art-mono` | Fine-Art Monochrome | Artistic & Lighting | 55 |

Rules the prompts follow:

- Name visual traits, never a studio, artist, film, franchise or character. A test fails if the catalog contains names such as "Studio Ghibli", "Miyazaki", "Pixar", "Disney", "Marvel" or "Aardman".
- No text in the image, including Cinematic Poster (no title or credits) and Manga Ink or Comic Book (no speech bubbles).
- No weapons, smoking, revealing clothing or face-covering elements.

## Changing the catalog

1. Edit `apps/style-api/styleapi/catalog.json`. IDs are lowercase kebab-case and stable once shipped; numbers run 1..n in order; `swatch` holds three `#RRGGBB` colours; `summary` is at most 90 characters.
2. Bump `version` (`YYYY-MM-DD.N`).
3. Run `make style-catalog` to regenerate the app's public copy.
4. Run `make test-style-api` (schema, prompt structure, drift and banned-name checks).
5. Run the live test for any new or changed style and review the output by eye before shipping (see TESTING.md).

A style that is removed from the server is refused with `INVALID_STYLE`, even if an old app still shows it.
