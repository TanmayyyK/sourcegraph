import { useEffect, useRef, forwardRef, ReactNode, useImperativeHandle } from "react";
import Lenis from "lenis";

type Props = {
  children:  ReactNode;
  className?: string;
};

/**
 * SmoothScrollProvider
 * Attaches a Lenis instance to the inner scroll surface and drives it
 * via requestAnimationFrame. Exposes the DOM node via ref so parents
 * can pass it to Framer Motion's useScroll({ container }).
 */
const SmoothScrollProvider = forwardRef<HTMLDivElement, Props>(
  ({ children, className = "" }, ref) => {
    const localRef = useRef<HTMLDivElement | null>(null);

    useImperativeHandle(ref, () => localRef.current as HTMLDivElement);

    useEffect(() => {
      const wrapper = localRef.current;
      if (!wrapper) return;

      const lenis = new Lenis({
        wrapper,
        content:        wrapper.firstElementChild as HTMLElement,
        duration:       1.15,
        easing:         (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        smoothWheel:    true,
        wheelMultiplier: 1,
        touchMultiplier: 1.2,
      });

      let frame = 0;
      const raf = (time: number) => {
        lenis.raf(time);
        frame = requestAnimationFrame(raf);
      };
      frame = requestAnimationFrame(raf);

      return () => {
        cancelAnimationFrame(frame);
        lenis.destroy();
      };
    }, []);

    return (
      <div
        ref={localRef}
        className={`relative h-full overflow-y-auto overflow-x-hidden scrollbar-none ${className}`}
        data-testid="smooth-scroll-wrapper"
      >
        <div className="min-h-full">{children}</div>
      </div>
    );
  },
);

SmoothScrollProvider.displayName = "SmoothScrollProvider";
export default SmoothScrollProvider;
