import { motion, useScroll, useTransform, MotionValue } from "framer-motion";
import { RefObject } from "react";

type Props = {
  scrollContainerRef?: RefObject<HTMLDivElement | null>;
};

/**
 * BackgroundBlob
 * Deep-blue top-right blob + violet bottom-left blob.
 * Both parallax gently with scroll depth.
 */
export default function BackgroundBlob({ scrollContainerRef }: Props) {
  const { scrollYProgress } = useScroll(
    scrollContainerRef ? { container: scrollContainerRef } : undefined,
  );

  const yTop: MotionValue<number>    = useTransform(scrollYProgress, [0, 1], [0, -120]);
  const yBottom: MotionValue<number> = useTransform(scrollYProgress, [0, 1], [0, 80]);
  const opacityTop                   = useTransform(scrollYProgress, [0, 0.6], [1, 0.45]);

  return (
    <div
      aria-hidden
      data-testid="background-blob"
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
    >
      {/* Top-right deep blue */}
      <motion.div
        style={{ y: yTop, opacity: opacityTop }}
        className="absolute -right-32 -top-32 h-[640px] w-[640px] rounded-full"
      >
        <div
          className="h-full w-full rounded-full"
          style={{
            background:
              "radial-gradient(closest-side, rgba(30,58,138,0.42), rgba(30,58,138,0.12) 55%, transparent 75%)",
            filter: "blur(120px)",
          }}
        />
      </motion.div>

      {/* Bottom-left violet */}
      <motion.div
        style={{ y: yBottom }}
        className="absolute -bottom-40 -left-40 h-[520px] w-[520px] rounded-full"
      >
        <div
          className="h-full w-full rounded-full"
          style={{
            background:
              "radial-gradient(closest-side, rgba(88,28,135,0.28), rgba(88,28,135,0.08) 55%, transparent 75%)",
            filter: "blur(140px)",
          }}
        />
      </motion.div>

      {/* Subtle horizon wash */}
      <div
        className="absolute inset-x-0 top-0 h-48"
        style={{ background: "linear-gradient(to bottom, rgba(59,130,246,0.05), transparent)" }}
      />
    </div>
  );
}
