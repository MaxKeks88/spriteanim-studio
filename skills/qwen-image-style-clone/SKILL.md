---
name: "qwen-image-style-clone"
description: "Analyze a reference image to extract its exact art style, linework, color palette, shading, and clothing aesthetic, then generate a structured English prompt for Qwen Image 2.1 to create a new character or asset in that identical style. Use when the user uploads a reference image and asks to write a Qwen Image prompt, copy a character's style, or generate a new game sprite or character matching an existing visual reference."
---

# Qwen Image Style Clone

Extract the visual DNA from a reference image and translate it into a structured, high-precision English prompt for Qwen Image 2.1 so new characters match the original style, clothing wear, and rendering.

## When to Use

- The user uploads a reference character or asset image and wants a prompt for Qwen Image 2.1.
- The user wants a new character, creature, or item to inherit the exact art style, linework, palette, and clothing feel of a reference image.
- The user is building consistent 2D game sprites or concept art sets and needs repeatable style transfer via text prompts.

## Steps

### 1. Deconstruct the reference image (Style DNA)

Before writing the prompt, silently inspect the reference image across six concrete axes:

1. **Asset type & framing:** Full-body sprite, bust, turnaround, three-quarter view, facing direction.
2. **Art style & linework:** Era or genre (e.g., 1930s rubber-hose, dark storybook ink, cel-shaded anime), outline thickness, ink roughness, hand-drawn vs. vector feel.
3. **Color palette & shading:** Dominant muted or vibrant tones, specific hues (e.g., dusty browns, sepia, charcoal, off-white), shading method (flat colors, subtle painterly shading, cross-hatching).
4. **Anatomy & proportions:** Head-to-body ratio, limb style (thin, stocky, multi-limbed), eye style (e.g., pie-cut eyes, expressive brows).
5. **Clothing & material aesthetic:** Level of wear (patched, tattered, scuffed, crisp), fabric weight, signature accessories (gloves, oversized shoes, buttons).
6. **Lighting & background:** Flat lighting vs. dramatic lighting, solid pure white or monochrome background, presence or absence of ground shadows.

### 2. Map the new subject onto the Style DNA

Replace only the subject's identity, species, pose, and specific props requested by the user. Keep all six visual axes from Step 1 locked so the new character looks like it belongs in the exact same world and was drawn by the same artist.

### 3. Assemble the Qwen Image 2.1 prompt

Write a single, cohesive English prompt block structured in this exact order (Qwen Image 2.1 responds best to front-loaded style and clear visual hierarchy):

1. **Asset format & subject:** Start with "In the exact same artistic style as the reference image," then full-body framing, asset type, new character species/identity.
2. **Art style & rendering:** Exact medium, era/style, linework quality, color palette, and shading extracted from the reference.
3. **Pose & expression:** Camera angle (e.g., three-quarter side view facing right), stance, and facial expression matching the reference's vibe.
4. **Anatomy & silhouette:** Body build and key anatomical features of the new character rendered in the reference's proportions.
5. **Clothing & props:** Requested outfit and held items described with the same material wear, textures, and detailing seen in the reference.
6. **Background & finish:** Reproduce the reference's background exactly — its colour, texture and ground shadow. Use a solid pure white background with no shadow only when the user asks for a clean sprite or transparent background.

### 4. Deliver the output

Present the ready-to-copy English prompt inside a blockquote, followed by 1 to 2 brief practical tweaks in the user's language (for example, how to swap a hat type or adjust limb count).

## Example (follow this level of detail and structure)

> In the exact same artistic style as the reference image, a full-body 2D ink illustration of an anthropomorphic stag beetle barista standing in a three-quarter pose on a solid, slightly textured olive-grey background. Detailed 2D illustration with crisp black ink outlines, fine crosshatching for shadows and texture, muted earthy palette of chestnut brown, charcoal, khaki and cream. Round beetle head with large sly eyes, black pupils and long fan-shaped antennae; segmented chestnut shell with elytra folded like coattails. He wears a dark charcoal zip-up hoodie, loose navy trousers with three white stripes down the sides, chunky vintage lace-up boots and white cartoon gloves with three black lines on the back. One hand holds a vintage glass milk bottle against his chest. A small hatched ground shadow under his feet.

## Gotchas

- **Do not copy the old subject's identity:** Transfer the aesthetic (e.g., tattered vintage fabric, scuffed off-white gloves, pie-cut eyes), not the previous character's species or unrelated props.
- **Background fidelity:** reproduce the reference's background exactly — its colour, texture and ground shadow (for example, a solid slightly textured olive-grey with a small hatched shadow). Use `solid pure white background` with no shadow only when the user asks for a clean sprite or transparent background; never invent a black background.
- **Style lock:** open with "In the exact same artistic style as the reference image" and name the medium and era exactly (e.g., "detailed 2D ink illustration", "ink etching", "1930s rubber-hose cartoon"). Never replace a hand-drawn 2D reference with "digital painting", "3D render", "photoreal" or "cinematic".
- **Explicit user direction wins:** if the user explicitly asks for cinematic, dramatic lighting, another medium or a different mood, follow that request while keeping the character design and palette from the reference. The reference dictates the style when the user does not ask for a change.
- **Keep the reference's signature styling:** when changing the outfit, keep its visual language — e.g., white cartoon gloves with three black lines, chunky vintage boots, muted earthy palette, hatched shading — so the new character belongs to the same world.
- **Use the measured colours when supplied:** the app sends `background #RRGGBB` and a dominant palette from the reference. Put that exact background hex in the prompt and build the palette from those colours; do not rename them ("olive-grey" ≠ "dark forest-green").
- **Lighting stays as in the reference:** reproduce its light direction and softness; do not add dramatic, cinematic or directional lighting unless it is visible in the reference.
- **Keep the species from the user's request:** if the user says "May beetle" / "cockchafer" (майский жук), write `cockchafer`, not another beetle species.
- **Do not invent anatomy, props or materials:** describe only what the user asked for plus the reference's visual language. No extra horns, masks, fur, watches or accessories.
- **Avoid negative-heavy phrasing:** Describe what should be present ("solid slightly textured olive-grey background, hatched ground shadow") rather than long lists of "no X, without Y".
- **Keep prompts in English:** Even when conversing in Russian or another language, always output the Qwen Image 2.1 prompt itself in clear, concrete English.
- **Be concrete, not generic:** Replace vague words like "cool style" or "nice colors" with specific visual descriptors ("crisp black ink outlines", "muted earthy palette of chestnut, charcoal and khaki", "fine crosshatching").
- **No placeholders:** Never leave `[Subject]`, `[Clothing Description]` or similar in the final prompt; fill them from the user's request and the reference.
