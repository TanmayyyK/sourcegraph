/**
 * NoiseOverlay
 * Fixed full-viewport SVG fractal-noise texture at 2.5% opacity.
 * pointer-events:none so clicks pass through entirely.
 */
export default function NoiseOverlay() {
  return (
    <div
      aria-hidden
      data-testid="noise-overlay"
      className="pointer-events-none fixed inset-0 z-[1] opacity-[0.025] mix-blend-overlay"
      style={{
        backgroundImage:
          'url("data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'220\' height=\'220\'><filter id=\'n\'><feTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'3\' stitchTiles=\'stitch\'/><feColorMatrix values=\'0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.45 0\'/></filter><rect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\'/></svg>")',
        backgroundSize: "220px 220px",
      }}
    />
  );
}
