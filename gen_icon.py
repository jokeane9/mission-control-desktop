#!/usr/bin/env python3
"""Render a 1024x1024 app icon PNG — monochrome, matching the dashboard tokens:
white tile + hairline border, near-black ◉ reticle, gray HUD corner brackets.
Uses AppKit (pyobjc)."""
import os
from AppKit import (NSBitmapImageRep, NSDeviceRGBColorSpace, NSGraphicsContext,
                    NSColor, NSBezierPath, NSString, NSFont,
                    NSMutableParagraphStyle, NSMutableDictionary)
from AppKit import (NSFontAttributeName, NSForegroundColorAttributeName,
                    NSParagraphStyleAttributeName)
from Foundation import NSMakeRect, NSPoint

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024

def gray(v, a=1.0):  # match dashboard hex tokens
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(v, v, v, a)
PANEL  = gray(1.00)      # #ffffff
BORDER = gray(0.631)     # #a1a1a1  (30% darker)
INK    = gray(0.055)     # #0e0e0e  (30% darker)
FAINT  = gray(0.461)     # #767676  (30% darker)

rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
    None, S, S, 8, 4, True, False, NSDeviceRGBColorSpace, 0, 0)
ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.setCurrentContext_(ctx)

# --- white tile + hairline border (like a card) ---
radius = S * 0.20
tile = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
    NSMakeRect(0, 0, S, S), radius, radius)
PANEL.set(); tile.fill()
inset = S * 0.012
bpath = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
    NSMakeRect(inset, inset, S - 2*inset, S - 2*inset),
    radius - inset, radius - inset)
bpath.setLineWidth_(S * 0.011)
BORDER.set(); bpath.stroke()

# --- HUD corner brackets ---
m, L, w = S * 0.11, S * 0.13, S * 0.015
FAINT.set()
def bracket(pts):
    p = NSBezierPath.bezierPath()
    p.setLineWidth_(w)
    p.moveToPoint_(NSPoint(*pts[0]))
    p.lineToPoint_(NSPoint(*pts[1]))
    p.lineToPoint_(NSPoint(*pts[2]))
    p.stroke()
bracket([(m, S-m-L), (m, S-m), (m+L, S-m)])          # top-left
bracket([(S-m-L, S-m), (S-m, S-m), (S-m, S-m-L)])    # top-right
bracket([(m, m+L), (m, m), (m+L, m)])                # bottom-left
bracket([(S-m-L, m), (S-m, m), (S-m, m+L)])          # bottom-right

# --- near-black ◉ reticle (flat, no glow) ---
glyph = NSString.stringWithString_("◉")
para = NSMutableParagraphStyle.alloc().init(); para.setAlignment_(2)
attrs = NSMutableDictionary.dictionary()
attrs.setObject_forKey_(NSFont.systemFontOfSize_(S * 0.56), NSFontAttributeName)
attrs.setObject_forKey_(INK, NSForegroundColorAttributeName)
attrs.setObject_forKey_(para, NSParagraphStyleAttributeName)
size = glyph.sizeWithAttributes_(attrs)
glyph.drawAtPoint_withAttributes_(
    NSPoint((S - size.width) / 2, (S - size.height) / 2), attrs)

NSGraphicsContext.restoreGraphicsState()
png = rep.representationUsingType_properties_(4, None)  # 4 = PNG
out = os.path.join(HERE, "icon_1024.png")
png.writeToFile_atomically_(out, True)
print("wrote", out)
