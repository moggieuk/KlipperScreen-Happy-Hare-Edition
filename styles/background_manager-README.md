# Dynamic Background Themes

## Overview

Dynamic Backgrounds provide optional rotating wallpaper support for individual
KlipperScreen themes.

When enabled, background images are displayed behind the user interface using a
dedicated background widget. Themes that do not define a
`dynamic_background` section continue to operate normally without any
additional overhead.

Background images are automatically scaled to fill the display while
preserving their aspect ratio. Scaled images are cached to reduce image
decoding and scaling during normal operation.

---

# Configuration

Dynamic Backgrounds are configured in the active theme's `style.conf` file.

Add the optional `dynamic_background` section **above** the existing
`graph_colors` section as part of the **same top-level JSON object**.

The overall structure should look like this:

```json
{
  "dynamic_background": {
    "enabled": true,
    "directory": "backgrounds",
    "interval": 300,
    "mode": "random",
    "preload": false
  },

  "graph_colors": {
    "extruder": {
      "colors": ["DC322F", "B58900", "CB4B16", "AA1F1D", "973911"],
      "state": 0
    },
    "bed": {
      "colors": ["268BD2"],
      "state": 0
    },
    "fan": {
      "colors": ["859900", "2AA198", "637300", "1F7A72"],
      "state": 0
    },
    "sensor": {
      "colors": ["D33682", "6C71C4", "C06CC4", "6D26D1", "2A34A1"],
      "state": 0
    }
  }
}
```

> **Important**
>
> The `dynamic_background` and `graph_colors` sections are members of the same
> JSON object. Do **not** create a second JSON block.

---

# Configuration Options

## enabled

Enables or disables Dynamic Backgrounds for the current theme.

Themes that omit the `dynamic_background` section behave exactly as they do
today.

**Valid values**

```text
true
false
```

**Default**

```json
"enabled": false
```

---

## directory

Specifies the directory containing the background images.

Relative paths are resolved relative to the active theme directory.

Absolute filesystem paths are also supported.

Example:

```json
"directory": "backgrounds"
```

Typical theme layout:

```text
styles/
└── dynamic_bg/
    ├── style.conf
    ├── style.css
    ├── backgrounds/
    │   ├── 1.jpg
    │   ├── 2.jpg
    │   ├── 3.jpg
    │   └── ...
    ├── images/
    └── ...
```

---

## interval

Specifies how long each background image is displayed before changing to the
next image.

The value is specified in **seconds**.

Example:

```json
"interval": 300
```

---

## mode

Determines the order in which background images are displayed.

Supported values:

```text
random
sequential
```

### random

Displays every image exactly once in a shuffled order before reshuffling.

This prevents immediate image repeats while maintaining a random viewing
experience.

### sequential

Displays images in alphabetical order and returns to the first image after the
last image has been shown.

Example:

```json
"mode": "random"
```

---

## preload

Preloads a limited number of wallpapers during startup.

When enabled, the first few background images are decoded, scaled and cached
during KlipperScreen startup. This reduces CPU usage during the first few
background changes while using a small amount of additional memory.

Only enough images to fill the internal cache are preloaded.

**Valid values**

```text
true
false
```

**Default**

```json
"preload": false
```

---

# Theme Styling

Dynamic backgrounds are rendered **behind** the KlipperScreen interface. In
order for the wallpaper to remain visible, the theme must use transparent
background colors.

Most existing themes use solid RGB or hexadecimal color definitions, which
completely obscure the wallpaper. Dynamic Background themes should use `rgba()`
colors with an alpha channel for windows, panels, buttons, sliders and other
UI elements.

For example, a standard theme might define:

```css
@define-color solarized-base02 #073642;
@define-color solarized-base03 #002b36;
```

A Dynamic Background theme would instead use transparent equivalents:

```css
@define-color solarized-base02 rgba(7, 54, 66, 0.2);
@define-color solarized-base03 rgba(0, 43, 54, 0.2);
```

The main application backgrounds should also be transparent:

```css
window,
.background,
.main,
.main_panel,
.content {
    background-color: transparent;
    background-image: none;
}
```

---

## Text Readability

Because wallpapers may contain bright or dark areas, transparent controls alone
may reduce text readability.

A light text color combined with a subtle drop shadow generally provides good
contrast across a wide variety of background images.

Example:

```css
@define-color text #ffffff;

* {
    color: @text;
    text-shadow: 2px 2px 4px #000000;
}
```

The exact transparency values are a matter of personal preference. Lower alpha
values reveal more of the wallpaper, while higher values improve readability.

---

# Supported Image Formats

Dynamic Backgrounds support any image format supported by GdkPixbuf,
including:

- JPEG / JPG
- PNG
- BMP
- TIFF
- GIF (static)

Images of any resolution may be used.

Backgrounds are automatically scaled and center-cropped to completely fill
the display while preserving their original aspect ratio.

---

# Performance

Background images are decoded and scaled only once, then stored in a bounded
cache. Reusing cached images minimizes CPU usage during normal operation while
keeping memory usage predictable.

In **random** mode, images are displayed in a shuffled order so every image is
shown once before the sequence is reshuffled. This prevents immediate repeats
while preserving a random viewing experience.

The currently displayed wallpaper is automatically saved and restored when
KlipperScreen starts, allowing rotation to resume from the last displayed
image.

---

# Summary

Dynamic Backgrounds provide an optional enhancement for KlipperScreen themes by
adding rotating wallpapers behind the existing user interface.

The feature is fully theme-driven, requires only a small addition to
`style.conf`, and can be enabled without affecting themes that choose not to
use it.

By combining transparent CSS styling with image caching, shuffle-based random
selection, automatic scaling, and persistent state, Dynamic Backgrounds
integrate seamlessly into KlipperScreen while remaining simple for theme
authors to configure and maintain.